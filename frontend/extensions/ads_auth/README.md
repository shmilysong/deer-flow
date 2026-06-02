# ADS 统一认证

## 说明

本模块提供基于 ADS (Application Delivery Service) 的统一认证功能，替换 DeerFlow 原生的登录认证系统。用户通过 ADS 用户名/密码登录，认证通过后由 `ads_token` Cookie 维护会话状态。

模块分为两部分：前端登录页面 + Next.js 中间件路由保护。

## 目录结构

```
ads_auth/
├── LoginPage.tsx          # ADS 登录页面组件
├── LoginLayout.tsx        # 登录布局包装
└── middleware-handler.ts  # Next.js 中间件（路由保护 + 重写）
```

## 核心文件说明

### LoginPage.tsx

`/ads-login` 路由渲染的登录页面，包含：

- **加载态检测**：首次加载时通过 `/api/v1/auth/me` 检查是否已登录，若已登录自动跳转到 `next` 参数指定的路径
- **登录表单**：用户名 + 密码输入，提交到 `/api/v1/auth/login/ads`（form-urlencoded 格式）
- **动画背景**：使用 FlickeringGrid 组件配合 deer.svg 遮罩生成闪烁网格动画
- **主题适配**：根据 next-themes 的暗色/亮色模式自动切换网格颜色
- **安全性**：`next` 参数经过 `validateNext()` 校验，防止开放重定向攻击

### LoginLayout.tsx

简单的布局包装组件，透传 children。设计用于扩展或替换登录页的布局结构。

### middleware-handler.ts

Next.js 中间件，在请求到达页面之前进行路由保护：

- **公共路径放行**：`/_next`、`/favicon.ico`、`/images`、`/ads-login` 可直接访问
- **路由重写**：访问 `/` 或 `/login` 时，URL 地址栏不变，但内容渲染为 `/ads-login` 页面
- **未登录跳转**：其他路径若无 `ads_token` Cookie，重定向到 `/login?next=原路径`
- **匹配范围**：排除 `/api`、`/_next/static`、`/_next/image`、`/_next/data` 路径

## 使用方式

部署后自动生效：

1. 用户访问 DeerFlow 首页 `/` → 中间件重写为 `/ads-login` → 显示登录页
2. 用户输入 ADS 账号密码提交 → 后端验证 → 设置 `ads_token` Cookie → 跳转到 workspace
3. 已登录用户直接访问 `/` → `/api/v1/auth/me` 返回 200 → 自动跳转到 workspace
4. 会话过期后访问任意受保护页面 → 重定向到 `/login` → 登录后回到原页面

## 依赖

- Next.js App Router 中间件系统
- next-themes（主题适配）
- shadcn/ui Button、Input 组件
- FlickeringGrid 动画组件

## 后端对应

后端认证逻辑（登录 API、ASGI 中间件、token 管理）位于 [deerflow_extensions/ads_auth/](../../deerflow_extensions/ads_auth/README.md)。
