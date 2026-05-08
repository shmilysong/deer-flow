# DeerFlow 部署已知问题与解决方案

> 本文档记录了 `build-release.sh` 一键编译 + 裸机部署过程中发现的问题及修复方案。
> 关联脚本：`scripts/build-release.sh`

---

## 1. 模型配置问题

### 1.1 Pro / Ultra 模式不可选

**现象**：前端对话输入框只能选 "Flash" 模式，"Pro" / "Ultra" / "Thinking" 呈灰色不可点。

**根因**：`config.yaml` 中模型配置缺少 `supports_thinking: true`。前端 `input-box.tsx` 的 `getResolvedMode()` 检测到该字段缺失时，判定模型不支持思考能力，将所有非 Flash 模式强制降级。

**修复**：
```yaml
models:
  - name: deepseek-chat
    display_name: DeepSeek / deepseek-chat
    use: langchain_deepseek:ChatDeepSeek
    model: deepseek-chat
    api_key: $DEEPSEEK_API_KEY
    supports_thinking: true    # ← 必须添加
```

### 1.2 模型名称不一致（Docker vs Bare-metal）

**现象**：Docker 启动显示 `deepseek-chat`，release 启动显示 `deepseek-v3`。

**根因**：`release/config.yaml` 是测试时手动创建的，用了自定义的 `name: deepseek-v3`，与项目根目录 `config.yaml` 的 `name: deepseek-chat` 不一致。

**修复**：保持模型名称与项目根目录 `config.yaml` 统一。

---

## 2. 前端构建问题

### 2.1 Module not found: `@/` 路径别名

**现象**：前端启动报错 `Module not found: Can't resolve '@/core/threads/utils'`。

**根因**：`tsconfig.json` 缺失。Next.js 的 `@/` 路径别名由 `tsconfig.json` 的 `paths` 配置定义，不复制该文件会导致所有 `@/` 导入解析失败。

**修复**（`build-release.sh` 已修复）：必须一并复制以下文件：
```
cp tsconfig.json $RELEASE_DIR/frontend/
cp postcss.config.js $RELEASE_DIR/frontend/
cp components.json $RELEASE_DIR/frontend/
cp -r styles $RELEASE_DIR/frontend/
```

### 2.2 `.next` 目录被重建覆盖

**现象**：`serve.sh --prod` 使用 `pnpm run preview`（`next build && next start`），会重新构建覆盖已有的 `.next/`。

**影响**：
- 构建耗时 2-5 分钟
- 依赖 `src/` 和 `node_modules/` 必须完整
- 需要 `.env` 存在（即使 `SKIP_ENV_VALIDATION=1`）

**建议**：在 release 中直接使用 `pnpm start`（仅启动，不构建），save.sh 中使用 `--prod` 时执行 `pnpm start` 而不是 `pnpm run preview`。

---

## 3. MCP 配置问题

### 3.1 ADS MCP 路径 `ENOENT`

**现象**：Gateway 日志报错 `ENOENT: /app/ads-mcp/dist/index.js`。

**根因**：`extensions_config.json` 中 `args` 的路径是 Docker 容器路径 `/app/ads-mcp/...`，裸机部署时不存在。

**修复**：使用相对路径（Gateway 工作目录为 `backend/`，所以用 `../ads-agent-mcp/`）：
```json
{
  "mcpServers": {
    "ads": {
      "args": ["../ads-agent-mcp/dist/index.js"],
      "env": {
        "ADS_CONFIG_PATH": "../ads-agent-mcp/.ads-mcp/config.json"
      }
    }
  }
}
```

### 3.2 ADS MCP 源码路径不匹配

**现象**：编译脚本在 `../ads-agent-mcp/` 找不到源码。

**根因**：`build-release.sh` 最初硬编码 `ADS_MCP_DIR="${REPO_ROOT}/../ads-agent-mcp"`，但 ADS MCP 仓库在 `deer-flow/ads-agent-mcp/` 同目录内。

**修复**（`build-release.sh` 已修复）：
```bash
ADS_MCP_DIR="${REPO_ROOT}/ads-agent-mcp"   # 同仓库内
```

### 3.3 `.ads-mcp/config.json` 配置不完整

**现象**：ADS MCP 启动后无正确 token。

**修复**：确保 `ads-agent-mcp/.ads-mcp/config.json` 包含完整的 ADS Server 配置：
```json
{
  "ads": {
    "server": {
      "url": "http://192.168.1.139:80"
    },
    "credentials": {
      "default": {
        "username": "admin",
        "password": "Admin#123"
      }
    }
  }
}
```

---

## 4. 启动脚本问题

### 4.1 `config-upgrade.sh` 找不到模板

**现象**：`✗ config.example.yaml not found at /usr/xccloud/deerflow/release/config.example.yaml`

**根因**：`config-upgrade.sh` 在 release 根目录找 `config.example.yaml`，但 `build-release.sh` 只复制到了 `release/config/` 子目录。

**修复**（`build-release.sh` 已修复）：
```bash
cp config.example.yaml "$RELEASE_DIR/config.example.yaml"
```

### 4.2 `serve.sh` 找不到 Nginx 配置

**现象**：`serve.sh` 启动时报 `nginx: [emerg] open() "/var/lib/nginx/...` 或配置文件不存在。

**根因**：`serve.sh` 读取 `docker/nginx/nginx.local.conf`（以 `$REPO_ROOT` 为基准），但 release 目录只有 `nginx/nginx.conf`。

**修复**（`build-release.sh` 已修复）：
```bash
mkdir -p "$RELEASE_DIR/docker/nginx"
cp docker/nginx/nginx.local.conf "$RELEASE_DIR/docker/nginx/nginx.local.conf"
```

---

## 5. 后端运行环境问题

### 5.1 `.venv` 跨平台不兼容

**现象**：服务器上 Python 虚拟环境无法使用。

**根因**：`uv sync` 在开发机预编译，.venv 包含原生扩展的 `.so` 文件，架构/OS 不匹配时无法加载。

**解决方案**（按优先级）：

| 方案 | 适用场景 |
|------|---------|
| 开发机和服务器同架构 + 同 OS | 直接复制 .venv，最简单 |
| 服务器有网络 | `cd backend && uv sync` 重新安装 |
| 服务器无网络 | 在服务器上 `uv venv --allow-existing .venv && uv sync --no-build` |

### 5.2 rsync chgrp 权限错误

**现象**：`rsync error: some files/attrs were not transferred (code 23)`，脚本因 `set -e` 中断。

**根因**：`rsync -a` 尝试保留文件 group/owner 属性，但当前文件系统不支持。

**修复**（`build-release.sh` 已修复）：所有 rsync 添加 `--no-g --no-o` 跳过 group/owner 保留，并加 `|| true` 防止非致命错误中断脚本。

---

## 6. 环境配置问题

### 6.1 `.env` 未自动加载

**现象**：API key 环境变量不存在，Gateway 启动失败。

**注意**：`serve.sh` 会自动加载 `$REPO_ROOT/.env`，但直接手动启动 Gateway 时不会加载。部署后必须确保：

```bash
# 方案 A：使用 serve.sh 启动（自动加载 .env）
./scripts/serve.sh --prod

# 方案 B：手动启动时手动 source
cd backend && source ../.env && ... uvicorn ...
```

### 6.2 config_version 不匹配

**现象**：`Your config.yaml (version N) is outdated — the latest version is M.`

**修复**：
```bash
./scripts/config-upgrade.sh
```

`build-release.sh` 在产物中已包含 `config-upgrade.sh`。

---

## 7. 网络与地址隔离

### 7.1 沙盒内无法杀掉外部端口

**现象**：在 Trae 沙盒内执行 `kill -9 $(lsof -ti:8001)` 无效。

**根因**：沙盒使用 bubblewrap/bwrap 隔离，进程空间隔离无法影响宿主机。

**解决**：在宿主机上执行：
```bash
sudo fuser -k 8001/tcp
sudo fuser -k 3000/tcp
```

---

## 检查清单速查

```bash
# 部署前检查（开发机）
./scripts/build-release.sh
rsync -avz --progress release/ user@server:/usr/xccloud/deerflow/

# 部署后检查（服务器）
cd /usr/xccloud/deerflow

# [ ] config.yaml 是否存在、模型配置是否完整
#     - name / display_name / use / model / api_key
#     - supports_thinking: true（否则 Pro/Ultra 无法使用）

# [ ] .env 是否存在（serve.sh 自动加载）
# [ ] extensions_config.json 路径是否正确（../ads-agent-mcp/）
# [ ] ads-agent-mcp/.ads-mcp/config.json 的 url 是否正确
# [ ] ads-agent-mcp/dist/index.js + node_modules/ 是否存在
# [ ] docker/nginx/nginx.local.conf 是否存在（serve.sh 需要）
# [ ] .venv 架构兼容

./scripts/serve.sh --prod
```

---

**最后更新**：2026-05-08
**关联文件**：`scripts/build-release.sh`
