# Cherry-Pick 冲突解决记录（2026-06-01）

> 本文件记录 Fork 同步过程中所有需要手动介入的冲突及其处理方式。
>
> **同步范围**：`upstream/main` 自 fork 分叉点后的 274 个提交 cherry-pick 到本地 `main`
> **同步方式**：`git cherry-pick`（逐条按时间正序）
> **处理原则**：所有冲突文件手动编辑保留双方，禁止 `--theirs` 丢弃本地

---

## 填写规范

每次遇到场景 C 或 D 的冲突时，按以下模板记录：

```markdown
### 提交 `<abbreviated_hash>` — `<提交标题>`

**冲突文件**：`path/to/file`

**冲突类型**：[场景C 双方改了相同区域] / [场景D 逻辑互斥]

**本地内容**：
```
本地在这段代码上的自定义逻辑
```

**Cherry-pick 内容**：
```
上游新提交的变更
```

**处理方式**：
1. 具体步骤
2. ...
3. 最终结果简述

**验证**：[如何确认合并正确]
```

---

## 冲突记录

### 提交 `898f4e8a` — fix: Memory update system has cache corruption, data loss, and thread-safety bugs

**冲突文件**：
- `backend/packages/harness/deerflow/agents/memory/storage.py`
- `backend/tests/test_memory_updater.py`

**冲突类型**：场景C — 双方改了相同区域

**本地内容**：per-user 内存隔离（`(user_id, agent_name)` 缓存键 + `_cache_key()` 方法 + `_get_memory_file_path()` 支持 user_id 参数 + `TestUserIdForwarding` 测试类）

**Cherry-pick 内容**：更简单的缓存键（仅 `agent_name`），同步模型调用（`invoke` 而非 `ainvoke`），无 per-user 支持

**处理方式**：保留本地版本。本地已包含 cherry-pick 的所有 bugfix 内容，且封装在更完善的 per-user 隔离框架中（包括 user_id 传递、缓存键升级、异步/同步模型兼容）。

**验证**：`grep -c "user_id\|_cache_key" backend/packages/harness/deerflow/agents/memory/storage.py` > 0

### 提交 `c6b04235` — feat(frontend): add Playwright E2E tests with CI workflow

**冲突文件**：
- `frontend/playwright.config.ts`
- `frontend/tests/e2e/utils/mock-api.ts`
- `frontend/pnpm-lock.yaml`（lock 文件，跳过）

**冲突类型**：场景C — 双方改了相同区域

**本地内容**：E2E 测试配置中包含 `DEER_FLOW_AUTH_DISABLED: "1"`（因使用 ADS 认证），mock-api.ts 中有额外 mock 路由（`/runs` GET、`/api/models`、`/api/threads/*/suggestions`）

**Cherry-pick 内容**：无 ADS 认证相关配置，无额外 mock 路由

**处理方式**：保留本地版本。本地已在 E2E 测试环境中配置 ADS 认证绕过（`DEER_FLOW_AUTH_DISABLED`），且 mock 路由覆盖了更多 API 端点。cherry-pick 结果是空提交，直接 `--skip`。
