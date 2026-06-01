# Fork 同步指南

> 本文档说明如何将上游仓库 `bytedance/deer-flow` 的更新同步到本 Fork 仓库。
>
> 本 Fork 包含大量自定义功能（ADS 认证、数据采集、training_logs、per-user 隔离等），因此不能使用 `rebase` 方式同步。

---

## 目录

- [前置条件](#前置条件)
- [同步方式：为什么用 cherry-pick](#同步方式为什么用-cherry-pick)
- [标准同步流程](#标准同步流程)
- [冲突分类与处理策略](#冲突分类与处理策略)
- [侵入点清单（必须保护的自定义代码）](#侵入点清单必须保护的自定义代码)
- [验证清单](#验证清单)
- [历史同步记录](#历史同步记录)

---

## 前置条件

```bash
# 添加上游仓库（仅首次）
git remote add upstream https://github.com/bytedance/deer-flow.git

# 确保备份分支存在
git branch backup-main        # 查看
git branch backup-main main   # 如不存在则创建
```

---

## 同步方式：为什么用 cherry-pick

| 方式 | 适用场景 | 本 Fork 的选择 |
|------|---------|---------------|
| **rebase** | 本地无自定义提交，纯同步上游 | ❌ 本地有大量自定义提交，rebase 会重放所有本地历史，每次都要重新解决冲突 |
| **cherry-pick** | 保留双方提交历史 | ✅ 只有上游新提交需要逐个 cherry-pick，本地提交不受影响，冲突只出现在双方都改过的文件 |

---

## 标准同步流程

### Step 1: 创建备份

```bash
# 更新备份分支到当前状态
git branch -f backup-main main
```

### Step 2: 获取上游最新代码

```bash
git fetch upstream
```

### Step 3: 找出需要 pick 的提交

```bash
# 从备份分支 HEAD 到上游最新
git log --oneline upstream/main --not backup-main > /tmp/cherry-pick-commits.txt
wc -l /tmp/cherry-pick-commits.txt   # 查看总数
```

### Step 4: 批量 cherry-pick

```bash
# 逐条处理
for hash in $(cut -d' ' -f1 /tmp/cherry-pick-commits.txt); do
    if git cherry-pick "$hash" 2>/dev/null; then
        echo "✅ $hash"
    elif grep -q "空提交\|empty commit" /tmp/cp_result.txt 2>/dev/null; then
        git cherry-pick --skip 2>/dev/null
        echo "⏭️ $hash (空提交)"
    else
        echo "❌ $hash 冲突，手动处理后继续"
        break
    fi
done
```

#### 批量处理技巧

如果提交数量很大（如 274 个），可采用自动化策略：

- **lock 文件冲突**（`uv.lock`、`pnpm-lock.yaml`）：保留本地版本，`git checkout --ours <file>` 
- **文档冲突**（`*.mdx`、`*.md`）：接受上游版本，`sed -i` 清除冲突标记后 git add
- **代码文件冲突**：需要手动审查，保留本地自定义的同时摄入上游变更

参考 `FORK_SYNC_20260601_CONFLICTS.md` 中的自动化脚本模板。

### Step 5: 验证侵入点完整性

```bash
# 检查 11 个侵入点是否完好
grep -c "install_data_collection" backend/app/gateway/app.py
grep -c "install_ads_auth" backend/app/gateway/app.py
grep -c "/login/ads" backend/app/gateway/auth_middleware.py
grep -c "/login/ads" backend/app/gateway/csrf_middleware.py
grep -c "user_from_state" backend/app/gateway/deps.py
grep -c "ads_token" backend/app/gateway/routers/auth.py
grep -c "beforeFiles" frontend/next.config.js
grep -c "PUBLIC_PATHS" frontend/middleware.ts
grep -c "ads-login" frontend/src/core/auth/types.ts
grep -c "deerflow_extensions" docker/docker-compose-dev.yaml
grep -c "training_logs" docker/docker-compose.yaml
```

### Step 6: 修复构建错误

```bash
# 前端构建验证
cd frontend && SKIP_ENV_VALIDATION=1 pnpm build

# 后端语法验证
cd backend && find . -name "*.py" -exec python3 -m py_compile {} \; 2>&1 | grep -v "Permission denied"
```

### Step 7: 运行测试

```bash
cd backend && make test
```

### Step 8: 提交同步结果

```bash
git add -A
git commit -m "Fork sync: N upstream commits + conflict resolutions"
```

---

## 冲突分类与处理策略

同步过程中可能遇到四类冲突：

| 场景 | 描述 | 处理策略 |
|------|------|---------|
| **A 自动合并** | Git 自动解决了冲突 | 无需处理，但需验证结果正确 |
| **B 空提交** | cherry-pick 的变更本地已有 | `git cherry-pick --skip` |
| **C 双方改了相同区域** | 同一文件双方都有修改 | **手动编辑**，保留双方逻辑 |
| **D 逻辑互斥** | 上游和本地的逻辑互斥 | 评估后选择一方，或重构 |

### 场景 C 详细处理流程

1. 找到冲突文件中的 `<<<<<<< HEAD` / `=======` / `>>>>>>>` 标记
2. 理解上游的变更意图和本地的自定义逻辑
3. 手动编辑保留 **双方** 的变更
4. 清除冲突标记
5. `git add <file> && git cherry-pick --continue`

**重要原则**：禁止使用 `--theirs` 或 `checkout --ours` 丢弃任何一方。所有场景 C 冲突都必须手动合并。

### 常见冲突文件及注意事项

| 文件 | 风险等级 | 说明 |
|------|---------|------|
| `backend/app/gateway/app.py` | 🔴 **高** | ADS 认证 + 数据采集注入点 |
| `backend/app/gateway/deps.py` | 🔴 **高** | `get_config` 函数 + `user_from_state` |
| `backend/app/gateway/routers/auth.py` | 🔴 **高** | ADS 登录路由 |
| `frontend/next.config.js` | 🟡 中 | `beforeFiles` 重写规则 |
| `frontend/middleware.ts` | 🟡 中 | PUBLIC_PATHS 白名单 |
| `backend/packages/harness/.../storage.py` | 🟡 中 | per-user 内存隔离 |
| `docker/docker-compose-dev.yaml` | 🟡 中 | 自定义卷挂载 |
| `docker/docker-compose.yaml` | 🟡 中 | 自定义卷挂载 |

---

## 侵入点清单（必须保护的自定义代码）

以下 11 个侵入点是本 Fork 的核心自定义，**任何同步操作都不能冲掉**：

| # | 位置 | 功能 | 保护方式 |
|---|------|------|---------|
| 1 | `backend/app/gateway/app.py:49-62` | 数据采集系统注入 | import + try/except 加载 |
| 2 | `backend/app/gateway/app.py:345-359` | ADS 认证注入 | import + try/except 加载 |
| 3 | `backend/app/gateway/auth_middleware.py` | `/login/ads` 路径放行 | PUBLIC_PATHS 数组 |
| 4 | `backend/app/gateway/csrf_middleware.py` | `/login/ads` CSRF 豁免 | exempt_paths 数组 |
| 5 | `backend/app/gateway/deps.py` | `user_from_state()` 上下文 | 独立函数 |
| 6 | `backend/app/gateway/routers/auth.py` | `ads_token` cookie 清除 | 新增 cookie 删除 |
| 7 | `frontend/next.config.js` | ADS 登录重定向 | `beforeFiles` 块 |
| 8 | `frontend/middleware.ts` | 公开路径白名单 | `PUBLIC_PATHS` 数组 |
| 9 | `frontend/src/core/auth/types.ts` | `ads-login` 构建 URL | buildLoginUrl 函数 |
| 10 | `docker/docker-compose-dev.yaml` | `deerflow_extensions` 挂载 | volumes 配置 |
| 11 | `docker/docker-compose.yaml` | `training_logs` 挂载 | volumes 配置 |

---

## 验证清单

同步完成后按以下顺序验证：

- [ ] 11 个侵入点 grep 检查通过
- [ ] `deerflow_extensions/` 目录完整（与 backup-main 一致）
- [ ] `.env.example` 中 ADS 配置完好
- [ ] 前端 `pnpm build` 通过
- [ ] 后端 Gateway 启动，health 返回 200
- [ ] `make test` 通过率 >= 99%
- [ ] 无未解决的冲突标记残留（`grep -r "<<<<<<<" backend/ frontend/` 为空）

---

## 历史同步记录

| 日期 | 同步范围 | 提交数 | 冲突数 | HEAD | 文档 |
|------|---------|--------|--------|------|------|
| 2026-05-07 | fork 分叉点后 | 128 | 6 | 939aff04 | [`FORK_SYNC_20260507.md`](FORK_SYNC_20260507.md) |
| 2026-06-01 | fork 分叉点后 | 274 | 3 | be7a1685 | [`FORK_SYNC_20260601_CONFLICTS.md`](FORK_SYNC_20260601_CONFLICTS.md) |

---

## 后续维护

### 定期同步频率

建议每 1-2 个月同步一次上游变更，避免累积过多冲突。

### 冲突记录

每次同步后在本目录新建 `<FORK_SYNC_YYYYMMDD.md>` 记录冲突情况，并更新本 README 的同步记录表。

---

**WING**
