#!/usr/bin/env bash
#
# build-backend-on-server.sh — 在目标服务器上编译 PyInstaller 二进制
#
# ╔══════════════════════════════════════════════════════════════╗
# ║  关键注意事项（每次编译前必读）                              ║
# ║                                                              ║
# ║  1. deerflow_entry.py 必须 import 模块级 app，避免 ❌        ║
# ║     双重 create_app()：                                       ║
# ║       from app.gateway.app import app   ← ✅ 正确           ║
# ║       from app.gateway.app import create_app; app=create_app() ← ❌ 会导致   ║
# ║      ADS 路由注册到错误实例 → 404                            ║
# ║                                                              ║
# ║  2. cp 命令必须用整个目录复制，不加 /*                      ║
# ║       cp -r dist/deerflow-gateway /usr/xccloud/deerflow/backend-bin/  ← ✅  ║
# ║       cp -r dist/deerflow-gateway/* ... ← ❌ 摊平结构，丢失路径            ║
# ║                                                              ║
# ║  3. server-release.sh 中路径为:                              ║
# ║       ./backend-bin/deerflow-gateway/deerflow-gateway        ║
# ║     目录结构必须为 backend-bin/deerflow-gateway/(二进制+_internal/)         ║
# ╚══════════════════════════════════════════════════════════════╝
#
# 用法：
#   1. 在本机构建 release (跳过 PyInstaller 步骤):
#      ./scripts/build-release.sh --skip-backend
#
#   2. 将 release/ 传到服务器:
#      rsync -avz --progress -e 'ssh -p 2222' release/ root@server:/usr/xccloud/deerflow/
#
#   3. 将 backend + deerflow_extensions 传到服务器:
#      sudo rsync -avz --progress --no-g --no-o -e 'ssh -p 2222' \
#        /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/backend/ \
#        /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/deerflow_extensions \
#        root@192.168.1.56:/usr/xccloud/deerflow/source/
#
#   4. SSH 到服务器，编译后端:
#      cd /usr/xccloud/deerflow/source && bash backend/scripts/build-backend-on-server.sh
#
#   5. 手动复制产物到 release 目录:
#      rm -rf /usr/xccloud/deerflow/backend-bin
#      cp -r dist/deerflow-gateway /usr/xccloud/deerflow/backend-bin/
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 从脚本位置往上找 deerflow_entry.py（确定 backend 根目录）
cd "$SCRIPT_DIR"
while [ ! -f "deerflow_entry.py" ] && [ "$(pwd)" != "/" ]; do
    cd ..
done
if [ ! -f "deerflow_entry.py" ]; then
    echo "✗ 找不到 deerflow_entry.py，脚本应在 backend/scripts/ 下执行"
    exit 1
fi
echo "  项目目录: $(pwd)"

echo "=========================================="
echo "  DeerFlow Gateway — 服务器端 PyInstaller 编译"
echo "=========================================="
echo ""

# ── 1. 检查 Python 3.12 ────────────────────────────────────────────────────

PYTHON=""
for candidate in python3.12 python3; do
    if command -v "$candidate" &>/dev/null; then
        ver=$("$candidate" --version 2>&1 | grep -oP '3\.12\.\d+') || true
        if [ -n "$ver" ]; then
            PYTHON="$candidate"
            echo "[1/6] ✓ 检测到 Python $ver: $(command -v "$candidate")"
            break
        fi
    fi
done

# 如果二进制存在但找不到共享库，修复 LD_LIBRARY_PATH 后重试
if [ -z "$PYTHON" ] && command -v python3.12 &>/dev/null; then
    ver=$(LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH python3.12 --version 2>&1 | grep -oP '3\.12\.\d+') || true
    if [ -n "$ver" ]; then
        export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
        PYTHON="python3.12"
        echo "[1/6] ✓ 检测到 Python $ver（修复共享库路径后可用）"
    fi
fi

if [ -z "$PYTHON" ]; then
    echo "[1/6] ✗ 未找到 Python 3.12，正在从源码编译安装..."
    echo "  安装编译依赖..."

    _install_missing_pkgs() {
        local pkg_manager="$1"
        shift
        local missing=()
        for pkg in "$@"; do
            rpm -q "$pkg" &>/dev/null || missing+=("$pkg")
        done
        if [ ${#missing[@]} -gt 0 ]; then
            "$pkg_manager" install -y "${missing[@]}"
        else
            echo "    所有依赖包已安装，跳过"
        fi
    }

    if command -v dnf &>/dev/null; then
        _install_missing_pkgs dnf \
            gcc gcc-c++ make openssl-devel bzip2-devel libffi-devel \
            zlib-devel readline-devel sqlite-devel wget \
            kernel-devel glibc-devel glibc-headers
    elif command -v yum &>/dev/null; then
        _install_missing_pkgs yum \
            gcc gcc-c++ make openssl-devel bzip2-devel libffi-devel \
            zlib-devel readline-devel sqlite-devel wget \
            kernel-devel glibc-devel glibc-headers
    fi

    # 验证 C 编译器和预处理器均正常（防止包管理器降级导致损坏）
    echo "  验证 C 编译器..."
    if ! echo 'int main(){return 0;}' | gcc -x c - -o /tmp/.gcc-test 2>/dev/null; then
        echo "  ✗ gcc 不可用！尝试修复..."
        if command -v dnf &>/dev/null; then
            dnf reinstall -y gcc gcc-c++ cpp glibc-devel
        elif command -v yum &>/dev/null; then
            yum reinstall -y gcc gcc-c++ cpp glibc-devel
        fi
        if ! echo 'int main(){return 0;}' | gcc -x c - -o /tmp/.gcc-test 2>/dev/null; then
            echo "  ✗ gcc 仍然不可用，请手动修复后重试"
            exit 1
        fi
    fi
    rm -f /tmp/.gcc-test
    echo "  ✓ gcc 正常"

    echo "  验证 C 预处理器 (/lib/cpp)..."
    echo '#include <limits.h>' > /tmp/.test-cpp.c
    if ! /lib/cpp /tmp/.test-cpp.c >/dev/null 2>/dev/null; then
        echo "  ✗ /lib/cpp 不可用！尝试修复..."
        if command -v dnf &>/dev/null; then
            dnf reinstall -y cpp glibc-devel kernel-devel
        elif command -v yum &>/dev/null; then
            yum reinstall -y cpp glibc-devel kernel-devel
        fi
        if ! /lib/cpp /tmp/.test-cpp.c >/dev/null 2>/dev/null; then
            echo "  ✗ /lib/cpp 仍然不可用，请手动修复后重试"
            rm -f /tmp/.test-cpp.c
            exit 1
        fi
    fi
    rm -f /tmp/.test-cpp.c
    echo "  ✓ /lib/cpp 正常"

    cd /tmp
    wget -q https://www.python.org/ftp/python/3.12.9/Python-3.12.9.tgz
    tar xzf Python-3.12.9.tgz
    cd Python-3.12.9
    ./configure --enable-shared --prefix=/usr/local
    make -j$(nproc)
    make install
    # 将 /usr/local/lib 加入动态链接器缓存
    echo "/usr/local/lib" > /etc/ld.so.conf.d/local.conf
    ldconfig
    export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
    cd "$OLDPWD"
    rm -rf /tmp/Python-3.12.9 /tmp/Python-3.12.9.tgz
    PYTHON="python3.12"
    echo "  ✓ Python 3.12.9 已安装到 /usr/local"
fi

# 确保后续所有命令能找到 libpython3.12.so
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH

# ── 2. 创建虚拟环境 ───────────────────────────────────────────────────────

echo "[2/6] 创建 Python 虚拟环境（自动清理旧环境）..."
rm -rf .venv-server
"$PYTHON" -m venv .venv-server
source .venv-server/bin/activate
echo "  ✓ 虚拟环境已激活"

# ── 3. 安装 uv ────────────────────────────────────────────────────────────

echo "[3/6] 安装 uv..."
pip install uv --quiet
echo "  ✓ uv 已安装"

# ── 4. 安装项目依赖 ──────────────────────────────────────────────────────

echo "[4/6] 安装项目依赖 (uv sync)..."
# 告诉 uv 使用 .venv-server 而非默认的 .venv
export UV_PROJECT_ENVIRONMENT=.venv-server
uv sync
# numpy 2.x 预编译 wheel 需要 x86-64-v2，服务器旧 CPU 不支持
# 降级到 numpy 1.x（无此要求）
echo "  降级 numpy 到 1.x（兼容旧 CPU）..."
uv pip install "numpy<2" --force-reinstall --quiet
echo "  ✓ 依赖已安装"

# ── 5. 安装 PyInstaller ─────────────────────────────────────────────────────

echo "[5/6] 安装 PyInstaller..."
# uv sync 已装好全部依赖，直接用 uv pip 装 PyInstaller
# 不需要 -e .，PyInstaller 通过 --paths . 和 --hidden-import=app 即可追踪
uv pip install pyinstaller --quiet
echo "  ✓ PyInstaller 已安装"

# ── 6. 编译 Gateway 二进制 ────────────────────────────────────────────────

echo "[6/6] 编译 Gateway 二进制（耗时 5-15 分钟）..."

# deerflow_extensions 可选，目录不存在就跳过
ADD_DATA=""
if [ -d "./deerflow_extensions" ]; then
    ADD_DATA="--add-data ./deerflow_extensions:deerflow_extensions"
else
    echo "  ⚠️  未找到 deerflow_extensions，跳过附加数据目录"
fi

.venv-server/bin/python -m PyInstaller --onedir --noconfirm \
    --name deerflow-gateway \
    --paths . \
    --paths packages/harness \
    $ADD_DATA \
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
echo "=========================================="
echo "  ✓ 编译完成！"
echo "=========================================="
echo ""
echo "  产物: $(pwd)/dist/deerflow-gateway/"
echo "  大小:"
du -sh "$(pwd)/dist/deerflow-gateway"
echo ""
echo "  验证: ldd dist/deerflow-gateway/_internal/libpython3.12.so.1.0 | grep 'not found'"
echo ""
echo "  ✓ 手动复制到 release 目录:"
echo "    rm -rf /usr/xccloud/deerflow/backend-bin"
echo "    cp -r dist/deerflow-gateway /usr/xccloud/deerflow/backend-bin/"
echo ""

# 退出虚拟环境
deactivate 2>/dev/null || true
