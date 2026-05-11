#!/usr/bin/env bash
#
# build-backend.sh — PyInstaller 编译 DeerFlow Gateway 为二进制可执行文件
#
# 用法：
#   cd backend && bash build-backend.sh
#
# 前置条件：
#   - uv sync 已完成（所有 Python 依赖已安装）
#
# 产物：
#   dist/deerflow-gateway/
#   ├── deerflow-gateway          ← ELF 可执行文件
#   └── _internal/                ← 编译后的 .pyc / .so
#
# 启动方式：
#   DEER_FLOW_CONFIG_PATH=/path/to/config.yaml ./dist/deerflow-gateway/deerflow-gateway
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  DeerFlow Gateway — PyInstaller 编译"
echo "=========================================="
echo ""

# ── 检查 deerflow_entry.py 是否存在 ──────────────────────────────────────────
if [ ! -f "deerflow_entry.py" ]; then
    echo "✗ deerflow_entry.py 不存在！请在 backend/ 目录下执行此脚本。"
    exit 1
fi

# ── 确保依赖已安装 ──────────────────────────────────────────────────────────
echo "[1/4] 确保 Python 依赖已安装..."
# 清理旧虚拟环境，确保每次编译从干净环境开始
rm -rf .venv
uv sync --quiet
echo "  ✓ uv sync 完成"

# ── 安装 PyInstaller ───────────────────────────────────────────────────────
echo "[2/4] 安装 PyInstaller..."
# uv sync 已装好全部依赖，直接装 PyInstaller
# 不需要 -e .，PyInstaller 通过 --paths . 和 --hidden-import=app 即可追踪
uv pip install pyinstaller --quiet 2>&1
echo "  ✓ PyInstaller 已安装"

# ── 编译 ────────────────────────────────────────────────────────────────────
echo "[3/4] 编译 Gateway 二进制（耗时约 5-15 分钟）..."
.venv/bin/python -m PyInstaller --onedir --noconfirm \
    --name deerflow-gateway \
    --paths . \
    --paths packages/harness \
    --add-data "../deerflow_extensions:deerflow_extensions" \
    \
    --hidden-import=app \
    --hidden-import=app.gateway \
    --hidden-import=app.gateway.app \
    --hidden-import=app.gateway.deps \
    --hidden-import=app.gateway.config \
    --hidden-import=app.gateway.authz \
    --hidden-import=app.gateway.services \
    --hidden-import=app.gateway.auth_middleware \
    --hidden-import=app.gateway.csrf_middleware \
    --hidden-import=app.gateway.internal_auth \
    --hidden-import=app.gateway.langgraph_auth \
    --hidden-import=app.gateway.path_utils \
    --hidden-import=app.gateway.utils \
    --hidden-import=app.gateway.routers \
    --hidden-import=app.gateway.routers.agents \
    --hidden-import=app.gateway.routers.artifacts \
    --hidden-import=app.gateway.routers.assistants_compat \
    --hidden-import=app.gateway.routers.auth \
    --hidden-import=app.gateway.routers.channels \
    --hidden-import=app.gateway.routers.feedback \
    --hidden-import=app.gateway.routers.mcp \
    --hidden-import=app.gateway.routers.memory \
    --hidden-import=app.gateway.routers.models \
    --hidden-import=app.gateway.routers.runs \
    --hidden-import=app.gateway.routers.skills \
    --hidden-import=app.gateway.routers.suggestions \
    --hidden-import=app.gateway.routers.thread_runs \
    --hidden-import=app.gateway.routers.threads \
    --hidden-import=app.gateway.routers.uploads \
    --hidden-import=app.gateway.auth \
    --hidden-import=app.gateway.auth.repositories \
    --hidden-import=app.gateway.auth.repositories.base \
    --hidden-import=app.gateway.auth.repositories.sqlite \
    --hidden-import=app.channels \
    --hidden-import=app.channels.service \
    --hidden-import=app.channels.manager \
    --hidden-import=app.channels.base \
    --hidden-import=app.channels.commands \
    --hidden-import=app.channels.message_bus \
    --hidden-import=app.channels.store \
    --hidden-import=app.channels.dingtalk \
    --hidden-import=app.channels.discord \
    --hidden-import=app.channels.feishu \
    --hidden-import=app.channels.slack \
    --hidden-import=app.channels.telegram \
    --hidden-import=app.channels.wechat \
    --hidden-import=app.channels.wecom \
    \
    --hidden-import=langchain_openai \
    --hidden-import=langchain_anthropic \
    --hidden-import=langchain_deepseek \
    --hidden-import=langchain_google_genai \
    \
    --hidden-import=deerflow.models.patched_openai \
    --hidden-import=deerflow.models.patched_deepseek \
    --hidden-import=deerflow.models.patched_minimax \
    --hidden-import=deerflow.models.vllm_provider \
    --hidden-import=deerflow.models.mindie_provider \
    --hidden-import=deerflow.models.claude_provider \
    --hidden-import=deerflow.models.openai_codex_provider \
    \
    --hidden-import=deerflow.sandbox.local \
    --hidden-import=deerflow.sandbox.tools \
    --hidden-import=deerflow.community.aio_sandbox \
    \
    --hidden-import=deerflow.community.ddg_search \
    --hidden-import=deerflow.community.serper \
    --hidden-import=deerflow.community.tavily \
    --hidden-import=deerflow.community.infoquest \
    --hidden-import=deerflow.community.exa \
    --hidden-import=deerflow.community.firecrawl \
    --hidden-import=deerflow.community.jina_ai \
    --hidden-import=deerflow.community.image_search \
    \
    --hidden-import=deerflow.tools.builtins \
    --hidden-import=deerflow.tools.builtins.tool_search \
    --hidden-import=deerflow.tools.skill_manage_tool \
    --hidden-import=deerflow.tools.builtins.invoke_acp_agent_tool \
    \
    --hidden-import=deerflow.guardrails.builtin \
    --hidden-import=deerflow.skills.storage.local_skill_storage \
    \
    --hidden-import=deerflow.runtime \
    --hidden-import=deerflow.runtime.converters \
    --hidden-import=deerflow.runtime.journal \
    --hidden-import=deerflow.runtime.serialization \
    --hidden-import=deerflow.runtime.user_context \
    --hidden-import=deerflow.runtime.checkpointer \
    --hidden-import=deerflow.runtime.checkpointer.async_provider \
    --hidden-import=deerflow.runtime.checkpointer.provider \
    --hidden-import=deerflow.runtime.events \
    --hidden-import=deerflow.runtime.events.store \
    --hidden-import=deerflow.runtime.events.store.base \
    --hidden-import=deerflow.runtime.events.store.db \
    --hidden-import=deerflow.runtime.events.store.jsonl \
    --hidden-import=deerflow.runtime.events.store.memory \
    --hidden-import=deerflow.runtime.runs \
    --hidden-import=deerflow.runtime.runs.manager \
    --hidden-import=deerflow.runtime.runs.schemas \
    --hidden-import=deerflow.runtime.runs.worker \
    --hidden-import=deerflow.runtime.runs.store \
    --hidden-import=deerflow.runtime.runs.store.base \
    --hidden-import=deerflow.runtime.runs.store.memory \
    --hidden-import=deerflow.runtime.store \
    --hidden-import=deerflow.runtime.store.async_provider \
    --hidden-import=deerflow.runtime.store.provider \
    --hidden-import=deerflow.runtime.store._sqlite_utils \
    --hidden-import=deerflow.runtime.stream_bridge \
    --hidden-import=deerflow.runtime.stream_bridge.async_provider \
    --hidden-import=deerflow.runtime.stream_bridge.base \
    --hidden-import=deerflow.runtime.stream_bridge.memory \
    \
    --hidden-import=deerflow.persistence \
    --hidden-import=deerflow.persistence.base \
    --hidden-import=deerflow.persistence.engine \
    --hidden-import=deerflow.persistence.feedback \
    --hidden-import=deerflow.persistence.feedback.model \
    --hidden-import=deerflow.persistence.feedback.sql \
    --hidden-import=deerflow.persistence.models \
    --hidden-import=deerflow.persistence.models.run_event \
    --hidden-import=deerflow.persistence.run \
    --hidden-import=deerflow.persistence.run.model \
    --hidden-import=deerflow.persistence.run.sql \
    --hidden-import=deerflow.persistence.thread_meta \
    --hidden-import=deerflow.persistence.thread_meta.base \
    --hidden-import=deerflow.persistence.thread_meta.memory \
    --hidden-import=deerflow.persistence.thread_meta.model \
    --hidden-import=deerflow.persistence.thread_meta.sql \
    --hidden-import=deerflow.persistence.user \
    --hidden-import=deerflow.persistence.user.model \
    \
    --hidden-import=langchain \
    --hidden-import=langchain_core \
    --hidden-import=langgraph \
    --hidden-import=langgraph.runtime \
    \
    --collect-all=langchain \
    --collect-all=langchain_core \
    --collect-all=langgraph \
    --collect-submodules=deerflow \
    \
    --exclude-module=tests \
    --exclude-module=docs \
    --exclude-module=tkinter \
    --exclude-module=matplotlib \
    \
    deerflow_entry.py 2>&1

echo ""
echo "[4/4] ✓ 编译完成！"
echo ""
echo "  产物: $(pwd)/dist/deerflow-gateway/"
echo ""
echo "  启动方式："
echo "    DEER_FLOW_CONFIG_PATH=/path/to/config.yaml \\"
echo "      ./dist/deerflow-gateway/deerflow-gateway"
echo ""
echo "  验证方式："
echo "    curl http://127.0.0.1:8001/health"
echo ""
