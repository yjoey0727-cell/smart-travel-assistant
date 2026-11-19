#!/bin/bash
cd "$(dirname "$0")"
./start.sh
echo
read -n 1 -s -r -p "按任意键关闭此窗口…"
echo
