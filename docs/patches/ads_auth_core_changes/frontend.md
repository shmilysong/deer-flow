# 前端补丁

## A6：`next.config.js` — 路由层重写 `/` 和 `/login` → `/ads-login`

**文件**: `frontend/next.config.js`
**风险**: ✅ 低（`{beforeFiles, afterFiles, fallback}` 为 Next.js 标准 API 格式，不是侵入性改动）

在 `async rewrites()` 中，返回格式从扁平数组改为标准对象格式：

```javascript
return {
  beforeFiles: [
    { source: "/", destination: "/ads-login" },
    { source: "/login", destination: "/ads-login" },
    { source: "/login/:path*", destination: "/ads-login/:path*" },
  ],
  afterFiles: [
    // ... 原有 API proxy rewrites
  ],
  fallback: [],
};
```

**为什么没有更小侵入的方案**:
- `beforeFiles` 是 Next.js 官方路由文档推荐的路径替换方式。扁平数组（`rewrites()` 返回数组）等价于 `afterFiles`，路由优先级低于页面组件，无法覆盖 `/` 和 `/login` 这类已存在的页面路由。
- `redirects()` 返回扁平数组不改格式，但触发 301/302 导致地址栏 URL 变化，用户体验差。
- `{beforeFiles, afterFiles, fallback}` 不是侵入性更改——它是 Next.js 的**完整 API 格式**，扁平数组只是它的简化糖。

---

## A7：`frontend/middleware.ts` — Next.js Middleware 内联（路由保护 + 重写）

**文件**: `frontend/middleware.ts`
**风险**: ✅ 低

之前该文件只有 1 行 re-export：`export { middleware, config } from "./extensions/ads_auth/middleware-handler";`

现在内联为完整 37 行 middleware，包含：

1. **公开路径跳过**: `/_next`、`/favicon.ico`、`/images`、`/ads-login` 直接 `next()`
2. **主页重写**: `/` → rewrite 到 `/ads-login`（与 `next.config.js` beforeFiles 冗余，但不冲突）
3. **登录页重写**: `/login` → rewrite 到 `/ads-login`
4. **Token 守卫**: 无 `ads_token` cookie 时 redirect 到 `/login?next=原路径`

**注意**: `next.config.js` 的 `beforeFiles` 优先级高于 middleware，所以第 2、3 步在实际运行中不会被触发（请求到 `/` 已在路由层被改写）。保留它们是为了**文档对称性和回退安全性**——如果未来去掉了 `beforeFiles`，middleware 仍能兜底。

---

## A8：`frontend/src/core/auth/types.ts` — 登录 URL 路由到 ADS

**文件**: `frontend/src/core/auth/types.ts`
**行号**: L29
**风险**: ✅ 极低

**改动**:
```diff
 export function buildLoginUrl(returnPath: string): string {
-  return `/login?next=${encodeURIComponent(returnPath)}`;
+  return `/ads-login?next=${encodeURIComponent(returnPath)}`;
 }
```

**原因**: `buildLoginUrl` 被客户端代码调用，生成跳转到登录页的 URL。原值 `/login` 会被 `next.config.js` 的 `beforeFiles` rewrite 到 `/ads-login`，但在某些客户端路由场景下，直接输出 `/ads-login` 更可靠（避免客户端 router 绕开 rewrite）。

---

## 验证命令

```bash
# === A6: beforeFiles rewrites ===
grep -n "beforeFiles" frontend/next.config.js

# === A7: middleware ts ads_token ===
grep -n "ads_token\|PUBLIC_PATHS" frontend/middleware.ts

# === A8: types.ts buildLoginUrl ===
grep -n "buildLoginUrl\|ads-login" frontend/src/core/auth/types.ts
```
