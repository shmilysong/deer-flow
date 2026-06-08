# DeerFlow 核心源码改动补丁记录（模块索引）

> 记录了所有扩展对 DeerFlow 核心源码的侵入性修改。
> 未来从 ByteDance 上游同步代码时，**必须重放以下补丁**。
> 每个补丁标注了文件、行号、改动内容和冲突风险。

---

## 总览

| 扩展 | 改动文件 | 风险 | 数量 |
|------|---------|------|------|
| **data_collection**（蒸馏数据采集） | `app.py` + `docker-compose*.yaml` + `entrypoint.sh` + `boot.py` | ✅ 低 | 4 个核心 + 1 个扩展 |
| **ads_auth**（ADS 统一认证） | `app.py` + `auth_middleware.py` + `csrf_middleware.py` + `deps.py` + `docker-compose-dev.yaml` + `next.config.js` + `middleware.ts` + `types.ts` + `.env.example` | ✅ 低 | 9 个核心 |
| **settings-dialog-ext**（SettingsDialog 扩展架构 + ADS 账号适配） | `settings-dialog.tsx` + `registry.ts` + `workspace-nav-menu.tsx` + `app.py` + `account-settings-page.tsx` | ✅ 低 | 4 个前端 + 1 个后端 |
| **input-suggestions**（输入建议按钮自定义） | `input-box.tsx`（2 行 import + 渲染改用动态注册）+ `registry.ts` + `config.ts` | ✅ 极低 | **1 个前端核心 + 2 个扩展** |
| topic_guardrail（回答范围限制） | `app.py`（boot_all_extensions）+ `deerflow_entry.py`（boot_topic_guardrail_early）+ `boot.py`（扩展目录）| ✅ 低 | **2 个核心 + 1 个扩展** |
| **Boot Loader**（扩展统一注入） | `app.py`（精简为 1 次调用）+ `deerflow_entry.py`（精简）+ `entrypoint.sh`（移除 sitecustomize） | ✅ 低 | **3 个核心精简** |

两条原则：
1. 所有注入代码都是 `try/except ImportError` 包起来的——即使扩展不可用，DeerFlow 正常运行
2. 扩展目录 `deerflow_extensions/` 和 `frontend/extensions/` 中的文件不算核心改动

---

## 模块索引

| 模块 | 文件 | 包含补丁 | 说明 |
|------|------|---------|------|
| **后端** | [backend.md](backend.md) | D1, A1, A2, A3, A3b, A10, T1, T5, T6, T7 | `app.py`、`auth_middleware.py`、`csrf_middleware.py`、`routers/auth.py`、`deps.py`、`deerflow_entry.py`、`boot.py` |
| **前端** | [frontend.md](frontend.md) | A6, A7, A8, A10, A11, A12, S1, S2, S3, S4, S5, IS1, WS | `next.config.js`、`middleware.ts`、`types.ts`、`server.ts`、`workspace-content.tsx`、`query-client-provider.tsx`、`settings-dialog.tsx`、`registry.ts`、`workspace-nav-menu.tsx`、`account-settings-page.tsx`、`input-box.tsx`、`env-settings/` |
| **Docker** | [docker.md](docker.md) | D2, D3, A4 | `docker-compose-dev.yaml`、`docker-compose.yaml` |
| **脚本** | [scripts.md](scripts.md) | D4 | `entrypoint.sh` |
| **配置** | [config.md](config.md) | A9 | `.env.example` |

---

## 快速验证

同步上游代码后，运行以下命令检查所有补丁是否还在：

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

echo "=== D4a: entrypoint.sh 符号链接 ==="
grep -n "ln -s" deerflow_extensions/entrypoint.sh

echo "=== D4b: entrypoint.sh boot_all_extensions ==="
grep -n "boot_all_extensions" deerflow_extensions/entrypoint.sh

echo "=== D5: boot.py ==="
ls -la deerflow_extensions/boot.py

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

echo "=== A5: boot.py ==="
grep -n "boot_all_extensions" deerflow_extensions/entrypoint.sh

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

# === settings-dialog-ext 补丁 ===
echo "=== S1: settings-dialog.tsx EXTENSION SLOT ==="
grep -c "EXTENSION SLOT" frontend/src/components/workspace/settings/settings-dialog.tsx

echo "=== S2: registry.ts ==="
grep -c "registerSettingsExtension" frontend/src/core/settings-extensions/registry.ts

echo "=== S3a: workspace-nav-menu.tsx getSettingsExtensions ==="
grep -n "getSettingsExtensions" frontend/src/components/workspace/workspace-nav-menu.tsx

echo "=== S3b: workspace-nav-menu.tsx EXTENSION IMPORT ==="
grep -n "EXTENSION IMPORT" frontend/src/components/workspace/workspace-nav-menu.tsx

# === account-settings-page 补丁 ===
echo "=== S4a: account-settings-page email/role 已隐藏 ==="
grep -c "t\.settings\.account\.email\|t\.settings\.account\.role" frontend/src/components/workspace/settings/account-settings-page.tsx

echo "=== S4b: account-settings-page 修改密码已隐藏 ==="
grep -c "修改密码表单被隐藏" frontend/src/components/workspace/settings/account-settings-page.tsx

echo "=== B1: app.py env_settings ==="
grep -n "env_settings" backend/app/gateway/app.py

echo "=== T1: prompt.py 已回退到官方版本（角色定义在 role_definition.txt）===
grep -n "open-source super agent" backend/packages/harness/deerflow/agents/lead_agent/prompt.py

echo "=== T5: patch_manager.py 集中管理 ==="
grep -n "apply_all\|_patch_sensitive_word\|_patch_immutable_constraint\|_patch_role" deerflow_extensions/patch_manager.py | head -5

echo "=== T6: app.py topic_guardrail 注入块 ==="
grep -n "TopicGuardrail\|apply_all" backend/app/gateway/app.py

echo "=== T6a: patch_role 模板替换（不再 monkeypatch 函数）==="
grep -n "SYSTEM_PROMPT_TEMPLATE = new_template" deerflow_extensions/patch_manager.py

echo "=== T5a: boot.py apply_all ==="
grep -n "apply_all" deerflow_extensions/boot.py | head -3

echo "=== T5b: deerflow_entry.py 委托 apply_all ==="
grep -n "TopicGuardrail\|apply_all" backend/deerflow_entry.py

echo "=== T5c: role_definition.txt ==="
ls -la deerflow_extensions/topic_guardrail/role_definition.txt

echo "=== T5d: 启动日志确认 ==="
grep "TopicGuardrail.*Patches:" logs/gateway.log

echo "=== T6d: 新暴力测试（25个单元测试） ==="
cd backend && PYTHONPATH=.:../deerflow_extensions:packages/harness uv run python3 -m pytest ../deerflow_extensions/topic_guardrail/tests/test_role_injection_fix.py -v 2>&1 | tail -5

echo "=== T6e: boot.py 统一入口 ==="
grep -n "boot_one\|_EXTENSIONS" deerflow_extensions/boot.py | head -3

echo "=== T6f: deerflow_entry.py 调用 boot_topic_guardrail_early ==="
grep -n "boot_topic_guardrail_early" backend/deerflow_entry.py

echo "=== T6g: SensitiveWordMiddleware isinstance 守卫 ==="
grep -n "isinstance.*SensitiveWordMiddleware" deerflow_extensions/patch_manager.py

echo "=== IS1: input-box.tsx 扩展 import ==="
grep -n "EXTENSION IMPORT" frontend/src/components/workspace/input-box.tsx

echo "=== A11: workspace-content.tsx MobileSidebarTrigger ==="
grep -n "MobileSidebarTrigger" frontend/src/app/workspace/workspace-content.tsx

echo "=== A12: query-client-provider.tsx 缓存配置 ==="
grep -n "gcTime\|staleTime" frontend/src/components/query-client-provider.tsx

echo "=== S5: workspace-nav-menu.tsx 隐藏菜单 ==="
grep -c "🚫 以下菜单项被隐藏" frontend/src/components/workspace/workspace-nav-menu.tsx

echo "=== T7: boot.py 统一 Boot Loader ==="
ls -la deerflow_extensions/boot.py

echo "=== T7a: app.py 调用 boot_all_extensions ==="
grep -n "boot_all_extensions" backend/app/gateway/app.py

echo "=== T7b: deerflow_entry.py 调用 boot_topic_guardrail_early ==="
grep -n "boot_topic_guardrail_early" backend/deerflow_entry.py

echo "=== T7c: sitecustomize 已全部删除 ==="
ls deerflow_extensions/sitecustomize.py 2>&1 | grep "No such file"
ls deerflow_extensions/ads_auth/sitecustomize.py 2>&1 | grep "No such file"
ls deerflow_extensions/data_collection/sitecustomize.py 2>&1 | grep "No such file"

echo "=== T7d: 启动日志 Boot Loader 注入验证 ==="
grep "\[Boot\] Complete" logs/gateway.log 2>/dev/null || echo "日志未找到（服务尚未启动）"

echo "=== WS13: env_settings /providers 路径拆分 ==="
grep -n "/providers" deerflow_extensions/env_settings/router.py

echo "=== WS14: env_settings /channels 路由组 ==="
grep -n "/channels" deerflow_extensions/env_settings/router.py

echo "=== WS15: filelock 保护 ==="
grep -n "filelock\|_get_env_lock" deerflow_extensions/env_settings/router.py
```

如果某个 grep 返回空，说明补丁被覆盖了，需要重新打上。
