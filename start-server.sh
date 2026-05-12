#!/bin/bash
# 用 start_new_session 啟動，完全脫離 terminal session
# 避免 SIGTTOU 暫停問題（即使 nohup / disown 也無效）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG=${1:-/tmp/vtuber.log}

python3 -c "
import subprocess, sys, os

# 載入 .env（若存在）
env_file = '$SCRIPT_DIR/.env'
env = os.environ.copy()
try:
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
except FileNotFoundError:
    pass

p = subprocess.Popen(
    ['$SCRIPT_DIR/.venv/bin/python3', 'run_server.py'],
    cwd='$SCRIPT_DIR',
    env=env,
    stdin=open('/dev/null'),
    stdout=open('$LOG', 'w'),
    stderr=subprocess.STDOUT,
    start_new_session=True
)
print(f'Server started: PID={p.pid}, log=$LOG')
"
