# 配置补丁

## A9：`.env.example` — ADS 配置示例

**文件**: `.env.example`
**行号**: L62-L68
**风险**: ✅ 极低

新增 ADS 统一认证的环境变量示例：

```bash
# ── ADS 统一认证 ──────────────────────────────────────────
# ADS_BASE_URL=http://ads:8080
# ADS_MCP_CONFIG_PATH=/path/to/ads-mcp/config.json
```

---

## 验证命令

```bash
# === A9: .env.example ADS ===
grep -n "ADS_BASE_URL\|ADS_MCP" .env.example
```

---

## D5：`backend/pyproject.toml` — filelock + pyahocorasick 依赖

**文件**: `backend/pyproject.toml`
**风险**: 🟡 中（上游频繁修改此文件，16 个提交）

两项追加依赖：

```toml
    "pyahocorasick>=2.3.1",
    "filelock>=3.0.0",
```

**原因**:
- `pyahocorasick`: AC 自动机敏感词检测引擎，topic_guardrail 扩展依赖
- `filelock`: 并发写入保护，env_settings 扩展依赖（`.env` 文件并发安全）

---

## 验证命令

```bash
# === D5: pyproject.toml 依赖 ===
grep -c "filelock\|pyahocorasick" backend/pyproject.toml
# 应输出 2
```
