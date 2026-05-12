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

# 注入 WebSocket URL 自動偵測腳本，讓部署在反代後面時能正確連線
RUN python3 - <<'PYEOF'
import re
path = "/app/frontend/index.html"
content = open(path, encoding="utf-8").read()
inject = (
    '    <script>(function(){'
    'var p=location.protocol==="https:"?"wss:":"ws:",h=location.host;'
    'function fix(k,v){var r=localStorage.getItem(k),ok=false;'
    'if(r){try{var x=JSON.parse(r);'
    'if(typeof x==="string"&&x.indexOf("127.0.0.1")===-1&&x.indexOf("localhost")===-1)ok=true;'
    '}catch(e){}}if(!ok)localStorage.setItem(k,JSON.stringify(v));}'
    'fix("wsUrl",p+"//"+h+"/client-ws");'
    'fix("baseUrl",location.protocol+"//"+h);'
    '})();</script>\n'
)
marker = '    <script type="module" crossorigin'
if "localStorage.setItem" not in content:
    content = content.replace(marker, inject + marker)
    open(path, "w", encoding="utf-8").write(content)
    print("index.html patched OK")
else:
    print("index.html already patched")
PYEOF

# 補裝 host venv 有、但沒進 uv.lock 的套件
RUN uv pip install silero-vad

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
  '# 6) backgrounds' \
  'if [ -d "/app/conf/backgrounds" ]; then' \
  '  rm -rf /app/backgrounds && ln -s /app/conf/backgrounds /app/backgrounds' \
  'fi' \
  '' \
  '# 7) start app' \
  'exec uv run run_server.py' \
  > /usr/local/bin/start-app && chmod +x /usr/local/bin/start-app

# Volumes
VOLUME ["/app/conf", "/app/models"]

EXPOSE 12393

CMD ["/usr/local/bin/start-app"]
