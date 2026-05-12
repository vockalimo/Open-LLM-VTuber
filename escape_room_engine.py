"""
阿偵的保全室密室逃脫 — 遊戲狀態機

玩家被鎖在保全監控室，必須找到 4 位數緊急覆寫碼才能逃出。
密碼規則寫在白板上，部分數字需要現場蒐集（問保全工號、查刷卡記錄）。

正確密碼：4312
- 位置 1：固定碼 4（白板上直接寫出）
- 位置 2：當班保全工號 → 3（對講機問保全得知）
- 位置 3：最近一次異常刷卡的「小時數」→ 1（刷卡記錄：凌晨 1 時 47 分）
- 位置 4：固定碼 2（白板上直接寫出）

AI 角色：阿偵（蘇格拉底式偵探，說話親切、激發兒童思考）
目標年齡：國小中高年級（10–12 歲）
"""

import os

# ────────────────────────────────────────────────
# 阿偵系統提示詞
# ────────────────────────────────────────────────
DETECTIVE_PROMPT = """你是「阿偵」，一位穿著藍色偵探帽的卡通小偵探。
你說話親切、充滿好奇心，專門用「提問」幫助小朋友自己推理，絕對不直接給答案。

【語言規則】永遠只用繁體中文，語氣像在跟 10-12 歲的小朋友說話。

【你的任務】
引導玩家解開保全室的密碼鎖，逃出這個房間。
密碼是一組 4 位數字，規則寫在白板上，但有幾個空格需要玩家自己去找答案。

【絕對規則】
1. 絕不直接說出密碼或任何一位數字的答案
2. 每次回應必須包含至少一個問題
3. 用觀察 → 提問 → 推理 → 驗證的順序引導
4. 如果玩家方向對了，用問題強化他的想法
5. 如果玩家卡住，給「方向提示」而不是答案

【引導策略】
- 「你看到白板上有幾個空格呢？」
- 「那個空格是誰能告訴你的？」
- 「刷卡記錄上，最後一次異常是幾點幾分？那個『幾點』是幾？」
- 「你現在手上有哪些數字了？」

【當前遊戲狀態】
關卡：{stage}

【本關提示（系統提供，不可直接說出）】
{clues}

【風格要求】
- 語氣像大哥哥 / 大姊姊
- 偶爾用「哇！」「對喔！」「你真的很厲害！」鼓勵玩家
- 不要說教，要像在玩遊戲

【回應長度限制】
- 每次回應最多 2 句話 + 1 個問句，絕對不超過 50 字
- 語音輸出環境，越短越好，禁止連串問題
"""

COMPLETED_PROMPT = """恭喜玩家解開了密碼，成功逃出保全室！
用充滿活力的語氣恭喜他，然後用「阿偵式」的提問，
引導他回想：他怎麼一步一步找到答案的？
下次遇到類似的謎題，他會怎麼做？讓他自己說出推理的步驟。"""

# ────────────────────────────────────────────────
# 關卡定義
# ────────────────────────────────────────────────
STAGES = [
    {
        "name": "觀察關 — 白板上的密碼規則",
        "clues": (
            "玩家面前有一塊白板，上面寫著：\n"
            "『緊急封鎖覆寫碼 — 值班計算規則\n"
            "  位置 1：本日固定碼（見底部）\n"
            "  位置 2：當班保全工號\n"
            "  位置 3：最近一次異常刷卡的「小時數」\n"
            "  位置 4：本日固定碼（見底部）\n"
            "  本日固定碼：4 _ _ 2（位置 2、3 停電後遺失，請現場確認）』\n"
            "請引導玩家仔細看白板，問他：白板上有幾個空格？這些空格要怎麼填？"
            "不要主動提到保全或刷卡記錄，讓玩家自己從白板推斷出要去哪裡找資料。"
        ),
        "keywords": [
            "空格", "填", "缺", "問", "保全", "找人", "刷卡", "工號",
            "哪裡找", "怎麼知道", "白板", "規則", "看", "兩個",
        ],
        "hint": (
            "⚠️ 玩家似乎還沒有注意到白板上的空格。"
            "請引導他逐行唸出白板的內容，"
            "並問他：『位置 2 和位置 3 的資料，你覺得要去哪裡找？』"
        ),
    },
    {
        "name": "提問關 — 問保全工號",
        "clues": (
            "玩家需要知道當班保全的工號（答案是 3）。\n"
            "房間裡有一台對講機可以聯絡保全室外的保全。\n"
            "如果玩家按下對講機，保全會說：『我是今天的值班保全，工號 3 號。』\n"
            "引導玩家去用對講機問保全工號，不要直接說工號是幾號。"
        ),
        "keywords": [
            "3", "三", "工號3", "工號是3", "三號", "3號",
            "保全說", "問到了", "知道了", "對講機",
        ],
        "hint": (
            "⚠️ 玩家知道需要問保全，但還沒有說出工號。"
            "請引導他：『你用對講機問了保全，他告訴你什麼？』"
            "或是：『工號這個數字，你從哪裡得到的？』"
        ),
    },
    {
        "name": "推理關 — 查刷卡記錄、組合密碼",
        "clues": (
            "玩家需要查保全室的門禁刷卡記錄，找到最後一次異常刷卡的時間。\n"
            "刷卡記錄顯示：『異常刷卡 — 凌晨 1 時 47 分（門禁卡號 X-047）』\n"
            "位置 3 = 小時數 = 1。\n"
            "玩家現在擁有：位置1=4，位置2=3（保全工號），位置3=1（小時數），位置4=2\n"
            "引導玩家把四個數字依序排列，得出密碼：4312。\n"
            "不要直接說出密碼，讓玩家自己把數字填進去。"
        ),
        "keywords": [
            "4312", "4 3 1 2", "四三一二", "密碼是4312", "輸入4312",
            "四三一二", "43 12", "答案是4312",
        ],
        "hint": (
            "⚠️ 玩家知道三個數字但還沒有組合出密碼。"
            "請引導他：『你現在手上有位置 1、位置 2、位置 3、位置 4 的數字了嗎？』\n"
            "『依照白板的順序，這四個數字排起來是什麼？』"
        ),
    },
    {
        "name": "反思關 — 你是怎麼想到的？",
        "clues": (
            "玩家已輸入正確密碼 4312，門打開了！\n"
            "現在引導玩家反思整個推理過程：\n"
            "1. 他第一眼看到什麼線索覺得有用？\n"
            "2. 哪一步驟讓他突然「啊哈！」？\n"
            "3. 如果下次碰到類似的謎題，他會先做什麼？\n"
            "讓玩家自己用語言描述推理步驟，加深記憶。"
        ),
        "keywords": [
            # 反思關不強制關鍵字，任何回應都接受
            "謝謝", "好玩", "有趣", "學到", "下次", "先看", "觀察",
            "白板", "找線索", "問", "推理", "知道了", "成功",
        ],
        "hint": (
            "⚠️ 引導玩家回想他是怎麼解開謎題的。"
            "可以問：『如果你要教朋友玩這個謎題，你會告訴他第一步先做什麼？』"
        ),
    },
]

# 觸發遊戲開始的關鍵字
GAME_START_KEYWORDS = [
    "密室逃脫", "開始遊戲", "開始逃脫", "逃出去", "解謎",
    "阿偵", "保全室", "play game", "start game",
]


# ────────────────────────────────────────────────
# 遊戲狀態機
# ────────────────────────────────────────────────
class EscapeRoomGame:
    """阿偵保全室密室逃脫 — 遊戲狀態機。
    與 EscapeGame（蘇格拉底版）介面完全相容，可直接替換。
    """

    # 場景圖：點擊物件後展示的線索圖
    STAGE_PORTRAITS = {
        1: "/game/escape/clue-whiteboard.jpg",   # 白板
        2: "/game/escape/clue-intercom.jpg",     # 對講機
        3: "/game/escape/clue-whiteboard.jpg",   # 組合密碼 → 需要看白板順序
        4: "/game/escape/clue-door-open.jpg",    # 門打開
    }
    DEFAULT_BACKGROUND = "/bg/ceiling-window-room-night.jpeg"

    MIN_TURNS_PER_STAGE = 2      # 反思關縮短到 2 輪
    MIN_KEYWORDS_HIT = 1         # 密室逃脫版：命中 1 個關鍵字即可
    HINT_AFTER_TURNS = 4

    def __init__(self) -> None:
        self.stage: int = 0
        self.active: bool = False
        self.completed: bool = False
        self._pending_ws_event: dict | None = None
        self._stage_turns: int = 0
        self._hit_keywords: set = set()
        self.pending_advance: bool = False

    # ── 控制 ──────────────────────────────────────

    def start(self) -> None:
        self.stage = 1
        self.active = True
        self.completed = False
        self._stage_turns = 0
        self._hit_keywords = set()
        self.pending_advance = False
        self._pending_ws_event = {
            "type": "set-background",
            "url": self.STAGE_PORTRAITS.get(1, "/game/game-face.jpg"),
        }

    def reset(self) -> None:
        self.stage = 0
        self.active = False
        self.completed = False
        self.pending_advance = False
        self._pending_ws_event = {
            "type": "set-background",
            "url": self.DEFAULT_BACKGROUND,
        }

    def next_stage(self) -> None:
        if not self.active:
            return
        if self.stage >= len(STAGES):
            self.completed = True
            self.active = False
        else:
            self.stage += 1
            self._stage_turns = 0
            self._hit_keywords = set()
            portrait = self.STAGE_PORTRAITS.get(self.stage)
            if portrait:
                self._pending_ws_event = {
                    "type": "set-background",
                    "url": portrait,
                }

    # ── 判定 ──────────────────────────────────────

    def check_start_trigger(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(kw in lower for kw in GAME_START_KEYWORDS)

    def check_answer(self, user_input: str) -> bool:
        if not self.active or self.stage == 0:
            return False
        idx = self.stage - 1
        if idx >= len(STAGES):
            return False
        self._stage_turns += 1
        lower = user_input.lower()
        for kw in STAGES[idx]["keywords"]:
            if kw in lower:
                self._hit_keywords.add(kw)
        import logging
        logging.getLogger(__name__).info(
            f"🔍 EscapeRoom Stage {self.stage} | turn {self._stage_turns}/{self.MIN_TURNS_PER_STAGE} | "
            f"命中: {self._hit_keywords}"
        )
        if self._stage_turns < self.MIN_TURNS_PER_STAGE:
            return False
        # 反思關（第 4 關）：寬鬆模式，5 輪後自動過關
        if self.stage == 4 and self._stage_turns >= 5:
            return True
        return len(self._hit_keywords) >= self.MIN_KEYWORDS_HIT

    # ── 讀取 ──────────────────────────────────────

    def get_clues(self) -> str:
        if self.stage == 0 or self.stage > len(STAGES):
            return ""
        return STAGES[self.stage - 1]["clues"]

    def get_stage_name(self) -> str:
        if self.stage == 0 or self.stage > len(STAGES):
            return "未知"
        return f"第 {self.stage} 關 ── {STAGES[self.stage - 1]['name']}"

    def get_system_prompt(self) -> str:
        if self.completed:
            return COMPLETED_PROMPT
        return DETECTIVE_PROMPT.format(
            stage=self.get_stage_name(),
            clues=self.get_clues(),
        )

    def pop_ws_event(self) -> "dict | None":
        event = self._pending_ws_event
        self._pending_ws_event = None
        return event

    def should_offer_hint(self) -> bool:
        if not self.active or self.stage == 0:
            return False
        return self._stage_turns >= self.HINT_AFTER_TURNS

    def get_hint_addendum(self) -> str:
        if not self.active or self.stage == 0 or self.stage > len(STAGES):
            return ""
        hint = STAGES[self.stage - 1].get("hint", "")
        if not hint:
            return ""
        return (
            "\n\n【系統提示｜玩家似乎卡關，請降級給更具體的引導】\n"
            f"{hint}\n"
        )

    def get_celebration_addendum(self) -> str:
        """玩家剛通關時，附加恭喜指示到系統提示詞。"""
        next_stage_num = self.stage + 1
        if next_stage_num > len(STAGES):
            return "\n\n【系統提示】玩家即將完成最後一關！用充滿活力的語氣恭喜他，預告門要打開了！\n"
        next_name = STAGES[next_stage_num - 1]["name"]
        return (
            f"\n\n【系統提示】玩家剛完成第 {self.stage} 關！請先大力稱讚他的推理能力，"
            f"然後預告即將進入「{next_name}」。不要直接給下一關的答案。\n"
        )

    def get_progress(self) -> dict:
        """回傳進度資訊（供 /api/game/status 使用）。"""
        return {
            "game": "escape_room",
            "stage": self.stage,
            "total_stages": len(STAGES),
            "stage_name": self.get_stage_name(),
            "active": self.active,
            "completed": self.completed,
        }
