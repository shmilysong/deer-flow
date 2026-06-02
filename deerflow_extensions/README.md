# DeerFlow Extensions 扩展插件目录

## 设计理念

本目录是 DeerFlow 的零侵入扩展插件目录（与 `backend/` 平级），存放独立于 DeerFlow 主干代码的扩展模块。所有插件通过 `try/except ImportError` 包裹的方式注入，扩展不可用时 DeerFlow 仍能正常运行，减少与上游同步时的冲突。

## 模块概览

| 模块 | 说明 | 核心文件 | 前端对应 |
|------|------|---------|---------|
| [ads_auth](./ads_auth/README.md) | ADS 统一认证登录，替换 DeerFlow 原生认证 | router.py, middleware.py, startup.py | [frontend/extensions/ads_auth/](../frontend/extensions/ads_auth/README.md) |
| [data_collection](./data_collection/README.md) | 蒸馏数据采集系统，全链路旁路采集训练数据 | collector.py, middleware.py, scripts/ | 无 |
| [env_settings](./env_settings/README.md) | 多厂商 API Key 管理，Key 写入 .env 并自动注册模型 | router.py, startup.py | [frontend/extensions/env-settings/](../frontend/extensions/env-settings/README.md) |
| [topic_guardrail](./topic_guardrail/README.md) | 回答范围限制，L1-L4 四层纵深防御 | topic_guardrail_provider.py, topics.yaml | 无 |

## 安装方式

所有插件通过 `deerflow_extensions/entrypoint.sh` 和 `deerflow_extensions/sitecustomize.py` 自动注入，无需手动安装。部署时确保：

1. `deerflow_extensions` 目录在 Python `sys.path` 中（Docker 通过 `PYTHONPATH=/app` + volume 挂载）
2. `sitecustomize.py` 在 site-packages 中（Docker 通过 entrypoint.sh 创建符号链接）
