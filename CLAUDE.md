# CLAUDE.md

本文件为 AI 编程助手（Claude Code、Codex、Cursor、Windsurf 等）提供 DeerFlow 项目指导。

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

**可用的 make 命令**：

| 命令 | 用途 |
|------|------|
| `make dev` | 本地开发模式（热更新） |
| `make dev-pro` | 本地开发 + Gateway 模式 |
| `make start` | 本地生产模式 |
| `make start-pro` | 本地生产 + Gateway 模式 |
| `make docker-start` | Docker 开发模式启动 |
| `make docker-stop` | Docker 开发模式停止 |
| `make doctor` | 诊断配置和环境问题 |
| `make check` | 检查依赖是否完整 |

## 项目概述

DeerFlow 是一个基于 LangGraph 的 AI Super Agent 系统，采用全栈架构：

- **Frontend** (Next.js 16, 端口 3000) → 通过 **Nginx** 反向代理 (端口 2026)
- **Gateway API** (FastAPI, 端口 8001) → REST API：模型、MCP、skills、内存、文件上传
- **LangGraph Server** (端口 2024) → Agent 运行时和工作流执行

详细架构说明见下方子模块文档。

## 子模块文档

```
@./backend/CLAUDE.md    # 后端：LangGraph agent 系统、harness/app 架构、middleware 链
@./frontend/CLAUDE.md    # 前端：Next.js 16、TanStack Query、thread hooks
@./docker/CLAUDE.md     # Docker：Compose 配置、环境变量
```

## ⚠️ 核心源码补丁（同步上游时注意）

两个扩展对 DeerFlow 核心源码的侵入性修改。从 ByteDance 上游 `git pull` 后，**必须检查这些补丁是否被覆盖**：

| 扩展 | 改动文件 | 风险 | 数量 |
|------|---------|------|------|
| **data_collection**（蒸馏数据采集） | `app.py` + `docker-compose*.yaml` + `entrypoint.sh` + `sitecustomize.py` | ✅ 低 | 4 个核心 + 1 个扩展 |
| **ads_auth**（ADS 统一认证） | `app.py` + `auth_middleware.py` + `csrf_middleware.py` + `deps.py` + `docker-compose-dev.yaml` + `next.config.js` + `middleware.ts` + `types.ts` + `.env.example` | ✅ 低 | 9 个核心 |

详细补丁内容与快速验证命令见：
➡️ `@./docs/patches/ads_auth_core_changes/README.md`（按模块拆分：`backend.md` / `frontend.md` / `docker.md` / `scripts.md` / `config.md`）

## ⚠️ Release 编译注意事项（部署 404 的常见根因）

编译 PyInstaller 二进制部署时，**必须注意以下两点**，否则 ADS 认证在部署环境会返回 404：

### 1. `deerflow_entry.py` 必须 import 模块级 `app`，不能调 `create_app()`

```python
# ✅ 正确
from app.gateway.app import app

# ❌ 错误 — 导致双重 create_app()，ADS 路由注册到错误实例 → 404
from app.gateway.app import create_app
app = create_app()
```

根因：`import create_app` 触发模块级 `app = create_app()`（App #1），显式调用又创建 App #2。`install_ads_auth()` 有 `_installed` 防重入，只在 App #1 生效 → uvicorn 运行 App #2 → 404。

### 2. `cp` 必须用整个目录复制，不加 `/*`

```bash
# ✅ 正确 — 保持 backend-bin/deerflow-gateway/(二进制+_internal/) 结构
rm -rf /usr/xccloud/deerflow/backend-bin
cp -r dist/deerflow-gateway /usr/xccloud/deerflow/backend-bin/

# ❌ 错误 — 摊平结构，server-release.sh 路径不匹配
cp -r dist/deerflow-gateway/* /usr/xccloud/deerflow/backend-bin/
```

服务器编译脚本 `@./backend/scripts/build-backend-on-server.sh` 头部已包含完整注意事项。

## 项目文档目录

详细文档位于 `docs/` 目录：

```
docs/
├── config/                        # 配置相关文档
├── mcp/                           # MCP 集成文档（ADS、DeepRAG 等）
├── changelog/                     # 代码变更记录
│   ├── CODE_CHANGE_SUMMARY_BY_FILE.md  # 原总览文件（已拆分，入口见子目录）
│   └── code_change_summary/       # 按模块拆分：backend/frontend/docker/scripts/skills/config
│       ├── README.md
│       ├── backend.md
│       ├── frontend.md
│       ├── docker.md
│       ├── scripts.md
│       ├── skills.md
│       └── config.md
├── patches/                       # 核心源码补丁记录
│   ├── ADS_AUTH_CORE_CHANGES.md   # 原总览文件（已拆分，入口见子目录）
│   └── ads_auth_core_changes/    # 按模块拆分：backend/frontend/docker/scripts/config
│       ├── README.md
│       ├── backend.md
│       ├── frontend.md
│       ├── docker.md
│       ├── scripts.md
│       └── config.md
├── operations/                    # 运维与故障排查指南
├── plans/                         # 技术方案计划
│   ├── deerflow模型蒸馏私有化可行性分析方案.md
│   ├── deerflow蒸馏数据采集体系设计.md
│   └── deerflow蒸馏数据采集体系-spec.md
├── skills/                        # Skill 相关文档
└── pr-evidence/                   # PR 测试截图
```

## 扩展插件目录

`deerflow_extensions/` 是独立插件目录（与 `backend/` 平级），存放零侵入扩展模块，不修改 DeerFlow 主干代码。

| 插件 | 路径 | 说明 |
|------|------|------|
| 蒸馏数据采集系统 | `@./deerflow_extensions/data_collection/` | Agent全链路数据旁路采集，为蒸馏训练储备数据 |
| **ADS 统一认证** | `@./deerflow_extensions/ads_auth/` | **ADS JWT 登录代理，替换 DeerFlow 原生认证** |
| README | `@./deerflow_extensions/data_collection/README.md` | 安装/使用/卸载说明 |
| API文档 | `@./deerflow_extensions/data_collection/API.md` | 完整API参考 |

| 文档 | 路径 | 说明 |
|------|------|------|
| 编译部署指南 | `@./docs/operations/BUILD_AND_DEPLOY.md` | 编译方式、56服务器传输、产物清单（主要方式：本机编译前端+56编译后端） |
| 运维指南 | `@./docs/operations/OPERATIONS.md` | Docker/WSL 内存、502 故障排查 |
| ADS MCP 集成 | `@./docs/mcp/ADS-MCP对接DeerFlow整合指南-实测版.md` | ADS MCP 对接配置与验证 |
| DeepRAG MCP 集成 | `@./docs/mcp/DeepRAG_MCP对接DeerFlow整合指南.md` | DeepRAG MCP 对接配置与验证 |
| 代码变更记录 | `@./docs/changelog/code_change_summary/README.md` | 按模块拆分的变更总结（`backend.md` / `frontend.md` / `docker.md` / `scripts.md` / `skills.md` / `config.md`） |
| Skill 名称冲突修复 | `@./docs/skills/SKILL_NAME_CONFLICT_FIX.md` | Skill 名称冲突解决方案 |

## 常用命令

```bash
# Docker（在 deer-flow/docker 目录）

# ⚠️ 重启前必须检查：Docker 占用状态
docker system df
# 如果 Images 可回收率 > 80%，或 Build Cache > 10GB，先清理：
docker system prune -a --volumes -f

# 重启 DeerFlow（永远不带 --build，因为 volume 已挂载代码目录）
docker compose down
docker compose up -d

# ⚠️ 铁律：
# 1. 禁止同时构建多镜像（gateway/langgraph/frontend 绝对不能一起 build）
# 2. 除非主子明确说 "rebuild xxx"，否则只用 up -d 不带 --build
docker compose up -d --build frontend   # 仅重建 frontend（修改了 Dockerfile / package.json / next.config.js 时）
docker compose up -d --build gateway     # 仅重建 gateway（修改了 Dockerfile / pyproject.toml 时）
docker compose up -d --build langgraph  # 仅重建 langgraph（修改了 Dockerfile / pyproject.toml 时）

# 关于 volume 挂载：docker-compose-dev.yaml 已配置好代码目录挂载
#   - frontend/src → /app/frontend/src   （Next.js 热更新）
#   - backend/    → /app/backend/         （uvicorn --reload 热更新）
# 所以改前端/后端代码不需要 rebuild！

docker logs <容器名> --tail 50    # 查看日志
docker stats --no-stream           # 查看资源使用

# 后端（在 deer-flow/backend 目录）
make dev      # 运行 LangGraph Server (端口 2024)
make gateway  # 运行 Gateway API (端口 8001)
make test     # 运行测试

# 前端（在 deer-flow/frontend 目录）
pnpm dev     # 开发服务器 (端口 3000)
pnpm build   # 生产构建
pnpm check   # Lint + 类型检查
```

## Docker/WSL 运维与故障排查

### WSL 内存增长 → 黑屏

**症状**：`vmmemws`（WSL2）占用大量内存，系统变得无响应或黑屏。

**根因**：
- 反复执行 `docker compose up --build` 会累积旧镜像和构建缓存
- 构建缓存可增长至 **65GB+**
- WSL2 不会自动将内存释放给 Windows

**预防**：
```bash
# 每周：轻量清理（删除停止的容器、未使用的网络、缓存）
docker system prune -f

# 每月：深度清理（删除所有未使用的镜像、容器、卷、缓存）
docker system prune -a --volumes -f

# 可选：通过 C:\Users\wing\.wslconfig 设置 WSL2 内存限制：
# [wsl2]
# memory=4GB
# processors=4
# swap=2GB
```

### Frontend 容器内存：2.9GB（正常：200-500MB）

**根因**：`docker-compose.yaml` 未设置 `mem_limit`，Dockerfile 未设置 `NODE_OPTIONS` 内存限制。

**已修复（2026-04-21 更新）**：
- `docker-compose-dev.yaml`：`mem_limit: 2g`（2GB，生产模式 next start）
- `Dockerfile`：`ENV NODE_OPTIONS="--max-old-space-size=768"`
- **注意**：Next.js 16.1.7 dev server + Turbopack SSR 会挂死，使用 `target: prod` + `pnpm start` 代替

验证命令：
```bash
docker inspect deer-flow-frontend --format '{{.HostConfig.Memory}}'
# 应显示：2147483648（2GB 字节数）
```

### 502 Bad Gateway / IsADirectoryError

**症状**：Gateway 或 LangGraph 启动失败：
```
IsADirectoryError: [Errno 21] Is a directory: '/app/backend/config.yaml'
RuntimeError: Failed to load configuration during gateway startup
```

**根因**：`docker/.env` 中的路径配置错误。`DEER_FLOW_CONFIG_PATH` 等环境变量必须是**主机路径**（Windows 路径），而不是容器内路径。Docker 会将主机路径当作文件挂载，如果路径不存在则创建同名**目录**。

**正确的 .env 配置**（docker/.env）：
```env
HOME=C:\Users\wing
BETTER_AUTH_SECRET=<你的密钥>
DEER_FLOW_CONFIG_PATH=C:\path\to\deer-flow\config.yaml
DEER_FLOW_EXTENSIONS_CONFIG_PATH=C:\path\to\deer-flow\extensions_config.json
DEER_FLOW_HOME=C:\path\to\deer-flow
DEER_FLOW_REPO_ROOT=C:\path\to\deer-flow
DEER_FLOW_DOCKER_SOCKET=/var/run/docker.sock
PORT=2026
```

**注意**：Docker Compose 会自动将这些主机路径映射到 docker-compose.yaml volumes 中定义的容器内路径。

### ADS MCP 识别不到 + Errno 30

**症状 1**：DeerFlow 无法识别 ADS MCP，LangGraph 日志中没有 `Configured MCP server: ads`。

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

---

**症状 2**：在 DeerFlow Web UI 中切换 ADS MCP 开关时报错：
```
Failed to update MCP configuration: [Errno 30] Read-only file system: '/app/backend/extensions_config.json'
```

**根因**：`docker/.env` 中的 `DEER_FLOW_EXTENSIONS_CONFIG_PATH=C:\Users\wing\...` 是 Windows 主机路径，在容器内不存在。`resolve_config_path()` 抛异常后被 `except Exception` 捕获，代码 fallback 失败导致 `Errno 30`。

**解决**：在 `docker-compose-dev.yaml` 的 `environment` 中显式设置容器内路径，**覆盖** `.env` 中的 Windows 路径：

```yaml
gateway:
  environment:
    - DEER_FLOW_EXTENSIONS_CONFIG_PATH=/app/extensions_config.json  # 覆盖 .env
  env_file:
    - ../.env

langgraph:
  environment:
    - DEER_FLOW_EXTENSIONS_CONFIG_PATH=/app/extensions_config.json  # 覆盖 .env
  env_file:
    - ../.env
```

**关键**：`environment` 中的变量会覆盖 `env_file` 中的同名变量。设置为容器内路径 `/app/extensions_config.json`（已通过 volume 挂载为可读写）。

**重要更新（2026-04-21）**：ADS MCP 有两层配置文件，详见 `@./docs/mcp/ADS-MCP对接DeerFlow整合指南-实测版.md`

## 故障排查清单

1. **检查容器状态**：
   ```bash
   docker ps
   ```

2. **检查容器日志**：
   ```bash
   docker logs deer-flow-gateway --tail 50
   docker logs deer-flow-langgraph --tail 50
   docker logs deer-flow-frontend --tail 50
   ```

3. **检查内存使用**：
   ```bash
   docker stats --no-stream
   ```

4. **重启服务**：
   ```bash
   docker compose down
   docker compose up -d
   ```

5. **深度清理**（内存/磁盘问题时）：
   ```bash
   docker system prune -a --volumes -f
   ```

## 重要开发准则

### 文档更新策略
**重要：代码变更后必须更新相关文档**

变更时：
- 用户面向变更更新 `README.md`（功能、设置、使用说明）
- 开发面向变更更新子模块的 `CLAUDE.md`（架构、命令、工作流）
- 保持文档与代码同步

### 零侵入原则
**优先零侵入方案，减少上游同步冲突**

对 DeerFlow 核心源码（`backend/`、`frontend/`、`docker/` 等）的所有修改，必须优先评估零侵入方案：

1. **优先走扩展目录**：能放在 `deerflow_extensions/` 或 `frontend/extensions/` 的逻辑，绝不直接改核心源码
2. **必要时才打补丁**：只有在扩展目录无法实现（如 middleware 链注入、路由配置侵入）时才允许直接改核心文件
3. **侵入代码必须 try/except 包裹**：所有注入扩展的 import 和调用都必须用 `try/except ImportError` 包起来——扩展不可用时 DeerFlow 仍能正常运行
4. **降低冲突面**：侵入改动集中在少数文件的同一区域（如 `app.py` 的启动注入块、`auth_middleware.py` 的 dispatch 守卫），方便上游同步时快速识别和重放

参考业界"依赖反转 + 插件化"最佳实践，零侵入不仅是设计目标，更是长期可维护性的保障。

### 代码变更记录义务
**重要：所有核心源码改动必须同时记录到 changelog 和 patches**

任何对 DeerFlow 核心源码（`backend/`、`frontend/`、`docker/`、`deerflow_extensions/entrypoint.sh`、`deerflow_extensions/sitecustomize.py`、`.env.example` 等）的修改，**必须**按以下要求记录：

1. **如果改动是侵入型补丁**（用于对接扩展模块，需在同步上游时重放）：
   - 写入 `@./docs/patches/ads_auth_core_changes/` 下对应模块文件（`backend.md` / `frontend.md` / `docker.md` / `scripts.md` / `config.md`）
   - 格式要求：文件路径、行号、改动内容（diff 块）、原因说明、风险标记（✅低 / ✅极低）

2. **如果改动是通用代码变更**（非补丁，如功能迭代、重构、bug 修复）：
   - 写入 `@./docs/changelog/code_change_summary/` 下对应模块文件（`backend.md` / `frontend.md` / `docker.md` / `scripts.md` / `skills.md` / `config.md`）
   - 格式要求：文件路径、diff 或改动说明、原因

3. **两者皆有**：每次修改代码后，先判断属于哪一类（或同时两类），各自写入对应模块文件

4. **同一改动的多模块影响**：如果一个改动涉及多个模块（如加一个环境变量同时改 backend 和 docker），则每个受影响的模块文件都要记录

### 测试驱动开发
每个功能或 bug 修复必须有单元测试。提交前运行 `make test`（后端）或 `pnpm test`（前端）。
