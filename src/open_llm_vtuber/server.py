"""
Open-LLM-VTuber Server
========================
This module contains the WebSocket server for Open-LLM-VTuber, which handles
the WebSocket connections, serves static files, and manages the web tool.
It uses FastAPI for the server and Starlette for static file serving.
"""

import os
import shutil

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles as StarletteStaticFiles

from .routes import init_client_ws_route, init_webtool_routes, init_proxy_route
from .service_context import ServiceContext
from .config_manager.utils import Config


# Create a custom StaticFiles class that adds CORS headers
class CORSStaticFiles(StarletteStaticFiles):
    """
    Static files handler that adds CORS headers to all responses.
    Needed because Starlette StaticFiles might bypass standard middleware.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)

        # Add CORS headers to all responses
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"

        if path.endswith(".js"):
            response.headers["Content-Type"] = "application/javascript"

        return response


class AvatarStaticFiles(CORSStaticFiles):
    """
    Avatar files handler with security restrictions and CORS headers
    """

    async def get_response(self, path: str, scope):
        allowed_extensions = (".jpg", ".jpeg", ".png", ".gif", ".svg")
        if not any(path.lower().endswith(ext) for ext in allowed_extensions):
            return Response("Forbidden file type", status_code=403)
        response = await super().get_response(path, scope)
        return response


class WebSocketServer:
    """
    API server for Open-LLM-VTuber. This contains the websocket endpoint for the client, hosts the web tool, and serves static files.

    Creates and configures a FastAPI app, registers all routes
    (WebSocket, web tools, proxy) and mounts static assets with CORS.

    Args:
        config (Config): Application configuration containing system settings.
        default_context_cache (ServiceContext, optional):
            Pre‑initialized service context for sessions' service context to reference to.
            **If omitted, `initialize()` method needs to be called to load service context.**

    Notes:
        - If default_context_cache is omitted, call `await initialize()` to load service context cache.
        - Use `clean_cache()` to clear and recreate the local cache directory.
    """

    def __init__(self, config: Config, default_context_cache: ServiceContext = None):
        self.app = FastAPI(title="Open-LLM-VTuber Server")  # Added title for clarity
        self.config = config
        self.default_context_cache = (
            default_context_cache or ServiceContext()
        )  # Use provided context or initialize a new empty one waiting to be loaded
        # It will be populated during the initialize method call

        # index.html no-cache middleware
        class NoCacheIndexMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                response = await call_next(request)
                if request.url.path in ("/", "/index.html"):
                    response.headers["Cache-Control"] = "no-store"
                return response

        self.app.add_middleware(NoCacheIndexMiddleware)

        # Add global CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Include routes, passing the context instance
        # The context will be populated during the initialize step
        self.app.include_router(
            init_client_ws_route(default_context_cache=self.default_context_cache),
        )
        self.app.include_router(
            init_webtool_routes(default_context_cache=self.default_context_cache),
        )

        # Initialize and include proxy routes if proxy is enabled
        system_config = config.system_config
        if hasattr(system_config, "enable_proxy") and system_config.enable_proxy:
            # Construct the server URL for the proxy
            host = system_config.host
            port = system_config.port
            server_url = f"ws://{host}:{port}/client-ws"
            self.app.include_router(
                init_proxy_route(server_url=server_url),
            )

        # Mount cache directory first (to ensure audio file access)
        if not os.path.exists("cache"):
            os.makedirs("cache")

        # 🎮 註冊遊戲 REST 端點（必須在靜態 mount 之前，否則會被 catch-all 攔截）
        self._register_game_routes()

        # 👀 註冊專心度 ingest 端點（前端 webcam → MediaPipe → POST 進來）
        self._register_attention_routes()

        # 👤 學生登入 / 登出 / 查詢
        self._register_student_routes()

        self.app.mount(
            "/cache",
            CORSStaticFiles(directory="cache"),
            name="cache",
        )

        # Mount static files with CORS-enabled handlers
        self.app.mount(
            "/live2d-models",
            CORSStaticFiles(directory="live2d-models"),
            name="live2d-models",
        )
        self.app.mount(
            "/bg",
            CORSStaticFiles(directory="backgrounds"),
            name="backgrounds",
        )
        self.app.mount(
            "/game",
            CORSStaticFiles(directory="game_assets"),
            name="game_assets",
        )
        self.app.mount(
            "/avatars",
            AvatarStaticFiles(directory="avatars"),
            name="avatars",
        )

        # Mount web tool directory separately from frontend
        self.app.mount(
            "/web-tool",
            CORSStaticFiles(directory="web_tool", html=True),
            name="web_tool",
        )

        # Mount main frontend last (as catch-all)
        self.app.mount(
            "/",
            CORSStaticFiles(directory="frontend", html=True),
            name="frontend",
        )

    def _register_game_routes(self):
        """🎮 註冊遊戲相關 REST 端點（HUD 用）。"""
        try:
            from game_engine import game_engine as _ge
        except Exception:
            _ge = None

        @self.app.get("/api/game/status")
        async def game_status():
            if _ge is None:
                return {"available": False}
            return {"available": True, **_ge.get_progress()}

        # ── Dashboard：對話 session 列表 + 詳細 ──
        import json as _json
        from pathlib import Path as _Path
        from fastapi import HTTPException

        SESSIONS_DIR = _Path("logs/game_sessions")

        def _read_jsonl(p: _Path):
            events = []
            try:
                with p.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            events.append(_json.loads(line))
                        except Exception:
                            continue
            except FileNotFoundError:
                pass
            return events

        def _summarize(events):
            """從事件列表算出單場摘要：用時、最高關卡、是否完成、卡關次數、用戶輪數。"""
            if not events:
                return {}
            ts0 = events[0].get("ts", 0)
            ts1 = events[-1].get("ts", ts0)
            user_turns = sum(1 for e in events if e.get("type") == "user")
            ai_turns = sum(1 for e in events if e.get("type") == "assistant")
            hints = sum(1 for e in events if e.get("type") == "hint_triggered")
            stage_changes = [e for e in events if e.get("type") == "stage_change"]
            max_stage = max((e.get("to_stage", 0) for e in stage_changes), default=0)
            completed = any(e.get("type") == "session_complete" for e in events)
            # 收集所有 hit_keywords（去重）
            all_hits = set()
            for e in events:
                if e.get("type") == "user":
                    for k in (e.get("progress") or {}).get("hit_keywords") or []:
                        all_hits.add(k)
            return {
                "duration_sec": round(ts1 - ts0, 1),
                "user_turns": user_turns,
                "ai_turns": ai_turns,
                "hint_count": hints,
                "max_stage": max_stage,
                "completed": completed,
                "unique_keywords": sorted(all_hits),
                "stage_changes": [
                    {
                        "ts": e.get("ts"),
                        "from": e.get("from_stage"),
                        "to": e.get("to_stage"),
                        "name": e.get("stage_name"),
                    }
                    for e in stage_changes
                ],
            }

        @self.app.get("/api/sessions")
        async def list_sessions():
            if not SESSIONS_DIR.exists():
                return {"sessions": []}
            files = sorted(SESSIONS_DIR.glob("*.jsonl"), reverse=True)
            out = []
            for p in files[:200]:  # 最多回 200 場
                events = _read_jsonl(p)
                s = _summarize(events)
                out.append({"id": p.stem, "size": p.stat().st_size, **s})
            return {"sessions": out}

        @self.app.get("/api/session/{session_id}")
        async def session_detail(session_id: str):
            # 防 path traversal
            if "/" in session_id or ".." in session_id:
                raise HTTPException(400, "invalid id")
            p = SESSIONS_DIR / f"{session_id}.jsonl"
            if not p.exists():
                raise HTTPException(404, "not found")
            events = _read_jsonl(p)
            return {"id": session_id, "summary": _summarize(events), "events": events}

        @self.app.get("/api/session/{session_id}/report")
        async def session_report(session_id: str):
            """🎓 5 維能力分析報告。"""
            if "/" in session_id or ".." in session_id:
                raise HTTPException(400, "invalid id")
            p = SESSIONS_DIR / f"{session_id}.jsonl"
            if not p.exists():
                raise HTTPException(404, "not found")
            try:
                from analyzer import analyze
            except Exception as ex:
                raise HTTPException(500, f"analyzer import failed: {ex}")
            events = _read_jsonl(p)
            return {"id": session_id, **analyze(events)}

    def _register_attention_routes(self):
        """👀 註冊專心度 ingest 端點。

        前端 webcam + MediaPipe FaceLandmarker 算出 focus/bored/confused 之後，
        每秒 POST 一筆過來，server 透過 vtuber_brain bridge 寫入 metric event
        （與 user_utterance / barge_in.* 同條 SQLite），admin SPA 即可看到原始事件。
        """
        from fastapi import HTTPException as _HTTPException, Request as _Request

        @self.app.post("/api/attention/engagement")
        async def ingest_engagement(payload: dict, request: _Request):
            """payload schema:
            {
              "label": "focused" | "bored" | "confused" | "neutral",
              "scores": {"focus": 0~1, "bored": 0~1, "confused": 0~1},
              "ts": <epoch ms>,
              "raw": {... 任何想保留的原始 landmark 派生指標 ...}
            }
            """
            import os as _os
            import time as _time

            scores = payload.get("scores") or {}
            for k in ("focus", "bored", "confused"):
                v = scores.get(k)
                if v is None or not isinstance(v, (int, float)):
                    raise _HTTPException(400, f"scores.{k} must be a number")
                if v < 0 or v > 1:
                    raise _HTTPException(400, f"scores.{k} out of range [0,1]")

            label = payload.get("label", "neutral")
            ts = payload.get("ts") or int(_time.time() * 1000)
            raw = payload.get("raw") or {}
            # device_id 優先序：cookie > context > env  (payload 不再採信，避免假冒)
            from ._device_ctx import get_active_device_id
            device_id = request.cookies.get("device_id") or get_active_device_id()
            if not device_id:
                # bridge 沒設裝置，靜默接收但不轉發
                return {"ok": True, "forwarded": False, "reason": "no device_id"}

            try:
                import importlib.util as _ilu
                import sys as _sys
                if "vtuber_brain" in _sys.modules:
                    vb = _sys.modules["vtuber_brain"]
                else:
                    vb_path = _os.environ.get("VTUBER_POC_PATH")
                    if not vb_path:
                        return {"ok": True, "forwarded": False, "reason": "no VTUBER_POC_PATH"}
                    init_py = _os.path.join(vb_path, "src", "vtuber_brain", "__init__.py")
                    if not _os.path.exists(init_py):
                        return {"ok": True, "forwarded": False, "reason": "vtuber_brain not found"}
                    spec = _ilu.spec_from_file_location("vtuber_brain", init_py)
                    vb = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
                    assert spec and spec.loader
                    spec.loader.exec_module(vb)  # type: ignore[union-attr]
                    _sys.modules["vtuber_brain"] = vb

                vb.emit_event(
                    "engagement",
                    device_id=device_id,
                    fields={
                        "label": label,
                        "scores": scores,
                        "ts": ts,
                        "raw": raw,
                    },
                )
                return {"ok": True, "forwarded": True}
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[attention] ingest failed: {e}")
                raise _HTTPException(500, f"ingest failed: {e}") from e

    def _register_student_routes(self):
        """👤 學生登入 / 登出 / 查詢。

        cookie 名稱：`device_id`，httpOnly + SameSite=Lax，30 天
        DEV 模式預設可自動註冊，正式部署設 `ALLOW_STUDENT_AUTOREGISTER=false` 並由
        admin SPA 預先把學生匯入 students table。
        """
        from fastapi import HTTPException as _HTTPException, Request, Response
        from . import _student_auth
        import time as _time

        COOKIE_NAME = "device_id"
        COOKIE_MAX_AGE = 30 * 24 * 60 * 60

        # 簡易 in-memory rate limit：每 IP 每分鐘最多 10 次登入嘗試
        _login_attempts: dict[str, list[float]] = {}
        _LOGIN_RATE_WINDOW = 60.0
        _LOGIN_RATE_MAX = 10

        def _check_login_rate(ip: str) -> bool:
            now = _time.time()
            buf = _login_attempts.get(ip, [])
            buf = [t for t in buf if now - t < _LOGIN_RATE_WINDOW]
            if len(buf) >= _LOGIN_RATE_MAX:
                _login_attempts[ip] = buf
                return False
            buf.append(now)
            _login_attempts[ip] = buf
            # 順手清掉很舊的 IP，避免 dict 無限長
            if len(_login_attempts) > 1000:
                cutoff = now - _LOGIN_RATE_WINDOW
                for k in list(_login_attempts.keys()):
                    _login_attempts[k] = [t for t in _login_attempts[k] if t > cutoff]
                    if not _login_attempts[k]:
                        del _login_attempts[k]
            return True

        @self.app.post("/api/student/login")
        async def student_login(payload: dict, request: Request, response: Response):
            client_ip = (request.client.host if request.client else "") or "unknown"
            if not _check_login_rate(client_ip):
                raise _HTTPException(429, "登入嘗試過於頻繁，請稍後再試")
            device_id = (payload.get("device_id") or "").strip()
            name = (payload.get("name") or "").strip()
            ok, info = _student_auth.login(device_id, name)
            if not ok:
                raise _HTTPException(400, info.get("error", "login failed"))
            response.set_cookie(
                COOKIE_NAME, device_id,
                max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax", path="/",
            )
            return {"ok": True, "student": info}

        @self.app.post("/api/student/logout")
        async def student_logout(response: Response):
            response.delete_cookie(COOKIE_NAME, path="/")
            return {"ok": True}

        @self.app.get("/api/student/me")
        async def student_me(request: Request):
            did = request.cookies.get(COOKIE_NAME) or ""
            if not did:
                return {"logged_in": False}
            student = _student_auth.find_student(did)
            return {"logged_in": bool(student), "student": student}

    async def initialize(self):
        """Asynchronously load the service context from config.
        Calling this function is needed if default_context_cache was not provided to the constructor."""
        await self.default_context_cache.load_from_config(self.config)

    @staticmethod
    def clean_cache():
        """Clean the cache directory by removing and recreating it."""
        cache_dir = "cache"
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir)
