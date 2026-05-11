#!/usr/bin/env bash
#
# server-release.sh — DeerFlow release 服务管理脚本
#
# 用法：
#   ./scripts/deerflow.sh              # 启动服务（后台运行）
#   ./scripts/deerflow.sh --stop       # 停止全部服务
#
# 说明：
#   启动后同时运行后端（Gateway 二进制）和前端（Next.js）。
#   日志输出到 release/logs/ 目录下。

set -e

SELF="$(basename "$0")"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ACTION="start"

for arg in "$@"; do
    case "$arg" in
        --stop)   ACTION="stop" ;;
        *)
            echo "用法: $0 [--stop]"
            exit 1
            ;;
    esac
done

mkdir -p logs

# ── 停止 ──────────────────────────────────────────────────────────────────

if [ "$ACTION" = "stop" ]; then
    echo "正在停止 DeerFlow 服务..."
    pkill -f "deerflow-gateway" 2>/dev/null || true
    pkill -f "next-server" 2>/dev/null || true
    pkill -f "server\.js" 2>/dev/null || true
    sleep 1
    # 强制释放端口（兼容没有 lsof/fuser 的系统，用 kill 强杀）
    for port in 8001 3000; do
        pid=$(ss -tlnp 2>/dev/null | grep ":$port " | sed 's/.*pid=\([0-9]*\).*/\1/')
        [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null || true
    done
    sleep 1
    for port in 8001 3000; do
        pid=$(ss -tlnp 2>/dev/null | grep ":$port " | sed 's/.*pid=\([0-9]*\).*/\1/')
        [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null || true
    done
    echo "✓ 全部服务已停止"
    exit 0
fi

# ── 启动 ──────────────────────────────────────────────────────────────────

pkill -f "deerflow-gateway" 2>/dev/null || true
pkill -f "next-server" 2>/dev/null || true
pkill -f "server\.js" 2>/dev/null || true
# 清理残留端口
for port in 8001 3000; do
    pid=$(ss -tlnp 2>/dev/null | grep ":$port " | sed 's/.*pid=\([0-9]*\).*/\1/')
    [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null || true
done
sleep 2

echo "=========================================="
echo "  DeerFlow 启动中"
echo "=========================================="
echo ""

echo "启动 Gateway (端口 8001)..."
DEER_FLOW_CONFIG_PATH="$(pwd)/config.yaml"
env DEER_FLOW_CONFIG_PATH="$DEER_FLOW_CONFIG_PATH" \
    ./backend-bin/deerflow-gateway/deerflow-gateway \
    > logs/gateway.log 2>&1 &

"$SCRIPTS_DIR/wait-for-port.sh" 8001 30 "Gateway" || {
    echo "✗ Gateway 启动失败，查看日志: tail -30 logs/gateway.log"
    exit 1
}
echo "✓ Gateway 已就绪 (localhost:8001)"

echo "启动 Frontend (端口 3000)..."
cd frontend && PORT=3000 node .next/standalone/server.js \
    > ../logs/frontend.log 2>&1 &
cd ..

"$SCRIPTS_DIR/wait-for-port.sh" 3000 120 "Frontend" || {
    echo "✗ Frontend 启动失败，查看日志: tail -30 logs/frontend.log"
    exit 1
}
echo "✓ Frontend 已就绪 (localhost:3000)"

echo ""
echo "=========================================="
echo "  ✓ DeerFlow 运行中"
echo "=========================================="
echo ""
echo "  访问: http://<服务器IP>:3000/"
echo "  API:  http://<服务器IP>:8001/"
echo ""
echo "  停止: ./scripts/${SELF} --stop"
echo "  日志: logs/gateway.log, logs/frontend.log"
echo ""
