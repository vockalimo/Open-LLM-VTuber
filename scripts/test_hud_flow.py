"""模擬玩家對話測 HUD：送 text-input 進 client-ws，每 2 秒打一次 /api/game/status 看數字。"""
import asyncio
import json
import urllib.request
import websockets

URL = "ws://localhost:12393/client-ws"
STATUS_URL = "http://localhost:12393/api/game/status"

# 一連串會通過第 1 關的台詞（包含 GAME_START 觸發詞 + stage1 關鍵字）
SCRIPT = [
    "我想開始遊戲",            # 觸發
    "我看到一個小孩在廢墟下，戴著彩色帽子",   # 關鍵字: 小孩, 廢墟, 帽子
    "他的手指好像有點奇怪，表情也不太自然",   # 關鍵字: 手指, 表情
    "這張臉的細節有點不對",                    # 第 3 輪 -> 應通關
]


def get_status() -> dict:
    with urllib.request.urlopen(STATUS_URL, timeout=2) as r:
        return json.loads(r.read())


def fmt(p: dict) -> str:
    return (
        f"stage={p.get('stage')}/{p.get('total_stages')} "
        f"name={p.get('stage_name')!r} "
        f"turns={p.get('turns')}/{p.get('min_turns')} "
        f"hits={p.get('hit_keywords')} "
        f"hint={p.get('hint_triggered')}"
    )


async def main():
    print("[init]", fmt(get_status()))

    async with websockets.connect(URL, max_size=None) as ws:
        # 等 server 推 init 訊息
        try:
            for _ in range(3):
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                # print("← init:", msg[:120])
        except asyncio.TimeoutError:
            pass

        for line in SCRIPT:
            print(f"\n→ 送出: {line!r}")
            await ws.send(json.dumps({"type": "text-input", "text": line}))

            # 收 server 回應直到對話結束（或 8 秒超時）
            deadline = asyncio.get_event_loop().time() + 12
            saw_progress = False
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.5)
                except asyncio.TimeoutError:
                    if saw_progress:
                        break
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                t = obj.get("type")
                if t == "game-progress":
                    saw_progress = True
                    print(f"  [game-progress] {obj.get('data')}")
                elif t in ("set-background",):
                    print(f"  [set-background] {obj.get('url')}")
                elif t == "full-text":
                    txt = (obj.get("text") or "")[:80]
                    print(f"  [full-text] {txt}…")
                elif t == "control" and obj.get("text") == "conversation-chain-end":
                    break

            await asyncio.sleep(0.3)
            print("  [HTTP /api/game/status]", fmt(get_status()))


asyncio.run(main())
