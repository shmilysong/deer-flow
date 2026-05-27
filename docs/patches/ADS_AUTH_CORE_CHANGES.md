# DeerFlow 核心源码改动补丁记录

> 记录了所有扩展对 DeerFlow 核心源码的侵入性修改。
> 未来从 ByteDance 上游同步代码时，**必须重放以下补丁**。
> 每个补丁标注了文件、行号、改动内容和冲突风险。

---

## 总览

| 扩展 | 改动文件 | 风险 | 数量 |
|------|---------|------|------|
| **data_collection**（蒸馏数据采集） | `app.py` + `docker-compose*.yaml` + `entrypoint.sh` + `sitecustomize.py` | ✅ 低 | 4 个核心 + 1 个扩展 |
| **ads_auth**（ADS 统一认证） | `app.py` + `auth_middleware.py` + `csrf_middleware.py` + `deps.py` + `docker-compose-dev.yaml` + `next.config.js` + `middleware.ts` + `types.ts` + `.env.example` | ✅ 低 | 9 个核心

两条原则：
1. 所有注入代码都是 `try/except ImportError` 包起来的——即使扩展不可用，DeerFlow 正常运行
2. 扩展目录 `deerflow_extensions/` 和 `frontend/extensions/` 中的文件不算核心改动

---

# data_collection 补丁

## D1：`app.py` — data_collection 注入（模块级）

**文件**: `backend/app/gateway/app.py`
**行号**: L46-L59
**风险**: ✅ 低（与 ADSAuth 注入块相邻，合并视为同一区域）

```python
# Data collection system (zero-injection, monkey-patch based)
import os as _os
import sys as _sys
_ext_path = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), "..", "..", ".."))
if _ext_path not in _sys.path:
    _sys.path.insert(0, _ext_path)
try:
    from deerflow_extensions.data_collection.startup import install_data_collection
    install_data_collection()
    logger.info("[DataCollection] System installed successfully at startup")
except ImportError:
    logger.warning("[DataCollection] Package not found, data collection is disabled")
except Exception as _e:
    logger.warning(f"[DataCollection] Install failed: {_e}")
```

**原因**: Gateway 进程启动时 monkey-patch 安装数据采集中间件。`try/except` 保证扩展不可用时不阻塞启动。

---

## D2：`docker-compose-dev.yaml` — Volume 挂载 + PYTHONPATH

**文件**: `docker/docker-compose-dev.yaml`
**风险**: ✅ 低

### D2a — deerflow_extensions volume（行 134）

```yaml
      - ../deerflow_extensions:/app/deerflow_extensions
```

### D2b — training_logs volume（行 135）

```yaml
      - ../training_logs:/data/deerflow/training_logs
```

### D2c — PYTHONPATH（行 123，内嵌在 command 中）

```bash
# 原 command 中内嵌：
PYTHONPATH=. uv run uvicorn ...
```
改为：
```bash
PYTHONPATH=/app uv run uvicorn ...
```

**原因**: Volume 挂载使扩展目录和采集数据在容器内可用；`PYTHONPATH=/app` 确保 Python 能找到 `deerflow_extensions` 包。

---

## D3：`docker-compose.yaml`（生产环境）— Volume 挂载 + PYTHONPATH

**文件**: `docker/docker-compose.yaml`
**风险**: ✅ 低

### D3a — deerflow_extensions volume（行 83）

```yaml
      - ../deerflow_extensions:/app/deerflow_extensions
```

### D3b — training_logs volume（行 84）

```yaml
      - ../training_logs:/data/deerflow/training_logs
```

### D3c — PYTHONPATH（行 76，内嵌在 command 中）

```bash
command: sh -c "cd backend && PYTHONPATH=. uv run uvicorn ..."
```

**原因**: 生产环境与 dev 环境相同需求。

---

## D4：`entrypoint.sh` — LangGraph 进程注入

**文件**: `deerflow_extensions/entrypoint.sh`
**风险**: ✅ 低

### D4a — deerflow_extensions 包符号链接（行 10-12）

```bash
if [ ! -e /app/backend/.venv/lib/python3.12/site-packages/deerflow_extensions ]; then
    ln -s /app/deerflow_extensions /app/backend/.venv/lib/python3.12/site-packages/deerflow_extensions
fi
```

### D4b — sitecustomize.py 符号链接（行 15-17）

```bash
if [ ! -e /app/backend/.venv/lib/python3.12/site-packages/sitecustomize.py ]; then
    ln -s /app/deerflow_extensions/sitecustomize.py /app/backend/.venv/lib/python3.12/site-packages/sitecustomize.py
fi
```

**原因**: LangGraph Server 进程运行在 `.venv` 中，`PYTHONPATH` 不包含 `/app`。通过符号链接到 `site-packages`，实现 Python 解释器启动时自动加载 `sitecustomize.py`。

---

## D5：`sitecustomize.py` — 运行时自动注入桥接

**文件**: `deerflow_extensions/sitecustomize.py`（扩展目录，但被符号链接到核心 site-packages）
**风险**: ✅ 低

```python
import sys

EXTENSION_PATH = "/app/deerflow_extensions"
if EXTENSION_PATH not in sys.path:
    sys.path.insert(0, EXTENSION_PATH)

DEERFLOW_PATH = "/app/backend/packages/harness"
if DEERFLOW_PATH not in sys.path:
    sys.path.insert(0, DEERFLOW_PATH)

try:
    from deerflow_extensions.data_collection.startup import install_data_collection
    install_data_collection()
except Exception:
    pass

try:
    from deerflow_extensions.ads_auth.startup import install_ads_auth
    install_ads_auth()
except Exception:
    pass
```

**原因**: Python 的 `sitecustomize.py` 机制——解释器启动时自动执行此文件。这是三条注入路径之一（另外两条：`app.py` 模块级注入、`entrypoint.sh` 符号链接）。

---

# ads_auth 补丁

## A1：`app.py` — ADS Auth 扩展注入（路由注册）

**文件**: `backend/app/gateway/app.py`
**行号**: L319-L339
**风险**: ✅ 极低

在 `app = FastAPI(...)` 之后、`AuthMiddleware` 和 `CSRFMiddleware` 之前：

```python
    # —— Extension: ADS Auth (router only, no middleware) ——————————
    # Registers the ADS login router. Does NOT add middleware —
    # auth logic is inlined in AuthMiddleware itself.
    import sys as _sys2
    _ext_path2 = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    if _ext_path2 not in _sys2.path:
        _sys2.path.insert(0, _ext_path2)
    try:
        from deerflow_extensions.ads_auth.startup import install_ads_auth

        install_ads_auth(app=app)
        logger.info("[ADSAuth] System installed successfully at startup")
    except ImportError:
        logger.warning("[ADSAuth] Package not found, ADS auth is disabled")
    except Exception as _e2:
        logger.warning(f"[ADSAuth] Install failed: {_e2}")
```

**为什么不需要关心中间件顺序**: `install_ads_auth()` **只注册路由**（`app.include_router`），不注册任何中间件。路由注册与中间件栈无关，放在 `AuthMiddleware` 之前或之后效果相同。

---

## A2：`auth_middleware.py` — 内联 ADS JWT 解码 + 公开路径

**文件**: `backend/app/gateway/auth_middleware.py`
**风险**: ✅ 极低

### A2a — frozenset 加 1 行（第 37 行）

```python
"/api/v1/auth/login/ads",       # ← ADDED for ADS Auth
```

### A2b — dispatch 加 ~25 行：内联 ADS JWT 解码（第 80-105 行）

在 `_is_public()` 检查之后、`internal_user` 检查之前。直接解码 cookie 中的 JWT payload 提取 username，绕过 DeerFlow 原生 JWT 验证（ADS token 用不同的 secret 签发）：

```python
        # Check for ADS authentication (cookie named "ads_token" or "access_token")
        ads_token = request.cookies.get("ads_token") or request.cookies.get("access_token")
        if ads_token:
            try:
                import base64, json
                parts = ads_token.split(".")
                if len(parts) == 3:
                    padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
                    payload = json.loads(base64.urlsafe_b64decode(padded))
                    username = payload.get("username")
                    if username:
                        import uuid
                        deterministic_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"ads-{username}"))
                        from app.gateway.auth.models import User
                        user = User(
                            id=deterministic_id,
                            email=f"{username}@example.com",
                            system_role="user",
                        )
                        request.state.user = user
                        from deerflow.runtime.user_context import set_current_user
                        set_current_user(user)
                        return await call_next(request)
            except Exception:
                import traceback, logging
                logging.getLogger(__name__).warning("[ADS] dispatch decode failed: %s", traceback.format_exc())
```

**关于用户 ID 的说明**: 
- 使用 `uuid5(NAMESPACE_DNS, "ads-{username}")` 生成**确定性 UUID**，而非系统默认的随机 `uuid4()`。
- 原因：ADS 用户没有持久化的 DB 记录，如果不设确定性 ID，每次请求 User 对象 ID 都不同 → authz 层 thread 所有权校验失败 → 404。
- 确定性 UUID 保证同用户名跨请求产生相同 ID，不同用户名产生不同 ID。

**注意**: 以前的版本使用 `request.state._ads_authenticated` scope 标记配合 ADSProxyMiddleware。该方案因 ASGI 层 cookie 解析冲突被废弃。当前版本直接内联在 AuthMiddleware 中。

**关键区别**:
- 旧方案: ADSProxyMiddleware(ASGI层) → scope → AuthMiddleware(读scope)
- 新方案: AuthMiddleware 直接读 cookie → 解码 JWT → 创建 User 对象

---

## A3：`csrf_middleware.py` — CSRF 豁免路径

**文件**: `backend/app/gateway/csrf_middleware.py`
**行号**: L51 + L176-185
**风险**: ✅ 极低

### A3a — frozenset 加 1 行（第 51 行）

```python
"/api/v1/auth/login/ads",       # ← ADDED for ADS Auth
```

### A3b — 跨源检查条件化（第 176-185 行）

原代码对所有 auth 端点做跨源检查（`Origin` vs `Host`），但 dev 模式下前端在 `:2026`/`:3000`、后端在 `:8001`，不匹配导致 403。改为**仅在 `GATEWAY_CORS_ORIGINS` 被显式配置时才检查**：

```diff
-        if should_check_csrf(request) and _is_auth and not is_allowed_auth_origin(request):
+        if should_check_csrf(request) and _is_auth:
+            configured = _configured_cors_origins()
+            if configured and not is_allowed_auth_origin(request):
                 return JSONResponse(
                     status_code=403,
                     content={"detail": "Cross-site auth request denied."},
                 )
```

这样 dev 模式不用配任何环境变量也能正常登录，生产环境通过 `GATEWAY_CORS_ORIGINS` 白名单仍可防跨源 login CSRF。

---

## A3b：`routers/auth.py` — Logout 同时清除 ads_token

**文件**: `backend/app/gateway/routers/auth.py`
**行号**: L328
**风险**: ✅ 极低

```python
response.delete_cookie(key="access_token", ...)
response.delete_cookie(key="ads_token", ...)   # ← ADDED for ADS Auth
```

**原因**: ADS 登录同时设置 `ads_token` 和 `access_token` 两个 cookie，原 logout 只清 `access_token`，导致用户点退出后 `ads_token` 残留 → middleware 仍放行 → 登出无效。

**验证命令**:
```bash
grep -n "ads_token" backend/app/gateway/routers/auth.py
```

---

## A4：`docker-compose-dev.yaml` — 环境变量

**文件**: `docker/docker-compose-dev.yaml`
**风险**: ✅ 低

```yaml
      - ADS_BASE_URL=${ADS_BASE_URL:-http://ads:8080}
      - ADS_MCP_CONFIG_PATH=${ADS_MCP_CONFIG_PATH:-}
```

---

## A5：`entrypoint.sh` — sitecustomize 符号链接路径

**文件**: `deerflow_extensions/entrypoint.sh`
**风险**: ✅ 低
**注意**: 该文件被 data_collection 和 ads_auth 两个扩展共用。ADS 改动仅为第 16 行符号链接路径（指向合并的 `sitecustomize.py`），已计入 data_collection 计数，不重复计入 ads_auth。

第 16 行，符号链接改为指向合并加载器：

```bash
# 改前:
ln -s /app/deerflow_extensions/data_collection/sitecustomize.py ...

# 改后（合并 data_collection + ads_auth）:
ln -s /app/deerflow_extensions/sitecustomize.py ...
```

---

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

**验证命令**:
```bash
grep -n "beforeFiles" frontend/next.config.js
```

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

**验证命令**:
```bash
grep -n "ads_token\|PUBLIC_PATHS" frontend/middleware.ts
```

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

**验证命令**:
```bash
grep -n "buildLoginUrl\|ads-login" frontend/src/core/auth/types.ts
```

---

## A9：`.env.example` — ADS 配置示例

**文件**: `.env.example`
**行号**: L62-L68
**风险**: ✅ 极低

新增 ADS 统一认证的环境变量示例：

```bash
# ── ADS 统一认证 ──────────────────────────────────────────
# ADS_BASE_URL=http://ads:8080
# ADS_MCP_CONFIG_PATH=/path/to/ads-mcp/config.json
```

**验证命令**:
```bash
grep -n "ADS_BASE_URL\|ADS_MCP" .env.example
```

---

## A10：`deps.py` — `get_current_user_from_request` 先查 `request.state.user`

**文件**: `backend/app/gateway/deps.py`
**行号**: L192-L196
**风险**: ✅ 极低

在函数体顶部插入 5 行守卫：

```python
    # If AuthMiddleware already set request.state.user (e.g. via ADS auth),
    # return it directly instead of re-validating with native JWT secret.
    user_from_state = getattr(request.state, "user", None)
    if user_from_state is not None:
        return user_from_state
```

**原因**: AuthMiddleware 已解码 ADS token 并创建 User 对象存入 `request.state.user`，但 route handler 的 `get_current_user_from_request` 直接读 cookie 用原生 `AUTH_JWT_SECRET` 验证——ADS token 的签发者不同，必返回 `invalid_signature`。此守卫使 route handler 直接使用 AuthMiddleware 已确认的用户。

**验证命令**:
```bash
grep -n "user_from_state\|request.state.user" backend/app/gateway/deps.py
```

---

## 快速验证清单

同步上游代码后，用 grep 检查所有补丁是否还在：

```bash
# === data_collection 补丁 ===
echo "=== D1: app.py data_collection 注入 ==="
grep -n "install_data_collection" backend/app/gateway/app.py

echo "=== D2a: volume deerflow_extensions ==="
grep -n "deerflow_extensions" docker/docker-compose-dev.yaml

echo "=== D2b: volume training_logs ==="
grep -n "training_logs" docker/docker-compose-dev.yaml

echo "=== D2c: PYTHONPATH ==="
grep -n "PYTHONPATH" docker/docker-compose-dev.yaml

echo "=== D3a: volume deerflow_extensions (prod) ==="
grep -n "deerflow_extensions" docker/docker-compose.yaml

echo "=== D3b: volume training_logs (prod) ==="
grep -n "training_logs" docker/docker-compose.yaml

echo "=== D4a/D4b: entrypoint.sh 符号链接 ==="
grep -n "ln -s" deerflow_extensions/entrypoint.sh

echo "=== D5: sitecustomize.py ==="
grep -c "install_data_collection" deerflow_extensions/sitecustomize.py
grep -c "install_ads_auth" deerflow_extensions/sitecustomize.py

# === ads_auth 补丁 ===
echo "=== A1: app.py ads_auth 注入 ==="
grep -n "install_ads_auth" backend/app/gateway/app.py

echo "=== A2a: auth_middleware /login/ads ==="
grep -n "login/ads" backend/app/gateway/auth_middleware.py

echo "=== A2b: auth_middleware ADS decode ==="
grep -n "username.*payload\|Example.com\|@example" backend/app/gateway/auth_middleware.py | head -3

echo "=== A3: csrf /login/ads ==="
grep -n "login/ads" backend/app/gateway/csrf_middleware.py

echo "=== A4: docker-compose ADS_BASE_URL ==="
grep -n "ADS_BASE_URL\|ADS_MCP" docker/docker-compose-dev.yaml

echo "=== A5: entrypoint.sh symlink ==="
grep -n "sitecustomize" deerflow_extensions/entrypoint.sh

echo "=== A6: beforeFiles rewrites ==="
grep -n "beforeFiles" frontend/next.config.js

echo "=== A7: middleware ts ads_token ==="
grep -n "ads_token\|PUBLIC_PATHS" frontend/middleware.ts

echo "=== A8: types.ts buildLoginUrl ==="
grep -n "buildLoginUrl\|ads-login" frontend/src/core/auth/types.ts

echo "=== A9: .env.example ADS ==="
grep -n "ADS_BASE_URL\|ADS_MCP" .env.example

echo "=== A10: deps.py state.user ==="
grep -n "user_from_state\|request.state.user" backend/app/gateway/deps.py
```

如果某个 grep 返回空，说明补丁被覆盖了，需要重新打上。
