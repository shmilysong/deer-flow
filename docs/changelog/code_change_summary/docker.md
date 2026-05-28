# Docker 变更

## 1. 修改 `docker/docker-compose-dev.yaml`（数据采集系统）

**gateway容器（2处改动）：**

```diff
- command: sh -c "... && PYTHONPATH=. uv run uvicorn ..."
+ command: sh -c "... && PYTHONPATH=/app uv run uvicorn ..."
```

```diff
  volumes:
    - ../ads-agent-mcp:/app/ads-mcp
+   - ../deerflow_extensions:/app/deerflow_extensions
```

**langgraph容器（2处改动）：**

```diff
- command: sh -c "... && uv run langgraph dev ..."
+ command: sh -c "... && PYTHONPATH=/app uv run langgraph dev ..."
```

```diff
  volumes:
    - ../ads-agent-mcp:/app/ads-mcp
+   - ../deerflow_extensions:/app/deerflow_extensions
```

- `PYTHONPATH=/app`：确保容器内 `/app/deerflow_extensions` 可被Python import。
- `deerflow_extensions`卷挂载：将宿主机插件目录映射到容器内。

## 2. 修改 `docker/docker-compose-dev.yaml`（ADS认证系统）

**Docker 环境变量**:

| 变量 | 默认值 | 位置 |
|------|--------|------|
| `ADS_BASE_URL` | `http://ads:8080` | `docker/docker-compose-dev.yaml` 两个服务 |
| `ADS_MCP_CONFIG_PATH` | `""` | 同上 |
