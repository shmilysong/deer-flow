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

### D4b — Boot extensions（行 14，替代 sitecustomize）

```bash
PYTHONPATH=/app:. python3 -c "from deerflow_extensions.boot import boot_all_extensions; boot_all_extensions()"
```

**原因**: LangGraph 进程不再通过 sitecustomize symlink 注入，改为直接调用 `boot.py` 的 `boot_all_extensions()`。sitecustomize 机制（CPython 用于系统级全站自定义）不适用于项目扩展注入。

---

## 验证命令

```bash
# === D4a/D4b: entrypoint.sh ===
grep -n "boot_all_extensions\|ln -s" deerflow_extensions/entrypoint.sh
```
