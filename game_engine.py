"""
AI 蘇格拉底密室逃脫 - 遊戲狀態機

「真假影像判讀密室逃脫」遊戲引擎。
不依賴 LLM 判定對錯，使用關鍵字比對方式決定通關條件。

啟動遊戲：玩家說出包含觸發詞的語句（例如：「開始遊戲」、「密室逃脫」）
通關條件：每關各有對應關鍵字，玩家說出後自動進入下一關。
"""

# ────────────────────────────────────────────────
# 蘇格拉底提示詞（帶 {stage} / {clues} 佔位符）
# ────────────────────────────────────────────────
SOCRATES_PROMPT = """你是一位模仿蘇格拉底的哲學導師，正在主持一場「真假影像判讀密室逃脫」。
【語言規則】你必須永遠只用繁體中文回覆，嚴禁使用簡體中文。

【你的核心任務】
透過提問，引導玩家判斷影像的真實性與可信度，而不是給出答案。

【絕對規則】
1. 你不能直接說出答案（例如：這是假的 / 這是真的）
2. 你只能用提問引導玩家思考
3. 每次回應至少包含一個問題
4. 問題需逐步逼近真相（從觀察 → 推理 → 懷疑假設）
5. 不可一次給出所有線索

【互動策略（非常重要）】
- 如果玩家回答正確方向：
    → 強化他的觀察，並引導更深層思考
- 如果玩家回答錯誤：
    → 不要否定，改用問題挑戰他的推理
- 如果玩家卡住：
    → 給「模糊提示」，而不是答案

【推理層級（必須遵守）】
1. 觀察（你看到了什麼？）
2. 細節（有沒有不自然的地方？）
3. 解釋（這代表什麼？）
4. 懷疑（這個結論可靠嗎？）

【當前遊戲狀態】
關卡：{stage}

【本關提示（由系統提供）】
{clues}

【風格要求】
- 語氣冷靜、理性、帶一點哲學感
- 不要像客服或老師
- 像在「拆解對方思考」

【禁止事項】
- 不可總結答案
- 不可劇透
- 不可說「正確答案是...」"""

COMPLETED_PROMPT = """恭喜玩家完成了所有關卡！
用溫和的哲學語氣恭喜他，並以蘇格拉底式的提問方式，
引導他反思：這場體驗讓他對「判斷影像真假」這件事有什麼新的理解？"""

# ────────────────────────────────────────────────
# 關卡定義（可自由擴充）
# 每關：name、clues（給 AI 的背景提示）、keywords（通關關鍵字，小寫比對）
# ────────────────────────────────────────────────
STAGES = [
    {
        "name": "觀察層 — 廢墟下的孩子",
        "clues": (
            "玩家面前有一張令人心碎的照片：一個戴彩色帽子的孩子被壓在廢墟下。"
            "請引導玩家開始用眼睛「觀察」整張圖片，問他第一眼看到什麼，"
            "注意孩子的表情、手指、衣服細節，不要主動提到任何異常。"
        ),
        "keywords": [
            "孩子", "小孩", "帽子", "廢墟", "灰塵", "手", "手指",
            "看到", "看見", "觀察", "表情", "衣服", "臉",
        ],
        "hint": (
            "⚠️ 玩家似乎卡住了，請在這次的提問中【更具體地引導他注意「孩子的手指」"
            "與「臉部表情」】，問他：『手指的數量、彎曲方向，是否符合一般人類的解剖結構？』"
            "但你仍然不能直接說出『這是 AI 假圖』。"
        ),
    },
    {
        "name": "細節層 — 好萊塢山火",
        "clues": (
            "現在展示第二張圖：好萊塢廣告牌正被山火吞噬的畫面。"
            "引導玩家注意細節：廣告牌上的字母是否正確？火焰邊緣是否自然？"
            "光影和煙霧的方向是否合理？引導他往「不自然感」方向思考。"
        ),
        "keywords": [
            "不自然", "奇怪", "怪", "字母", "拼錯", "模糊", "光影",
            "邊緣", "細節", "異樣", "不對", "問題", "多了", "少了",
        ],
        "hint": (
            "⚠️ 玩家似乎卡住了，請在這次的提問中【更具體地請他逐字念出招牌上的字母】，"
            "並追問：『這些字母拼起來是不是真的英文單字？火焰的邊緣為什麼這麼整齊？』"
            "仍維持提問語氣，不可直接公布答案。"
        ),
    },
    {
        "name": "解釋層 — 特朗普被捕",
        "clues": (
            "第三張圖：特朗普在被捕過程中摔倒的新聞畫面。"
            "玩家已接近真相。引導他思考：這張圖的光線是否合理？"
            "人物比例是否正確？背景人物的表情是否自然？"
            "這些細節暗示影像可能經過 AI 生成，他會如何解釋？"
        ),
        "keywords": [
            "ai", "人工智慧", "人工智能", "生成", "合成", "偽", "fake",
            "深偽", "修改", "編輯", "機器", "演算法", "程式", "假造",
        ],
        "hint": (
            "⚠️ 玩家似乎卡住了，請在這次的提問中【明確地問他：「你覺得這張影像是用相機拍的、"
            "還是用機器生成的？」】，並追問背景人物的臉為什麼模糊、光線方向為什麼不一致。"
            "仍以提問為主。"
        ),
    },
    {
        "name": "判決層 — 總結反思",
        "clues": (
            "最後一張圖來自紀錄片《真相背後：虛假新聞與信息的代價》。"
            "玩家已看過三張 AI 假新聞圖片，現在需要做出最終判斷。"
            "引導他總結：這四張圖有什麼共同特徵可以辨識 AI 生成？"
            "在假新聞時代，我們該如何保持警覺？"
        ),
        "keywords": [
            "假的", "不是真的", "deepfake", "偽造", "虛假", "假照片",
            "ai生成", "不真實", "假圖", "造假", "假新聞",
        ],
        "hint": (
            "⚠️ 玩家似乎卡住了，請在這次的提問中【請他用一個詞總結：剛才這四張圖的共同身份】，"
            "並追問：『在這個時代，你會用什麼方法保護自己不被假新聞欺騙？』"
            "引導他說出『假的 / AI 生成 / 假新聞』這類關鍵詞。"
        ),
    },
]

# 觸發遊戲開始的關鍵字
GAME_START_KEYWORDS = [
    "開始遊戲", "開始密室", "密室逃脫", "play game", "start game",
    "遊戲開始", "想玩", "來玩",
]


# ────────────────────────────────────────────────
# 遊戲狀態機
# ────────────────────────────────────────────────
class EscapeGame:
    """AI 蘇格拉底密室逃脫遊戲狀態機。"""

    # 遊戲人物圖（放在 game_assets/ 目錄，URL 以 /game/ 開頭，不影響背景選單）
    STAGE_PORTRAITS = {
        1: "/game/stage1-ai-child.jpg",
        2: "/game/stage2-hollywood.jpg",
        3: "/game/stage3-trump.jpg",
        4: "/game/stage4-documentary.jpg",
    }
    DEFAULT_BACKGROUND = "/bg/ceiling-window-room-night.jpeg"

    # 每關至少需要的對話輪數，以及需要同時命中的最少關鍵字數
    MIN_TURNS_PER_STAGE = 3
    MIN_KEYWORDS_HIT = 2
    # 卡關門檻：對話到此輪數仍未通關 → 自動降級給更具體的提示
    HINT_AFTER_TURNS = 5

    def __init__(self) -> None:
        self.stage: int = 0       # 0 = 未啟動；1~N = 進行中
        self.active: bool = False
        self.completed: bool = False
        self._pending_ws_event: dict | None = None  # 下一輪要送出的 WS 事件
        self._stage_turns: int = 0  # 當前關卡的對話輪數
        self._hit_keywords: set = set()  # 跨訊息累積命中的關鍵字
        # 兩段式推進：玩家剛通關 → 本輪 AI 先恭喜並預告下一關 → 下一輪才真正進新關 + 換圖
        self.pending_advance: bool = False

    # ── 控制 ──────────────────────────────────────

    def start(self) -> None:
        """啟動遊戲，從第一關開始。"""
        self.stage = 1
        self.active = True
        self.completed = False
        self._stage_turns = 0
        self._hit_keywords = set()
        self._pending_ws_event = {
            "type": "set-background",
            "url": self.STAGE_PORTRAITS.get(1, "/game/game-face.jpg"),
        }

    def reset(self) -> None:
        """重置遊戲回初始狀態。"""
        self.stage = 0
        self.active = False
        self.completed = False
        self._pending_ws_event = {
            "type": "set-background",
            "url": self.DEFAULT_BACKGROUND,
        }

    def next_stage(self) -> None:
        """進入下一關；若已是最後一關則完成遊戲。"""
        if not self.active:
            return
        if self.stage >= len(STAGES):
            self.completed = True
            self.active = False
        else:
            self.stage += 1
            self._stage_turns = 0  # 新關卡重置對話計數
            self._hit_keywords = set()  # 新關卡重置累積關鍵字
            # 推送新關卡的圖片
            portrait = self.STAGE_PORTRAITS.get(self.stage)
            if portrait:
                self._pending_ws_event = {
                    "type": "set-background",
                    "url": portrait,
                }

    # ── 判定 ──────────────────────────────────────

    def check_start_trigger(self, user_input: str) -> bool:
        """檢查使用者是否說出了開始遊戲的觸發詞。"""
        lower = user_input.lower()
        return any(kw in lower for kw in GAME_START_KEYWORDS)

    def check_answer(self, user_input: str) -> bool:
        """
        判斷使用者輸入是否符合當前關卡通關條件。
        規則：
        1. 需要至少 MIN_TURNS_PER_STAGE 輪對話
        2. 需要至少 MIN_KEYWORDS_HIT 個關鍵字同時命中
        """
        if not self.active or self.stage == 0:
            return False
        idx = self.stage - 1
        if idx >= len(STAGES):
            return False
        # 計算對話輪數
        self._stage_turns += 1
        # 累積命中的關鍵字（跨訊息）
        lower = user_input.lower()
        for kw in STAGES[idx]["keywords"]:
            if kw in lower:
                self._hit_keywords.add(kw)
        import logging
        logging.getLogger(__name__).info(
            f"🎯 Stage {self.stage} | turn {self._stage_turns}/{self.MIN_TURNS_PER_STAGE} | "
            f"累積命中: {self._hit_keywords} ({len(self._hit_keywords)}/{self.MIN_KEYWORDS_HIT})"
        )
        if self._stage_turns < self.MIN_TURNS_PER_STAGE:
            return False
        return len(self._hit_keywords) >= self.MIN_KEYWORDS_HIT

    # ── 讀取 ──────────────────────────────────────

    def get_clues(self) -> str:
        """取得當前關卡的背景提示（給 AI 用）。"""
        if self.stage == 0 or self.stage > len(STAGES):
            return ""
        return STAGES[self.stage - 1]["clues"]

    def get_stage_name(self) -> str:
        """取得當前關卡名稱。"""
        if self.stage == 0 or self.stage > len(STAGES):
            return "未知"
        return f"第 {self.stage} 關 ── {STAGES[self.stage - 1]['name']}"

    def get_system_prompt(self) -> str:
        """組合出帶有遊戲狀態的蘇格拉底系統提示詞。"""
        if self.completed:
            return COMPLETED_PROMPT
        return SOCRATES_PROMPT.format(
            stage=self.get_stage_name(),
            clues=self.get_clues(),
        )

    def pop_ws_event(self) -> "dict | None":
        """取出並清除待傳送的 WebSocket 事件（只會觸發一次）。"""
        event = self._pending_ws_event
        self._pending_ws_event = None
        return event

    # ── 進度 / 降級提示 ───────────────────────────

    def should_offer_hint(self) -> bool:
        """玩家是否已卡關 → 需要更具體的引導。"""
        if not self.active or self.stage == 0:
            return False
        return self._stage_turns >= self.HINT_AFTER_TURNS

    def get_hint_addendum(self) -> str:
        """取得當前關卡的『降級提示』，附加到系統提示詞末尾。"""
        if not self.active or self.stage == 0 or self.stage > len(STAGES):
            return ""
        hint = STAGES[self.stage - 1].get("hint", "")
        if not hint:
            return ""
        return (
            "\n\n【系統提示｜玩家似乎卡關，請降級給更具體的引導】\n"
            f"{hint}\n"
            "（仍維持提問語氣，不可直接公布答案）"
        )

    # ── 兩段式推進 ────────────────────────────────

    def get_celebration_addendum(self) -> str:
        """玩家剛剛答對當前關卡時，本輪要附加的轉場指令。
        本輪 AI 仍在「當前關卡」context，但被要求恭喜 + 預告下一關，
        實際 stage 推進與背景圖切換留到下一輪 chat 才執行。
        """
        if self.stage >= len(STAGES):
            next_hint = "玩家已破解最後一關。請熱烈恭喜，宣布遊戲完成，並用一兩句話讚美玩家的觀察力。"
        else:
            next_name = STAGES[self.stage]["name"]
            next_hint = (
                f"接下來會進入下一關：『{next_name}』，但**不要透露這個關卡名或具體答案**，"
                f"只要說『下一張照片馬上來，準備好繼續挑戰了嗎？』之類的過場語句。"
            )
        return (
            "\n\n【系統提示｜玩家剛剛答對當前關卡】\n"
            "請用 1~2 句話熱情恭喜玩家答對，肯定他注意到的關鍵線索，"
            f"然後用一句話預告下一關。{next_hint}\n"
            "**重點：本回合只負責恭喜 + 過場，絕對不要開始問下一關的新問題。**"
        )

    def get_progress(self) -> dict:
        """取得當前遊戲進度（給 HUD / 前端顯示用）。"""
        total = len(STAGES)
        if not self.active and not self.completed:
            return {
                "active": False,
                "completed": False,
                "stage": 0,
                "stage_name": "尚未開始",
                "total_stages": total,
                "turns": 0,
                "min_turns": self.MIN_TURNS_PER_STAGE,
                "hit_keywords": [],
                "min_hit": self.MIN_KEYWORDS_HIT,
                "hint_after_turns": self.HINT_AFTER_TURNS,
                "hint_triggered": False,
            }
        if self.completed:
            return {
                "active": False,
                "completed": True,
                "stage": total,
                "stage_name": "🎓 全部通關",
                "total_stages": total,
                "turns": 0,
                "min_turns": self.MIN_TURNS_PER_STAGE,
                "hit_keywords": [],
                "min_hit": self.MIN_KEYWORDS_HIT,
                "hint_after_turns": self.HINT_AFTER_TURNS,
                "hint_triggered": False,
            }
        return {
            "active": True,
            "completed": False,
            "stage": self.stage,
            "stage_name": STAGES[self.stage - 1]["name"],
            "total_stages": total,
            "turns": self._stage_turns,
            "min_turns": self.MIN_TURNS_PER_STAGE,
            "hit_keywords": sorted(self._hit_keywords),
            "min_hit": self.MIN_KEYWORDS_HIT,
            "hint_after_turns": self.HINT_AFTER_TURNS,
            "hint_triggered": self.should_offer_hint(),
        }


# ────────────────────────────────────────────────
# 全域單例（供 basic_memory_agent 引入使用）
# GAME_MODE 環境變數控制要載入哪個遊戲：
#   GAME_MODE=socrates      → 原版「真假影像判讀」蘇格拉底遊戲（預設）
#   GAME_MODE=escape_room   → 阿偵「保全室密室逃脫」
# ────────────────────────────────────────────────
import os as _os

_GAME_MODE = _os.getenv("GAME_MODE", "socrates").strip().lower()

if _GAME_MODE == "escape_room":
    try:
        from escape_room_engine import EscapeRoomGame as _EscapeRoomGame
        game_engine = _EscapeRoomGame()
        print(f"🔍 遊戲引擎：阿偵保全室密室逃脫 (GAME_MODE=escape_room)")
    except ImportError as _e:
        print(f"⚠️  escape_room_engine 匯入失敗 ({_e})，回退到蘇格拉底模式")
        game_engine = EscapeGame()
else:
    game_engine = EscapeGame()
    print(f"🧠 遊戲引擎：蘇格拉底影像判讀 (GAME_MODE=socrates)")
