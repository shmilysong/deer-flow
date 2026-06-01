# CLAUDE.md

本文件为 AI 编程助手（Claude Code、Codex、Cursor、Windsurf 等）提供 DeerFlow 项目指导。

## ⚠️ 铁律：启动/停止 DeerFlow 必须使用 start-deerflow.sh

**绝对禁止**使用 `make`、`uv run`、`python -m`、`docker compose`、`./scripts/serve.sh` 等命令。

**唯一正确方式**：

```bash
# ✅ 编译 + 后台启动（正确方式）
bash scripts/start-deerflow.sh

# ✅ 停止服务
bash scripts/start-deerflow.sh --stop

# ✅ 重启（先停→编译→再启）
bash scripts/start-deerflow.sh --restart

# ❌ 禁止以下任何方式（自作主张）
make dev               # 禁止（用了 serve.sh + docker）
make docker-start      # 禁止
docker compose ...     # 禁止
./scripts/serve.sh     # 禁止
uv run uvicorn ...     # 禁止
pnpm dev               # 禁止
```

**日志查看**：

```bash
tail -f logs/gateway.log    # 后端日志
tail -f logs/frontend.log   # 前端日志
```

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
| **settings-dialog-ext**（SettingsDialog 扩展架构） | `settings-dialog.tsx` + `registry.ts` + `workspace-nav-menu.tsx` + `app.py` | ✅ 低 | 3 个前端 + 1 个后端 |

详细补丁内容与快速验证命令见：
➡️ `@./docs/patches/README.md`（按模块拆分：`backend.md` / `frontend.md` / `docker.md` / `scripts.md` / `config.md`）

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
├── auth/                          # 认证相关文档
├── changelog/                     # 代码变更记录
│   └── code_change_summary/       # 按模块拆分：backend/frontend/docker/scripts/skills/config
│       ├── README.md
│       ├── backend.md
│       ├── frontend.md
│       ├── docker.md
│       ├── scripts.md
│       ├── skills.md
│       └── config.md
├── channels/                      # IM 渠道集成文档
├── config/                        # 配置相关文档
├── fork-sync/                     # Fork 同步记录与指南
├── mcp/                           # MCP 集成文档（ADS、DeepRAG 等）
├── operations/                    # 运维与故障排查指南
├── patches/                       # 核心源码补丁记录（已合并为扁平文件）
│   ├── README.md                  # 总览与快速验证
│   ├── backend.md
│   ├── frontend.md
│   ├── docker.md
│   ├── scripts.md
│   └── config.md
├── plans/                         # 技术方案计划
│   ├── 2026-04-01-langfuse-tracing.md
│   ├── deerflow模型蒸馏私有化-数据量硬件与效果深度分析.md
│   ├── deerflow模型蒸馏私有化可行性分析方案.md
│   └── deerflow蒸馏数据采集体系设计.md
├── pr-evidence/                   # PR 测试截图
├── skills/                        # Skill 相关文档
└── superpowers/                   # Superpowers 框架文档
    ├── plans/
    └── specs/
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

运维与故障排查内容已落地到独立文档，以下仅列摘要和引用：

| 主题 | 文档 |
|------|------|
| WSL 内存管理 / Frontend 内存问题 / 502 Gateway / .env 配置 / ADS MCP 故障 | `@./docs/operations/OPERATIONS.md` |
| ADS MCP 两层配置 & 整合细则 | `@./docs/mcp/ADS-MCP对接DeerFlow整合指南-实测版.md` |
| 编译部署 & NumPy 兼容性 | `@./docs/operations/BUILD_AND_DEPLOY.md` |
| 部署已知问题 | `@./docs/operations/DEPLOYMENT_KNOWN_ISSUES.md` |

**快速验证命令**：
```bash
# 检查容器内存限制
docker inspect deer-flow-frontend --format '{{.HostConfig.Memory}}'
# 应显示：2147483648（2GB 字节数）

# 检查 ADS MCP 构建状态
ls "/home/wing/wing/git/ds2server/ds2server/ads-agent/mcp/dist/"
ls "/home/wing/wing/git/ds2server/ds2server/ads-agent/mcp/node_modules/"
```

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
   - 写入 `@./docs/patches/` 下对应模块文件（`backend.md` / `frontend.md` / `docker.md` / `scripts.md` / `config.md`）
   - 格式要求：文件路径、行号、改动内容（diff 块）、原因说明、风险标记（✅低 / ✅极低）

2. **如果改动是通用代码变更**（非补丁，如功能迭代、重构、bug 修复）：
   - 写入 `@./docs/changelog/code_change_summary/` 下对应模块文件（`backend.md` / `frontend.md` / `docker.md` / `scripts.md` / `skills.md` / `config.md`）
   - 格式要求：文件路径、diff 或改动说明、原因

3. **两者皆有**：每次修改代码后，先判断属于哪一类（或同时两类），各自写入对应模块文件

4. **同一改动的多模块影响**：如果一个改动涉及多个模块（如加一个环境变量同时改 backend 和 docker），则每个受影响的模块文件都要记录

### 测试驱动开发
每个功能或 bug 修复必须有单元测试。提交前运行 `make test`（后端）或 `pnpm test`（前端）。
