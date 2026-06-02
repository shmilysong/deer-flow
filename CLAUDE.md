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

## ⚠️ 铁律：零侵入扩展原则

**绝对禁止**直接修改核心源码来添加功能。所有自定义功能必须优先走扩展目录。详见 `@./docs/methodology/零侵入扩展方法论.md`。

### 扩展目录
- 前端：`frontend/extensions/`
- 后端：`deerflow_extensions/`

### 三层扩展模式（从优到劣）
1. **Level 1 纯扩展** — 代码全在扩展目录，零侵入核心。如：input-suggestions、mobile-sidebar
2. **Level 2 注入扩展** — 扩展目录实现逻辑，核心源码加 try/except 注入。如：env-settings
3. **Level 3 补丁扩展** — 少量核心源码改动，try/except 包裹 + _installed 守卫。如：ads_auth、data_collection

### 改造完成后必须归档文档
| 文档 | 位置 | 适用场景 |
|------|------|---------|
| 扩展 README.md | 扩展目录自身 | 所有 Level |
| 补丁记录 | `docs/patches/` | Level 2/3 |
| 变更记录 | `docs/changelog/code_change_summary/` | 所有核心源码改动 |

## 项目概述

DeerFlow 是一个基于 LangGraph 的 AI Super Agent 系统，采用全栈架构：

- **Frontend** (Next.js 16, 端口 3000) → 通过 **Nginx** 反向代理 (端口 2026)
- **Gateway API** (FastAPI, 端口 8001) → REST API：模型、MCP、skills、内存、文件上传
- **LangGraph Server** (端口 2024) → Agent 运行时和工作流执行

**技术栈：** Next.js 16 + React 19 + pnpm 10 | FastAPI + LangGraph + SQLAlchemy | Nginx + Docker

**子模块 CLAUDE.md：** `@./backend/CLAUDE.md`（后端架构）、`@./frontend/CLAUDE.md`（前端开发）、`@./docker/CLAUDE.md`（Docker 配置）

## ⚠️ 核心源码补丁

所有扩展对核心源码的侵入性修改清单见 `@./docs/patches/README.md`（总览 + 快速验证命令）。

**核心原则：** 所有注入代码均以 `try/except ImportError` 包裹，扩展不可用时 DeerFlow 正常运行。从 ByteDance 上游 `git pull` 后必须运行 `docs/patches/README.md` 中的验证命令检查补丁是否被覆盖。

## ⚠️ Release 编译注意事项

编译 PyInstaller 二进制部署时需注意的两大常见坑点（ADS 认证 404 的根因），详见 `@./docs/operations/BUILD_AND_DEPLOY.md#5-release-常见坑点`。

## 扩展插件目录

`deerflow_extensions/` 是独立插件目录（与 `backend/` 平级），存放零侵入扩展模块。前端扩展位于 `frontend/extensions/`。

| 插件 | 路径 | 说明 |
|------|------|------|
| 蒸馏数据采集系统 | `@./deerflow_extensions/data_collection/` | Agent全链路数据旁路采集，为蒸馏训练储备数据 |
| **ADS 统一认证** | `@./deerflow_extensions/ads_auth/` | **ADS JWT 登录代理，替换 DeerFlow 原生认证** |
| **Env Settings** | `@./deerflow_extensions/env_settings/` | **多厂商 API Key 管理（7厂商），自动注册/清理 config.yaml 模型** |
| **topic_guardrail** | `@./deerflow_extensions/topic_guardrail/` | 回答范围限制：System Prompt 角色定位 + L3 敏感词过滤 |
| **input-suggestions** | `@./frontend/extensions/input-suggestions/` | 输入建议按钮自定义，替换内置的"小惊喜/写作/研究"等按钮 |
| **mobile-sidebar** | `@./frontend/extensions/mobile-sidebar/` | 移动端侧栏浮动汉堡触发按钮 |

## 文档与参考目录

完整文档目录索引见 `@./docs/README.md`。

## 常用命令

### 后端（在 deer-flow/backend 目录）
make dev      # 运行 LangGraph Server (端口 2024)
make gateway  # 运行 Gateway API (端口 8001)
make test     # 运行测试

### 前端（在 deer-flow/frontend 目录）
pnpm dev     # 开发服务器 (端口 3000)
pnpm build   # 生产构建
pnpm check   # Lint + 类型检查

### Docker
详见 `@./docs/operations/OPERATIONS.md`。

## 开发准则

### 文档同步
代码变更后必须同步更新 `docs/` 下对应的文档（创建新文档或新目录按需），以及各级 `CLAUDE.md` 和用户面向的 `README.md`。

### 代码变更记录
任何核心源码改动必须记录到 `@./docs/patches/`（补丁）或 `@./docs/changelog/code_change_summary/`（通用变更），详见这两份文档的格式要求。

### 测试驱动
每个功能或 bug 修复必须有单元测试。提交前运行 `make test`（后端）或 `pnpm test`（前端）。
