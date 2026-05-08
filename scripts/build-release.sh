#!/usr/bin/env bash
#
# build-release.sh — 一键编译 DeerFlow 部署产物（2026-05-07 新版架构）
#
# 用法：
#   ./scripts/build-release.sh
#
# 执行后在当前目录生成 release/ 目录，
# 包含所有需要部署到服务器的产物。
#
# 产物清单：
#   - frontend/                 (Next.js 生产构建 + 生产依赖，无源码)
#   - backend-bin/              (PyInstaller 编译产物：二进制 + _internal/，无 .py 源码)
#   - skills/                   (Agent skills)
#   - ads-agent-mcp/            (可选 ADS MCP)
#   - scripts/                  (启动脚本)
#   - nginx/                    (Nginx 配置)
#   - config/                   (配置模板)
#   - backend/extensions_config.json  (MCP 配置)
#   - config.yaml               (填 key 即用，含 supports_thinking: true)
#   - docker/nginx/             (serve.sh 需要的 nginx 配置)
#   - .env                      (环境变量，需部署后创建)
#
# 产物输出到：$(pwd)/release/
#

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RELEASE_DIR="${RELEASE_DIR:-$(pwd)/release}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=========================================="
echo "  DeerFlow Release Builder"
echo "  新版架构（Gateway 内嵌 Agent 运行时）"
echo "=========================================="
echo ""
echo "  仓库目录: $REPO_ROOT"
echo "  输出目录: $RELEASE_DIR"
echo "  时间戳: $TIMESTAMP"
echo ""

# ── 清理旧产物 ──────────────────────────────────────────────────────────────

if [ -d "$RELEASE_DIR" ]; then
    echo "[1/9] 清理旧产物..."
    rm -rf "$RELEASE_DIR"
fi

# ── 创建目录结构 ────────────────────────────────────────────────────────────

echo "[2/9] 创建目录结构..."
mkdir -p "$RELEASE_DIR"/{frontend,backend-bin,skills,scripts,nginx,config,ads-agent-mcp}

# ── 编译前端 ────────────────────────────────────────────────────────────────

echo "[3/9] 编译前端 (Next.js)..."
cd "$REPO_ROOT/frontend"

if [ ! -d "node_modules" ]; then
    echo "  安装前端依赖..."
    pnpm install --frozen-lockfile
fi

SKIP_ENV_VALIDATION=1 pnpm build

echo "  复制前端构建产物（仅运行时所需，无源码）..."
cp -r .next "$RELEASE_DIR/frontend/"
cp -r public "$RELEASE_DIR/frontend/"
cp package.json "$RELEASE_DIR/frontend/"
cp pnpm-lock.yaml "$RELEASE_DIR/frontend/"
cp next.config.js "$RELEASE_DIR/frontend/"
cp .env.example "$RELEASE_DIR/frontend/.env"
# 只复制运行时必需的 src/env.js（next.config.js 在运行时 import 它）
mkdir -p "$RELEASE_DIR/frontend/src"
cp src/env.js "$RELEASE_DIR/frontend/src/env.js"
echo "  安装前端生产依赖（在 release 目录重新安装，避免 pnpm 硬链接断裂）..."
cd "$RELEASE_DIR/frontend"
pnpm install --frozen-lockfile --prod 2>&1
cd "$REPO_ROOT"

cd "$REPO_ROOT"

# ── 编译后端（PyInstaller → 二进制）────────────────────────────────────────

echo "[4/9] 编译后端 (PyInstaller → 二进制、无源码)..."
cd "$REPO_ROOT/backend"

echo "  安装后端依赖 (uv sync)..."
uv sync

echo "  安装 PyInstaller 到项目 .venv..."
.venv/bin/pip install pyinstaller --quiet

echo "  编译 Gateway 二进制（耗时 5-15 分钟）..."
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
    --collect-submodules=langchain \
    --collect-submodules=langchain_core \
    --collect-submodules=langgraph \
    --collect-submodules=deerflow \
    \
    --exclude-module=tests \
    --exclude-module=docs \
    --exclude-module=tkinter \
    --exclude-module=matplotlib \
    \
    deerflow_entry.py 2>&1

echo "  复制编译产物到 release/backend-bin/..."
mkdir -p "$RELEASE_DIR/backend-bin"
cp -r "$REPO_ROOT/backend/dist/deerflow-gateway" "$RELEASE_DIR/backend-bin/"
# 清理编译中间文件
rm -rf "$REPO_ROOT/backend/dist" "$REPO_ROOT/backend/build" "$REPO_ROOT/backend/deerflow-gateway.spec"

cd "$REPO_ROOT"

# ── 复制 Skills ─────────────────────────────────────────────────────────────

echo "[5/9] 复制 Skills..."
rsync -av --no-g --no-o \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    skills/ "$RELEASE_DIR/skills/" || true

# ── 复制脚本 ───────────────────────────────────────────────────────────────

echo "[6/9] 复制启动脚本..."
cp scripts/serve.sh "$RELEASE_DIR/scripts/"
cp scripts/wait-for-port.sh "$RELEASE_DIR/scripts/"
cp scripts/config-upgrade.sh "$RELEASE_DIR/scripts/"
cp scripts/cleanup-containers.sh "$RELEASE_DIR/scripts/"
chmod +x "$RELEASE_DIR/scripts/"*.sh

# ── 适配并复制 Nginx 配置 ───────────────────────────────────────────────────

echo "[7/9] 生成 Nginx 配置..."
cat docker/nginx/nginx.local.conf > "$RELEASE_DIR/nginx/nginx.conf"
# serve.sh 读取的是 docker/nginx/nginx.local.conf（以自身路径为基准）
mkdir -p "$RELEASE_DIR/docker/nginx"
cp docker/nginx/nginx.local.conf "$RELEASE_DIR/docker/nginx/nginx.local.conf"

# ── 复制配置模板 ────────────────────────────────────────────────────────────

echo "  复制配置模板..."
cp config.example.yaml "$RELEASE_DIR/config/"
cp extensions_config.example.json "$RELEASE_DIR/config/"
# 复制到根目录（serve.sh 的 config-upgrade.sh 需要）
cp config.example.yaml "$RELEASE_DIR/config.example.yaml"

# ── 生成完整可用的 config.yaml ─────────────────────────────────────────────

echo "  生成 release/config.yaml（填 key 即可用）..."
SKILLS_PATH="$RELEASE_DIR/skills"
if [ -n "$DEER_FLOW_SKILLS_PATH" ]; then
    SKILLS_PATH="$DEER_FLOW_SKILLS_PATH"
fi

# 读取项目根目录现有 config.yaml，提取已启用的模型列表
MODEL_BLOCK=""
if [ -f "$REPO_ROOT/config.yaml" ]; then
    # 查找非注释的模型定义（跳过 # 开头的行）
    IN_MODELS=false
    MODEL_LINES=""
    while IFS= read -r line; do
        # 如果遇到 models: 开始收集
        if echo "$line" | grep -q "^models:"; then
            IN_MODELS=true
            continue
        fi
        # 如果遇到非 models 区域的顶级 key，停止
        if $IN_MODELS && echo "$line" | grep -qP "^(sandbox|skills|tools|tool_groups|title|data_collection|subagents|checkpointer|log_level|token_usage|config_version):"; then
            IN_MODELS=false
            break
        fi
        if $IN_MODELS; then
            # 跳过注释行
            if echo "$line" | grep -qP "^\s*#"; then
                continue
            fi
            # 去掉注释后缀
            clean_line=$(echo "$line" | sed 's/ *#.*$//')
            MODEL_LINES="$MODEL_LINES"$'\n'"$clean_line"
        fi
    done < "$REPO_ROOT/config.yaml"

    # 检查是否已有 supports_thinking，如果没有添加到第一个模型
    if echo "$MODEL_LINES" | grep -q "supports_thinking"; then
        MODEL_BLOCK="$MODEL_LINES"
    else
        # 在第一个模型的 api_key 行后插入 supports_thinking: true
        MODEL_BLOCK=$(echo "$MODEL_LINES" | sed '0,/api_key:.*/{
    /api_key:.*/a\
    supports_thinking: true
}')
    fi

    # 保存 $ 符号（否则无引号 heredoc 会吃掉环境变量引用）
    MODEL_BLOCK_ESCAPED=$(echo "$MODEL_BLOCK" | sed 's/\$/DOLLARSIGN/g')
fi

# 如果实在没解析到模型配置，使用默认
if [ -z "$MODEL_BLOCK" ]; then
    MODEL_BLOCK='  - name: deepseek-chat
    display_name: DeepSeek / deepseek-chat
    use: langchain_deepseek:ChatDeepSeek
    model: deepseek-chat
    api_key: $DEEPSEEK_API_KEY
    supports_thinking: true
    timeout: 600.0
    max_retries: 2'
fi

if [ -z "$MODEL_BLOCK_ESCAPED" ]; then
    MODEL_BLOCK_ESCAPED="$MODEL_BLOCK"
fi

cat > "$RELEASE_DIR/config.yaml" << CONFIGEOF
config_version: 8
log_level: info

token_usage:
  enabled: false

models:
$(echo "$MODEL_BLOCK_ESCAPED" | sed 's/DOLLARSIGN/$/g')

sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider
  allow_host_bash: true

skills:
  path: $SKILLS_PATH
  container_path: /mnt/skills

title:
  enabled: false

data_collection:
  enabled: true
  output_dir: ./data_collection_logs

subagents:
  enabled: false

tool_groups:
  - name: web
  - name: file:read
  - name: file:write
  - name: bash

tools:
  - name: web_search
    group: web
    use: deerflow.community.ddg_search.tools:web_search_tool
    max_results: 5
  - name: web_fetch
    group: web
    use: deerflow.community.jina_ai.tools:web_fetch_tool
    timeout: 10
CONFIGEOF
echo "  ✓ config.yaml 已生成（含 supports_thinking: true，填 key 即可用）"

# ── ADS MCP（可选组件）───────────────────────────────────────────────────────

echo "[8/9] ADS MCP..."
ADS_MCP_DIR="${REPO_ROOT}/ads-agent-mcp"
if [ -d "$ADS_MCP_DIR" ]; then
    echo "  检测到 ADS MCP..."
    if [ ! -d "$ADS_MCP_DIR/dist" ] || [ ! -d "$ADS_MCP_DIR/node_modules" ]; then
        echo "  ⚠️  ADS MCP 未构建（缺少 dist/ 或 node_modules/）"
        echo "  ⚠️  请先执行：cd $ADS_MCP_DIR && npm install && npm run build"
        echo "  ⚠️  跳过 ADS MCP..."
    else
        echo "  复制 ADS MCP..."
        rsync -av --no-g --no-o \
            --exclude='__pycache__' \
            --exclude='.git' \
            "$ADS_MCP_DIR/" "$RELEASE_DIR/ads-agent-mcp/" || true
        echo "  ✓ ADS MCP 复制完成"
    fi
else
    echo "  ⏩ 未检测到 ADS MCP（deer-flow/ads-agent-mcp/ 不存在），跳过"
fi

# ── 生成 backend MCP 配置文件（相对路径）─────────────────────────────────────

echo "[9/9] 生成 backend/extensions_config.json（相对路径）..."
mkdir -p "$RELEASE_DIR/backend"
MCP_CONFIG_FILE="$RELEASE_DIR/backend/extensions_config.json"
ADS_ENABLED=false
ADS_DESCRIPTION="ADS MCP Server for cloud desktop management"
DEEPRAG_ENABLED=false
DEEPRAG_DESCRIPTION="DeepRAG 知识库检索"

# 检测 ADS MCP 是否已复制到 release
if [ -f "$RELEASE_DIR/ads-agent-mcp/dist/index.js" ]; then
    ADS_ENABLED=true
fi

# 检测项目源目录中的 extensions_config.json 是否有 deeprag 配置
if grep -q '"deeprag"' "$REPO_ROOT/extensions_config.json" 2>/dev/null; then
    DEEPRAG_ENABLED=true
    DEEPRAG_URL=$(grep -A5 '"deeprag"' "$REPO_ROOT/extensions_config.json" | grep '"url"' | head -1 | sed 's/.*"url": *"\(.*\)",*/\1/')
    DEEPRAG_DESC=$(grep -A8 '"deeprag"' "$REPO_ROOT/extensions_config.json" | grep '"description"' | head -1 | sed 's/.*"description": *"\(.*\)",*/\1/')
fi

cat > "$MCP_CONFIG_FILE" << MCPEOF
{
  "mcpServers": {
    $(if [ "$ADS_ENABLED" = "true" ]; then echo '"ads": {
      "enabled": true,
      "type": "stdio",
      "command": "node",
      "args": ["../ads-agent-mcp/dist/index.js"],
      "env": {
        "ADS_API_BASE_URL": "http://127.0.0.1:80",
        "ADS_CONFIG_PATH": "../ads-agent-mcp/.ads-mcp/config.json"
      },
      "description": "'$ADS_DESCRIPTION'"
    },'; fi)
    $(if [ "$DEEPRAG_ENABLED" = "true" ]; then echo '"deeprag": {
      "enabled": true,
      "type": "http",
      "url": "'$DEEPRAG_URL'",
      "description": "'$DEEPRAG_DESC'"
    }'; fi)
  },
  "skills": {}
}
MCPEOF
# 清理尾部多余逗号（如果 ADS 开启而 DeepRAG 没开，或反之）
if [ "$ADS_ENABLED" = "true" ] && [ "$DEEPRAG_ENABLED" != "true" ]; then
    sed -i 's/},$/}/' "$MCP_CONFIG_FILE"
fi
echo "  ✓ extensions_config.json 已生成（使用相对路径）"

# ── 完成 ────────────────────────────────────────────────────────────────────

echo ""
echo "=========================================="
echo "  ✓ Release 构建完成！"
echo "=========================================="
echo ""
echo "  产物目录: $RELEASE_DIR"
echo ""
echo "  目录大小:"
du -sh "$RELEASE_DIR"/*
echo ""
echo "  下一步："
echo "  1. 上传到服务器："
echo "     rsync -avz --progress $RELEASE_DIR/ user@192.168.1.56:/usr/xccloud/deerflow/"
echo ""
echo "  2. 在服务器上配置并启动："
echo "     cd /usr/xccloud/deerflow"
echo "     cp config/config.example.yaml config.yaml"
echo "     vim config.yaml  # 编辑 API keys + 添加 supports_thinking: true"
echo "     vim extensions_config.json  # 修改 ADS MCP 路径（如需要）"
echo "     ./scripts/serve.sh --prod"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  部署常见问题（详见 docs/operations/DEPLOYMENT_KNOWN_ISSUES.md）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  1. Pro / Ultra 模式不可选"
echo "     → config.yaml 中模型配置需加 supports_thinking: true"
echo ""
echo "  2. ADS MCP 路径错误的 ENOENT"
echo "     → extensions_config.json 中的 args 指向 /app/ads-mcp/"
echo "     → 必须改为服务器实际路径或相对路径 ../ads-agent-mcp/"
echo ""
echo "  3. 前端启动失败（Module not found: @/...）"
echo "     → 检查 release/frontend/ 是否缺少 package.json 或 node_modules"
echo "     → 脚本已自动执行 pnpm install --prod"
echo ""
echo "  4. 后端 PyInstaller 编译"
echo "     → cd backend && bash build-backend.sh"
echo "     → 产物: dist/deerflow-gateway/（ELF 二进制，无 .py 源码）"
echo ""
