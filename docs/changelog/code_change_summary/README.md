# 代码更改总结 — 模块索引

## 统计

| 项目 | 数量 |
|------|------|
| 修改文件 | 18 |
| 新增文件 | 1（markdown-content.tsx） |
| 删除文件 | 5（safe-citation-content.tsx, inline-citation.tsx, core/citations/* 共 3 个） |
| 总行数变化 | +62 / -894（diff stat） |

| 项目（含 ADS 认证） | 数量 |
|----------------------|------|
| 修改文件（deerflow侧） | 2（app.py / docker-compose-dev.yaml） |
| **deerflow包内修改** | **0** |
| 新增文件 | 18（deerflow_extensions/） |
| 总代码行 | ~1,500行（模块）+ 81个测试用例 |
| 零侵入验证 | ✅ 删除 app.py 5行 + docker-compose 4行即可完全卸载 |

## 模块文件列表

| 文件 | 内容说明 |
|------|----------|
| [backend.md](backend.md) | 后端变更 — CLAUDE.md、lead_agent prompt、artifacts路由、subagent通用助手、data_collection扩展、ads_auth后端模块 |
| [frontend.md](frontend.md) | 前端变更 — 文档与工具（AGENTS.md/CLAUDE.md/README.md/utils.ts）、组件（artifact-file-detail/message-group等）、core（citations删除/i18n locale）、ads_auth前端模块 |
| [docker.md](docker.md) | Docker变更 — docker-compose-dev.yaml（data_collection卷挂载 + ADS环境变量） |
| [scripts.md](scripts.md) | 部署脚本变更 — entrypoint.sh sitecustomize符号链接、sitecustomize.py合并加载器 |
| [skills.md](skills.md) | 技能与Demo变更 — github-deep-research SKILL.md、market-analysis SKILL.md、demo thread数据 |
| [config.md](config.md) | 配置变更 — 环境变量、配置文件相关 |

## 变更范围概述

- **后端**：移除引用系统（citations_format删除、artifacts中citation剥离逻辑移除）、新增data_collection数据采集系统、新增ADS统一认证
- **前端**：移除引用系统（citations core目录删除、SafeCitationContent→MarkdownContent替换、inline-citation删除）、新增ads_auth登录页
- **Docker**：data_collection卷挂载、ADS环境变量注入
- **部署脚本**：sitecustomize符号链接指向合并加载器
- **技能**：引用格式描述调整（from citations to references）
