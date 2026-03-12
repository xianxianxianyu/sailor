#!/bin/bash
# 启动 Sailor 后端服务

cd "$(dirname "$0")/.."

echo "正在启动 Sailor 后端服务..."
echo "端口: 8000"
echo "按 Ctrl+C 停止服务"
echo ""

python -m uvicorn backend.app.main:app --reload --port 8000
