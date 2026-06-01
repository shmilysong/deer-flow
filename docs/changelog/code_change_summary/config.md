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

## 2026-06-01: API Keys 配置界面优化

### `.env.example` 新增

新增 7 个国产大模型厂商共 21 个环境变量（全部注释标注可选）：

| 厂商 | 环境变量 |
|------|---------|
| 硅基流动 | `SILICONFLOW_API_KEY` / `SILICONFLOW_BASE_URL` / `SILICONFLOW_MODEL` |
| DeepSeek | `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` |
| Kimi (月之暗面) | `MOONSHOT_API_KEY` / `MOONSHOT_BASE_URL` / `MOONSHOT_MODEL` |
| Doubao (字节豆包) | `VOLCENGINE_API_KEY` / `VOLCENGINE_BASE_URL` / `VOLCENGINE_MODEL` |
| 千问 (阿里云) | `DASHSCOPE_API_KEY` / `DASHSCOPE_BASE_URL` / `DASHSCOPE_MODEL` |
| MiniMax | `MINIMAX_API_KEY` / `MINIMAX_BASE_URL` / `MINIMAX_MODEL` |
| GLM (智谱) | `ZHIPUAI_API_KEY` / `ZHIPUAI_BASE_URL` / `ZHIPUAI_MODEL` |

同时清理了 Optional 节中已覆盖的旧变量（`FIRECRAWL_API_KEY`、`VOLCENGINE_API_KEY`、`DEEPSEEK_API_KEY`、`NOVITA_API_KEY`、`MINIMAX_API_KEY`、`VLLM_API_KEY`）。

## 核心改动中的配置相关

| 文件 | 改动 |
|------|------|
| `backend/app/gateway/csrf_middleware.py` | frozenset 加 `/login/ads`（1 行）— CSRF 白名单路由配置 |
| `backend/app/gateway/auth_middleware.py` | 内联 JWT decode，支持 ADS token + 确定性 UUID |
| `docker/docker-compose-dev.yaml` | 两个服务增加 `ADS_BASE_URL` 和 `ADS_MCP_CONFIG_PATH` 环境变量 |
