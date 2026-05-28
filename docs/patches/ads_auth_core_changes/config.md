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
