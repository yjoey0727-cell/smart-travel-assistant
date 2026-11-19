#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p backend/data

URL="http://127.0.0.1:8000"
HOST="${HOST:-0.0.0.0}"

if curl -sS --max-time 2 "$URL/api/v1/health" >/dev/null 2>&1; then
  echo "服务已在运行：$URL"
  if [ "${NO_OPEN:-0}" != "1" ] && command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
  fi
  exit 0
fi

echo "正在启动智能旅行助手…"
cd backend
nohup ../.venv/bin/uvicorn app.main:app --host "$HOST" --port 8000 \
  > data/server.log 2>&1 &
echo $! > data/server.pid

for ((i = 0; i < 30; i++)); do
  if curl -sS --max-time 2 "$URL/api/v1/health" >/dev/null 2>&1; then
    echo "启动成功：$URL"
    if [ "$HOST" = "0.0.0.0" ]; then
      LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || true)"
      if [ -n "$LAN_IP" ]; then echo "局域网地址：http://$LAN_IP:8000"; fi
    fi
    if [ "${NO_OPEN:-0}" != "1" ] && command -v open >/dev/null 2>&1; then
      open "$URL" >/dev/null 2>&1 || true
    fi
    exit 0
  fi
  sleep 0.5
done

echo "启动失败，最近日志："
tail -n 30 data/server.log || true
exit 1
