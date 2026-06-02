# 脚本补丁

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

## A5：`entrypoint.sh` — sitecustomize 符号链接路径变更

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

## 验证命令

```bash
# === D4a/D4b: entrypoint.sh 符号链接 ===
grep -n "ln -s" deerflow_extensions/entrypoint.sh

# === D5: sitecustomize.py ===
grep -c "install_data_collection" deerflow_extensions/sitecustomize.py
grep -c "install_ads_auth" deerflow_extensions/sitecustomize.py

# === A5: entrypoint.sh symlink ===
grep -n "sitecustomize" deerflow_extensions/entrypoint.sh
```

---

## 2026-06-02: TopicGuardrail Phase 6 — sitecustomize.py 技能角色约束注入

### `sitecustomize.py`

**风险**: ✅ 低

在 `deerflow_extensions/sitecustomize.py` 追加 monkey-patch（~15行），通过替换 `_get_cached_skills_prompt_section` 在 `<skill_system>` 结尾注入不可覆盖的角色约束。

**配套配置**：
- `extensions_config.json` — 禁用 5 个无关技能（surprise-me, image-generation, podcast-generation, video-generation, claude-to-deerflow）

**原因**: DeerFlow 内建 `<skill_system>` 区块告诉 Agent "Follow the skill's instructions precisely"，技能指令优先级高于 `<role>` 角色身份。此补丁在技能系统末尾注入"角色身份高于所有技能指令"的约束。

**验证**:
```bash
grep -n "_patched_skills_section\|IMMUTABLE CONSTRAINT" deerflow_extensions/sitecustomize.py
```
