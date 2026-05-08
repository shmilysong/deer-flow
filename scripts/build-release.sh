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
#   - frontend/.next/          (Next.js 生产构建)
#   - backend/                 (Python 源码 + .venv)
#   - skills/                  (Agent skills)
#   - ads-agent-mcp/           (可选 ADS MCP)
#   - scripts/                 (启动脚本)
#   - nginx/                   (Nginx 配置)
#   - config/                  (配置模板)
#   - deerflow_extensions/     (可选扩展)
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
mkdir -p "$RELEASE_DIR"/{frontend,backend,skills,scripts,nginx,config,deerflow_extensions,ads-agent-mcp}

# ── 编译前端 ────────────────────────────────────────────────────────────────

echo "[3/9] 编译前端 (Next.js)..."
cd "$REPO_ROOT/frontend"

if [ ! -d "node_modules" ]; then
    echo "  安装前端依赖..."
    pnpm install --frozen-lockfile
fi

SKIP_ENV_VALIDATION=1 pnpm build

echo "  复制前端构建产物..."
cp -r .next "$RELEASE_DIR/frontend/"
cp -r public "$RELEASE_DIR/frontend/"
cp package.json "$RELEASE_DIR/frontend/"
cp pnpm-lock.yaml "$RELEASE_DIR/frontend/"
cp next.config.js "$RELEASE_DIR/frontend/"
cp tsconfig.json "$RELEASE_DIR/frontend/"
cp postcss.config.js "$RELEASE_DIR/frontend/"
cp components.json "$RELEASE_DIR/frontend/"
cp -r src "$RELEASE_DIR/frontend/"
cp -r styles "$RELEASE_DIR/frontend/"
cp .env.example "$RELEASE_DIR/frontend/.env"
echo "  复制前端 node_modules（运行时依赖）..."
cp -r node_modules "$RELEASE_DIR/frontend/"

cd "$REPO_ROOT"

# ── 编译后端 ────────────────────────────────────────────────────────────────

echo "[4/9] 编译后端 (Python + uv)..."
cd "$REPO_ROOT/backend"

echo "  安装后端依赖 (uv sync)..."
uv sync

echo "  复制后端源码..."
rsync -av --no-g --no-o \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.ruff_cache' \
    --exclude='.coverage' \
    --exclude='*.egg-info' \
    --exclude='build/' \
    --exclude='dist/' \
    --exclude='wheels/' \
    --exclude='.langgraph_api' \
    --exclude='log/' \
    --exclude='.deer-flow/' \
    --exclude='.claude/' \
    --exclude='.ads-mcp/' \
    . "$RELEASE_DIR/backend/" || true

echo "  复制 Python 虚拟环境..."
cp -r .venv "$RELEASE_DIR/backend/"

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
  output_dir: /data/deerflow/training_logs

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

# ── 复制 deerflow_extensions ───────────────────────────────────────────────

echo "  复制 deerflow_extensions..."
if [ -d "deerflow_extensions" ]; then
    rsync -av --no-g --no-o \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.git' \
        deerflow_extensions/ "$RELEASE_DIR/deerflow_extensions/" || true
fi

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
        "ADS_API_BASE_URL": "http://192.168.1.139:80",
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
echo "     → tsconfig.json 缺失，需一并复制到前端目录"
echo ""
echo "  4. 服务器 .venv 不可用"
echo "     → 开发机与服务器架构/OS 必须一致"
echo ""
