#!/usr/bin/env bash
# start-deerflow.sh — 编译、启动、停止 DeerFlow (nohup &, 不用 Docker)
# 用法:
#   ./scripts/start-deerflow.sh          # 编译 + 启动（后台运行）
#   ./scripts/start-deerflow.sh --stop   # 停止所有服务
#   ./scripts/start-deerflow.sh --restart # 停止后重新编译 + 启动

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# ── 停止功能 ──────────────────────────────────────────────────────────────

stop_all() {
    echo "停止 DeerFlow 服务..."
    local found=false
    for port in 8001 3000; do
        local pids
        pids=$(lsof -t -i ":$port" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "  释放端口 $port (PID: $(echo $pids | tr '\n' ' '))"
            kill -9 $pids 2>/dev/null || true
            found=true
        fi
    done
    # 额外清理孤儿进程
    pkill -f "uvicorn app.gateway.app" 2>/dev/null || true
    pkill -f "next.*start" 2>/dev/null || true
    pkill -f "next.*dev" 2>/dev/null || true
    sleep 1
    if ss -tlnp 2>/dev/null | grep -qE ':8001|:3000'; then
        echo "⚠️  部分端口仍未释放，尝试强制清理..."
        fuser -k 8001/tcp 2>/dev/null || true
        fuser -k 3000/tcp 2>/dev/null || true
        sleep 1
    fi
    if $found; then
        echo "✅ DeerFlow 已停止"
    else
        echo "ℹ️  未发现运行中的 DeerFlow 服务"
    fi
}

# ── 参数解析 ──────────────────────────────────────────────────────────────

if [ "${1:-}" = "--stop" ]; then
    stop_all
    exit 0
fi

if [ "${1:-}" = "--restart" ]; then
    stop_all
    echo ""
    echo "重新启动..."
fi

# ── 启动流程 ──────────────────────────────────────────────────────────────

echo "=========================================="
echo "  编译 + 启动 DeerFlow"
echo "=========================================="
echo ""

# 1. 编译前端
echo "[1/3] 编译前端..."
cd frontend
SKIP_ENV_VALIDATION=1 pnpm build
cd "$REPO_ROOT"

# 2. 启动 Backend (Gateway)
echo "[2/3] 启动 Gateway (端口 8001)..."
mkdir -p logs
cd backend
nohup env DEER_FLOW_INTERNAL_AUTH_TOKEN=deerflow-local-dev-token PYTHONPATH=. uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 > ../logs/gateway.log 2>&1 &
GATEWAY_PID=$!
echo "  Gateway PID: $GATEWAY_PID"
cd "$REPO_ROOT"

# 3. 启动 Frontend (端口 3000)
echo "[3/3] 启动 Frontend (端口 3000)..."
cd frontend
nohup env BETTER_AUTH_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(16))') DEER_FLOW_INTERNAL_AUTH_TOKEN=deerflow-local-dev-token pnpm run start > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"
cd "$REPO_ROOT"

echo ""
echo "等待服务启动..."
sleep 4

# 验证
echo ""
echo "=== 服务状态 ==="
if ss -tlnp | grep -q :8001; then echo "✅ Gateway   → http://localhost:8001"; else echo "❌ Gateway 启动失败"; fi
if ss -tlnp | grep -q :3000; then echo "✅ Frontend  → http://localhost:3000"; else echo "❌ Frontend 启动失败"; fi

echo ""
echo "=== 测试 env-settings API ==="
JWT=$(python3 -c "
import base64, json, time
h = base64.urlsafe_b64encode(json.dumps({'alg':'HS256'}).encode()).rstrip(b'=').decode()
p = base64.urlsafe_b64encode(json.dumps({'username':'admin','exp':time.time()+3600}).encode()).rstrip(b'=').decode()
print(f'{h}.{p}.fakesig')
" 2>/dev/null)
curl -s -b "access_token=$JWT" http://localhost:8001/api/env-settings \
  | python3 -m json.tool | head -10

echo ""
echo "=== 日志 ==="
echo "  Gateway:  tail -f logs/gateway.log"
echo "  Frontend: tail -f logs/frontend.log"
echo ""
echo "停止:  ./scripts/start-deerflow.sh --stop"
