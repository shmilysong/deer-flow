# 配置变更

## 环境变量与配置

| 配置项 | 说明 | 来源 |
|--------|------|------|
| `ADS_BASE_URL` | ADS 服务器地址，默认 `http://ads:8080` | `deerflow_extensions/ads_auth/config.py` + `docker-compose-dev.yaml` |
| `ADS_MCP_CONFIG_PATH` | MCP 配置文件路径 | `docker-compose-dev.yaml` |
| `GATEWAY_CORS_ORIGINS` | 跨域允许来源配置 | `.env.example` 新增 |
| `PYTHONPATH=/app` | 容器内 Python 模块搜索路径 | `docker-compose-dev.yaml` command 行 |

## 配置加载优先级

- `deerflow_extensions/data_collection/config.py`：3级优先级（独立YAML > config.yaml > 环境变量）
- `deerflow_extensions/ads_auth/config.py`：从环境变量 `ADS_BASE_URL` 读取 ADS 地址，增加 `_load_dotenv()` 自动加载 `.env`

## `.env.example` 新增

- 新增 `GATEWAY_CORS_ORIGINS` 配置示例
- 新增 ADS 相关配置示例

## 核心改动中的配置相关

| 文件 | 改动 |
|------|------|
| `backend/app/gateway/csrf_middleware.py` | frozenset 加 `/login/ads`（1 行）— CSRF 白名单路由配置 |
| `backend/app/gateway/auth_middleware.py` | 内联 JWT decode，支持 ADS token + 确定性 UUID |
| `docker/docker-compose-dev.yaml` | 两个服务增加 `ADS_BASE_URL` 和 `ADS_MCP_CONFIG_PATH` 环境变量 |
