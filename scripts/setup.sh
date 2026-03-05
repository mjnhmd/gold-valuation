#!/bin/bash

# 本地开发启动脚本
# 用于快速启动后端和前端开发服务器

set -e

echo "🏆 黄金优惠监控系统 - 本地开发环境"
echo "======================================"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，请先安装"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ 未找到 Node.js，请先安装"
    exit 1
fi

# 创建虚拟环境（如果不存在）
if [ ! -d "backend/venv" ]; then
    echo "📦 创建 Python 虚拟环境..."
    python3 -m venv backend/venv
fi

# 激活虚拟环境并安装依赖
echo "📦 安装后端依赖..."
source backend/venv/bin/activate
pip install -q -r backend/requirements.txt

# 安装前端依赖
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 安装前端依赖..."
    cd frontend && npm install && cd ..
fi

echo ""
echo "✅ 环境准备完成！"
echo ""
echo "请在两个终端窗口中分别运行："
echo ""
echo "🔸 终端1 - 启动后端 (端口 8000):"
echo "   cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo ""
echo "🔸 终端2 - 启动前端 (端口 3000):"
echo "   cd frontend && npm run dev"
echo ""
echo "然后访问: http://localhost:3000"
echo ""
