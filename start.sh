#!/bin/bash

echo "🎮 启动海龟汤推理游戏"
echo "===================="

# 检查Python
if ! command -v python &> /dev/null; then
    echo "❌ 未找到Python，请先安装Python 3.9+"
    exit 1
fi

# 检查依赖
if [ ! -d "backend/__pycache__" ]; then
    echo "📦 首次运行，安装依赖..."
    cd backend
    pip install -r requirements.txt
    cd ..
fi

# 检查.env文件
if [ ! -f "backend/.env" ]; then
    echo "⚠️  未找到.env文件，从.env.example创建..."
    cp backend/.env.example backend/.env
    echo "⚠️  请编辑 backend/.env 文件，填入你的 ANTHROPIC_API_KEY"
    echo "   获取API Key: https://console.anthropic.com/"
    exit 1
fi

# 启动后端
echo "🚀 启动后端服务..."
cd backend
python main.py &
BACKEND_PID=$!
cd ..

echo "✅ 后端已启动 (PID: $BACKEND_PID)"
echo "📡 API地址: http://localhost:8000"
echo ""

# 等待后端启动
sleep 3

# 启动前端
echo "🌐 启动前端服务..."
cd frontend
python -m http.server 8080 &
FRONTEND_PID=$!
cd ..

echo "✅ 前端已启动 (PID: $FRONTEND_PID)"
echo "🎯 游戏地址: http://localhost:8080"
echo ""
echo "===================="
echo "🎮 游戏已就绪！"
echo "   在浏览器打开: http://localhost:8080"
echo ""
echo "停止服务: Ctrl+C 或运行 ./stop.sh"
echo "===================="

# 等待用户中断
wait
