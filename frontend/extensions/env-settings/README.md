# 环境变量设置

## 说明

提供 AI 模型 API Key 的图形化管理界面，支持 7 家主流 AI 厂商。通过 SettingsDialog 扩展注册为"API Keys"配置页，用户可在设置面板中完成 Key 的配置、验证和管理。

## 目录结构

```
env-settings/
├── api.ts                   # REST API 封装
├── env-settings-page.tsx    # 设置页面 UI 组件
├── extension.ts             # 注册到 SettingsDialog 扩展系统
├── hooks.ts                 # TanStack Query hooks
├── providers.ts             # 7 家 AI 厂商元数据定义
└── types.ts                 # TypeScript 类型定义
```

## 核心文件说明

### types.ts

定义模块所需的所有 TypeScript 类型：

- `ProviderInfo` — 厂商信息（ID、名称、默认地址、默认模型列表、Key 是否存在、掩码 Key、当前地址、当前模型）
- `EnvSettingsResponse` — 后端返回的完整配置数据（`providers` 映射表）
- `EnvSettingsUpdateRequest` — 保存 Key 的请求参数（provider、api_key、base_url、model）
- `EnvSettingsUpdateResponse` / `VerifyResponse` / `DeleteResponse` — 各操作响应

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

- `loadEnvSettings()` — GET `/api/env-settings`，加载完整配置
- `updateEnvSetting(data)` — PUT `/api/env-settings`，保存厂商 API Key
- `deleteEnvSetting(provider)` — DELETE `/api/env-settings/:provider`，清除指定厂商配置
- `verifyProviderKey(provider, apiKey, baseUrl)` — POST `/api/env-settings/:provider/verify`，验证 API Key 连通性

后端路由和数据操作在 `deerflow_extensions/env_settings/router.py` 中实现，前端零侵入。

### hooks.ts

基于 TanStack Query 的数据管理 hooks：

- `useEnvSettings()` — 查询配置数据，返回 `{ settings, isLoading, error }`
- `useUpdateEnvSetting()` — 保存 Key 的 mutation，成功后自动刷新配置列表
- `useDeleteEnvSetting()` — 清除 Key 的 mutation，成功后自动刷新配置列表
- `useVerifyProviderKey()` — 验证 Key 连通性的 mutation

### env-settings-page.tsx

设置面板 UI 组件，包含：

- **服务商选择**：下拉框切换 7 家厂商
- **API Key 输入**：密码输入框，支持显示/隐藏切换、显示当前掩码 Key、输入新 Key 替换
- **连通性验证**：调用 verify API 检查 Key 是否可用
- **模型选择**：预置模型下拉框，支持自定义模型名输入
- **请求地址**：可选的自定义 Base URL，默认使用厂商预设地址
- **清除 Key**：确认弹窗后清除该厂商全部配置
- **状态反馈**：操作成功/失败消息提示

### extension.ts

模块入口，通过 `registerSettingsExtension()` 注册到 SettingsDialog 扩展系统：

```typescript
registerSettingsExtension({
  id: "api",
  label: "API Keys",
  icon: KeyIcon,
  component: EnvSettingsPage,
});
```

## 使用方式

1. 在 DeerFlow 界面中打开设置面板
2. 进入"API Keys"配置页
3. 选择 AI 厂商
4. 输入 API Key（必填）、选择/输入模型（必填）、可选修改请求地址
5. 点击"验证连通性"确认 Key 可用
6. 点击"保存"完成配置

## 依赖

- @tanstack/react-query（状态管理）
- shadcn/ui Button、Input、Select 组件
- lucide-react（图标）
- SettingsDialog 扩展注册系统

## 后端对应

后端 API 路由（Key 读写/验证/模型注册）位于 [deerflow_extensions/env_settings/](../../deerflow_extensions/env_settings/README.md)。
