# Extensions 扩展目录

## 设计理念

本目录遵循**零侵入扩展架构**——所有代码独立于 DeerFlow 官方源码，不与上游版本产生冲突。扩展模块通过注册表（Registry）模式或中间件注入方式与核心系统对接，核心源码仅需少量 try/except 包裹的注入点，扩展不可用时 DeerFlow 仍能正常运行。

## 模块概览

| 模块 | 说明 | 核心文件 |
|------|------|----------|
| [ads_auth](./ads_auth/README.md) | ADS 统一认证登录，替换 DeerFlow 原生登录页 | LoginPage.tsx, middleware-handler.ts |
| [env-settings](./env-settings/README.md) | AI 模型 API Key 配置面板 + IM 渠道凭据管理（WeCom Bot） | provider-settings-page.tsx, providers.ts, hooks.ts |
| [input-suggestions](./input-suggestions/README.md) | 输入建议按钮自定义系统，替换内置快捷按钮 | registry.ts, config.ts |
| [mobile-sidebar](./mobile-sidebar/README.md) | 移动端侧栏浮动汉堡触发按钮 | mobile-sidebar-trigger.tsx |

## 各模块详情

### ads_auth — ADS 统一认证

提供基于 ADS (Application Delivery Service) 的统一认证登录页和 Next.js 中间件保护。

- 登录页：`/ads-login` 路由渲染，含动画背景、用户名/密码表单
- 中间件：公共路径放行、首页和 `/login` 路由重写到 ADS 登录页、未登录状态自动跳转
- 通过 `ads_token` Cookie 维护登录会话

详见 [ads_auth/README.md](./ads_auth/README.md)。

---

### env-settings — 环境变量设置

提供 AI 模型 API Key 和 IM 渠道凭据的图形化管理界面，通过 SettingsDialog 扩展注册为两个标签页。

**API Keys 配置**：
- 支持 7 家厂商：DeepSeek、Kimi、Doubao、Qwen、MiniMax、GLM、硅基流动
- 功能：Key 保存、Key 清除、连通性验证、模型选择（预置/自定义）、自定义请求地址
- 路径：`/api/env-settings/providers/*`

**渠道配置**：
- 支持企业微信（WeCom）Bot ID/Secret 配置
- 功能：凭据保存、清除、连通性验证、热重启、运行状态感知、审计日志
- 路径：`/api/env-settings/channels/*`

数据通过 REST API 与后端交互，状态由 TanStack Query 管理。后端路由和数据库操作在 `deerflow_extensions/env_settings/` 中实现，前端零侵入。

详见 [env-settings/README.md](./env-settings/README.md)。

---

### input-suggestions — 输入建议

通过注册表模式实现输入建议按钮的自定义系统，替代内置的"小惊喜/写作/研究"等按钮。

- 注册表 API：`registerInputSuggestion()` / `getInputSuggestions()` / `clearInputSuggestions()`
- 预注册 7 个按钮：产品咨询、技术支持、关联模板（main 组）；运维报告、配置脚本、知识检索、数据分析（create 组）
- 每个按钮含 id、标签、提示词、图标、分组信息

详见 [input-suggestions/README.md](./input-suggestions/README.md)。

---

### mobile-sidebar — 移动端侧栏

在移动端设备上提供一个浮动在左上角的汉堡菜单按钮，点击后打开侧栏。

- 仅在移动端（`isMobile`）且侧栏关闭（`openMobile` 为 false）时显示
- 使用 shadcn/ui Sidebar 的 `toggleSidebar` 控制侧栏开闭
- 毛玻璃效果背景，固定定位

详见 [mobile-sidebar/README.md](./mobile-sidebar/README.md)。
