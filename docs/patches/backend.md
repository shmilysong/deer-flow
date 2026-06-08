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

### Env Settings 路径拆分 + 渠道配置

- **文件**: `deerflow_extensions/env_settings/router.py`
- **改动**: 
  1. 现有 4 个端点路径从 `/` 改为 `/providers/`
  2. 新增 4 个 `/channels/` 端点（GET/PUT/DELETE/POST verify）
  3. 新增 filelock 保护 `.env` 并发写入
  4. 新增渠道模型和相关辅助函数
- **风险**: ✅ 低（try/except 包裹，扩展不可用时 DeerFlow 正常运行）

**原因**：
- 问题 1：清除 key 后重保存模型不出现 — 增加日志便于排查
- 问题 2：验证连通性时好时坏 — 区分 429 限流与网络错误
- 问题 3：旧代码 `model` 可选导致空 model 也能保存

---

### 2026-06-03: T3 — 角色定义外部化（v6）

### `sitecustomize.py` — 新增角色定义覆盖 patch

**文件**: `deerflow_extensions/sitecustomize.py`
**行号**: L55-L82
**风险**: ✅ 低（try/except 保护，不影响其他扩展；全在扩展目录，零核心侵入）

新增 monkey-patch 块，拦截 `apply_prompt_template` 替换 `<role>` 区块：

```python
try:
    import deerflow.agents.lead_agent.prompt as _prompt_apply
    _orig_apply = _prompt_apply.apply_prompt_template
    import os as _os

    def _patched_apply(*args, **kwargs):
        result = _orig_apply(*args, **kwargs)
        role_path = _os.path.join(
            _os.path.dirname(__file__),
            "topic_guardrail/role_definition.txt"
        )
        if _os.path.isfile(role_path):
            with open(role_path, "r", encoding="utf-8") as f:
                role_content = f.read().strip()
            if role_content:
                role_start = result.find("<role>")
                role_end = result.rfind("</role>")
                if role_start >= 0 and role_end > role_start:
                    result = (
                        result[:role_start]
                        + f"<role>\n{role_content}\n</role>"
                        + result[role_end + len("</role>"):]
                    )
        return result

    _prompt_apply.apply_prompt_template = _patched_apply
except Exception:
    pass
```

**新增文件**:
- `deerflow_extensions/topic_guardrail/role_definition.txt` — 运行时角色定义（部署后直接编辑，重启生效）

**原因**:
- `prompt.py` 编译进 PyInstaller 二进制后无法修改
- 将角色定义移到外部文件，编译后只需改文件 + 重启即可微调回答范围
- 文件不存在时静默使用编译时默认值

**验证命令**:
```bash
# === T3: sitecustomize.py 角色外部化 ===
grep -n "_patched_apply\|role_definition" deerflow_extensions/sitecustomize.py
grep -n "apply_prompt_template\|apply_prompt_template" deerflow_extensions/sitecustomize.py

# === T3a: role_definition.txt ===
ls -la deerflow_extensions/topic_guardrail/role_definition.txt

# === T3b: 单元测试 ===
python -m pytest deerflow_extensions/topic_guardrail/tests/test_role_externalization.py -v

# === T4: deerflow_entry.py TopicGuardrail 注入 ===
grep -n "TopicGuardrail extensions\|_patched_build\|_patched_skills_section\|_patched_apply" backend/deerflow_entry.py

# === T4a: deerflow_entry.py _ext_internal 路径修复 ===
grep -n "_ext_candidates\|_internal_dir" backend/deerflow_entry.py
```

---

## 2026-06-03: T4 — deerflow_entry.py 扩展注入 + 路径修复

### `deerflow_entry.py` — PyInstaller 入口文件

**文件**: `backend/deerflow_entry.py`
**行号**: L20-L34（路径修复）、L164-L226（3 个 patch 块）
**风险**: ✅ 低（try/except 保护，不影响正常启动）

**两处改动**：

#### T4a — `_ext_internal` 路径检测修复（L20-L34）

**原因**：原代码第 21 行硬编码 `os.path.join(_backend_root, "deerflow_extensions")`，只匹配开发模式路径。PyInstaller 打包后 `deerflow_extensions` 在 `_internal/deerflow_extensions/` 下，导致找不到扩展目录。

**改动**：改为多候选路径检测，优先查找 `_internal/deerflow_extensions/`（frozen），fallback 到 `backend/deerflow_extensions/`（dev）：

```python
_ext_candidates = [
    os.path.join(_internal_dir, "deerflow_extensions"),   # frozen
    os.path.join(_backend_root, "deerflow_extensions"),    # dev
]
_ext_internal = None
for _cand in _ext_candidates:
    if os.path.isdir(_cand):
        _ext_internal = os.path.normpath(_cand)
        ...
        break
```

#### T4b — 新增第 11 节：3 个 monkey-patch 块（L164-L226）

**原因**：`sitecustomize.py` 只被标准 CPython 解释器自动加载，**PyInstaller 不会加载它**。因此生产环境（二进制）下 `SensitiveWordMiddleware`、IMMUTABLE CONSTRAINT、角色定义替换 3 个 patch 全部不生效。需要将 patch 逻辑也执行一次在 `deerflow_entry.py`（PyInstaller 入口文件）中。

**改动**：

| 块 | 功能 | 代码 |
|----|------|------|
| 块1 | SensitiveWordMiddleware 注入 | `_patched_build` → 中间件链插入 |
| 块2 | IMMUTABLE CONSTRAINT | `_patched_skills_section` → skill 指令不可覆盖角色 |
| 块3 | 角色定义替换 | `_patched_apply` → 读取 role_definition.txt 替换 `<role>` |

**角色路径**使用 `_ext_internal` 变量（自动适应 frozen/dev）：

```python
role_path = os.path.join(
    os.path.dirname(_ext_internal),
    "topic_guardrail/role_definition.txt"
) if _ext_internal else None
```

**配套扩展文件**（零核心侵入）：
- `deerflow_extensions/sitecustomize.py` — `__file__` → `realpath(__file__)` 修复（作用同上，给 dev 模式用）

**影响**：现在生产部署（PyInstaller 二进制）也能正确加载 3 个 TopicGuardrail patch。

**验证命令**：
```bash
# === T4: deerflow_entry.py TopicGuardrail 注入 ===
grep -n "TopicGuardrail extensions\|_patched_build\|_patched_skills_section\|_patched_apply" backend/deerflow_entry.py

# === T4a: deerflow_entry.py _ext_internal 路径修复 ===
grep -n "_ext_candidates\|_internal_dir" backend/deerflow_entry.py
```

---

## 验证命令

```bash
grep -n "install_env_settings" backend/app/gateway/app.py
grep -n "env_settings" backend/app/gateway/routers/__init__.py || echo "旧文件已删除"
ls deerflow_extensions/env_settings/
```

---

---

## 2026-06-08: filelock 正式依赖声明

### `backend/pyproject.toml` — 追加 filelock 到 dependencies

**文件**: `backend/pyproject.toml`
**风险**: ✅ 零

**改动**：在 `dependencies` 列表追加一行：

```toml
    "filelock>=3.0.0",
```

**原因**: `filelock` 之前是未声明的传递依赖，新环境的 `.venv` 中不存在时导致 `env_settings` 扩展静默加载失败（`ImportError: No module named 'filelock'`）。加入正式依赖后，所有构建路径（`uv sync`、Docker build、PyInstaller）自动包含。

**验证命令**:
```bash
grep "filelock" backend/pyproject.toml
grep "filelock" backend/uv.lock
curl -s http://localhost:8001/openapi.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(sum(1 for k in d['paths'] if 'env-settings' in k), 'env-settings routes')"
# 预期输出: 6 env-settings routes (对应 8 个端点)
```

---

## 2026-06-08: config.yaml 渠道 enabled 自动管理

### `deerflow_extensions/env_settings/router.py` — 新增 `_set_channel_enabled_in_config()`

**风险**: ✅ 零（全在扩展目录，非关键路径）

**改动**:

1. **新增函数** `_set_channel_enabled_in_config(channel_id, enabled)` — 读/写 config.yaml 的 `channels.<id>.enabled` 字段，区块不存在则自动创建
2. **PUT /channels handler** — 在 Test-Before-Switch 之后调用 `_set_channel_enabled_in_config(channel_id, True)`
3. **DELETE /channels/{channel} handler** — 在清除凭据后调用 `_set_channel_enabled_in_config(channel, False)`

**验证命令**:
```bash
# 验证 config.yaml 被自动修改
python3 -c "
import yaml
with open('config.yaml') as f: cfg = yaml.safe_load(f)
print('channels.wecom.enabled:', cfg['channels']['wecom']['enabled'])
"
```

---

## 2026-06-04: T8 — 敏感词检测纵深防御（v7）

### 变更概览
所有改动在 `deerflow_extensions/topic_guardrail/` 扩展目录，**零核心源码侵入**。

### 新增文件
| 文件 | 说明 |
|------|------|
| `text_preprocessor.py` | 输入文本预处理（Unicode归一化、零宽字符清除、拼音检测、全角→半角、单字母间隙压缩） |
| `wordlist/pinyin_variants.txt` | 拼音/英文变体敏感词（AC 自动机第三词源） |
| `tests/test_text_preprocessor.py` | TextPreprocessor 17 个单元测试 |
| `tests/test_sensitive_word_middleware.py` | Fail-closed 14 个单元测试 |
| `tests/test_sensitive_word_bypass.py` | 暴力测试 34 个用例 |
| `tests/run_violent_tests.sh` | API 批量暴力测试脚本 |

### 修改文件
| 文件 | 改动 |
|------|------|
| `sensitive_word_middleware.py` | Fail-closed 加固、引入 TextPreprocessor、审计日志、拼音变体词源加载 |
| `topics.yaml` | 追加 `pinyin_variants`、`semantic_guard`、`audit` 配置块 |
| `role_definition.txt` | 追加 `STRICTLY FORBIDDEN` 禁止事项清单 |
| `wordlist/custom_sensitive_words.txt` | 追加政治人物缺失词条（特朗普、川普等） |

### 核心改动

1. **Fail-Closed**：`_has_sensitive()` 中 `except AttributeError: pass` → `except Exception: logger.exception(); return True`；`_automaton is None` → CRITICAL 日志 + return True
2. **TextPreprocessor**：预处理管道（NFC归一化 → 零宽字符清除 → 全角→半角 → 空格压缩 → 单字母间隙压缩 → lowercase → 拼音检测）
3. **拼音变体词源**：AC 自动机第三词源 `pinyin_variants.txt`
4. **审计日志**：`AUDIT|BLOCKED|reason=...|ts=...`
5. **语义审核**：可选集成（默认关闭，通过 `semantic_guard.enabled` 控制）
6. **L1 硬约束**：`role_definition.txt` 追加 `STRICTLY FORBIDDEN`

### 暴力测试结果
65/65 测试通过，覆盖：
- A 类（直接政治人物名）：7 用例 ✅
- B 类（拼音/英文变体）：7 用例 ✅
- D 类（语义包装）：3 用例 ✅
- E 类（零宽字符绕过）：5 用例 ✅
- F 类（Unicode 归一化）：2 用例 ✅
- G 类（正常输入不应误杀）：7 用例 ✅
- H 类（极端边界）：3 用例 ✅
- Fail-Closed 单元测试：14 用例 ✅
- TextPreprocessor 单元测试：17 用例 ✅

### 验证命令
```bash
# 单元测试
cd backend && PYTHONPATH=.:../deerflow_extensions:packages/harness uv run python3 \
  -m pytest ../deerflow_extensions/topic_guardrail/tests/ -v
# 预期: 65 passed

# 文件存在性
ls -la deerflow_extensions/topic_guardrail/text_preprocessor.py
ls -la deerflow_extensions/topic_guardrail/wordlist/pinyin_variants.txt
grep -c "特朗普" deerflow_extensions/topic_guardrail/wordlist/custom_sensitive_words.txt
grep -c "STRICTLY FORBIDDEN" deerflow_extensions/topic_guardrail/role_definition.txt


---

## 2026-06-04: T9 — PyInstaller 数据文件路径修复

### 问题
PyInstaller `--onedir` 模式下，Python 模块存放于 `_internal/topic_guardrail/`，但 `--add-data ./deerflow_extensions:deerflow_extensions` 将数据文件放到 `_internal/deerflow_extensions/topic_guardrail/`。`__file__` 解析到模块路径，导致 `topics.yaml` 和 `wordlist/*.txt` 找不到 → `FileNotFoundError` → patch 失败。

### 修改文件
| 文件 | 改动 |
|------|------|
| `deerflow_extensions/topic_guardrail/sensitive_word_middleware.py` | `_load_config()` + `_resolve_word_path()` 增加 PyInstaller fallback |
| `backend/scripts/build-backend-on-server.sh` | 新增 2 行 `--add-data` 映射数据到模块路径 |

### 核心改动

1. **方案 A（运行时 fallback）**：`_load_config` 和 `_resolve_word_path` 在原始路径找不到时，自动尝试 `_internal/deerflow_extensions/topic_guardrail/` 路径
2. **方案 B（构建时保障）**：build 脚本增加：
   ```bash
   --add-data ./deerflow_extensions/topic_guardrail/topics.yaml:topic_guardrail/
   --add-data ./deerflow_extensions/topic_guardrail/wordlist:topic_guardrail/wordlist/
   ```

### 验证命令
```bash
# 单元测试
cd backend && PYTHONPATH=.:../deerflow_extensions:packages/harness uv run python3 \
  -m pytest ../deerflow_extensions/topic_guardrail/tests/test_pyinstaller_path_fix.py -v
# 预期: 7 passed

# 编译产物验证
ls dist/deerflow-gateway/_internal/topic_guardrail/topics.yaml
ls dist/deerflow-gateway/_internal/topic_guardrail/wordlist/
```


---

## 2026-06-02: TopicGuardrail v4 — prompt.py 角色身份重定义

> ⚠️ **已废弃**：v6 已将角色定义外部化为 `role_definition.txt`，prompt.py 只保留编译时默认值。
> 2026-06-03 已回退 `prompt.py` 的 `<role>` 到官方版本 `"You are {agent_name}, an open-source super agent."`。
> 详见下方 **T3：角色定义外部化**。

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

## 2026-06-04: T6 — 角色注入架构升级（模板字符串替换 + app.py 注入入口）

### `patch_manager.py` — `_patch_role()` 从函数 monkeypatch 改为模板字符串替换

**文件**: `deerflow_extensions/patch_manager.py`
**行号**: L145-L188
**风险**: ✅ 零（全在扩展目录）

**架构升级**：
| 旧方案 | 新方案 |
|--------|--------|
| monkeypatch `apply_prompt_template` 函数引用 | 替换 `SYSTEM_PROMPT_TEMPLATE` 模块级字符串 |
| 受 `from X import Y` 导入时序影响 | Python `LOAD_GLOBAL` 字节码动态查找，与导入路径无关 |

**原因**: `agent.py:27` 和 `client.py:37` 使用 `from deerflow.agents.lead_agent.prompt import apply_prompt_template` 导入。函数 monkeypatch 在 `from X import Y` 模式下，如果导入发生在 patch 之前，已导入的模块持有旧函数引用。而修改模块级字符串常量后，所有调用者（不论如何导入）通过 `LOAD_GLOBAL` 字节码每次动态查找模板，即时生效。

**改动**：
```python
# 旧方案：替换函数引用
_orig = _prompt.apply_prompt_template
# ... 包装器 ...
_prompt.apply_prompt_template = _patched_apply

# 新方案：替换模块级字符串
_prompt.SYSTEM_PROMPT_TEMPLATE = new_template
```

### `app.py` — 新增 TopicGuardrail 注入块

**文件**: `backend/app/gateway/app.py`
**行号**: L269-L380（在 env_settings 注入之后、AuthMiddleware 之前）
**风险**: ✅ 低（与现有 ads_auth/env_settings/data_collection 注入块完全一致）

```python
    # —— Extension: TopicGuardrail (role + sensitive word + immutable constraint) —
    import sys as _sys4
    _ext_path4 = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), "..", "..", ".."))
    if _ext_path4 not in _sys4.path:
        _sys4.path.insert(0, _ext_path4)
    try:
        from deerflow_extensions.patch_manager import apply_all
        apply_all()
        logger.info("[TopicGuardrail] All patches applied successfully")
    except ImportError:
        logger.warning("[TopicGuardrail] Package not found, topic guardrail is disabled")
    except Exception as _e4:
        logger.warning(f"[TopicGuardrail] Patch apply failed: {_e4}")
```

**原因**: 本地开发模式 `start-deerflow.sh` 使用 `PYTHONPATH=.` 启动，但没有 sitecustomize 符号链接 → CPython 不会自动加载 `sitecustomize.py` → `apply_all()` 从未被调用。`app.py` 已有 data_collection/ads_auth/env_settings 三个注入块，遗漏了 topic_guardrail。

### 连带修复：import 路径统一 + SensitiveWordMiddleware 重复注入守卫

**涉及文件**: `deerflow_extensions/sitecustomize.py` + `backend/deerflow_entry.py`
**风险**: ✅ 低

**问题**: `apply_all()` 的 `_APPLIED` 幂等保护因 `sys.modules` 入口不一致而失效。

| 文件 | 原 import | 问题 |
|------|----------|------|
| `sitecustomize.py` | `from patch_manager import apply_all` | `sys.modules['patch_manager']` |
| `app.py` | `from deerflow_extensions.patch_manager import apply_all` | `sys.modules['deerflow_extensions.patch_manager']` |

Python 将两个路径视为**不同模块对象**，各有独立的 `_APPLIED` 变量。第二次调用时 `_APPLIED` 仍为 `False`，导致 SensitiveWordMiddleware 在中间件链中出现两次 → `AssertionError: Please remove duplicate middleware instances.`

**修复**:
1. **`sitecustomize.py`** — `from patch_manager` → `from deerflow_extensions.patch_manager`（统一模块键名）
2. **`deerflow_entry.py`** — 同上统一 + `sys.path` 改为加入父目录（而非扩展目录自身）
3. **`patch_manager._patch_sensitive_word()`** — 加 `isinstance` 双重守卫：`any(isinstance(m, SensitiveWordMiddleware) for m in middlewares)` — 即使 `_APPLIED` 失效也不会重复注入

**验证命令**:
```bash
# === T6: app.py topic_guardrail 注入 ===
grep -n "TopicGuardrail\|apply_all" backend/app/gateway/app.py

# === T6a: patch_role 模板替换验证 ===
grep -n "SYSTEM_PROMPT_TEMPLATE = new_template" deerflow_extensions/patch_manager.py

# === T6b: 新暴力测试（25个单元测试全部通过） ===
cd backend && PYTHONPATH=.:../deerflow_extensions:packages/harness uv run python3 -m pytest ../deerflow_extensions/topic_guardrail/tests/test_role_injection_fix.py -v

# === T6c: 启动日志验证 ===
grep "TopicGuardrail.*Patches:" logs/gateway.log
grep "SYSTEM_PROMPT_TEMPLATE updated" logs/gateway.log
```

---

## 2026-06-04: T7 — Boot Loader 统一扩展注入 (deerflow_extensions/boot.py)

### `boot.py` — 新增统一 Boot Loader

**文件**: `deerflow_extensions/boot.py` **[NEW]**
**风险**: ✅ 零（全在扩展目录）

**背景**: 4 个扩展（data_collection、ads_auth、env_settings、topic_guardrail）的注入逻辑分散在 `app.py`（50+ 行重复 try/except）和 `deerflow_entry.py`（5 行）中，维护困难、容易遗漏。

**改动**: 新增 `boot.py` 提供两个公开入口：
- `boot_all_extensions(app=None)` — 按序加载全部 4 个扩展，各扩展自身的 `_installed`/`_APPLIED` 保证幂等
- `boot_topic_guardrail_early(ext_internal)` — PyInstaller 专用，在 `import app` 之前注入 topic_guardrail

### `app.py` — 注入逻辑精简

**文件**: `backend/app/gateway/app.py`
**风险**: ✅ 低

**改动**:
- **删除** L45-L58：data_collection 独立注入块（14 行）
- **删除** L337-L380：ads_auth + env_settings + topic_guardrail 独立注入块（43 行）
- **新增** L337-L350：统一调用 `boot_all_extensions(app=app)` ≈ 12 行

净效果：app.py 减少约 45 行重复代码。

**2026-06-04 修复**：Boot Loader 代码块内使用 `sys.path` 但缺少 `import sys`，导致 `NameError: name 'sys' is not defined`。已添加 `import sys as _sys` 并用 `_sys.path` 引用。

### `deerflow_entry.py` — 精简为 boot_topic_guardrail_early

**文件**: `backend/deerflow_entry.py`
**风险**: ✅ 低

**改动**: `from deerflow_extensions.patch_manager import apply_all; apply_all(...)` → `from deerflow_extensions.boot import boot_topic_guardrail_early; boot_topic_guardrail_early(_ext_internal)`

### `entrypoint.sh` — 移除 sitecustomize symlink

**文件**: `deerflow_extensions/entrypoint.sh`
**风险**: ✅ 低

**改动**:
- **删除** L15-L17：`ln -s .../sitecustomize.py` 符号链接
- **新增** L14：`python3 -c ... boot_all_extensions()` 直接调用

### 删除死代码

**文件**: `deerflow_extensions/sitecustomize.py`、`ads_auth/sitecustomize.py`、`data_collection/sitecustomize.py` — **全部删除**
**风险**: ✅ 零（均从未被 Gateway 主进程加载）

### 业况最佳实践

CPython 官方文档明确 `sitecustomize.py` 用于**系统级全站自定义**（如企业环境统一配置），不适合作为项目扩展注入入口。本项目改用统一 Boot Loader 模式，与 Django/Flask 的 `AppConfig.ready()`、Spring Boot 的 `@ComponentScan` 等主流框架的扩展加载机制一致。

**验证命令**:
```bash
# === T7: boot.py 存在 ===
ls -la deerflow_extensions/boot.py

# === T7a: app.py 调用 boot_all_extensions ===
grep -n "boot_all_extensions" backend/app/gateway/app.py

# === T7b: deerflow_entry.py 调用 boot_topic_guardrail_early ===
grep -n "boot_topic_guardrail_early" backend/deerflow_entry.py

# === T7c: sitecustomize 已删除 ===
ls deerflow_extensions/sitecustomize.py 2>&1 | grep "No such file"
ls deerflow_extensions/ads_auth/sitecustomize.py 2>&1 | grep "No such file"  
ls deerflow_extensions/data_collection/sitecustomize.py 2>&1 | grep "No such file"

# === T7d: entrypoint.sh 不再有 sitecustomize symlink ===
grep -n "sitecustomize" deerflow_extensions/entrypoint.sh 2>/dev/null || echo "sitecustomize 已清除"
```
