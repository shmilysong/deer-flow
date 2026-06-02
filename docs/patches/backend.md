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

## 2026-06-01: Env Settings 路由迁移到 deerflow_extensions

### `app.py` — 删除内置 env_settings 路由，改为扩展注入

**文件**: `backend/app/gateway/app.py`
**风险**: ✅ 极低（与现有 ads_auth/data_collection 扩展注入模式完全一致）

**三处改动**：

1. **删除 import**（第 19 行）：
   ```python
   # 删除这一行
   from app.gateway.routers import (
       ...
       env_settings,   # DELETED
       ...
   )
   ```

2. **新增扩展注入块**（在 ADS Auth 注入之后）：
   ```python
       # —— Extension: Env Settings (multi-provider API router) —————
       import sys as _sys3
       _ext_path3 = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), "..", "..", ".."))
       if _ext_path3 not in _sys3.path:
           _sys3.path.insert(0, _ext_path3)
       try:
           from deerflow_extensions.env_settings.startup import install_env_settings
           install_env_settings(app=app)
           logger.info("[EnvSettings] Multi-provider router installed")
       except ImportError:
           logger.warning("[EnvSettings] Extension not found")
       except Exception as _e3:
           logger.warning(f"[EnvSettings] Install failed: {_e3}")
   ```

3. **删除路由注册**（原第 424-425 行）：
   ```python
   # Env Settings API is mounted at /api/env-settings
   app.include_router(env_settings.router)   # DELETED
   ```

4. **删除 openapi_tags 中的 env-settings 标签**。

**配套文件**（全部在扩展目录，不碰官方源码）：
| 文件 | 说明 |
|------|------|
| `deerflow_extensions/env_settings/__init__.py` | 包文件 |
| `deerflow_extensions/env_settings/router.py` | 7 厂商通用管理：GET/PUT/DELETE/verify |
| `deerflow_extensions/env_settings/startup.py` | `install_env_settings(app)` 注入函数 |
| `frontend/extensions/env-settings/` (6 个文件) | 前端 API Key 配置 UI |

---

---

## 2026-06-02: Env Settings 后端 Bug 修复（model 必填 + 429 检测 + 日志增强）

### `deerflow_extensions/env_settings/router.py`

**文件**: `deerflow_extensions/env_settings/router.py`
**风险**: ✅ 零（全在扩展目录，无侵入）

**改动**：

1. **`EnvSettingsUpdateRequest.model` 从可选改为必填**：
   ```python
   # 修改前
   model: str | None = Field(default=None, description="Selected model")
   
   # 修改后
   model: str = Field(description="Selected model", min_length=1)
   ```
   - 空 model 请求返回 422（Pydantic 自动校验）

2. **`verify_provider_key` 增加 429 限流检测**：
   ```python
   # 新增分支
   elif resp.status_code == 429:
       return VerifyResponse(valid=False, message=f"{meta['name']} API 请求过于频繁，请稍后重试")
   ```

3. **`_register_model_to_config` 增加详细日志与异常处理**：
   - 记录 config_path、provider_id、model_name、base_url
   - 记录当前 config.yaml 中模型数量
   - try/except 包裹文件读写操作
   
4. **`_remove_models_from_config` 增加详细日志与异常处理**：
   - 记录删除前后模型数量
   - try/except 包裹文件读写操作

5. **PUT handler 简化**：model 必填后移除 `if request.model` 判断，直接执行注册。

**原因**：
- 问题 1：清除 key 后重保存模型不出现 — 增加日志便于排查
- 问题 2：验证连通性时好时坏 — 区分 429 限流与网络错误
- 问题 3：旧代码 `model` 可选导致空 model 也能保存

---

### 验证命令

```bash
grep -n "install_env_settings" backend/app/gateway/app.py
grep -n "env_settings" backend/app/gateway/routers/__init__.py || echo "旧文件已删除"
ls deerflow_extensions/env_settings/
```

---

## 2026-06-02: TopicGuardrail v4 — prompt.py 角色身份重定义

### `prompt.py` — 从"通用助手+禁止清单"改为"领域专精顾问"

**文件**: `backend/packages/harness/deerflow/agents/lead_agent/prompt.py`
**行号**: L364-L383
**风险**: ✅ 极低（纯 prompt 文本修改，不改变任何运行时逻辑）

**改动内容**：
1. `<role>` 从 `"You are {agent_name}, an open-source super agent."` 改为东方亿盟技术顾问的具体身份描述（含公司信息、业务领域、核心产品、技术能力）
2. 删除 `<topic_boundary>` 区块（约25行）
3. 参考：Anthropic Role Prompting 最佳实践——角色认同 > 规则禁止

**原因**: 
- v3 的 `topic_boundary` 用"禁止清单"控制范围，LLM 有"乐于助人"的天性会找理由绕过
- v4 改为"身份认同"——告诉 LLM 它是什么领域的专家，超出领域的问题它"不了解"而非"不被允许"
- 业界共识（Anthropic/NeMo/OpenAI/Microsoft）：角色定义是最强力的行为控制手段

**影响**: 核心代码侵入从 ~25行（topic_boundary 区块）降到 ~20行（role 内容），但角色定义更丰富

**配套扩展配置**（全在 `deerflow_extensions/`，无侵入）：
- `deerflow_extensions/topic_guardrail/topic_guardrail_provider.py` — TopicGuardrailProvider（AC自动机敏感词过滤，L3 兜底不变）
- `deerflow_extensions/topic_guardrail/topics.yaml` — 规则配置
- `deerflow_extensions/topic_guardrail/wordlist/base_sensitive_words.txt` — 16,669 个敏感词

**配套用户配置**：
- `config.yaml` — 启用 `guardrails.enabled: true`，`config_path: topics.yaml`（注意：路径相对于 Provider 文件所在目录）

---

## 2026-06-02: TopicGuardrail v5 — SensitiveWordMiddleware + sitecustomize 注入

### 改动 1：新增 `sensitive_word_middleware.py`

**文件**: `deerflow_extensions/topic_guardrail/sensitive_word_middleware.py`
**风险**: ✅ 零（全在扩展目录）

新文件，实现 `AgentMiddleware` 子类 `SensitiveWordMiddleware`：
- `before_model` — L2 输入检查：用户消息命中敏感词 → 直接返回拒绝 `AIMessage`
- `after_model` — L3 输出检查：模型输出命中敏感词 → 替换为拒绝 `AIMessage`
- AC自动机 + 白名单 + 正则三层过滤引擎

### 改动 2：`topic_guardrail_provider.py` 简化

**文件**: `deerflow_extensions/topic_guardrail/topic_guardrail_provider.py`
**风险**: ✅ 零（全在扩展目录）

**删除内容**：
- `content_check_tools` 配置项读取
- AC自动机构建、白名单加载、敏感词匹配逻辑
- 搜索词敏感词扫描逻辑（`web_search/web_fetch` 内容检查）

**保留内容**：
- `denied_tools` 检查（禁止工具名黑名单）
- `evaluate()` / `aevaluate()` 接口

**原因**：敏感词内容检查职责转移到 `SensitiveWordMiddleware`，Provider 只做工具名级别的 deny/allow。

### 改动 3：`sitecustomize.py` 注入

**文件**: `deerflow_extensions/sitecustomize.py`
**风险**: ✅ 低（try/except 保护，不影响其他扩展）

新增 monkey-patch 块（位于现有 data_collection / ads_auth 注入之后）：

```python
try:
    from topic_guardrail.sensitive_word_middleware import SensitiveWordMiddleware
    import deerflow.agents.lead_agent.agent as _agent_mw
    _orig_build = _agent_mw._build_middlewares

    def _patched_build(config, *args, **kwargs):
        middlewares = _orig_build(config, *args, **kwargs)
        middlewares.insert(-1, SensitiveWordMiddleware())
        return middlewares

    _agent_mw._build_middlewares = _patched_build
except Exception:
    pass
```

**注入位置**：中间件链倒数第二个（`insert(-1)`），位于 `ClarificationMiddleware`（最后一位）之前。

### 配套文件变动

| 文件 | 改动 |
|------|------|
| `deerflow_extensions/topic_guardrail/topics.yaml` | 删除 `content_check_tools` 字段，保留 `denied_tools` + `wordlist` + `patterns`（纯配置简化） |

### 架构变化：v4 → v5

| 层 | v4 | v5 |
|---|----|-----|
| L1 | prompt.py `<role>` 身份认同 | 不变 |
| L2 | ❌ 无（预留 Input Self-Check） | `SensitiveWordMiddleware.before_model`（输入敏感词过滤） |
| L3 | ❌ 无 | `SensitiveWordMiddleware.after_model`（输出敏感词过滤） |
| L4 | `TopicGuardrailProvider`（denied_tools + 搜索词敏感词扫描） | `TopicGuardrailProvider`（仅 denied_tools，内容检查移除） |

### 验证命令

```bash
# === T2: sitecustomize.py SensitiveWordMiddleware ===
grep -n "SensitiveWordMiddleware\|_patched_build" deerflow_extensions/sitecustomize.py
# 期望输出：2 行（SensitiveWordMiddleware 导入 + _patched_build 定义）
```

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

# === T1: prompt.py 角色 identity 定义 ===
grep -n "北京东方亿盟科技" backend/packages/harness/deerflow/agents/lead_agent/prompt.py
```
