# 环境变量设置

## 说明

本模块提供多厂商 AI 模型 API Key 的管理功能，以及多 IM 渠道 Bot 凭据的配置管理。用户通过前端配置界面提交凭据后，后端将其写入 `.env` 文件，并自动联动 `config.yaml`。

- **厂商配置**：管理 7 家 AI 厂商的 API Key（DeepSeek、Kimi、Doubao、Qwen、MiniMax、GLM、硅基流动）
- **渠道配置**：管理 4 个国内 IM 渠道的 Bot 凭据（企业微信、飞书、钉钉、微信）

## 目录结构

```
env_settings/
├── __init__.py   # 空文件，标识 Python 包
├── router.py     # FastAPI 路由（CRUD + 验证 + 连通性测试）
├── startup.py    # 注入逻辑
└── tests/        # 测试文件
```

## 核心文件说明

### router.py

FastAPI 路由模块，挂载于 `/api/env-settings` 前缀：

### 厂商配置 (/api/env-settings/providers)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/env-settings/providers` | 读取所有厂商的当前配置（Key 已掩码） |
| PUT | `/api/env-settings/providers` | 更新指定厂商的 API Key、Base URL、Model，写入 `.env` 并注册到 `config.yaml` |
| DELETE | `/api/env-settings/providers/{provider}` | 清除指定厂商的配置，并从 `config.yaml` 移除对应模型 |
| POST | `/api/env-settings/providers/{provider}/verify` | 向该厂商 API 发送测试请求验证 Key 连通性 |

### 渠道配置 (/api/env-settings/channels)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/env-settings/channels` | 读取渠道配置状态（凭据掩码 + 运行状态） |
| PUT | `/api/env-settings/channels` | 保存渠道凭据（值不变跳过 + 输入裁剪 + Test-Before-Switch 安全重启 + 审计日志） |
| DELETE | `/api/env-settings/channels/{channel}` | 清除渠道凭据（文件锁保护 + 同步热停止 + 内存清理 + 审计日志） |
| POST | `/api/env-settings/channels/{channel}/verify` | 验证渠道连通性（SDK 连接测试 + 审计日志） |

核心逻辑：

- **厂商元数据** — `PROVIDERS` 字典定义 7 家厂商的 ID、名称、环境变量前缀、默认 API 地址、预置模型列表
- **模型注册** — `_register_model_to_config()` 将用户选择的模型追加到 `config.yaml` 的 `models` 列表，使用各厂商对应的 LangChain/LangGraph 类路径
- **模型清理** — `_remove_models_from_config()` 删除该厂商在 `config.yaml` 中注册的所有模型
- **环境变量读写** — 通过 `dotenv_values()` / `set_key()` 操作 `.env` 文件，Key 名格式为 `{PREFIX}_API_KEY`、`{PREFIX}_BASE_URL`、`{PREFIX}_MODEL`
- **连通性验证** — 调用各厂商兼容的 `/models` 端点，根据 HTTP 状态码判断 Key 有效性（200/404 视为有效，401/403/429 视为无效）
- **渠道启用管理** — PUT 渠道凭据时自动设置 `config.yaml` 的 `channels.<id>.enabled: true`，DELETE 时自动设为 `false`，无需手动编辑 config.yaml
- **凭据通用化** — 渠道凭据通过 `_CHANNEL_META` 的 `credential_fields` 元数据驱动，新增渠道仅需添加元数据 + 接入测试函数
- **Test-Before-Switch** — 渠道运行中时，先测试新凭据连通性再重启；测试失败则旧渠道不受影响

### 渠道元数据 (_CHANNEL_META)

`_CHANNEL_META` 字典包含每个渠道的元数据：

| 渠道 ID | 名称 | 环境变量前缀 | 凭据字段 |
|---------|------|-------------|---------|
| `wecom` | 企业微信 | `WECOM` | `bot_id`, `bot_secret` |
| `feishu` | 飞书 | `FEISHU` | `app_id`, `app_secret` |
| `dingtalk` | 钉钉 | `DINGTALK` | `client_id`, `client_secret` |
| `wechat` | 微信(个人) | `WECHAT` | `bot_token` |

每个渠道条目包含 `credential_fields` 列表，定义了需要用户输入的凭据键和标签。前端和后端均根据此元数据动态渲染/处理凭据字段。

### 连通性测试函数

每个渠道有独立的连通性测试函数，通过 `_channel_test_fns` 字典分发：

- **企业微信** (`_test_wecom_connect`) — 使用 `aibot.WSClient` WebSocket 连接，监听 `authenticated`/`error` 事件，10s 超时
- **飞书** (`_test_feishu_connect`) — 使用 `lark_oapi.Client` REST API 验证凭据
- **钉钉** (`_test_dingtalk_connect`) — 调用钉钉开放平台 `gettoken` API 验证凭据
- **微信** (`_test_wechat_connect`) — 格式验证（Token 长度 >= 8），标注"连接性需启动后确认"

### 文件锁

所有 `.env` 写操作使用 `filelock` 保护，防止并发写入导致数据覆盖。锁超时 5 秒。

### startup.py

注入函数 `install_env_settings()`，通过 `app.include_router(router)` 注册路由。使用 `_installed` 全局变量确保幂等，`try/except` 捕获导入错误保证零侵入。

## 使用方式

1. 在 DeerFlow 设置面板中打开"API Keys"或"渠道配置"页
2. 选择厂商/渠道 → 输入凭据 → 保存
3. 后端自动将 Key 写入 `.env`，厂商模型注册到 `config.yaml`，渠道自动启用
4. 刷新页面后，新注册的模型即可在聊天中选择使用

## 前端对应

前端配置界面位于 [frontend/extensions/env-settings/](../../frontend/extensions/env-settings/README.md)。

## 依赖

- FastAPI（路由）
- python-dotenv（.env 文件读写）
- PyYAML（config.yaml 读写）
- httpx（API Key 连通性验证 + 钉钉连通性验证）
- filelock（.env 并发写入保护，声明于 `backend/pyproject.toml`）
