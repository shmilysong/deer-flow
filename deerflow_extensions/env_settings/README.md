# 环境变量设置

## 说明

本模块提供多厂商 AI 模型 API Key 的管理功能。用户通过前端配置界面提交 API Key 后，后端将其写入 `.env` 文件，并自动将模型注册到 DeerFlow 的 `config.yaml` 中，使模型可在聊天中使用。

支持 7 家 AI 厂商：DeepSeek、Kimi、Doubao、Qwen、MiniMax、GLM、硅基流动。

## 目录结构

```
env_settings/
├── __init__.py   # 空文件，标识 Python 包
├── router.py     # FastAPI 路由（CRUD + 验证）
└── startup.py    # 注入逻辑
```

## 核心文件说明

### router.py

FastAPI 路由模块，挂载于 `/api/env-settings` 前缀：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/env-settings` | 读取所有厂商的当前配置（Key 已掩码） |
| PUT | `/api/env-settings` | 更新指定厂商的 API Key、Base URL、Model，写入 `.env` 并注册到 `config.yaml` |
| DELETE | `/api/env-settings/{provider}` | 清除指定厂商的 API_KEY、BASE_URL、MODEL，并从 `config.yaml` 移除对应模型 |
| POST | `/api/env-settings/{provider}/verify` | 向该厂商 API 发送测试请求验证 Key 连通性 |

核心逻辑：

- **厂商元数据** — `PROVIDERS` 字典定义 7 家厂商的 ID、名称、环境变量前缀、默认 API 地址、预置模型列表
- **模型注册** — `_register_model_to_config()` 将用户选择的模型追加到 `config.yaml` 的 `models` 列表，使用各厂商对应的 LangChain/LangGraph 类路径
- **模型清理** — `_remove_models_from_config()` 删除该厂商在 `config.yaml` 中注册的所有模型
- **环境变量读写** — 通过 `dotenv_values()` / `set_key()` 操作 `.env` 文件，Key 名格式为 `{PREFIX}_API_KEY`、`{PREFIX}_BASE_URL`、`{PREFIX}_MODEL`
- **连通性验证** — 调用各厂商兼容的 `/models` 端点，根据 HTTP 状态码判断 Key 有效性（200/404 视为有效，401/403/429 视为无效）

### startup.py

注入函数 `install_env_settings()`，通过 `app.include_router(router)` 注册路由。使用 `_installed` 全局变量确保幂等，`try/except` 捕获导入错误保证零侵入。

## 使用方式

1. 在 DeerFlow 设置面板中打开"API Keys"配置页
2. 选择厂商 → 输入 API Key → 选择/输入模型 → 保存
3. 后端自动将 Key 写入 `.env`，模型注册到 `config.yaml`
4. 刷新页面后，新注册的模型即可在聊天中选择使用

## 前端对应

前端配置界面位于 [frontend/extensions/env-settings/](../../frontend/extensions/env-settings/README.md)。

## 依赖

- FastAPI（路由）
- python-dotenv（.env 文件读写）
- PyYAML（config.yaml 读写）
- httpx（API Key 连通性验证）
