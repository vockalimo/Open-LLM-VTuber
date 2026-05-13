FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    CONFIG_FILE=/app/conf/conf.yaml

WORKDIR /app

# Base dependencies
RUN apt-get update -o Acquire::Retries=5 \
 && apt-get install -y --no-install-recommends \
      ffmpeg git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install deps (cache-friendly)，排除 torch 避免裝 CUDA 版
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-package torch --no-install-package torchaudio

# 直接裝 CPU 版 torch（不裝 CUDA，省 ~8GB）
RUN uv pip install \
      torch torchaudio \
      --index-url https://download.pytorch.org/whl/cpu

# Copy source & install project
COPY . /app
RUN uv pip install --no-deps .

# 修補 frontend，讓部署在 reverse proxy 後面時 URL 正確
# 策略：
#   - frontend-overlay/ 覆蓋 submodule 的自訂檔案（含遊戲 UI、character-switch 等）
#   - index.html 裡的 main-*.js script tag hash 動態替換成實際檔名
#   - DEFAULT_BASE_URL="" → 背景圖用相對路徑
#   - DEFAULT_WS_URL → 根據 location.protocol/host 動態決定
RUN python3 - <<'PYEOF'
import glob, re, shutil, os

# 1. 覆蓋 submodule 的自訂 frontend 檔案（index.html / character-switch.js 等）
overlay_dir = "/app/frontend-overlay"
frontend_dir = "/app/frontend"
if os.path.isdir(overlay_dir):
    for fname in os.listdir(overlay_dir):
        src = os.path.join(overlay_dir, fname)
        dst = os.path.join(frontend_dir, fname)
        shutil.copy2(src, dst)
        print(f"✅ overlay: {fname}")
else:
    print("WARNING: frontend-overlay/ not found, skipping overlay")

# 2. 修正 index.html 裡的 main-*.js script tag（hash 可能與 overlay 存的不同）
html_path = "/app/frontend/index.html"
try:
    html = open(html_path, encoding="utf-8").read()
    js_matches = glob.glob("/app/frontend/assets/main-*.js")
    if js_matches:
        actual_js = os.path.basename(js_matches[0])
        html_new = re.sub(r'main-[^"\']+\.js', actual_js, html)
        if html_new != html:
            open(html_path, "w", encoding="utf-8").write(html_new)
            print(f"✅ index.html JS hash updated → {actual_js}")
        else:
            print(f"index.html JS hash already correct ({actual_js})")
    else:
        print("WARNING: no main-*.js found in /app/frontend/assets/")
except FileNotFoundError as e:
    print(f"WARNING: {e}")

# 3. 修補 compiled JS bundle（DEFAULT_BASE_URL / DEFAULT_WS_URL）
js_matches = glob.glob("/app/frontend/assets/main-*.js")
js_path = js_matches[0] if js_matches else None
try:
    if not js_path:
        raise FileNotFoundError("no main-*.js found in /app/frontend/assets/")
    js = open(js_path, encoding="utf-8").read()
    changed = False

    old_base = 'DEFAULT_BASE_URL="http://127.0.0.1:12393"'
    if old_base in js:
        js = js.replace(old_base, 'DEFAULT_BASE_URL=""')
        changed = True

    old_ws = 'DEFAULT_WS_URL="ws://127.0.0.1:12393/client-ws"'
    new_ws = 'DEFAULT_WS_URL=(location.protocol==="https:"?"wss:":"ws:")+"//"+location.host+"/client-ws"'
    if old_ws in js:
        js = js.replace(old_ws, new_ws)
        changed = True

    # data:audio/wav → Blob URL（相容 iOS Safari）
    old_audio = '`data:audio/wav;base64,${dt}`'
    new_audio = '(()=>{try{const b=atob(dt),ab=new ArrayBuffer(b.length),v=new Uint8Array(ab);for(let i=0;i<b.length;i++)v[i]=b.charCodeAt(i);return URL.createObjectURL(new Blob([ab],{type:"audio/wav"}))}catch(e){return`data:audio/wav;base64,${dt}`}})()'
    if old_audio in js:
        js = js.replace(old_audio, new_audio)
        changed = True
        print("✅ audio data URI → Blob URL patch applied")
    else:
        print("WARNING: audio data URI pattern not found, skipping Blob URL patch")

    if changed:
        open(js_path, "w", encoding="utf-8").write(js)
        print("✅ main.js patched OK")
    else:
        print("main.js already patched or pattern not found")

    # 驗證 patch 有效：若 127.0.0.1 還在，表示上游改了變數名，build 應失敗
    final_js = open(js_path, encoding="utf-8").read()
    assert "127.0.0.1" not in final_js, (
        f"PATCH FAILED: 127.0.0.1 still in {js_path} — "
        "upstream may have renamed DEFAULT_WS_URL or DEFAULT_BASE_URL. "
        "Update the patch strings in dockerfile."
    )
    print("✅ patch verification passed (no 127.0.0.1 in JS)")
except FileNotFoundError as e:
    print(f"WARNING: {e}, skipping JS patch")
PYEOF

# 補裝 host venv 有、但沒進 uv.lock 的套件
RUN uv pip install silero-vad

# 下載靜態資源（backgrounds + game_assets）—— 公開 GCS bucket，不需驗證
# 在 build 階段下載而非 startup，消除冷啟動延遲
RUN python3 - <<'PYEOF'
import urllib.request, json, os

BASE   = "https://storage.googleapis.com"
BUCKET = "lalacube-assets"

for prefix in ["vtuber/backgrounds/", "vtuber/game_assets/"]:
    try:
        list_url = f"{BASE}/storage/v1/b/{BUCKET}/o?prefix={prefix}&fields=items(name)"
        with urllib.request.urlopen(list_url, timeout=30) as resp:
            items = json.load(resp).get("items", [])
        for item in items:
            name = item["name"]           # "vtuber/backgrounds/foo.jpeg"
            rel  = name[len("vtuber/"):]  # "backgrounds/foo.jpeg"
            dest = f"/app/{rel}"
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            print(f"⬇️  {name}")
            urllib.request.urlretrieve(f"{BASE}/{BUCKET}/{name}", dest)
        print(f"✅  {prefix} 下載完成（{len(items)} 個）")
    except Exception as e:
        print(f"⚠️  下載 {prefix} 失敗（{e}），build 繼續")
PYEOF

# Startup script
RUN printf '%s\n' \
  '#!/usr/bin/env sh' \
  'set -eu' \
  '' \
  'mkdir -p /app/conf /app/models' \
  '' \
  '# 1) conf.yaml (required)' \
  'if [ -f "/app/conf/conf.yaml" ]; then' \
  '  echo "Using user-provided conf.yaml"' \
  '  # 容器內必須監聽 0.0.0.0 才能被 Caddy reverse_proxy 看到' \
  '  sed "s/^  host:.*/  host: '"'"'0.0.0.0'"'"'/" /app/conf/conf.yaml > /app/conf.yaml' \
  'else' \
  '  echo "ERROR: conf.yaml is required."' \
  '  echo "Please mount your config dir to /app/conf"' \
  '  exit 1' \
  'fi' \
  '' \
  '# 2) model_dict.json (optional)' \
  'if [ -f "/app/conf/model_dict.json" ]; then' \
  '  ln -sf /app/conf/model_dict.json /app/model_dict.json' \
  'fi' \
  '' \
  '# 3) live2d-models' \
  'if [ -d "/app/conf/live2d-models" ]; then' \
  '  rm -rf /app/live2d-models && ln -s /app/conf/live2d-models /app/live2d-models' \
  'fi' \
  '' \
  '# 4) characters' \
  'if [ -d "/app/conf/characters" ]; then' \
  '  rm -rf /app/characters && ln -s /app/conf/characters /app/characters' \
  'fi' \
  '' \
  '# 5) avatars' \
  'if [ -d "/app/conf/avatars" ]; then' \
  '  rm -rf /app/avatars && ln -s /app/conf/avatars /app/avatars' \
  'fi' \
  '' \
  '# 6) backgrounds（若掛載了外部目錄則覆蓋 image 內建資源）' \
  'if [ -d "/app/conf/backgrounds" ]; then' \
  '  rm -rf /app/backgrounds && ln -s /app/conf/backgrounds /app/backgrounds' \
  'fi' \
  '' \
  '# 7) game_assets（若掛載了外部目錄則覆蓋 image 內建資源）' \
  'if [ -d "/app/conf/game_assets" ]; then' \
  '  rm -rf /app/game_assets && ln -s /app/conf/game_assets /app/game_assets' \
  'fi' \
  '' \
  '# 8) start app' \
  'exec uv run run_server.py' \
  > /usr/local/bin/start-app && chmod +x /usr/local/bin/start-app

# Volumes
VOLUME ["/app/conf", "/app/models"]

EXPOSE 12393

CMD ["/usr/local/bin/start-app"]
