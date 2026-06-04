# ADS 统一认证集成指南

## 概述

将 ADS（若依系统）作为 DeerFlow 的唯一身份提供者（IdP），替换 DeerFlow 自有的本地认证体系。用户使用 ADS 账号密码登录，ADS JWT 作为唯一的会话令牌，同时自动同步到 ADS-MCP。

## 架构

```
用户输入 ADS 账号密码
    │
    ▼
POST /api/v1/auth/login/ads (DeerFlow 代理)
    │
    ▼
POST /jwt/login (ADS 服务器, form-encoded)
    │
    ├── 成功 → 返回 JWT
    │          ├── 同时设两个 HttpOnly Cookie:
    │          │   ├── ads_token  （ADS 专用，新前端逻辑使用）
    │          │   └── access_token（兼容原有 SSR 认证 server.ts）
    │          ├── 写入 ADS-MCP config.json
    │          └── 返回登录成功
    │
    └── 失败 → 返回 401
```

## 核心设计原则

### 零侵入核心源码

ADS 认证扩展遵循与 `data_collection` 一致的零侵入原则——所有改动仅在扩展目录中，核心源码 0 行改动。

| 扩展 | 核心源码改动 |
|------|------------|
| `data_collection`（蒸馏数据采集） | 5 个文件（注入代码 + Docker + entrypoint） |
| `ads_auth`（ADS 统一认证） | 4 个文件（注入代码 + Docker + 中间件 hook） |

> 详细补丁清单见 `docs/patches/ADS_AUTH_CORE_CHANGES.md`

### Cookie 双写策略（兼容 SSR）

登录时同时设置 `ads_token` 和 `access_token` 两个 cookie：

- `ads_token` — 新前端逻辑（middleware、ADSLoginPage）使用
- `access_token` — 兼容原有 `server.ts` SSR 认证（第 26 行检查 `access_token`）

ADS 中间件接受两个 cookie 名中的任意一个：

```python
# middleware.py 第 49 行
ads_token = request.cookies.get("ads_token") or request.cookies.get("access_token")
```

这样原有 `server.ts`、`fetcher.ts`、`AuthProvider.tsx` 等核心文件完全不需要修改。

### 前端路由透明重写

利用 `next.config.js` 的 `beforeFiles` rewrites，在路由层将 `/` 和 `/login` 透明替换为 `/ads-login` 的渲染内容，地址栏 URL 不变：

```javascript
// next.config.js
beforeFiles: [
  { source: "/", destination: "/ads-login" },
  { source: "/login", destination: "/ads-login" },
  { source: "/login/:path*", destination: "/ads-login/:path*" },
],
```

- `/` → ADS 登录页替换着陆页（用户打开主页直接进入登录）
- `/login` → ADS 登录页替换原有登录页
- 所有客户端 `router.push("/login")`、`router.push("/")`、`window.location.href = "/login"` 都无需修改
- `beforeFiles` 运行在路由层，优先于页面组件和 middleware，无 3xx 重定向

## 部署配置

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ADS_BASE_URL` | `http://ads:8080` | ADS 服务器地址 |
| `ADS_MCP_CONFIG_PATH` | `""` | ADS-MCP config.json 路径 |

### docker-compose-dev.yaml 配置

```yaml
gateway:  # 和 langgraph 服务都需要
  environment:
    - ADS_BASE_URL=${ADS_BASE_URL:-http://ads:8080}
    - ADS_MCP_CONFIG_PATH=${ADS_MCP_CONFIG_PATH:-}
```

## 文件结构

### 后端扩展（`deerflow_extensions/ads_auth/`）

| 文件 | 说明 |
|------|------|
| `config.py` | 从环境变量读取 ADS 服务器地址 |
| `ads_auth.py` | 调 ADS `/jwt/login`，异步 httpx 请求 |
| `middleware.py` | `ADSProxyMiddleware` — 唯一认证关口 |
| `router.py` | `POST /api/v1/auth/login/ads` 端点 |
| `token_manager.py` | token 内存存储 + 写 MCP config.json |
| `startup.py` | 注入逻辑：`app.include_router()`（通过 `boot.py` Boot Loader 统一触发） |

### 统一注入（`deerflow_extensions/boot.py`）

所有扩展通过 Boot Loader 统一注入，由 `app.py` 的 `boot_all_extensions(app=app)` 自动完成。`sitecustomize.py` 机制已移除（CPython 文档明确其用于系统级全站自定义，不适合项目扩展注入）。详见 `@./deerflow_extensions/boot.py`。

### 前端扩展（`frontend/extensions/ads_auth/`）

| 文件 | 说明 |
|------|------|
| `middleware-handler.ts` | Next.js Middleware 认证网关 |
| `LoginPage.tsx` | ADS 登录页（FlickeringGrid 背景，与原有风格一致） |
| `LoginLayout.tsx` | 简版布局 |

### 前端桥接文件

| 文件 | 行数 | 内容 |
|------|------|------|
| `frontend/middleware.ts` | 1 行 | `export { middleware, config } from "./extensions/ads_auth/middleware-handler"` |
| `frontend/src/app/ads-login/page.tsx` | 1 行 | `export { default } from "../../../extensions/ads_auth/LoginPage"` |
| `frontend/src/app/ads-login/layout.tsx` | 1 行 | `export { default } from "../../../extensions/ads_auth/LoginLayout"` |

## 核心改动

`backend/app/gateway/auth_middleware.py` 第 79 行插入 1 行 Extension Hook：

```python
if getattr(request.state, "_ads_authenticated", False):
    return await call_next(request)
```

## 认证流程

### 请求生命周期

```
请求 → ADSProxyMiddleware (扩展目录)
  │
  ├── 公开路径? (health, docs, /login/ads, /logout)
  │     └── 放行
  │
  ├── 原有认证端点? (/login/local, /register, /initialize, /setup-status)
  │     └── 410 Gone
  │
  ├── Cookie "ads_token" 存在?
  │   ├── 是 → 解码 JWT → 设置 request.state.user + _ads_authenticated
  │   │        → 进入 AuthMiddleware (1 行守卫跳过)
  │   │
  │   └── 否 → 401 未认证
  │
  └── AuthMiddleware (核心, 1 行守卫)
        └── _ads_authenticated = True → 直接跳过, 放行到路由
```

### 前端路由拦截

```
浏览器请求 /workspace → Next.js Middleware (middleware.ts)
  │
  ├── 无 ads_token cookie?
  │     └── 307 重定向 → /ads-login?next=/workspace
  │
  ├── 访问 /login?
  │     └── rewrite → /ads-login (原有登录页永不命中)
  │
  └── 有 ads_token → 放行
```

## MCP config.json 同步

登录成功后将以下字段写入 ADS-MCP 的 config.json：

| 字段 | 来源 | 示例 |
|------|------|------|
| `ads.server.url` | `ADS_BASE_URL` 环境变量 | `https://192.168.1.54` |
| `ads.token.value` | ADS `/jwt/login` 返回的 JWT | `eyJ0eXAiOiJKV1Qi...` |
| `ads.token.expires` | `now + 1800` (30 分钟) | `1746001800` |
| `ads.token.loginTime` | `time.time()` | `1746000000` |
| `ads.token.usedBy` | 固定值 `"deerflow"` | `deerflow` |

`ads.credentials` 保留不动。

## 被替换的功能

| 功能 | 状态 | 替代 |
|------|------|------|
| `POST /api/v1/auth/login/local` | ❌ 410 Gone | `POST /api/v1/auth/login/ads` |
| `POST /api/v1/auth/register` | ❌ 410 Gone | ADS 管理用户 |
| `POST /api/v1/auth/initialize` | ❌ 410 Gone | ADS 管理用户 |
| `GET /api/v1/auth/setup-status` | ❌ 410 Gone | ADS 管理用户 |
| `create_access_token()` (DeerFlow JWT) | ❌ 不再使用 | ADS JWT |
| 用户表 CRUD (SQLite/Postgres) | ❌ 不再使用 | ADS 数据库 |
| `setup/page.tsx` | ❌ 永不命中 | ADS 管理用户 |
| `(auth)/login/page.tsx` | ❌ rewrite 绕过 | `ads-login/page.tsx` |

## 测试

### ADS 服务器

| 项目 | 值 |
|------|-----|
| 测试服务器 | `https://192.168.1.54` |
| JWT 端点 | `POST /jwt/login` |
| 请求格式 | `application/x-www-form-urlencoded`，参数 `username` + `password` |
| 成功响应 | `{"code": 0, "msg": "...", "token": "eyJ..."}` |
| 失败响应 | `{"code": 500, "msg": "用户不存在/密码错误!"}` |

### 暴力测试

测试文件: `backend/tests/test_ads_auth_violent.py`

| 测试项 | 说明 |
|--------|------|
| 连续 100 次登录 | 验证无内存泄漏（`tracemalloc` 检测） |
| 并发 50 个请求 | 验证无死锁、并发安全 |
| ADS 服务器不可用 | 验证返回 401 + 友好错误，进程不崩溃 |
| 过期 token | 验证返回 401 |
| 恶意/畸形 token | 验证全部返回 401（SQL 注入、XSS payload 等） |

## 卸载

1. 删除 `auth_middleware.py` 中新增的 1 行守卫
2. 删除 `deerflow_extensions/ads_auth/` 目录
3. 删除 `frontend/extensions/ads_auth/` 目录
4. 删除 `frontend/middleware.ts`（桥接文件）
5. 删除 `frontend/src/app/ads-login/` 目录（桥接文件）
6. 删除 Docker 环境变量 `ADS_BASE_URL`、`ADS_MCP_CONFIG_PATH`
7. 确保 `entrypoint.sh` 中调用 `boot_all_extensions()`（见 `deerflow_extensions/entrypoint.sh`）
8. 重启服务
