# DeerFlow 核心源码改动补丁记录（模块索引）

> 记录了所有扩展对 DeerFlow 核心源码的侵入性修改。
> 未来从 ByteDance 上游同步代码时，**必须重放以下补丁**。
> 每个补丁标注了文件、行号、改动内容和冲突风险。

---

## 总览

| 扩展 | 改动文件 | 风险 | 数量 |
|------|---------|------|------|
| **data_collection**（蒸馏数据采集） | `app.py` + `docker-compose*.yaml` + `entrypoint.sh` + `sitecustomize.py` | ✅ 低 | 4 个核心 + 1 个扩展 |
| **ads_auth**（ADS 统一认证） | `app.py` + `auth_middleware.py` + `csrf_middleware.py` + `deps.py` + `docker-compose-dev.yaml` + `next.config.js` + `middleware.ts` + `types.ts` + `.env.example` | ✅ 低 | 9 个核心 |
| **settings-dialog-ext**（SettingsDialog 扩展架构 + ADS 账号适配） | `settings-dialog.tsx` + `registry.ts` + `workspace-nav-menu.tsx` + `app.py` + `account-settings-page.tsx` | ✅ 低 | 4 个前端 + 1 个后端 |

两条原则：
1. 所有注入代码都是 `try/except ImportError` 包起来的——即使扩展不可用，DeerFlow 正常运行
2. 扩展目录 `deerflow_extensions/` 和 `frontend/extensions/` 中的文件不算核心改动

---

## 模块索引

| 模块 | 文件 | 包含补丁 | 说明 |
|------|------|---------|------|
| **后端** | [backend.md](backend.md) | D1, A1, A2, A3, A3b, A10 | `app.py`、`auth_middleware.py`、`csrf_middleware.py`、`routers/auth.py`、`deps.py` |
| **前端** | [frontend.md](frontend.md) | A6, A7, A8, S1, S2, S3, S4 | `next.config.js`、`middleware.ts`、`types.ts`、`settings-dialog.tsx`、`registry.ts`、`workspace-nav-menu.tsx`、`account-settings-page.tsx` |
| **Docker** | [docker.md](docker.md) | D2, D3, A4 | `docker-compose-dev.yaml`、`docker-compose.yaml` |
| **脚本** | [scripts.md](scripts.md) | D4, D5, A5 | `entrypoint.sh`、`sitecustomize.py` |
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
```

如果某个 grep 返回空，说明补丁被覆盖了，需要重新打上。
