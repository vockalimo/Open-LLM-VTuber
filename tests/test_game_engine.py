"""
遊戲引擎 e2e 測試
測試項目:
  1. 開始遊戲觸發
  2. 關卡門檻（MIN_TURNS + MIN_KEYWORDS_HIT）
  3. 關卡推進與圖片切換
  4. 完成遊戲

執行方式:
  cd ~/Documents/lalacube/lalacube/Open-LLM-VTuber
  python -m pytest tests/test_game_engine.py -v
"""

import pytest
from game_engine import EscapeGame, STAGES, GAME_START_KEYWORDS


class TestGameStart:
    """測試遊戲啟動"""

    def test_start_trigger_keywords(self):
        g = EscapeGame()
        assert g.check_start_trigger("開始遊戲") is True
        assert g.check_start_trigger("我想玩密室逃脫") is True
        assert g.check_start_trigger("start game") is True
        assert g.check_start_trigger("來玩") is True

    def test_start_trigger_no_match(self):
        g = EscapeGame()
        assert g.check_start_trigger("你好") is False
        assert g.check_start_trigger("今天天氣如何") is False

    def test_start_initializes_state(self):
        g = EscapeGame()
        g.start()
        assert g.active is True
        assert g.stage == 1
        assert g.completed is False
        assert g._stage_turns == 0

    def test_start_emits_ws_event(self):
        g = EscapeGame()
        g.start()
        event = g.pop_ws_event()
        assert event is not None
        assert event["type"] == "set-background"
        assert "stage1" in event["url"]

    def test_ws_event_consumed_after_pop(self):
        g = EscapeGame()
        g.start()
        g.pop_ws_event()
        assert g.pop_ws_event() is None


class TestStagePassing:
    """測試關卡通過門檻"""

    def setup_method(self):
        self.g = EscapeGame()
        self.g.start()
        self.g.pop_ws_event()  # 消耗初始事件

    def test_cannot_pass_before_min_turns(self):
        """前 MIN_TURNS_PER_STAGE 輪不應過關，無論命中多少關鍵字"""
        for i in range(self.g.MIN_TURNS_PER_STAGE - 1):
            # 給出含大量關鍵字的回答
            result = self.g.check_answer("孩子 帽子 廢墟 灰塵 手 手指 看到 看見 觀察 表情 衣服 臉")
            assert result is False, f"第 {i+1} 輪不應過關（需要 {self.g.MIN_TURNS_PER_STAGE} 輪）"
        assert self.g.stage == 1

    def test_cannot_pass_with_insufficient_keywords(self):
        """達到最低輪數後，只命中 1 個關鍵字不應過關"""
        # 先消耗掉所需輪數
        for _ in range(self.g.MIN_TURNS_PER_STAGE - 1):
            self.g.check_answer("嗯讓我想想")
        # 第 MIN_TURNS 輪，只命中 1 個
        result = self.g.check_answer("我看到一些東西")  # 只有 "看到"
        assert result is False

    def test_pass_with_min_turns_and_keywords(self):
        """達到最低輪數且命中 >= MIN_KEYWORDS_HIT 個關鍵字時過關"""
        for _ in range(self.g.MIN_TURNS_PER_STAGE - 1):
            self.g.check_answer("嗯讓我想想")
        # 第 MIN_TURNS 輪，命中 2+ 個
        result = self.g.check_answer("我觀察到孩子的手指")
        assert result is True

    def test_stage_not_auto_advanced(self):
        """check_answer 返回 True 不應自動推進關卡"""
        for _ in range(self.g.MIN_TURNS_PER_STAGE - 1):
            self.g.check_answer("嗯")
        self.g.check_answer("觀察到孩子在廢墟中")
        assert self.g.stage == 1  # 仍然在第 1 關


class TestStageProgression:
    """測試關卡推進"""

    def setup_method(self):
        self.g = EscapeGame()
        self.g.start()
        self.g.pop_ws_event()

    def _pass_current_stage(self):
        """模擬通過當前關卡"""
        for _ in range(self.g.MIN_TURNS_PER_STAGE - 1):
            self.g.check_answer("嗯讓我想想")
        # 命中足夠的關鍵字
        stage_idx = self.g.stage - 1
        kws = STAGES[stage_idx]["keywords"][:self.g.MIN_KEYWORDS_HIT]
        self.g.check_answer(" ".join(kws))

    def test_next_stage_advances(self):
        self._pass_current_stage()
        self.g.next_stage()
        assert self.g.stage == 2

    def test_next_stage_resets_turn_counter(self):
        self._pass_current_stage()
        self.g.next_stage()
        assert self.g._stage_turns == 0

    def test_next_stage_emits_new_portrait(self):
        self._pass_current_stage()
        self.g.next_stage()
        event = self.g.pop_ws_event()
        assert event is not None
        assert "stage2" in event["url"]

    def test_new_stage_requires_fresh_turns(self):
        """進入新關卡後，即使之前已對話多輪，新關卡仍需重新累積"""
        self._pass_current_stage()
        self.g.next_stage()
        self.g.pop_ws_event()
        # 第 2 關第 1 輪，命中多個關鍵字也不應過
        result = self.g.check_answer("不自然 奇怪 邊緣 模糊 光影 細節")
        assert result is False

    def test_all_stages_completion(self):
        """測試完整通關流程"""
        for stage_num in range(1, len(STAGES) + 1):
            assert self.g.stage == stage_num
            assert self.g.active is True
            self._pass_current_stage()
            self.g.next_stage()
            self.g.pop_ws_event()

        assert self.g.completed is True
        assert self.g.active is False

    def test_portraits_all_different(self):
        """每關的圖片應該不同"""
        portraits = list(EscapeGame.STAGE_PORTRAITS.values())
        assert len(portraits) == len(set(portraits))


class TestReset:
    """測試遊戲重置"""

    def test_reset_clears_state(self):
        g = EscapeGame()
        g.start()
        g.pop_ws_event()
        # 玩幾輪
        g.check_answer("test")
        g.check_answer("test")
        # 重置
        g.reset()
        assert g.active is False
        assert g.stage == 0
        assert g.completed is False

    def test_reset_emits_default_background(self):
        g = EscapeGame()
        g.start()
        g.pop_ws_event()
        g.reset()
        event = g.pop_ws_event()
        assert event is not None
        assert event["url"] == EscapeGame.DEFAULT_BACKGROUND


class TestResendLogic:
    """測試重連時重發當前關卡圖片邏輯"""

    def test_resend_portrait_when_no_pending(self):
        """遊戲進行中但沒有 pending event 時，應能取得當前 portrait"""
        g = EscapeGame()
        g.start()
        g.pop_ws_event()  # 消耗初始事件
        # 此時 active=True 但沒有 pending event
        assert g.pop_ws_event() is None
        # 但可以用 STAGE_PORTRAITS 來重發
        portrait = g.STAGE_PORTRAITS.get(g.stage)
        assert portrait is not None
        assert "stage1" in portrait
