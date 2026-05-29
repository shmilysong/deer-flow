# 后端补丁

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

## A2c：`auth_middleware.py` — ADS JWT exp 验证（2026-05-29 新增）

**文件**: `backend/app/gateway/auth_middleware.py`
**行号**: L90-L95
**风险**: ✅ 极低

在 ADS JWT 解码段新增 exp 字段提取和过期判断：

```python
exp = payload.get("exp")                    # ← 新增 exp 提取
if username:
    if exp is not None and time.time() > exp:
        pass                                 # token 过期 → fall through 到原生路径
    else:
        # ... 原有的创建 User 代码 ...
```

**原因**: 已过期的 ADS JWT 可通过中间件认证（原代码只取 username，不验证 exp）。

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
response.delete_cookie(key="ads_token", ...)   # ← 保留作为旧 cookie 残留清理
```

**原因**: ADS 登录统一使用 `access_token`（2026-05-29 起不再设置 `ads_token`），但保留此行为以清除旧用户残留的 `ads_token`。

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

---

---

## B1：`app.py` — env_settings 路由注册

**文件**: `backend/app/gateway/app.py`
**风险**: ✅ 极低（与现有路由注册模式完全一致）

### B1a — import env_settings 路由器（L20）

```python
from app.gateway.routers import (
    agents,
    artifacts,
    assistants_compat,
    auth,
    channels,
    env_settings,   # ← ADDED
    feedback,
    mcp,
    memory,
    models,
    runs,
    skills,
    suggestions,
    thread_runs,
    threads,
    uploads,
)
```

**原因**: 导入新创建的 `env_settings` 路由模块。

### B1b — openapi_tags 增加 env-settings 标签（L314-L316）

```python
            {
                "name": "env-settings",
                "description": "Manage environment variable settings and DeepSeek API key verification",
            },
```

**原因**: 在 OpenAPI 文档中为 `env-settings` 路由分组添加标签描述。

### B1c — 注册 env_settings 路由器（L413-L414）

```python
    # Env Settings API is mounted at /api/env-settings
    app.include_router(env_settings.router)
```

**原因**: 注册 `env_settings` 路由模块，挂载点在 `/api/env-settings`，提供环境变量读取/更新/验证接口。

**配套文件**（新创建的核心文件，不计入核心源码改动）：

`backend/app/gateway/routers/env_settings.py`（136 行）— 3 个端点：
| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/env-settings` | 读取环境变量（值已掩码） |
| `PUT` | `/api/env-settings` | 更新 DeepSeek API Key 并写入 `.env` 文件 |
| `POST` | `/api/env-settings/deepseek/verify` | 向 DeepSeek API 发测试请求验证 Key 有效性 |

---

## 验证命令

```bash
# === D1: app.py data_collection 注入 ===
grep -n "install_data_collection" backend/app/gateway/app.py

# === A1: app.py ads_auth 注入 ===
grep -n "install_ads_auth" backend/app/gateway/app.py

# === A2a: auth_middleware /login/ads ===
grep -n "login/ads" backend/app/gateway/auth_middleware.py

# === A2b: auth_middleware ADS decode ===
grep -n "username.*payload\|Example.com\|@example" backend/app/gateway/auth_middleware.py | head -3

# === A3: csrf /login/ads ===
grep -n "login/ads" backend/app/gateway/csrf_middleware.py

# === A3b: routers/auth.py ads_token ===
grep -n "ads_token" backend/app/gateway/routers/auth.py

# === A10: deps.py state.user ===
grep -n "user_from_state\|request.state.user" backend/app/gateway/deps.py

# === B1a: app.py env_settings import ===
grep -n "env_settings" backend/app/gateway/app.py | head -3

# === B1b: app.py env_settings include_router ===
grep -n "env_settings.router" backend/app/gateway/app.py

# === B1c: app.py env-settings openapi tag ===
grep -n "env-settings" backend/app/gateway/app.py
```
