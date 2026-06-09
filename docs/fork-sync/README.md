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

### Step 6: 修复构建错误 + 合并残留扫描

```bash
# 后端语法检查
cd backend && find . -name "*.py" -not -path "*/__pycache__/*" \
  -exec python3 -m py_compile {} \; 2>&1 | grep -v "Permission denied"

# 对关键文件做引用计数快照（确认本地自定义未丢失）
for f in backend/packages/harness/deerflow/tools/builtins/task_tool.py \
         backend/packages/harness/deerflow/tools/builtins/setup_agent_tool.py \
         backend/packages/harness/deerflow/models/factory.py; do
    echo "$f: app_config=$(grep -c 'app_config' "$f")"
done

# ------ 合并残留扫描 ------
# 扫描重复的函数调用参数（常见合并残留：参数写了两遍）
echo "=== [RESIDUE] 重复位置参数 ==="
grep -rnP "\.(\w+)\(\s*\w+,\s*\w+,\s*\w+,\s*\w+" backend/app/ --include="*.py" \
  | grep -v "__pycache__" | grep -v "test_" || echo "(none)"

echo "=== [RESIDUE] 重复 keyword 参数 ==="
grep -rnP "(\w+)=.*,\s*\1=" backend/app/ --include="*.py" \
  | grep -v "#" | grep -v "__pycache__" || echo "(none)"

echo "=== [RESIDUE] 重复 import ==="
for f in backend/app/gateway/app.py backend/app/gateway/routers/*.py; do
  grep "^from " "$f" 2>/dev/null | cut -d' ' -f2 | sort | uniq -d | xargs -I{} echo "  $f: {}"
done

echo "=== [RESIDUE] 重复函数定义 ==="
for f in backend/app/gateway/*.py backend/app/gateway/routers/*.py; do
  dups=$(grep -oP "^(async )?def \w+" "$f" 2>/dev/null | sort | uniq -d)
  if [ -n "$dups" ]; then echo "  $f: $dups"; fi
done
# ------------------------

# 前端构建验证
cd frontend && SKIP_ENV_VALIDATION=1 pnpm build

# 前端类型检查（对冲突文件）
cd frontend && npx tsc --noEmit --strict src/path/to/conflicted-file.tsx

# 确认 .env 关键变量保持注释（rewrite 代理模式）
grep -n "^NEXT_PUBLIC_BACKEND_BASE_URL" frontend/.env

# 工作区状态确认
git status --short
git diff --stat
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
| `backend/app/gateway/app.py` | 🔴 **高** | Boot Loader 统一注入点（影响全部 4 个扩展） |
| `backend/app/gateway/auth_middleware.py` | 🔴 **高** | ADS JWT 内联解码 + exp 验证 + `uuid5()` 确定性 ID |
| `backend/app/gateway/csrf_middleware.py` | 🔴 **高** | `/login/ads` CSRF 豁免 + 跨源检查条件化 |
| `backend/app/gateway/deps.py` | 🔴 **高** | `user_from_state` 守卫 |
| `backend/app/gateway/routers/auth.py` | 🔴 **高** | ADS 登录路由 + `ads_token` cookie 清除 |
| `backend/deerflow_entry.py` | 🔴 **高** | PyInstaller 入口扩展注入 + frozen/dev 路径修复 |
| `frontend/next.config.js` | 🟡 中 | `beforeFiles` 重写规则（路由格式变更） |
| `frontend/middleware.ts` | 🟡 中 | PUBLIC_PATHS 白名单 + auth guard 内联 |
| `frontend/src/core/auth/server.ts` | 🟢 低 | E2E 后门 NODE_ENV 门控 |
| `frontend/src/components/workspace/settings/settings-dialog.tsx` | 🟡 中 | 4 处 EXTENSION SLOT 插槽 |
| `frontend/src/components/workspace/workspace-nav-menu.tsx` | 🟡 中 | 扩展注册表集成 + 隐藏菜单按钮 |
| `frontend/src/components/workspace/settings/account-settings-page.tsx` | 🟢 低 | ADS 字段隐藏注释 |
| `frontend/src/app/workspace/workspace-content.tsx` | 🟢 低 | MobileSidebarTrigger 注入 |
| `frontend/src/components/workspace/input-box.tsx` | 🟢 低 | input-suggestions 动态注册 import |
| `frontend/src/components/query-client-provider.tsx` | 🟢 低 | TanStack Query 缓存配置 |
| `docker/docker-compose-dev.yaml` | 🟡 中 | 自定义卷挂载 + PYTHONPATH + ADS env |
| `docker/docker-compose.yaml` | 🟡 中 | 自定义卷挂载 |

---

## 侵入点清单（必须保护的自定义代码）

以下 19 个侵入点是本 Fork 的核心自定义，**任何同步操作都不能冲掉**：

| # | 位置 | 功能 | 保护方式 | 风险 |
|---|------|------|---------|------|
| **后端核心文件** |
| 1 | `backend/app/gateway/app.py` | `boot_all_extensions()` 统一注入，运行全部扩展 | 统一调用 + try/except | ✅ 低 |
| 2 | `backend/app/gateway/auth_middleware.py` | `/login/ads` 放行 + ADS JWT 内联解码(~25行) + exp 验证 + `uuid5()` ID | 内联代码 | ✅ 低 |
| 3 | `backend/app/gateway/csrf_middleware.py` | `/login/ads` CSRF 豁免 + 跨源检查条件化 | 内联代码 + frozenset | ✅ 低 |
| 4 | `backend/app/gateway/deps.py` | `user_from_state` 守卫，先查 request.state.user | 函数守卫(5行) | ✅ 低 |
| 5 | `backend/app/gateway/routers/auth.py` | `ads_token` cookie 清除 | cookie 删除行 | ✅ 低 |
| 6 | `backend/deerflow_entry.py` | `boot_topic_guardrail_early()` + frozen/dev 双路径修复 | 统一调用 + try/except | 🔴 高 |
| **前端核心文件** |
| 7 | `frontend/next.config.js` | `beforeFiles` ADS 登录重定向 | beforeFiles 块 | 🟡 中 |
| 8 | `frontend/middleware.ts` | `PUBLIC_PATHS` + auth guard 内联(~37行) | 全文件重写 | 🟡 中 |
| 9 | `frontend/src/core/auth/types.ts` | `buildLoginUrl()` → `/ads-login` | 1 行 URL 修改 | ✅ 低 |
| 10 | `frontend/src/core/auth/server.ts` | E2E 后门 NODE_ENV 门控 | 条件守卫 | ✅ 低 |
| 11 | `frontend/src/components/workspace/settings/settings-dialog.tsx` | 4 处 EXTENSION SLOT（additionalSections + hiddenSectionIds） | 扩展插槽 | 🟡 中 |
| 12 | `frontend/src/components/workspace/workspace-nav-menu.tsx` | `getSettingsExtensions()` + 隐藏菜单按钮(S5) | 注册表 + 注释隐藏 | 🟡 中 |
| 13 | `frontend/src/components/workspace/settings/account-settings-page.tsx` | ADS 字段隐藏(email/role + 修改密码) | 注释隐藏 | ✅ 低 |
| 14 | `frontend/src/app/workspace/workspace-content.tsx` | MobileSidebarTrigger 注入(2行) | JSX 行追加 | ✅ 低 |
| 15 | `frontend/src/components/workspace/input-box.tsx` | input-suggestions 动态注册 import | import 行 + 动态渲染 | ✅ 低 |
| 16 | `frontend/src/components/query-client-provider.tsx` | TanStack Query 缓存配置(gcTime/staleTime) | 配置对象 | ✅ 低 |
| **Docker 文件** |
| 17 | `docker/docker-compose-dev.yaml` | `deerflow_extensions` 和 `training_logs` 挂载 + PYTHONPATH + ADS env | volumes 配置 | ✅ 低 |
| 18 | `docker/docker-compose.yaml` | `deerflow_extensions` 和 `training_logs` 挂载 | volumes 配置 | ✅ 低 |
| **配置文件** |
| 19 | `.env.example` | ADS_BASE_URL + ADS_MCP_CONFIG_PATH 配置示例 | 行追加 | ✅ 极低 |

---

## 验证清单

同步完成后按以下顺序验证：

- [ ] 19 个侵入点 grep 检查通过（详见 `docs/patches/` 中各模块的验证命令）
- [ ] `deerflow_extensions/` + `frontend/extensions/` 目录完整（与 backup-main 一致）
- [ ] 后端全量 `.py` 语法检查通过（`python3 -m py_compile`）
- [ ] 关键文件的本地自定义引用计数正常（`app_config`、`user_id` 等）
- [ ] 前端核心区域扩展插槽、注释隐藏未被覆写（`EXTENSION SLOT`、`EXTENSION IMPORT`、`🚫 以下菜单项` 等标记存在）
- [ ] 合并残留扫描：无重复位置参数/keyword/import/函数定义
- [ ] 无未解决的冲突标记残留（`grep -r "<<<<<<<" backend/ frontend/` 为空）
- [ ] `.env` 中 `NEXT_PUBLIC_BACKEND_BASE_URL` 保持注释状态
- [ ] 前端 `pnpm build` 通过
- [ ] 后端 Gateway 启动，health 返回 200
- [ ] API 冒烟测试：`/api/mcp/config`、`/api/skills`、`/api/memory` 返回 JSON（非 HTML）
- [ ] `make test` 通过率 >= 99%
- [ ] 工作区干净（`git status --short` 无意外修改）

---

## 历史同步记录

| 日期 | 同步范围 | 提交数 | 冲突数 | HEAD | 变更摘要 | 文档 |
|------|---------|--------|--------|------|---------|------|
| 2026-05-07 | fork 分叉点后 | 128 | 6 | 939aff04 | 上游大版本重构：Gateway 嵌入 LangGraph 运行时、认证系统重构（auth_middleware/CSRF）、Docker 大幅改造（docker.sh/nginx/compose）、Makefile 重构、DingTalk/Serper 等新集成 | [`FORK_SYNC_20260507.md`](FORK_SYNC_20260507.md) |
| 2026-06-01 | fork 分叉点后 | 274 | 3 | be7a1685 | 上游大量稳定性修复：persistence SQL 化 + run history 持久化 + event store 重构、per-user 隔离完善、DingTalk/Feishu 频道增强、静态 system prompt 优化、run 恢复机制、subagent token 用量追踪、BlockingIO 防护 | [`FORK_SYNC_20260601_CONFLICTS.md`](FORK_SYNC_20260601_CONFLICTS.md) |

---

## 经验教训

以下记录前两次同步中遇到的问题及其预防措施，供后续同步参考。

### 教训 1：冲突解决后必须做语法/类型检查

**问题**：冲突标记清除后，`skills_config.py` 仍存在重复 `description` 和缩进错误未被发现就提交了，导致后端无法启动。

**根因**：场景 C 冲突（双方改了相同区域）手动编辑后，开发者只确认了"冲突标记已清除"和"逻辑看起来对"，没有运行语法/静态检查。

**预防**：在 Step 6 的验证中加入：

```bash
# Python 语法检查（所有 .py 文件）
cd backend && find . -name "*.py" -not -path "*/__pycache__/*" \
  -exec python3 -m py_compile {} \; 2>&1 | grep -v "Permission denied"

# 前端类型检查（至少对冲突文件）
cd frontend && npx tsc --noEmit --strict src/path/to/conflicted-file.tsx
```

### 教训 2：绝对禁止用 `git checkout` 解决冲突

**问题**：为了修复语法错误，执行了 `git checkout upstream/main -- backend/packages/harness/deerflow/`，导致 `task_tool.py` 中 6 处 `app_config` 引用被上游版本覆盖（29 → 23）。工作区被"污染"后差点将本地自定义丢失。

**根因**：`git checkout <branch> -- <file>` 是**完全替换**，等价于 `--theirs`。这和场景 C 的"手动合并保留双方"原则完全矛盾。

**预防**：牢记一条铁律：

> **冲突解决只能用编辑器手动合并，禁止使用 `git checkout <branch> -- <file>` 或 `git checkout --ours/theirs` 替代。**

如果必须恢复特定文件，使用 `git checkout HEAD -- <file>`（恢复成本地版本）或 `git checkout upstream/main -- <file>`（丢弃本地改用上游），但必须理解这是"放弃一方"，事后要用回归验证确认。

验证完整性：

```bash
# 对关键文件做引用计数快照，与 backup-main 对比
for f in backend/packages/harness/deerflow/tools/builtins/task_tool.py \
         backend/packages/harness/deerflow/tools/builtins/setup_agent_tool.py \
         backend/packages/harness/deerflow/models/factory.py; do
    echo "$f: app_config=$(grep -c 'app_config' "$f")"
done
```

### 教训 3：`.env` 文件不可随意修改

**问题**：往 `.env` 加了 `NEXT_PUBLIC_BACKEND_BASE_URL=http://localhost:8001`，但 `next.config.js` 的 API rewrite 规则在检测到这个变量后**全部跳过**，导致前端 `/api/*` 请求直接发到后端端口（跨端口 Cookie 丢失）而非通过 Next.js 代理，返回 404。

**根因**：`.env` 是 gitignored 文件，容易在调试时被随意修改。`NEXT_PUBLIC_*` 变量控制了 `next.config.js` 的关键行为。

**预防**：

```bash
# 确认关键变量保持注释状态（rewrite 代理模式）
grep -n "^NEXT_PUBLIC_BACKEND_BASE_URL" frontend/.env
# 应该输出一行注释，如：# NEXT_PUBLIC_BACKEND_BASE_URL="http://localhost:8001"

# 与 .env.example 对比差异（忽略注释）
diff <(grep -v '^#' frontend/.env.example | grep -v '^$') \
     <(grep -v '^#' frontend/.env | grep -v '^$')
```

#### `.env` 关键变量速查表

| 变量 | 作用 | 同步后应保持的状态 |
|------|------|------------------|
| `NEXT_PUBLIC_BACKEND_BASE_URL` | 控制 Next.js API rewrite | **注释掉**，让 rewrite 生效 |
| `NEXT_PUBLIC_LANGGRAPH_BASE_URL` | LangGraph 路由模式 | **注释掉**或用兼容模式 |
| `DEER_FLOW_INTERNAL_GATEWAY_BASE_URL` | SSR 内部访问 Gateway 地址 | 不设置（默认 `http://127.0.0.1:8001`，与 uvicorn 端口一致） |

### 教训 4：前端文件冲突后需做去重审查

**问题**：多个前端文件（`message-list.tsx`、`settings-dialog.tsx`、`page.tsx` 等）在冲突解决后出现重复 import、重复 JSX props、重复标签嵌套等问题，导致 `pnpm build` 失败。

**根因**：场景 C 冲突中双方在同一函数块各自添加了不同代码，合并后出现了：上游加了 `import`、本地也加了同名 `import`；上游改了 `output:`、本地也改了——两行同时保留。开发者手动合并时只关注了冲突标记，没有检查整体结构。

**预防**：在 Step 6 的构建验证前增加去重检查：

```bash
# 检查冲突文件是否存在重复 import（一种常见的合并残留特征）
grep -c "^import " frontend/src/components/workspace/messages/message-list.tsx | \
  sort | uniq -d

# 检查是否有重复的 JSX prop 键（如 className 出现两次）
# TypeScript 构建时自然会报错，但可以预先发现
```

如果冲突文件数量较多（超过 5 个），建议优先 `pnpm build` 让编译器一次性暴露所有语法/类型错误，集中修复。

### 教训 5：工作区状态要始终保持干净

**问题**：多次在不同终端操作导致工作区、索引、HEAD 三者状态不一致。部分修复在某个终端做了但没被 commit，另一终端又以旧状态为基础继续操作。

**根因**：多终端切换 + 异步操作，缺乏单一的工作区状态管理。

**预防**：每次操作前确认工作区干净：

```bash
git status --short   # 确保无未暂存修改
git diff --stat      # 确认差异在预期范围内
```

### 教训 6：禁止"无脑合并双方"—冲突标记清除不等于去重完成

**问题**：前两次同步后，多处文件出现重复代码。典型案例如下：

| 类型 | 具体表现 | 后果 |
|------|---------|------|
| **参数重复** | `list_messages_by_run(thread_id, run_id, thread_id, run_id)` — 参数被写了两遍 | 后端 500，前端 JSON.parse 报错 |
| **import 重复** | `from sqlalchemy import select` 出现两次 | 语法正确但代码冗余 |
| **语句重复** | 两个 `model_instance = model_class(...)` 拼接行 | 后者覆盖前者，逻辑错误 |
| **JSX 重复** | 两个 `className` 或两个同类型标签嵌套 | pnpm build 失败 |

**根因**：冲突解决的思维误区——开发者看到 `<<<<<<< HEAD / ======= / >>>>>>>` 标记后，第一反应是"两边都要保留"。但场景 C 冲突的本质是双方在同一位置做了不同修改，机械保留两行必然产生重复。

**易发模式**（参数重复是其中最隐蔽的一种）：
```python
# 上游在第1-2行加了参数，本地也在第1-2行改了不同东西
await event_store.list_messages_by_run(
    thread_id,      # 上游版本
    run_id,
    thread_id, run_id,  # ← 本地版本残留，没有删除
    limit=50,
)
```

**预防**——解决冲突时的四步心法：

```
第1步：理解双方各自做了什么（读 `git show <hash> -- <file>`，不要只读冲突标记）
第2步：判断冲突区的代码是"添加"还是"修改"
  - 上游添加 + 本地添加 → 可能都要（但要检查是否功能重复）
  - 上游修改 + 本地修改 → 必须手动合并，不能机械保留两行
  - 上游删除 + 本地修改 → 评估上游删的理由，决定保留谁
第3步：清除冲突标记后，审查整个函数/代码块
  - 有没有同类语句出现了两遍？（如两个 `model_instance =`）
  - 有没有同一个 import 出现了两次？
  - 如果是函数调用参数，参数个数是否比函数签名多？
第4步：运行自动化扫描脚本
```

**金句**：

> **冲突标记清除了 ≠ 合并正确了。** 清除标记只是第一步，去重才是真正的合并。宁可花 1 分钟理解上游改了什么，也不要花 1 小时 debug 重复代码导致的怪 bug。

**自动化扫描**（在 Step 6 中执行）：

```bash
# 扫描重复位置参数（参数重复的特化检测）
echo "=== [RESIDUE] 重复位置参数 ==="
grep -rnP "\.(\w+)\(\s*\w+,\s*\w+,\s*\w+,\s*\w+" backend/app/ --include="*.py" \
  | grep -v "__pycache__" | grep -v "test_" || echo "(none)"

# 对争议文件做"同类语句出现次数"快照
echo "=== [BASELINE] 语句出现次数 ==="
for f in backend/app/gateway/app.py backend/packages/harness/deerflow/models/factory.py; do
    echo "$f: model_instance=$(grep -c 'model_instance' "$f")"
    echo "$f: from sqlalchemy import select=$(grep -c 'from sqlalchemy import select' "$f")"
done
```

如果输出中 `model_instance` > 1 或 `from sqlalchemy import select` > 1，说明存在重复残留。

---

## 后续维护

### 定期同步频率

建议每 1-2 个月同步一次上游变更，避免累积过多冲突。

### 下次同步计划（2026-06-15 前后）

| 项目 | 内容 |
|------|------|
| **上次同步** | 2026-06-01，HEAD `be7a1685` |
| **预计提交范围** | 上次同步之后 ~6月8日前的新提交（约 37 个） |
| **涉及侵入点** | 19 个（见上方清单） |
| **备份分支** | `backup-main`（当前 `88da215f`，已推送到 origin） |
| **执行计划** | `.trae/documents/fork-sync-20260609-execution-plan.md` |

同步前注意事项：
- 先 `git fetch upstream` 重新查询提交（用 `git log --after="2026-06-01" --before="2026-06-09"` + `git merge-base --is-ancestor` 双重确认）
- 确保 `git branch -f backup-main main` + `git push origin backup-main --force`
- cherry-pick 过程中遇冲突遵循"四步心法"（见教训 6），禁止无脑合并
- 同步完成后更新本 README 的历史同步记录表

### 冲突记录

每次同步后在本目录新建 `<FORK_SYNC_YYYYMMDD.md>` 记录冲突情况，并更新本 README 的同步记录表。

---

**WING**
