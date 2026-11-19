#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ -f backend/data/server.pid ]; then
  PID="$(cat backend/data/server.pid)"
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    echo "已停止后端进程 $PID"
    rm -f backend/data/server.pid
    exit 0
  fi
fi

if pkill -f "uvicorn app.main:app" 2>/dev/null; then
  echo "已停止 uvicorn 进程"
else
  echo "后端当前未运行"
fi
