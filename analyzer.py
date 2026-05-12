"""
🎓 媒體素養能力分析器
======================
讀取單場 game session JSONL，輸出 5 維能力評分與依據。

維度設計參考：
  - UNESCO MIL Curriculum
  - Stanford SHEG「Civic Online Reasoning」
  - EU DigComp 2.2 Information & Data Literacy
  - 教育部 108 課綱「媒體素養」核心素養

5 個維度：
  A. 細節觀察力  (Detail Observation)
  B. 證據連結力  (Evidence Linking)
  C. 假設懷疑力  (Hypothesis Skepticism)
  D. 概念命名力  (Concept Naming)
  E. 反思遷移力  (Reflection Transfer)
"""

from __future__ import annotations

from typing import Any

# ── 各關「細節詞」「術語詞」「反思詞」分桶 ──
STAGE_DETAIL_KEYWORDS = {
    1: {"手", "手指", "表情", "臉", "衣服"},  # 觀察層該抓的細節
    2: {"字母", "拼錯", "光影", "邊緣", "細節", "多了", "少了"},
    3: {"光線", "比例", "背景", "細節", "光影", "邊緣"},
    4: {"共同", "特徵", "辨識", "查證"},
}
STAGE_SURFACE_KEYWORDS = {
    1: {"小孩", "孩子", "帽子", "廢墟", "看到", "看見", "觀察"},  # 表層詞（只算部分達標）
    2: {"不自然", "奇怪", "怪", "問題", "不對", "異樣"},
    3: set(),
    4: set(),
}
CONCEPT_KEYWORDS = {"ai", "人工智慧", "人工智能", "生成", "合成", "深偽", "deepfake",
                    "ai生成", "假新聞", "造假", "偽造", "假的", "假圖"}
SKEPTIC_KEYWORDS = {"不自然", "奇怪", "怪", "可疑", "懷疑", "真的嗎", "不對", "問題",
                    "異樣", "不合理"}
REFLECT_KEYWORDS = {"查證", "保護", "警覺", "小心", "驗證", "交叉", "求證", "判斷",
                    "媒體素養", "辨識"}


def _level(score: int) -> tuple[str, str]:
    """0-5 → (文字等級, 顏色 class)"""
    if score >= 4:
        return ("達標", "good")
    if score >= 2:
        return ("部分達標", "warn")
    return ("需加強", "bad")


def _evidence(events: list[dict], pred) -> list[dict]:
    """挑出符合 pred 的玩家發話作為證據（最多 3 句）。"""
    out = []
    for e in events:
        if e.get("type") != "user":
            continue
        if pred(e):
            out.append({
                "ts": e.get("ts"),
                "text": e.get("text"),
                "stage": (e.get("progress") or {}).get("stage"),
            })
            if len(out) >= 3:
                break
    return out


def analyze(events: list[dict]) -> dict[str, Any]:
    """主分析函數：吃事件列表，回傳 5 維評分 + 證據 + 建議。"""
    if not events:
        return {"available": False}

    # ── 預處理：抓出所有 user 事件、stage 紀錄 ──
    user_events = [e for e in events if e.get("type") == "user"]
    stage_events = [e for e in events if e.get("type") == "stage_change"]
    hint_events = [e for e in events if e.get("type") == "hint_triggered"]
    completed = any(e.get("type") == "session_complete" for e in events)
    max_stage = max((e.get("to_stage", 0) for e in stage_events), default=0)

    # 全部講過的話（小寫合併）
    all_text = " ".join((e.get("text") or "").lower() for e in user_events)

    # 各關卡命中的細節詞數
    stage1_users = [e for e in user_events if (e.get("progress") or {}).get("stage") == 1]
    stage1_text = " ".join((e.get("text") or "").lower() for e in stage1_users)
    stage1_detail_hits = sum(1 for k in STAGE_DETAIL_KEYWORDS[1] if k in stage1_text)
    stage1_surface_hits = sum(1 for k in STAGE_SURFACE_KEYWORDS[1] if k in stage1_text)

    stage2_users = [e for e in user_events if (e.get("progress") or {}).get("stage") == 2]
    stage2_text = " ".join((e.get("text") or "").lower() for e in stage2_users)
    stage2_detail_hits = sum(1 for k in STAGE_DETAIL_KEYWORDS[2] if k in stage2_text)

    stage3_users = [e for e in user_events if (e.get("progress") or {}).get("stage") == 3]
    stage3_text = " ".join((e.get("text") or "").lower() for e in stage3_users)

    stage4_users = [e for e in user_events if (e.get("progress") or {}).get("stage") == 4]
    stage4_text = " ".join((e.get("text") or "").lower() for e in stage4_users)

    # ── A. 細節觀察力 (0-5) ──
    if stage1_detail_hits >= 2:
        a_score = 5
    elif stage1_detail_hits == 1:
        a_score = 3
    elif stage1_surface_hits >= 1:
        a_score = 2
    else:
        a_score = 1 if max_stage >= 1 else 0
    a_evidence = _evidence(stage1_users, lambda e: any(
        k in (e.get("text") or "").lower() for k in STAGE_DETAIL_KEYWORDS[1]
    ))

    # ── B. 證據連結力：第 2 關除了「奇怪」還有沒有具體指出原因 ──
    b_score = 0
    if max_stage >= 2:
        if stage2_detail_hits >= 2:
            b_score = 5
        elif stage2_detail_hits == 1:
            b_score = 3
        elif any(k in stage2_text for k in STAGE_SURFACE_KEYWORDS[2]):
            b_score = 2
        else:
            b_score = 1
    b_evidence = _evidence(stage2_users, lambda e: any(
        k in (e.get("text") or "").lower() for k in STAGE_DETAIL_KEYWORDS[2]
    ))

    # ── C. 假設懷疑力：是否在前 3 輪內就出現懷疑詞、是否觸發降級 ──
    early_skeptic = 0
    for e in user_events[:6]:
        if any(k in (e.get("text") or "").lower() for k in SKEPTIC_KEYWORDS):
            early_skeptic += 1
    if len(hint_events) >= 2:
        c_score = 1
    elif len(hint_events) == 1:
        c_score = 2
    elif early_skeptic >= 2:
        c_score = 5
    elif early_skeptic == 1:
        c_score = 4
    else:
        c_score = 3 if max_stage >= 2 else 1
    c_evidence = _evidence(user_events, lambda e: any(
        k in (e.get("text") or "").lower() for k in SKEPTIC_KEYWORDS
    ))

    # ── D. 概念命名力：是否說出 AI/Deepfake 等術語 ──
    concept_hits = sum(1 for k in CONCEPT_KEYWORDS if k in all_text)
    if concept_hits >= 3:
        d_score = 5
    elif concept_hits >= 1:
        d_score = 4
    elif max_stage >= 3:
        d_score = 2  # 通關到第 3+ 關卻沒講出術語
    else:
        d_score = 1
    d_evidence = _evidence(user_events, lambda e: any(
        k in (e.get("text") or "").lower() for k in CONCEPT_KEYWORDS
    ))

    # ── E. 反思遷移力：第 4 關有沒有出現查證/警覺類動詞 ──
    reflect_hits = sum(1 for k in REFLECT_KEYWORDS if k in stage4_text)
    if completed and reflect_hits >= 2:
        e_score = 5
    elif completed and reflect_hits >= 1:
        e_score = 4
    elif completed:
        e_score = 3
    elif max_stage >= 3:
        e_score = 2
    else:
        e_score = 1
    e_evidence = _evidence(stage4_users, lambda e: any(
        k in (e.get("text") or "").lower() for k in REFLECT_KEYWORDS
    ))

    # ── 建議練習 ──
    suggestions = []
    if a_score < 4:
        suggestions.append({
            "ability": "細節觀察力",
            "tip": "建議練習「找碴題」型遊戲，或下載 Where's Wally 類圖鑑訓練眼力。",
        })
    if b_score < 4:
        suggestions.append({
            "ability": "證據連結力",
            "tip": "練習「觀察 → 為什麼這代表造假」的因果連結，例如：『手指 6 根 → AI 模型早期版本常見錯誤』。",
        })
    if c_score < 4:
        suggestions.append({
            "ability": "假設懷疑力",
            "tip": "推薦 Stanford SHEG「Lateral Reading」教材，學會看到任何圖先問「來源？」",
        })
    if d_score < 4:
        suggestions.append({
            "ability": "概念命名力",
            "tip": "補充核心詞彙：AI 生成 / Deepfake / 深偽 / 生成式對抗網路 (GAN)。",
        })
    if e_score < 4:
        suggestions.append({
            "ability": "反思遷移力",
            "tip": "讀台灣事實查核中心案例，學會把單張圖的判斷推廣到日常閱聽行為。",
        })

    abilities = [
        {
            "code": "A", "name": "細節觀察力",
            "desc": "能在影像中注意到不一致或異常的細節",
            "score": a_score, "level": _level(a_score),
            "evidence": a_evidence,
            "rule": f"第 1 關命中 {stage1_detail_hits} 個細節詞（手指/表情/衣服等）",
        },
        {
            "code": "B", "name": "證據連結力",
            "desc": "能把觀察到的細節連到「為什麼這代表造假」",
            "score": b_score, "level": _level(b_score),
            "evidence": b_evidence,
            "rule": f"第 2 關命中 {stage2_detail_hits} 個證據詞（字母/光影/邊緣等）",
        },
        {
            "code": "C", "name": "假設懷疑力",
            "desc": "不被表面情緒帶走，主動懷疑來源",
            "score": c_score, "level": _level(c_score),
            "evidence": c_evidence,
            "rule": f"前 6 輪內出現 {early_skeptic} 次懷疑詞｜觸發降級提示 {len(hint_events)} 次",
        },
        {
            "code": "D", "name": "概念命名力",
            "desc": "能用正確術語描述（AI 生成、Deepfake、深偽）",
            "score": d_score, "level": _level(d_score),
            "evidence": d_evidence,
            "rule": f"全程主動說出 {concept_hits} 個 AI/Deepfake 相關術語",
        },
        {
            "code": "E", "name": "反思遷移力",
            "desc": "能把單張圖的判斷推廣為「我該怎麼辦」",
            "score": e_score, "level": _level(e_score),
            "evidence": e_evidence,
            "rule": f"第 4 關出現 {reflect_hits} 個反思詞（查證/警覺/求證等）｜全部通關：{completed}",
        },
    ]

    overall = round(sum(a["score"] for a in abilities) / len(abilities), 1)
    return {
        "available": True,
        "completed": completed,
        "max_stage": max_stage,
        "overall_score": overall,
        "abilities": abilities,
        "suggestions": suggestions,
        "framework_refs": [
            "UNESCO MIL Curriculum",
            "Stanford SHEG Civic Online Reasoning",
            "EU DigComp 2.2",
            "教育部 108 課綱·媒體素養",
        ],
    }
