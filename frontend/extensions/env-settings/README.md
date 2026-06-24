# 环境变量设置

## 说明

本扩展提供两方面的环境变量配置管理：

**AI 模型 API Key 管理** — 支持 7 家主流 AI 厂商（DeepSeek、Kimi、Doubao、Qwen、MiniMax、GLM、硅基流动）的 API Key 图形化管理。通过 SettingsDialog 扩展注册为"API Keys"配置页，用户可在设置面板中完成 Key 的配置、验证和管理。

**IM 渠道凭据管理** — 支持 4 个国内 IM 渠道（企业微信 WeCom / 飞书 Feishu / 钉钉 DingTalk / 个人微信 WeChat）的可视化凭据配置，通过 SettingsDialog 扩展注册为"渠道配置"标签页。渠道凭据通过上游 `/api/channels/*` 接口管理（`adapters/channel-adapter.ts` 适配层），凭据持久化到 `runtime-config.json`，配置后自动热重启渠道，支持凭据验证、清除等操作。

后端 API 路径：`/api/env-settings/providers/*` 处理厂商配置，渠道配置使用上游 `/api/channels/*`。

## 目录结构

```
env-settings/
├── adapters/                 # 适配层（连接上游 `/api/channels/*` API）
│   └── channel-adapter.ts   # 渠道 API 适配器（Adapter Pattern）
├── api.ts                   # REST API 封装（厂商配置）
├── provider-settings-page.tsx    # 厂商配置 UI 组件
├── channel-settings-page.tsx     # 渠道配置 UI 组件
├── extension.ts             # 注册到 SettingsDialog 扩展系统
├── hooks.ts                 # TanStack Query hooks
├── channels.ts              # @deprecated 渠道元数据（已由适配器替代）
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
- `ChannelInfo` — 渠道信息（ID、名称、运行状态、凭据字典、凭据字段定义）
- `ChannelUpdateInput` — 保存渠道凭据的请求参数（channel、通用 `credentials` 字典）

> 渠道配置类型定义由 `adapters/channel-adapter.ts` 中的 `AdaptedChannelInfo` 驱动，从上游 `ChannelProvider` 类型映射而来。

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

### channels.ts

4 个国内 IM 渠道的元数据定义，前端据此动态渲染凭据表单：

| ID | 名称 | 环境变量前缀 | 凭据字段 |
|----|------|-------------|---------|
| wecom | 企业微信 | WECOM | `bot_id`, `bot_secret` |
| feishu | 飞书 | FEISHU | `app_id`, `app_secret` |
| dingtalk | 钉钉 | DINGTALK | `client_id`, `client_secret` |
| wechat | 微信（个人） | WECHAT | `bot_token` |

```typescript
export interface ChannelMeta {
  id: string;
  name: string;
  envPrefix: string;
  credentialFields: CredentialField[];
}
```

通过 `getChannelMeta(id)` 查找指定渠道的元数据。渠道配置 UI 现在从 `adapters/channel-adapter.ts` 获取凭据字段定义（从上游 `credential_fields` 动态映射），而非 `channels.ts`。

### api.ts

封装与后端的 REST API 通信：

**厂商配置**（路径 `/api/env-settings/providers`）：
- `loadProviderSettings()` — GET `/api/env-settings/providers`，加载厂商配置
- `updateProviderSetting(data)` — PUT `/api/env-settings/providers`，保存厂商 API Key
- `deleteProviderSetting(provider)` — DELETE `/api/env-settings/providers/:provider`，清除指定厂商配置
- `verifyProviderKey(provider, apiKey, baseUrl)` — POST `/api/env-settings/providers/:provider/verify`，验证 API Key 连通性

**渠道配置**（已迁移至上游 `/api/channels/*`，通过 `adapters/channel-adapter.ts` 适配层调用）：
- `listChannels()` — GET `/api/channels/providers` + `/api/channels/connections`，加载渠道配置状态
- `saveChannel(data)` — POST `/api/channels/:provider/runtime-config`，保存渠道凭据
- `deleteChannel(channel)` — DELETE `/api/channels/:provider/runtime-config`，清除渠道配置
- `verifyChannel(channel, credentials?)` — 无独立端点，临时保存后验证再回滚

渠道数据通过 adapter 适配层映射，保持与原有 UI 兼容。上游后端由 `backend/app/gateway/routers/channel_connections.py` 提供。

### hooks.ts

基于 TanStack Query 的数据管理 hooks：

**厂商配置**（queryKey: `["providerSettings"]`）：
- `useProviderSettings()` — 查询厂商配置数据，返回 `{ settings, isLoading, error }`
- `useUpdateProviderSetting()` — 保存 Key 的 mutation，成功后自动刷新配置列表
- `useDeleteProviderSetting()` — 清除 Key 的 mutation，成功后自动刷新配置列表
- `useVerifyProviderKey()` — 验证 Key 连通性的 mutation

**渠道配置**（queryKey: 共享上游 `["channelProviders"]` + `["channelConnections"]`，通过 `adapters/channel-adapter.ts` 调用）：
- `useChannelSettings()` — 查询渠道配置数据，返回 `{ settings, isLoading, error }`
- `useUpdateChannel()` — 保存渠道凭据的 mutation，成功后自动刷新上游缓存
- `useDeleteChannel()` — 清除渠道凭据的 mutation，成功后自动刷新上游缓存
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

- **多渠道选择器**：从 channels.ts 元数据渲染渠道下拉列表，切换后动态显示对应的凭据输入字段
- **动态凭据表单**：根据当前渠道的 `credentialFields` 元数据自动渲染输入框（字段名、标签均由元数据驱动）
- **密码输入**：凭据输入框支持显示/隐藏切换，显示掩码当前值，Secret 类字段绝不回传前端
- **保存**：值不变跳过 + 输入裁剪 + 连通性测试通过后热重启渠道
- **验证连通性**：调用渠道专用连通性测试函数
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
3. 从下拉列表选择要配置的渠道，根据自动显示的凭据字段输入对应凭据
4. 点击"验证连通性"测试凭据可用性
5. 点击"保存"写入配置并自动热重启渠道
6. 配置保存后自动在 config.yaml 中设置 `enabled: true` 并热重启渠道，无需手动修改配置文件

## 依赖

- @tanstack/react-query（状态管理）
- shadcn/ui Button、Input、Select 组件
- lucide-react（图标）
- SettingsDialog 扩展注册系统

## 后端对应

后端 API 路由（Key 读写/验证/模型注册）位于 [deerflow_extensions/env_settings/](../../deerflow_extensions/env_settings/README.md)。
