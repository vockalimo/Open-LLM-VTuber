"""
ScenarioAgent：把 vtuber-poc 的 scenario engine 包成 OLV agent。

原理：
  - OLV 收到學生語音 → ASR → BatchInput → agent.chat()
  - 我們不接 LLM，改成 HTTP 打 vtuber-poc 的 /scenario/start /scenario/respond
  - 把 server 回傳的 speak 文字包成 SentenceOutput，OLV 自動 TTS + Live2D 動嘴

用法（conf.yaml）：
    conversation_agent_choice: "scenario_agent"
    agent_settings:
      scenario_agent:
        scenario_api_url: "http://127.0.0.1:8765"
        scenario_id: "inn-bullying-01"
        speaker_name: "雷無桀"
"""
from __future__ import annotations

import uuid
from typing import AsyncIterator, Optional

import httpx
from loguru import logger

from .agent_interface import AgentInterface
from ..input_types import BaseInput, BatchInput
from ..output_types import Actions, DisplayText, SentenceOutput


class ScenarioAgent(AgentInterface):
    """OLV agent that drives a remote scenario state machine.

    每個 OLV session 都會有一個獨立的 ScenarioAgent 實例。
    第一次 chat() 觸發 /scenario/start，之後每一次 chat() 觸發 /scenario/respond。
    """

    AGENT_TYPE = "scenario_agent"

    def __init__(
        self,
        scenario_api_url: str = "http://127.0.0.1:8765",
        scenario_id: str = "inn-bullying-01",
        speaker_name: str = "AI",
        request_timeout: float = 60.0,
    ) -> None:
        self.api_url = scenario_api_url.rstrip("/")
        self.scenario_id = scenario_id
        self.speaker_name = speaker_name
        self.timeout = request_timeout
        self.session_id: Optional[str] = None
        self._done = False

    # ---------- AgentInterface ----------
    async def chat(self, input_data: BaseInput) -> AsyncIterator[SentenceOutput]:
        if self._done:
            logger.info("[scenario] already done, replaying ending hint")
            async for o in self._yield("（這一回已經結束了。重新整理頁面再來一場吧。）"):
                yield o
            return

        text = self._extract_text(input_data)

        try:
            if self.session_id is None:
                speak, done = await self._start()
            else:
                speak, done = await self._respond(text)
        except httpx.HTTPError as e:
            logger.error(f"[scenario] HTTP error: {e}")
            async for o in self._yield("（我這邊網路有點問題，再試一次吧。）"):
                yield o
            return
        except Exception as e:
            logger.exception(f"[scenario] unexpected error: {e}")
            async for o in self._yield("（系統卡了一下，再試一次吧。）"):
                yield o
            return

        if done:
            self._done = True

        async for o in self._yield(speak):
            yield o

    def handle_interrupt(self, heard_response: str) -> None:
        # scenario 不需要記憶，學生打斷就讓他打斷，下一輪 respond 會繼續
        logger.debug(f"[scenario] interrupt heard: {heard_response[:40]}…")

    def set_memory_from_history(self, conf_uid: str, history_uid: str) -> None:
        # 不接記憶
        return None

    # ---------- internal ----------
    async def _start(self) -> tuple[str, bool]:
        body = {
            "scenario_id": self.scenario_id,
            "session_id": uuid.uuid4().hex,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as cli:
            r = await cli.post(f"{self.api_url}/scenario/start", json=body)
            r.raise_for_status()
            data = r.json()
        self.session_id = data["session_id"]
        logger.info(f"[scenario] started session={self.session_id[:8]}")
        return data.get("speak", ""), bool(data.get("done"))

    async def _respond(self, transcript: str) -> tuple[str, bool]:
        body = {"session_id": self.session_id, "transcript": transcript or ""}
        async with httpx.AsyncClient(timeout=self.timeout) as cli:
            r = await cli.post(f"{self.api_url}/scenario/respond", json=body)
            r.raise_for_status()
            data = r.json()
        return data.get("speak", ""), bool(data.get("done"))

    @staticmethod
    def _extract_text(input_data: BaseInput) -> str:
        if not isinstance(input_data, BatchInput):
            return ""
        parts = []
        for t in input_data.texts or []:
            content = (t.content or "").strip()
            if content:
                parts.append(content)
        return " ".join(parts).strip()

    async def _yield(self, text: str) -> AsyncIterator[SentenceOutput]:
        text = (text or "").strip()
        if not text:
            return
        yield SentenceOutput(
            display_text=DisplayText(text=text, name=self.speaker_name),
            tts_text=text,
            actions=Actions(),
        )
