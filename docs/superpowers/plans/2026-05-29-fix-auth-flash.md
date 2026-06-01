# 首屏登录闪屏修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 消除已登录用户访问 DeerFlow 时瞬间闪现登录界面的问题，并修复 ADS JWT 安全验证漏洞

**核心原则（业界最佳实践）:**
1. 认证路由决策必须在中间件/服务器层完成，绝不能先渲染客户端页面再检查认证状态
2. JWT 必须验证 `exp`（过期时间），仅解码 payload 取 username 而不验证签名/过期是安全漏洞
3. Cookie 生命周期必须与 JWT 生命周期对齐，绝不出现「cookie 还在但 token 已过期」的现象
4. 零侵入原则：所有修改要么在扩展目录，要么在已有 ADS 补丁范围内增强

**涉及修改的文件（按影响范围排序）:**

| 文件 | 优先级 | 改动类型 |
|------|--------|---------|
| `frontend/middleware.ts` | P0 🔴 | 核心文件已有 ADS 补丁，增强逻辑 |
| `frontend/extensions/ads_auth/LoginPage.tsx` | P0 🔴 | 扩展目录，自由修改 |
| `deerflow_extensions/ads_auth/router.py` | P0 🔴 | 扩展目录，自由修改 |
| `frontend/src/core/auth/server.ts` | P1 🟡 | 核心文件已有 ADS 补丁，增强逻辑 |
| `frontend/src/core/auth/AuthProvider.tsx` | P2 🟢 | 核心文件，单行修改 |

**不涉及（已确认无需改动）：**
- `backend/app/gateway/routers/auth.py` — logout 已有 `ads_token` 清理，保持不动
- `backend/app/gateway/deps.py` — 原生 JWT 路径，ADS 扩展已短路拦截
- `backend/app/gateway/authz.py` — 不受影响
- `backend/tests/` — 已有暴力测试覆盖

---

## 问题根源

```
主上访问 / → middleware.ts rewrite 到 /ads-login（无条件，不检查 cookie）
  → ADSLoginPage 直接渲染登录表单 ← 闪屏开始
  → useEffect 发 fetch("/api/v1/auth/me") ← 此时才检查
  → 后端返回 200（已认证）→ router.push("/workspace") ← 闪屏结束
```

**根因:** middleware.ts 对 `/` 路径不做任何认证检查，无条件 rewrite 到登录页。

**安全漏洞（附带发现）:** auth_middleware.py 解码 ADS JWT 时只 base64 解析 payload 取 `username`，完全不验证 `exp`（过期时间）和签名。已过期的 ADS JWT 也能通过认证。

---

## 任务分解与实施细节

### Task 1 (P0 🔴): 修复 middleware.ts — 中间件级别认证预检

**涉及文件:**
- `deer-flow/frontend/middleware.ts`（扩展已有 ADS 补丁）

**设计:** 对 `/` 路径检查 `access_token` cookie，有则直接 302 重定向到 `/workspace`，不渲染登录页。遵循 Auth.js、Clerk、Supabase SSR 等主流框架的「认证决策在中间件层完成」原则。

**改动:** 将 `/` 路径的处理逻辑从「无条件 rewrite 到 /ads-login」改为「有 access_token 则 redirect 到 /workspace，无 cookie 才 rewrite 到 /ads-login」

**为什么用 `access_token` 而不是 `ads_token`：**
- 业界最佳实践：统一 cookie 名，避免「前端中间件认 A」、「后端中间件认 B」、「SSR 认 C」的混乱
- `access_token` 是 DeerFlow 原生使用的 cookie 名，所有后端代码、proxy-policy、SSR 都认它
- ADS 登录时同时设置两个 cookie（值相同），改为只认 `access_token` 后 router.py 也相应改为只种 `access_token`
- 旧用户残留的 `ads_token` 由 logout 时的 `delete_cookie("ads_token")` 在下次登出时清除

**风险:** 无。已确认所有层都认 `access_token`，唯一使用 `ads_token` 的中间件和 ADS 扩展改为认 `access_token` 后，SSR 路通天成。

---

### Task 2 (P0 🔴): 修复 LoginPage.tsx — 添加加载转圈

**涉及文件:**
- `deer-flow/frontend/extensions/ads_auth/LoginPage.tsx`（扩展目录）

**设计:** 添加 `isLoading` 状态变量，初始化时全屏居中显示加载转圈 + "验证登录状态..."，确认未认证后才渲染登录表单。

Fix 1 已在中间件层拦截 99% 的已登录用户场景，LoginPage 的 check 只是极端情况下的安全兜底：
- 中间件 cookie 过期但后端 session 有效
- 边缘运行时静默重启
- 用户直接从书签进入 `/ads-login` 路径

**转圈设计（参考业界最佳实践）：**
- **Clerk**：全屏居中简洁 spinner + 品牌色
- **Auth.js**：页面级 loading 覆盖层
- **Google/GitHub**：纯 CSS 旋转动画，无文字
- **Shadcn UI**：`Loader2Icon`（lucide-react）配合 `animate-spin`

采用项目已有组件 `Loader2Icon` + `animate-spin`，全屏居中，文案不遮挡：

```
初始状态: isLoading=true
  → 渲染全屏居中 <Loader2Icon className="size-8 animate-spin" />
fetch("/api/v1/auth/me") 响应:
  - r.ok（已认证）→ router.push(nextPath)，不渲染表单
  - !r.ok（未认证）→ isLoading=false → 渲染表单
catch（网络错误）→ isLoading=false → 渲染表单（用户可重试）
```

**改动详情：**
1. 新增 `useState(true)` 作为 `isLoading`
2. `useEffect` 成功后 `router.push()` 跳转；失败后 `setIsLoading(false)`
3. JSX 最顶层加 `if (isLoading) return <spinner>`
4. spinner 复用项目已有组件：`Loader2Icon` from `lucide-react`（项目中已广泛使用）
5. 零侵入 —— 此文件在 `extensions/ads_auth/` 扩展目录内

---

### Task 3 (P0 🔴): ADS JWT exp 验证 — auth_middleware.py

**涉及文件:**
- `deer-flow/backend/app/gateway/auth_middleware.py`（已有 ADS 补丁范围内增强）

**设计:** 在 `auth_middleware.py` 的 ADS JWT 解码段，解码 payload 后验证 `exp` 字段：

```python
# 当前流程（不安全）：
payload = json.loads(base64_decode(parts[1]))
username = payload.get("username")          # ← 不检查 exp!
if username: → 直接创建 User 放行

# 修复后流程：
payload = json.loads(base64_decode(parts[1]))
username = payload.get("username")
exp = payload.get("exp")                    # ← 新增 exp 检查
if username:
    if exp is not None and time.time() > exp:
        return Response(401)                # token 过期 → 不创建 User
    → 创建 User 放行
```

**原理：** ADS JWT 本身包含 `exp`（过期时间戳）。即使 cookie 被浏览器保留（如用户手动延长 cookie 寿命），中间件层也会拒绝过期的 JWT。

**与 Task 4 的关系：** 两层保障——
- Task 3 (auth_middleware.py)：每次请求都验证 exp，防御所有残留 cookie
- Task 4 (router.py)：登录时动态 max_age，从源头确保 cookie 与 JWT 同时死亡

---

### Task 4 (P0 🔴): cookie 动态与 JWT 对齐 — router.py

**涉及文件:**
- `deer-flow/deerflow_extensions/ads_auth/router.py`（扩展目录）

**设计:** 登录时解码 ADS JWT 的 `exp` 字段，计算剩余秒数，设为 cookie 的 `max_age`：

```python
ads_token = result["ads_token"]
parts = ads_token.split(".")
payload = json.loads(base64_decode(parts[1]))
exp = payload.get("exp")
max_age = max(exp - time.time(), 0) if exp else 1800  # 动态计算，兜底 30 分钟

response.set_cookie(key="access_token", value=ads_token, max_age=max_age, ...)
```

**不再同时设置 `ads_token`：** 统一为只设置 `access_token`。

**效果：** cookie 的生存期 = JWT 的剩余有效期。JWT 过期时 cookie 也被浏览器自动删除，没有残留。

**边界情况：**
- JWT 不包含 `exp` 字段 → 兜底 1800 秒（30 分钟）
- JWT 已经过期（`exp < now`）→ `max_age = 0`，cookie 立即删除，登录失败
- JWT 剩余寿命很长（如 7 天）→ cookie 存活 7 天

---

### Task 5 (P1 🟡): SSR server.ts 统一认 access_token

**涉及文件:**
- `deer-flow/frontend/src/core/auth/server.ts`（已有 ADS 补丁范围内增强）

**设计：** `getServerSideUser()` 已经读 `access_token`（第 26 行），无需修改。

```typescript
// 当前代码 — 已经是统一的 access_token
const sessionCookie = cookieStore.get("access_token");
```

**但是需要确认：** `access_token` cookie 转发到后端的 header 格式是否正确。当前第 69 行在 Cookies header 中只传了 `access_token`，后端 `auth_middleware.py` 收到后，Task 4 改后 `access_token` = ADS JWT，后端在 `request.cookies.get("ads_token")` 会为空，然后 `request.cookies.get("access_token")` 会拿到 ADS JWT，触发 ADS 预检路径 — 走通。

**结论：此文件零改动。** 只需确认 Task 1 和 Task 4 统一使用 `access_token` 后，SSR 路径自然对齐。

---

### Task 6 (P2 🟢): DEER_FLOW_AUTH_DISABLED 改为 NODE_ENV=test 门控

**涉及文件:**
- `deer-flow/frontend/src/core/auth/AuthProvider.tsx`（已有 ADS 补丁范围内增强）

**设计:** 将 E2E 测试后门从独立环境变量 `DEER_FLOW_AUTH_DISABLED=1` 改为 `NODE_ENV=test` 门控：

```typescript
// 当前（不安全 — 环境变量泄露即可绕过所有认证）：
if (process.env.DEER_FLOW_AUTH_DISABLED === "1") {
    return { tag: "authenticated", user: { ... admin ... } };
}

// 修复后（仅测试环境生效）：
if (process.env.NODE_ENV === "test") {
    if (process.env.DEER_FLOW_AUTH_DISABLED === "1") {
        return { tag: "authenticated", user: { ... admin ... } };
    }
}
```

**业界最佳实践（Next.js 官方 + Auth.js）：** E2E 测试后门只应在 `NODE_ENV=test` 下激活。独立环境变量存在生产环境泄漏风险。

**影响范围：** 仅 E2E 测试的部署脚本需要设置 `NODE_ENV=test`。如果 E2E 测试在 `next dev` 下运行，`NODE_ENV` 默认就是 `development`，需要显式设置。

---

## 完整实施顺序

```
Task 3 (router.py: max_age 动态对齐)   → 从源头控制 cookie 寿命
   ↓
Task 4 (auth_middleware.py: exp 验证)  → 后端层防御过期 token
   ↓
Task 1 (middleware.ts: 预检 redirect) → 前端中间件层消灭闪屏根因
   ↓
Task 2 (LoginPage.tsx: 三段式渲染)     → 客户端层安全兜底
   ↓
Task 5 (server.ts: 确认统一)           → SSR 层确认（大概率零改动）
   ↓
Task 6 (AuthProvider.tsx: 后门门控)    → 安全加固
   ↓
验证 (tsc + Python 语法检查)
```

---

## 验证方案

### 验证 1: TypeScript 编译
```bash
cd deer-flow/frontend && npx tsc --noEmit
```
预期：无类型错误

### 验证 2: Python 语法
```bash
cd deer-flow/backend && python -c "import ast; ast.parse(open('deerflow_extensions/ads_auth/router.py').read()); print('OK')"
```
预期：打印 OK

### 验证 3: 人工检查 — 未曾登录的用户首次访问
1. 清除所有 cookie
2. 访问 `http://localhost:2026/`
3. 预期：直接看到 ADS 登录表单，无闪烁/白屏

### 验证 4: 人工检查 — 已登录用户再次进入
1. 正常登录完成
2. 关闭浏览器标签页
3. 重新打开 `http://localhost:2026/`
4. 预期：直接进入工作区，完全看不到登录页

### 验证 5: 人工检查 — ADS JWT 过期后
1. 正常登录完成
2. 等待 ADS JWT 过期（或在浏览器中手动删除部分 cookie 模拟）
3. 刷新页面
4. 预期：重定向到登录页，显示登录表单

---

## 参考业界最佳实践

| 框架 | 做法 | DeerFlow 对照 |
|------|------|--------------|
| **Auth.js (NextAuth v5)** | 中间件直接读 JWT cookie，已认证则立即重定向 | Fix 1 实现 |
| **Clerk** | `clerkMiddleware` 中间件层完成所有路由决策，Auth 页先展示骨架屏 | Fix 2（改良版）实现 |
| **Supabase SSR** | 中间件刷新 session，路由决策在页面渲染前完成 | Fix 1 实现 |
| **Auth0 / Okta** | 每次请求验证 JWT 的 exp + 签名 | Fix 3 + Fix 4 实现 |
| **OWASP JWT Cheatsheet** | Cookie max_age 应与 JWT exp 对齐 | Fix 3 实现 |
| **Next.js 官方指南** | E2E 后门仅 `NODE_ENV=test` 激活 | Fix 6 实现 |
