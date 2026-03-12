#!/bin/bash
# 检查 Sailor 服务状态和 API 可用性

BASE_URL="http://localhost:8000"

echo "=========================================="
echo "Sailor 服务状态检查"
echo "=========================================="
echo ""

# 1. 检查服务是否运行
echo "[1/5] 检查服务健康状态..."
if curl -s -f "$BASE_URL/healthz" > /dev/null 2>&1; then
    echo "  [OK] 服务正在运行"
else
    echo "  [ERROR] 服务未运行或无法访问"
    echo "  请运行: python -m uvicorn backend.app.main:app --reload --port 8000"
    exit 1
fi

# 2. 检查 Boards API
echo ""
echo "[2/5] 检查 Boards API..."
if curl -s -f "$BASE_URL/boards" > /dev/null 2>&1; then
    echo "  [OK] Boards API 可用"
else
    echo "  [ERROR] Boards API 不可用"
    echo "  可能需要重启服务"
fi

# 3. 检查 Follows API
echo ""
echo "[3/5] 检查 Follows API..."
if curl -s -f "$BASE_URL/follows" > /dev/null 2>&1; then
    echo "  [OK] Follows API 可用"
else
    echo "  [ERROR] Follows API 不可用"
    echo "  可能需要重启服务"
fi

# 4. 检查 Paper Programs API
echo ""
echo "[4/5] 检查 Paper Programs API..."
if curl -s -f "$BASE_URL/paper/programs" > /dev/null 2>&1; then
    echo "  [OK] Paper Programs API 可用"
else
    echo "  [ERROR] Paper Programs API 不可用"
    echo "  可能需要重启服务"
fi

# 5. 检查网络访问
echo ""
echo "[5/5] 检查外部网络访问..."
if curl -s -I https://github.com/trending | head -1 | grep -q "200"; then
    echo "  [OK] GitHub 可访问"
else
    echo "  [WARN] GitHub 可能无法访问"
fi

if curl -s -I https://huggingface.co/api/models | head -1 | grep -q "200"; then
    echo "  [OK] HuggingFace 可访问"
else
    echo "  [WARN] HuggingFace 可能无法访问"
fi

echo ""
echo "=========================================="
echo "检查完成"
echo "=========================================="
