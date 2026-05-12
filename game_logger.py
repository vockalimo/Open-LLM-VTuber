"""
🎮 遊戲對話紀錄器
================
把每場「蘇格拉底密室逃脫」遊戲的對話與狀態以 JSONL 格式寫入 logs/game_sessions/。
之後可用於：能力分析報告、教師後台、研究素材。

事件型別：
  - session_start       新 session 開始
  - user                玩家輸入 + 當下進度快照
  - assistant           AI 回應
  - stage_change        關卡推進（含 from/to）
  - hint_triggered      系統觸發降級提示
  - session_complete    全部通關
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

LOG_DIR = Path("logs/game_sessions")


class GameLogger:
    """單例：跨整個 server 共用一份。每次 game_engine.start() 會 rotate 新檔。"""

    def __init__(self) -> None:
        self.session_id: str | None = None
        self.path: Path | None = None
        self._last_stage: int = 0

    # ── 內部 ──────────────────────────────────────

    def _ensure_session(self) -> None:
        """若尚未有 session 就開一個（log 之前 lazy 啟動，避免漏記）。"""
        if self.session_id is None:
            self.start()

    def _write(self, event_type: str, **payload: Any) -> None:
        if self.path is None:
            return
        line = {
            "ts": time.time(),
            "iso": datetime.now().isoformat(timespec="seconds"),
            "session": self.session_id,
            "type": event_type,
            **payload,
        }
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
        except Exception:
            # 紀錄失敗不應影響主流程
            pass

    # ── 對外 API ──────────────────────────────────

    def start(self) -> str:
        """開新 session，回傳 session_id。"""
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.session_id = (
            datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        )
        self.path = LOG_DIR / f"{self.session_id}.jsonl"
        self._last_stage = 0
        self._write("session_start")
        return self.session_id

    def log_user(self, text: str, progress: dict | None = None) -> None:
        self._ensure_session()
        self._write("user", text=text, progress=progress or {})

    def log_assistant(self, text: str) -> None:
        self._ensure_session()
        self._write("assistant", text=text)

    def log_stage_change(self, from_stage: int, to_stage: int, stage_name: str) -> None:
        self._ensure_session()
        self._write(
            "stage_change",
            from_stage=from_stage,
            to_stage=to_stage,
            stage_name=stage_name,
        )

    def log_hint(self, stage: int, turns: int) -> None:
        self._ensure_session()
        self._write("hint_triggered", stage=stage, turns=turns)

    def log_complete(self, total_stages: int) -> None:
        self._ensure_session()
        self._write("session_complete", total_stages=total_stages)

    def maybe_log_stage_change(self, progress: dict, stage_names: list[str]) -> None:
        """根據 progress 自動偵測關卡跳動並記錄。"""
        cur = progress.get("stage", 0) if progress else 0
        if cur != self._last_stage:
            name = ""
            if 1 <= cur <= len(stage_names):
                name = stage_names[cur - 1]
            self.log_stage_change(self._last_stage, cur, name)
            self._last_stage = cur


# 全域單例
game_logger = GameLogger()
