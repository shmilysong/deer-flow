# 环境变量设置

## 说明

本扩展提供两方面的环境变量配置管理：

**AI 模型 API Key 管理** — 支持 7 家主流 AI 厂商（DeepSeek、Kimi、Doubao、Qwen、MiniMax、GLM、硅基流动）的 API Key 图形化管理。通过 SettingsDialog 扩展注册为"API Keys"配置页，用户可在设置面板中完成 Key 的配置、验证和管理。

**IM 渠道凭据管理** — 支持企业微信（WeCom）Bot ID/Secret 的可视化配置，通过 SettingsDialog 扩展注册为"渠道配置"标签页。配置后自动热重启渠道，支持凭据验证、清除等操作。

后端 API 分路径设计：`/api/env-settings/providers/*` 处理厂商配置，`/api/env-settings/channels/*` 处理渠道配置。

## 目录结构

```
env-settings/
├── api.ts                   # REST API 封装
├── provider-settings-page.tsx    # 厂商配置 UI 组件
├── extension.ts             # 注册到 SettingsDialog 扩展系统
├── hooks.ts                 # TanStack Query hooks
├── providers.ts             # 7 家 AI 厂商元数据定义
└── types.ts                 # TypeScript 类型定义
```

## 核心文件说明

### types.ts

定义模块所需的所有 TypeScript 类型：

- `ProviderInfo` — 厂商信息（ID、名称、默认地址、默认模型列表、Key 是否存在、掩码 Key、当前地址、当前模型）
- `EnvSettingsResponse` — 后端返回的厂商配置数据（`providers` 映射表）
- `EnvSettingsUpdateRequest` — 保存 Key 的请求参数（provider、api_key、base_url、model）
- `EnvSettingsUpdateResponse` / `VerifyResponse` / `DeleteResponse` — 各操作响应
- `ChannelInfo` — 渠道信息（ID、名称、运行状态、凭据状态）
- `ChannelSettingsResponse` — 后端返回的渠道配置数据（`channels` 映射表）
- `ChannelUpdateRequest` — 保存渠道凭据的请求参数（channel、bot_id、bot_secret）

### providers.ts

7 家 AI 厂商的元数据定义：

### providers.ts

7 家 AI 厂商的元数据定义：

| ID | 名称 | 默认 API 地址 |
|----|------|---------------|
| deepseek | DeepSeek | https://api.deepseek.com |
| moonshot | Kimi | https://api.moonshot.cn/v1 |
| volcengine | Doubao | https://ark.cn-beijing.volces.com/api/v3 |
| dashscope | Qwen | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| minimax | MiniMax | https://api.minimax.io/v1 |
| zhipuai | GLM | https://open.bigmodel.cn/api/paas/v4 |
| siliconflow | 硅基流动 | https://api.siliconflow.cn/v1 |

通过 `getProviderMeta(id)` 查找指定厂商元数据。

### api.ts

封装与后端的 REST API 通信：

**厂商配置**（路径 `/api/env-settings/providers`）：
- `loadProviderSettings()` — GET `/api/env-settings/providers`，加载厂商配置
- `updateProviderSetting(data)` — PUT `/api/env-settings/providers`，保存厂商 API Key
- `deleteProviderSetting(provider)` — DELETE `/api/env-settings/providers/:provider`，清除指定厂商配置
- `verifyProviderKey(provider, apiKey, baseUrl)` — POST `/api/env-settings/providers/:provider/verify`，验证 API Key 连通性

**渠道配置**（路径 `/api/env-settings/channels`）：
- `loadChannelSettings()` — GET `/api/env-settings/channels`，加载渠道配置状态
- `updateChannel(data)` — PUT `/api/env-settings/channels`，保存渠道凭据
- `deleteChannel(channel)` — DELETE `/api/env-settings/channels/:channel`，清除渠道配置
- `verifyChannel(channel, botId, botSecret)` — POST `/api/env-settings/channels/:channel/verify`，验证渠道连通性

后端路由和数据操作在 `deerflow_extensions/env_settings/router.py` 中实现，前端零侵入。

### hooks.ts

基于 TanStack Query 的数据管理 hooks：

**厂商配置**（queryKey: `["providerSettings"]`）：
- `useProviderSettings()` — 查询厂商配置数据，返回 `{ settings, isLoading, error }`
- `useUpdateProviderSetting()` — 保存 Key 的 mutation，成功后自动刷新配置列表
- `useDeleteProviderSetting()` — 清除 Key 的 mutation，成功后自动刷新配置列表
- `useVerifyProviderKey()` — 验证 Key 连通性的 mutation

**渠道配置**（queryKey: `["channelSettings"]`）：
- `useChannelSettings()` — 查询渠道配置数据，返回 `{ settings, isLoading, error }`
- `useUpdateChannel()` — 保存渠道凭据的 mutation，成功后自动刷新渠道列表
- `useDeleteChannel()` — 清除渠道凭据的 mutation，成功后自动刷新渠道列表
- `useVerifyChannel()` — 验证渠道连通性的 mutation

### provider-settings-page.tsx — ProviderSettingsPage

API Keys 设置面板 UI 组件，包含：

- **服务商选择**：下拉框切换 7 家厂商
- **API Key 输入**：密码输入框，支持显示/隐藏切换、显示当前掩码 Key、输入新 Key 替换
- **连通性验证**：调用 verify API 检查 Key 是否可用
- **模型选择**：预置模型下拉框，支持自定义模型名输入
- **请求地址**：可选的自定义 Base URL，默认使用厂商预设地址
- **清除 Key**：确认弹窗后清除该厂商全部配置
- **状态反馈**：操作成功/失败消息提示

### channel-settings-page.tsx

渠道配置设置面板 UI 组件，包含：

- **WeCom Bot 配置卡片**：显示渠道名称和运行状态（已启用·运行中 / 已配置·未启用）
- **Bot ID 输入**：密码输入框，支持显示/隐藏切换，显示掩码当前值
- **Bot Secret 输入**：密码输入框（Secret 绝不回传前端）
- **保存**：值不变跳过 + 输入裁剪 + 连通性测试通过后热重启渠道
- **验证连通性**：WebSocket 连接测试
- **清除配置**：确认弹窗后清除凭据 + 同步停止渠道
- **状态反馈**：操作成功/失败消息提示

### extension.ts

模块入口，通过 `registerSettingsExtension()` 注册到 SettingsDialog 扩展系统，注册两个标签页：

```typescript
registerSettingsExtension({ id: "api", label: "API Keys", icon: KeyIcon, component: ProviderSettingsPage });
registerSettingsExtension({ id: "channels", label: "渠道配置", icon: MessageSquareIcon, component: ChannelSettingsPage });
```

## 使用方式

### API Keys 配置
1. 在 DeerFlow 界面中打开设置面板
2. 进入"API Keys"配置页
3. 选择 AI 厂商
4. 输入 API Key（必填）、选择/输入模型（必填）、可选修改请求地址
5. 点击"验证连通性"确认 Key 可用
6. 点击"保存"完成配置

### 渠道配置
1. 在 DeerFlow 界面中打开设置面板
2. 进入"渠道配置"标签页
3. 输入企业微信 Bot ID 和 Bot Secret
4. 点击"验证连通性"测试凭据可用性
5. 点击"保存"写入配置并自动热重启渠道
6. 如需在 config.yaml 中启用渠道，设置 `channels.wecom.enabled: true` 并重启服务

## 依赖

- @tanstack/react-query（状态管理）
- shadcn/ui Button、Input、Select 组件
- lucide-react（图标）
- SettingsDialog 扩展注册系统

## 后端对应

后端 API 路由（Key 读写/验证/模型注册）位于 [deerflow_extensions/env_settings/](../../deerflow_extensions/env_settings/README.md)。
