# Docker 配置补丁

## D2：`docker-compose-dev.yaml` — Volume 挂载 + PYTHONPATH

**文件**: `docker/docker-compose-dev.yaml`
**风险**: ✅ 低

### D2a — deerflow_extensions volume（行 134）

```yaml
      - ../deerflow_extensions:/app/deerflow_extensions
```

### D2b — training_logs volume（行 135）

```yaml
      - ../training_logs:/data/deerflow/training_logs
```

### D2c — PYTHONPATH（行 123，内嵌在 command 中）

```bash
# 原 command 中内嵌：
PYTHONPATH=. uv run uvicorn ...
```
改为：
```bash
PYTHONPATH=/app uv run uvicorn ...
```

**原因**: Volume 挂载使扩展目录和采集数据在容器内可用；`PYTHONPATH=/app` 确保 Python 能找到 `deerflow_extensions` 包。

---

## D3：`docker-compose.yaml`（生产环境）— Volume 挂载 + PYTHONPATH

**文件**: `docker/docker-compose.yaml`
**风险**: ✅ 低

### D3a — deerflow_extensions volume（行 83）

```yaml
      - ../deerflow_extensions:/app/deerflow_extensions
```

### D3b — training_logs volume（行 84）

```yaml
      - ../training_logs:/data/deerflow/training_logs
```

### D3c — PYTHONPATH（行 76，内嵌在 command 中）

```bash
command: sh -c "cd backend && PYTHONPATH=. uv run uvicorn ..."
```

**原因**: 生产环境与 dev 环境相同需求。

---

## A4：`docker-compose-dev.yaml` — ADS 环境变量

**文件**: `docker/docker-compose-dev.yaml`
**风险**: ✅ 低

```yaml
      - ADS_BASE_URL=${ADS_BASE_URL:-http://ads:8080}
      - ADS_MCP_CONFIG_PATH=${ADS_MCP_CONFIG_PATH:-}
```

---

## 验证命令

```bash
# === D2a: volume deerflow_extensions ===
grep -n "deerflow_extensions" docker/docker-compose-dev.yaml

# === D2b: volume training_logs ===
grep -n "training_logs" docker/docker-compose-dev.yaml

# === D2c: PYTHONPATH ===
grep -n "PYTHONPATH" docker/docker-compose-dev.yaml

# === D3a: volume deerflow_extensions (prod) ===
grep -n "deerflow_extensions" docker/docker-compose.yaml

# === D3b: volume training_logs (prod) ===
grep -n "training_logs" docker/docker-compose.yaml

# === A4: docker-compose ADS_BASE_URL ===
grep -n "ADS_BASE_URL\|ADS_MCP" docker/docker-compose-dev.yaml
```
