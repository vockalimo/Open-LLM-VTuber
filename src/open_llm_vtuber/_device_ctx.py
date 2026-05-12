"""目前作用中的 device_id（學生 ID）context。

設計：
- 每個 ws 連線進來時，從 cookie/query 取出 device_id → 用 contextvars set
- 後端各處 helper 用 get_active_device_id()：context 為主，env 為 fallback
- 完全 backward compatible：沒設 cookie/query 仍會吃舊的 VTUBER_BRAIN_DEVICE_ID
"""
from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Optional

_current_device_id: ContextVar[Optional[str]] = ContextVar(
    "vtuber_current_device_id", default=None
)


def set_active_device_id(device_id: Optional[str]) -> None:
    _current_device_id.set(device_id or None)


def get_active_device_id() -> Optional[str]:
    """取得當前作用中的 device_id。

    優先序：contextvars > env (`VTUBER_BRAIN_DEVICE_ID`)。

    多人模式：設 `VTUBER_MULTI_TENANT=true` 後完全不吃 env，避免 env
    殘留導致學生 A 的事件被寫到學生 B 名下。
    """
    val = _current_device_id.get()
    if val:
        return val
    if os.environ.get("VTUBER_MULTI_TENANT", "").lower() in ("1", "true", "yes", "on"):
        return None
    return os.environ.get("VTUBER_BRAIN_DEVICE_ID") or None


def extract_device_id_from_ws(websocket) -> Optional[str]:
    """從 ws 的 query string 或 cookie 取 device_id。"""
    try:
        # 1. query string ?device_id=xxx
        qp = getattr(websocket, "query_params", None)
        if qp:
            v = qp.get("device_id")
            if v:
                return v
        # 2. Starlette WebSocket cookies 屬性
        cookies = getattr(websocket, "cookies", None) or {}
        v = cookies.get("device_id")
        if v:
            return v
        # 3. fallback：直接解析 raw Cookie header（部分環境 .cookies 可能為空）
        headers = getattr(websocket, "headers", None) or {}
        raw_cookie = headers.get("cookie") or headers.get("Cookie") or ""
        if raw_cookie:
            for part in raw_cookie.split(";"):
                part = part.strip()
                if part.startswith("device_id="):
                    v = part[len("device_id="):].strip()
                    if v:
                        return v
    except Exception:  # noqa: BLE001
        pass
    return None
