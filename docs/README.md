# Documentation 文档目录

## ⚠️ 方法论（核心）

本目录最重要的文档——所有扩展开发和代码修改必须遵循的方法论。

| 文档 | 说明 |
|------|------|
| [methodology/零侵入扩展方法论.md](./methodology/%E9%9B%B6%E4%BE%B5%E5%85%A5%E6%89%A9%E5%B1%95%E6%96%B9%E6%B3%95%E8%AE%BA.md) | 三条铁律、三层扩展模式、决策树、文档归档规范、补丁契约。**阅读优先级最高** |

---

## [auth/](./auth) — 认证

| 文档 | 说明 |
|------|------|
| [ADS统一认证集成.md](./auth/ADS%E7%BB%9F%E4%B8%80%E8%AE%A4%E8%AF%81%E9%9B%86%E6%88%90.md) | ADS 统一认证集成指南：架构、配置、部署 |

---

## [changelog/code_change_summary/](./changelog/code_change_summary) — 代码变更记录

| 文档 | 说明 |
|------|------|
| [README.md](./changelog/code_change_summary/README.md) | 代码变更总结模块索引（总览 + 统计） |
| [backend.md](./changelog/code_change_summary/backend.md) | 后端代码变更详情 |
| [frontend.md](./changelog/code_change_summary/frontend.md) | 前端代码变更详情 |
| [docker.md](./changelog/code_change_summary/docker.md) | Docker 配置变更详情 |
| [scripts.md](./changelog/code_change_summary/scripts.md) | 部署脚本变更详情 |
| [skills.md](./changelog/code_change_summary/skills.md) | 技能与 Demo 变更详情 |
| [config.md](./changelog/code_change_summary/config.md) | 环境变量与配置文件变更详情 |

---

## [channels/](./channels) — IM 渠道集成

| 文档 | 说明 |
|------|------|
| [README.md](./channels/README.md) | IM 渠道集成文档索引 |
| [WECOM.md](./channels/WECOM.md) | 企业微信渠道集成 |
| [FEISHU.md](./channels/FEISHU.md) | 飞书渠道集成 |
| [SLACK.md](./channels/SLACK.md) | Slack 渠道集成 |
| [TELEGRAM.md](./channels/TELEGRAM.md) | Telegram 渠道集成 |
| [DISCORD.md](./channels/DISCORD.md) | Discord 渠道集成 |
| [WECHAT.md](./channels/WECHAT.md) | 微信公众号渠道集成 |

---

## [config/](./config) — 配置

| 文档 | 说明 |
|------|------|
| [NETWORK_CONFIG_CHANGES.md](./config/NETWORK_CONFIG_CHANGES.md) | Docker 网络配置变更记录（host.docker.internal 等问题解决） |

---

## [fork-sync/](./fork-sync) — Fork 同步记录

| 文档 | 说明 |
|------|------|
| [README.md](./fork-sync/README.md) | Fork 同步记录索引 |
| [FORK_SYNC_20260507.md](./fork-sync/FORK_SYNC_20260507.md) | 2026-05-07 首次 Fork 同步记录 |
| [FORK_SYNC_20260601_CONFLICTS.md](./fork-sync/FORK_SYNC_20260601_CONFLICTS.md) | 2026-06-01 Fork 同步冲突处理记录 |

---

## [mcp/](./mcp) — MCP 集成

| 文档 | 说明 |
|------|------|
| [ADS-MCP对接DeerFlow整合指南-实测版.md](./mcp/ADS-MCP%E5%AF%B9%E6%8E%A5DeerFlow%E6%95%B4%E5%90%88%E6%8C%87%E5%8D%97-%E5%AE%9E%E6%B5%8B%E7%89%88.md) | ADS MCP 对接配置与验证 |
| [DeepRAG_MCP对接DeerFlow整合指南.md](./mcp/DeepRAG_MCP%E5%AF%B9%E6%8E%A5DeerFlow%E6%95%B4%E5%90%88%E6%8C%87%E5%8D%97.md) | DeepRAG MCP 对接配置与验证 |
| [HERMES_AGENT_INTEGRATION.md](./mcp/HERMES_AGENT_INTEGRATION.md) | Hermes Agent 集成改造参考 |
| [RAGFLOW_MCP_INTEGRATION.md](./mcp/RAGFLOW_MCP_INTEGRATION.md) | RagFlow MCP 集成修改记录（已停用） |

---

## [operations/](./operations) — 运维与部署

| 文档 | 说明 |
|------|------|
| [OPERATIONS.md](./operations/OPERATIONS.md) | 运维与故障排查指南（Docker/WSL 内存、502、Frontend 内存、ADS MCP 故障等） |
| [BUILD_AND_DEPLOY.md](./operations/BUILD_AND_DEPLOY.md) | 编译部署指南（前后端编译方式、56 服务器传输、Release 产物、常见坑点） |
| [DEPLOYMENT_KNOWN_ISSUES.md](./operations/DEPLOYMENT_KNOWN_ISSUES.md) | 部署已知问题与解决方案（模型配置、内存、路径等） |
| [HERMES_AGENT_DEPLOY.md](./operations/HERMES_AGENT_DEPLOY.md) | Hermes Agent 部署配置参考 |
| [USE_GUIDE.md](./operations/USE_GUIDE.md) | 部署使用指南（产物清单、服务器配置、启动停止流程） |

---

## [patches/](./patches) — 核心源码补丁记录

| 文档 | 说明 |
|------|------|
| [README.md](./patches/README.md) | 补丁总览与快速验证命令（git pull 后检查补丁是否被覆盖） |
| [backend.md](./patches/backend.md) | 后端核心源码补丁（app.py、auth_middleware.py、prompt.py 等） |
| [frontend.md](./patches/frontend.md) | 前端核心源码补丁（middleware.ts、settings-dialog.tsx、input-box.tsx 等） |
| [docker.md](./patches/docker.md) | Docker 核心源码补丁（docker-compose-dev.yaml 等） |
| [scripts.md](./patches/scripts.md) | 脚本核心源码补丁（entrypoint.sh——sitecustomize 已替换为 boot.py） |
| [config.md](./patches/config.md) | 配置核心源码补丁（.env.example 等） |

---

## [plans/](./plans) — 技术方案

| 文档 | 说明 |
|------|------|
| [2026-04-01-langfuse-tracing.md](./plans/2026-04-01-langfuse-tracing.md) | Langfuse 跟踪技术方案 |
| [deerflow模型蒸馏私有化可行性分析方案.md](./plans/deerflow%E6%A8%A1%E5%9E%8B%E8%92%B8%E9%A6%8F%E7%A7%81%E6%9C%89%E5%8C%96%E5%8F%AF%E8%A1%8C%E6%80%A7%E5%88%86%E6%9E%90%E6%96%B9%E6%A1%88.md) | 模型蒸馏私有化可行性分析 |
| [deerflow模型蒸馏私有化-数据量硬件与效果深度分析.md](./plans/deerflow%E6%A8%A1%E5%9E%8B%E8%92%B8%E9%A6%8F%E7%A7%81%E6%9C%89%E5%8C%96-%E6%95%B0%E6%8D%AE%E9%87%8F%E7%A1%AC%E4%BB%B6%E4%B8%8E%E6%95%88%E6%9E%9C%E6%B7%B1%E5%BA%A6%E5%88%86%E6%9E%90.md) | 模型蒸馏数据量、硬件与效果深度分析 |
| [deerflow蒸馏数据采集体系设计.md](./plans/deerflow%E8%92%B8%E9%A6%8F%E6%95%B0%E6%8D%AE%E9%87%87%E9%9B%86%E4%BD%93%E7%B3%BB%E8%AE%BE%E8%AE%A1.md) | 蒸馏数据采集体系设计方案 |

---

## [skills/](./skills) — Skill 相关

| 文档 | 说明 |
|------|------|
| [SKILL_NAME_CONFLICT_FIX.md](./skills/SKILL_NAME_CONFLICT_FIX.md) | Skill 名称冲突修复方案 |

---

## [pr-evidence/](./pr-evidence) — PR 测试截图

| 文件 | 说明 |
|------|------|
| session-skill-manage-e2e-20260406-194030.png | E2E 测试截图 |
| session-skill-manage-e2e-20260406-202745.png | E2E 测试截图 |

---

## 文档归档规范

| Level | 扩展方式 | 必须创建的文档 |
|-------|---------|-------------|
| Level 1 | 纯扩展（零侵入） | 扩展目录下 `README.md` |
| Level 2 | 注入扩展（低侵入） | 同上 + `docs/patches/` + `docs/changelog/code_change_summary/` |
| Level 3 | 补丁扩展（中侵入） | 同上 + `docs/patches/` + `docs/changelog/code_change_summary/` |

详见 [methodology/零侵入扩展方法论.md](./methodology/零侵入扩展方法论.md)。
