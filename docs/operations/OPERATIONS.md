# DeerFlow 运维与故障排查指南

## ⚠️ 铁律：启动 DeerFlow 必须使用封装好的 make 命令

**绝对禁止**自作主张使用 `uv run`、`python -m`、`./scripts/serve.sh` 等底层命令启动 DeerFlow。

**唯一正确方式**：使用项目提供的 Makefile 封装命令：

```bash
# ✅ 本地开发启动（正确方式）
make dev              # 启动所有本地开发服务
make docker-start     # Docker 开发模式启动

# ❌ 禁止使用以下方式（自作主张）
uv run python ...     # 禁止
python -m ...        # 禁止
./scripts/serve.sh    # 禁止
```

## 概述

本文档包含 DeerFlow 生产/开发环境运行的运维知识和故障排查经验。

## 目录

- [Docker/WSL 内存管理](#dockerwsl-内存管理)
- [Frontend 内存问题](#frontend-内存问题)
- [502 Bad Gateway](#502-bad-gateway)
- [Docker 环境配置](#docker-环境配置)
- [维护命令](#维护命令)

---

## Docker/WSL 内存管理

### 问题：WSL 内存增长 → 黑屏

**症状**：
- `vmmemws` 进程占用大量内存
- Windows 变得无响应或黑屏
- 系统内存耗尽

**根因**：
- 反复执行 `docker compose up --build` 会累积旧 Docker 镜像和构建缓存
- 构建缓存可增长至 **65GB+**
- WSL2 不会自动将内存释放回 Windows

**预防**：

```bash
# 每周：轻量清理（删除停止的容器、未使用的网络、缓存）
docker system prune -f

# 每月：深度清理（删除所有未使用的镜像、容器、卷、缓存）
docker system prune -a --volumes -f

# 可选：通过 C:\Users\wing\.wslconfig 设置 WSL2 内存限制
# [wsl2]
# memory=4GB
# processors=4
# swap=2GB
```

**清理前状态**：
```
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          16        4         35.55GB   28.21GB (79%)
Build Cache     128       0         30.24GB   21.44GB
Volumes         12        4         3.649GB   1.88GB (51%)
────────────────────────────────────────────────────
总计可回收：约 51GB+
```

---

## Frontend 内存问题

### 问题：Frontend 容器使用 2.9GB 内存

**症状**：
- `docker stats` 显示 frontend 容器使用 2.9GB（正常：200-500MB）
- 系统内存压力
- 可能触发 OOM killer

**根因**：
- `docker-compose.yaml` 未设置内存限制
- Dockerfile 未设置 `NODE_OPTIONS` 内存上限
- Node.js 默认允许无限制的堆内存增长

**已修复（2026-04-21 更新）**：

1. `docker-compose-dev.yaml` - 添加内存限制（2GB，生产模式 next start）：
```yaml
services:
  frontend:
    mem_limit: 2g
    memswap_limit: 2g
```

2. `Dockerfile` - 添加 Node.js 内存上限：
```dockerfile
ENV NODE_OPTIONS="--max-old-space-size=768"
```

3. `next.config.js` - 禁用 source maps：
```javascript
productionBrowserSourceMaps: false,
```

4. `query-client-provider.tsx` - 配置 QueryClient 缓存：
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      gcTime: 1000 * 60 * 3,      // 3 分钟
      staleTime: 1000 * 60,        // 1 分钟
      refetchOnWindowFocus: false,
    },
  },
});
```

**注意**：Next.js 16.1.7 dev server + Turbopack SSR 会挂死，使用 `target: prod` + `pnpm start` 代替。

**修复结果**：
```
MEM USAGE / LIMIT: 89.38MiB / 2GiB   4.4%
```

验证命令：
```bash
docker inspect deer-flow-frontend --format '{{.HostConfig.Memory}}'
# 应显示：2147483648（2GB 字节数）
```

---

## 502 Bad Gateway

### 问题：Gateway/LangGraph 启动失败

**症状**：
```
IsADirectoryError: [Errno 21] Is a directory: '/app/backend/config.yaml'
RuntimeError: Failed to load configuration during gateway startup
```

**根因**：
`docker/.env` 文件中的路径配置错误。`DEER_FLOW_CONFIG_PATH` 等环境变量必须是**主机路径**，而不是容器内路径。

当 Docker 看到不存在的主机路径时，会在挂载点创建一个同名**目录**而不是文件。

**错误的 .env**：
```env
# 错误 - 这些是容器内路径，不是主机路径！
DEER_FLOW_HOME=/app/backend/.deer-flow
DEER_FLOW_CONFIG_PATH=/app/backend/config.yaml
```

**正确的 .env**：
```env
# 正确 - 这些是 Windows 主机路径
HOME=C:\Users\wing
BETTER_AUTH_SECRET=<你的密钥>
DEER_FLOW_CONFIG_PATH=C:\path\to\deer-flow\config.yaml
DEER_FLOW_EXTENSIONS_CONFIG_PATH=C:\path\to\deer-flow\extensions_config.json
DEER_FLOW_HOME=C:\path\to\deer-flow
DEER_FLOW_REPO_ROOT=C:\path\to\deer-flow
DEER_FLOW_DOCKER_SOCKET=/var/run/docker.sock
PORT=2026
```

**工作原理**：
1. Docker Compose 从 `.env` 读取主机路径
2. 通过 `volumes:` 将其映射到容器内路径
3. 示例：`${DEER_FLOW_CONFIG_PATH}:/app/backend/config.yaml:ro` 将主机文件映射到容器路径

---

## Docker 环境配置

### 文件结构

```
deer-flow/
├── docker/
│   ├── docker-compose.yaml    # 服务定义
│   └── .env                  # 环境变量（不要提交到 git！）
├── config.yaml               # 主应用配置
├── extensions_config.json     # MCP & skills 配置
└── backend/
    └── .deer-flow/          # 运行时数据（启动时创建）
```

### 必填环境变量 (.env)

| 变量 | 用途 | 示例 |
|----------|---------|---------|
| `HOME` | 用户主目录 | `C:\Users\wing` |
| `BETTER_AUTH_SECRET` | 认证密钥 | `your-secret-key` |
| `DEER_FLOW_CONFIG_PATH` | config.yaml 的主机路径 | `C:\path\to\config.yaml` |
| `DEER_FLOW_EXTENSIONS_CONFIG_PATH` | extensions config 的主机路径 | `C:\path\to\extensions_config.json` |
| `DEER_FLOW_HOME` | 项目根目录的主机路径 | `C:\path\to\deer-flow` |
| `DEER_FLOW_REPO_ROOT` | 同 DEER_FLOW_HOME | `C:\path\to\deer-flow` |
| `DEER_FLOW_DOCKER_SOCKET` | Docker socket（sandbox 模式） | `/var/run/docker.sock` |
| `PORT` | nginx 对外端口 | `2026` |

### 重要说明

1. **不要将 .env 提交到 git** - 包含密钥
2. **路径必须是绝对 Windows 路径** - Docker Compose 会解析
3. **反斜杠或正斜杠都可以** - Windows 上两者都有效

### 常见 .env 配置陷阱

**问题**：Gateway 或 LangGraph 无法找到配置文件，启动时报 `IsADirectoryError: [Errno 21] Is a directory: '/app/backend/config.yaml'`

**根因**：`docker/.env` 中的 `DEER_FLOW_EXTENSIONS_CONFIG_PATH` 等变量是 Windows 主机路径，在容器内不存在。`resolve_config_path()` 抛异常后被 `except Exception` 捕获，fallback 失败导致 Errno 30。

**解决**：在 `docker-compose-dev.yaml` 的 `environment` 中显式设置容器内路径，**覆盖** `.env` 中的 Windows 路径：

```yaml
gateway:
  environment:
    - DEER_FLOW_EXTENSIONS_CONFIG_PATH=/app/extensions_config.json
  env_file:
    - ../.env

langgraph:
  environment:
    - DEER_FLOW_EXTENSIONS_CONFIG_PATH=/app/extensions_config.json
  env_file:
    - ../.env
```

**关键**：`environment` 中的变量会覆盖 `env_file` 中的同名变量。设置为容器内路径 `/app/extensions_config.json`（已通过 volume 挂载为可读写）。

---

## 维护命令

### 启动/停止

```bash
# 启动所有服务（在 docker/ 目录）
cd deer-flow/docker
docker compose up -d

# 重建并启动（网络重建，避免 502）
docker compose up -d --build

# 仅重建 frontend（仅前端变更时节省时间）
docker compose up -d --build frontend

# 仅重建 gateway（仅后端变更时）
docker compose up -d --build gateway

# 停止所有服务
docker compose down

# ⚠️ 禁止使用 restart：nginx 会缓存旧容器 IP 导致 502
# 必须用 down + up 重建网络
docker compose restart nginx  # ❌ 禁止！
docker compose down && docker compose up -d  # ✅ 正确
```

### 监控

```bash
# 检查容器状态
docker ps

# 检查容器资源使用
docker stats --no-stream

# 检查特定容器日志
docker logs deer-flow-gateway --tail 50
docker logs deer-flow-langgraph --tail 50
docker logs deer-flow-frontend --tail 50
```

### 清理

```bash
# 轻量清理 - 删除停止的容器、未使用的网络、缓存
docker system prune -f

# 深度清理 - 删除所有未使用的镜像、容器、卷、缓存
docker system prune -a --volumes -f

# 删除特定构建缓存
docker builder prune -a
```

### 故障排查

```bash
# 验证 .env 是否正确加载
docker compose config | Select-String DEER_FLOW

# 检查配置文件是否存在于容器内
docker exec deer-flow-gateway ls -la /app/backend/config.yaml

# 重启特定服务（⚠️ 不推荐，使用 down + up 代替）
docker compose restart gateway
```

---

## Frontend Next.js SSR 挂死（2026-04-21 新增）

### 问题：所有需要 SSR 的路由（/workspace 等）返回 502 或卡死

**症状**：
- `http://localhost:2026/` 返回 200 OK（静态页面）
- `http://localhost:2026/workspace` 返回 502 或 Internal Server Error
- `curl localhost:3000/` 正常，但 `curl localhost:3000/workspace` 超时
- `nc localhost 3000` 能连接，但 HTTP 请求无响应

**根因**：Next.js 16.1.7 + Turbopack 在 Docker Alpine 环境下 SSR 时挂死

| 路由类型 | 行为 | 原因 |
|----------|------|------|
| `/` | 200 OK | 静态 HTML，直接从文件系统返回 |
| `/workspace` | 502/卡死 | Turbopack SSR 渲染 React 组件时挂死 |
| `/workspace/chats/new` | 308 重定向 | redirect() 也被 Turbopack 阻塞 |

**诊断方法**：
```bash
# 容器内测试 - 静态页面正常但 SSR 挂死
docker exec deer-flow-frontend wget -qO- --timeout=5 http://localhost:3000/
# → 返回 HTML ✅

docker exec deer-flow-frontend wget -qO- --timeout=5 http://localhost:3000/workspace
# → 超时 ❌
```

### 解决方案

**方案 A（推荐）：使用 prod target + next start（生产模式）**

原理：预编译的 .next 产物不依赖 Turbopack/Webpack dev server。

修改 `docker-compose-dev.yaml`：
```yaml
frontend:
  build:
    context: ../
    dockerfile: frontend/Dockerfile
    target: prod  # ✅ 用 prod target（已预编译）
  command: sh -c "pnpm start > /app/logs/frontend.log 2>&1"
  mem_limit: 2g
  memswap_limit: 2g
```

**方案 B：禁用 Turbopack（使用 webpack dev server）**

修改 `frontend/package.json`：
```json
"dev": "next dev --webpack"
```

注意：`next dev`（不带参数）在 Next.js 16.1.7 中默认启用 Turbopack，需要显式 `--webpack`。

---

### 问题：512MB 内存运行 `pnpm build` 导致 OOM（Exit Code 137）

**症状**：
```
Error: spawn ENOMEM
Container exited with code 137 (OOM Killed)
```

**原因**：`pnpm build` 需要 1.5GB+ 内存，512MB 不足。

**解决**：使用 prod target（已在镜像中预编译），无需在容器内 build。

---

### 问题：prod target 启动后 Internal Server Error（BETTER_AUTH_SECRET 缺失）

**症状**：nginx → frontend 返回 200，但浏览器显示 Internal Server Error。

**根因**：`frontend/.env` 中没有 `BETTER_AUTH_SECRET`，而 prod target 从 `frontend/.env` 读取。

**解决**：修改 `docker-compose-dev.yaml` 的 env_file：
```yaml
frontend:
  env_file:
    - ../.env  # ✅ 指向根目录 .env（包含 BETTER_AUTH_SECRET）
```

---

## ADS MCP 配置陷阱（2026-04-21 新增）

### 问题：ADS MCP 有两层配置文件，修改一处不够

**症状**：修改了 `extensions_config.json` 中的 `ADS_API_BASE_URL`，但 ADS MCP 仍然使用旧地址。

**根因**：ADS MCP 有**独立的配置文件**：

| 配置文件 | 路径（容器内） | 作用 |
|----------|---------------|------|
| `extensions_config.json` | `/app/extensions_config.json` | DeerFlow → MCP Server 的启动配置 |
| `.ads-mcp/config.json` | `/app/ads-mcp/.ads-mcp/config.json` | ADS MCP 内部配置（API 地址、凭证） |

ADS MCP **优先读取自己的内部配置**，忽略 `extensions_config.json` 中的 `env.ADS_API_BASE_URL`。

**诊断**：
```bash
# 检查 MCP 内部配置
docker exec deer-flow-gateway cat /app/ads-mcp/.ads-mcp/config.json
```

### 解决方案

**方案 A：在 gateway 启动命令中 sed 替换（推荐）**

修改 `docker-compose-dev.yaml` 的 gateway command：
```yaml
gateway:
  command: sh -c "{ sed -i 's|http://127.0.0.1:80|https://192.168.1.54|g' /app/ads-mcp/.ads-mcp/config.json /app/ads-mcp/config.json && cd backend && ...; } > /app/logs/gateway.log 2>&1"
```

同时修改 ADS MCP 源目录的配置文件（永久生效）：
```bash
# 修改 Windows 源文件
notepad "C:\Users\wing\Documents\Wing\git\ds2server\ds2server\ads-agent\mcp\.ads-mcp\config.json"
```

### 问题：ADS MCP 挂载为只读导致无法修改配置

**症状**：`sed: couldn't open directory .ads-mcp: No such file or directory`

**原因**：`docker-compose-dev.yaml` 中 ADS MCP 目录挂载为 `:ro`（只读）。

**解决**：改为可读写：
```yaml
# 之前（只读）
- /home/wing/wing/git/ds2server/ds2server/ads-agent/mcp:/app/ads-mcp:ro

# 现在（可读写）
- /home/wing/wing/git/ds2server/ds2server/ads-agent/mcp:/app/ads-mcp
```

---

## nginx 重定向地址修复（2026-04-21 新增）

### 问题：Next.js SSR redirect 返回 308，浏览器收到后无法访问

**症状**：`/workspace` → `308 Redirect` → `Location: http://frontend:3000/workspace/chats/new` → 浏览器无法访问 Docker 内部地址。

**根因**：nginx 收到 upstream 的 redirect 响应后，`Location` header 指向容器内地址，浏览器无法访问。

**解决**：在 nginx.conf 中添加 `proxy_redirect`：
```nginx
location / {
    proxy_pass http://frontend;
    proxy_redirect http://frontend:3000 http://$host:$server_port;
    # ...
}
```

---

## NumPy CPU 指令集不兼容（PyInstaller 编译部署）（2026-05-12 新增）

### 问题：编译后的 Gateway 二进制在目标服务器启动失败

**症状**：
```
RuntimeError: NumPy was built with baseline optimizations:
(X86_V2) but your machine doesn't support:
(X86_V2).

ERROR:    Application startup failed. Exiting.
```

**涉及场景**：
- 在本机（CPU 较新）执行 `bash build-backend.sh` 编译
- 将编译产物 `dist/deerflow-gateway/` 传到目标服务器（CPU 较老）
- 启动后 NumPy 检测到当前 CPU 不支持 x86-64-v2 指令集，直接崩溃

**根因**：
NumPy 在安装（或编译）时会自动检测当前 CPU 支持的指令集，启用最高级别的基线优化。较新的 CPU 支持 `x86-64-v2`（AVX、SSE4.2 等），而较老的服务器 CPU（如 Haswell 之前）不支持。PyInstaller 将 NumPy 的 `.so` 编译进二进制后，这个优化检测结果被锁定，无法在运行服务器上降级。

**已修复**（2026-05-12）：
`backend/build-backend.sh` 已在 `uv sync` 后自动执行 `uv pip install "numpy<2"` 降级 numpy。**直接用 `build-backend.sh` 编译即可，无需手动降级**。

### 首次遇到此问题的修复流程

如果仍然遇到此错误，说明二进制是旧版本编译的，重新编译即可：

```bash
cd /usr/xccloud/deerflow/source

# 1. 如果之前手动降级过 numpy，重复执行保留（脚本会自动处理）
# 2. 直接重新编译（build-backend.sh 已内置 numpy 降级）
bash build-backend.sh

# 3. 覆盖旧二进制
cp -r dist/deerflow-gateway /usr/xccloud/deerflow/backend-bin/

# 4. 重启
cd /usr/xccloud/deerflow
./scripts/deerflow.sh --stop
./scripts/deerflow.sh
```

### 手动降级 numpy（仅当脚本未生效时备用）

```bash
cd /usr/xccloud/deerflow/source
uv pip install "numpy<2" --force-reinstall
bash build-backend.sh
```

**最佳实践**：
- 后端编译尽量在目标服务器上执行（确保 CPU 架构一致）
- `build-backend.sh` 已内置 numpy 降级，保持脚本为最新版本
- 前后端分离：本机只编译前端，后端始终在服务器编译

---

## ADS MCP 故障排查

### 问题：DeerFlow 无法识别 ADS MCP

**症状**：LangGraph 日志中没有 `Configured MCP server: ads`。

**根因**：ADS MCP 源码目录缺少 `dist/` 和 `node_modules/`（未执行 `npm run build`），容器挂载的是空目录。

**排查**：
```bash
ls "/home/wing/wing/git/ds2server/ds2server/ads-agent/mcp/dist/"
ls "/home/wing/wing/git/ds2server/ds2server/ads-agent/mcp/node_modules/"
```

**解决**：
```bash
cd "/home/wing/wing/git/ds2server/ds2server/ads-agent/mcp"
npm install && npm run build
docker compose -f docker-compose-dev.yaml down && docker compose -f docker-compose-dev.yaml up -d
```

### 问题：切换 ADS MCP 开关时报 Errno 30

**症状**：Web UI 中切换 ADS MCP 开关时返回 `Failed to update MCP configuration: [Errno 30] Read-only file system: '/app/backend/extensions_config.json'`

**根因**：`docker/.env` 中的路径是 Windows 主机路径，在容器内不存在。另外，ADS MCP 目录可能挂载为 `:ro`（只读）。

**解决**：将 `docker-compose-dev.yaml` 中 ADS MCP 目录挂载改为可读写：
```yaml
# 之前（只读）
# - /home/wing/wing/git/ds2server/ds2server/ads-agent/mcp:/app/ads-mcp:ro

# 现在（可读写）
- /home/wing/wing/git/ds2server/ds2server/ads-agent/mcp:/app/ads-mcp
```

同时确保 `docker-compose-dev.yaml` 中 `DEER_FLOW_EXTENSIONS_CONFIG_PATH` 设置为容器内路径（见上文 .env 配置陷阱）。

---

## 快速故障排查流程图

```
容器无法启动？
│
├─► 检查状态：docker ps
│   └─► 容器未运行？检查日志：docker logs <名称>
│
├─► 502 Bad Gateway？
│   ├─► 检查 gateway 日志：docker logs deer-flow-gateway
│   ├─► 检查 langgraph 日志：docker logs deer-flow-langgraph
│   └─► IsADirectoryError？修复 .env 路径（见上文）
│
├─► 内存问题？
│   ├─► 检查使用：docker stats --no-stream
│   ├─► 轻量清理：docker system prune -f
│   └─► 深度清理：docker system prune -a --volumes -f
│
└─► 配置未加载？
    ├─► 验证 .env 存在于 docker/ 目录
    ├─► 验证路径是主机路径（不是容器路径）
    └─► 重启：docker compose down && docker compose up -d
```

---

## 最佳实践

1. **不要重建所有内容**：仅前端变更时使用 `docker compose up -d --build frontend`
2. **定期清理**：每周运行 `docker system prune -f`
3. **监控内存**：偶尔运行 `docker stats` 检查异常
4. **不要提交 .env**：包含敏感密钥
5. **先检查日志**：大多数问题在容器日志中可见
6. **先尝试重启**：许多问题可通过 `docker compose down && docker compose up -d` 解决

---

## 启动前预检

```bash
# 检查 Docker 占用状态
docker system df
# 如果 Images 可回收率 > 80%，或 Build Cache > 10GB，先清理：
docker system prune -a --volumes -f
```

### 构建铁律

1. **禁止同时构建多镜像**：gateway、langgraph、frontend 绝对不能一起 build
2. **除非明确说 "rebuild xxx"**，否则只用 `docker compose up -d` 不带 `--build`
3. **volume 已挂载代码目录**，修改代码无需 rebuild：
   - `frontend/src` → `/app/frontend/src`（Next.js 热更新）
   - `backend/` → `/app/backend/`（uvicorn --reload 热更新）

---

## 快速验证

```bash
# 检查容器内存限制
docker inspect deer-flow-frontend --format '{{.HostConfig.Memory}}'
# 应显示：2147483648（2GB 字节数）

# 检查 ADS MCP 构建状态
ls "/home/wing/wing/git/ds2server/ds2server/ads-agent/mcp/dist/"
ls "/home/wing/wing/git/ds2server/ds2server/ads-agent/mcp/node_modules/"
```
