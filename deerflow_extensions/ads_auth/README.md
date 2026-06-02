# ADS 统一认证扩展

## 概述

将 ADS（若依系统）作为 DeerFlow 的统一身份提供者（IdP）。用户使用 ADS 账号密码登录 DeerFlow，ADS JWT 是唯一的会话令牌，不再使用 DeerFlow 自有的本地认证体系。

## 原理

```
用户输入 ADS 账号密码 → POST /api/v1/auth/login/ads
  → DeerFlow 转发 POST /jwt/login (form-encoded)
  → ADS 返回 JWT (HS256, 30分钟过期)
  → DeerFlow 将 JWT 设为 HttpOnly Cookie
  → 同时写入 ADS-MCP 的 config.json
  → 后续请求由 ADSProxyMiddleware 验证 JWT
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `config.py` | 从环境变量 `ADS_BASE_URL` 读取 ADS 服务器地址（默认 `http://ads:8080`） |
| `ads_auth.py` | 调 ADS `/jwt/login` 拿 JWT，httpx 异步请求 |
| `middleware.py` | `ADSProxyMiddleware` — FastAPI ASGI 中间件，唯一认证关口 |
| `router.py` | `POST /api/v1/auth/login/ads` 登录端点 |
| `token_manager.py` | 内存 token 存储 + 写 MCP config.json |
| `startup.py` | 注入逻辑：`app.add_middleware()` + `app.include_router()` |
| `sitecustomize.py` | Python 自启动入口，由 Python 解释器自动加载 |

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ADS_BASE_URL` | `http://ads:8080` | ADS 服务器地址，如 `https://192.168.1.54` |
| `ADS_MCP_CONFIG_PATH` | `""` | ADS-MCP config.json 路径，如 `/home/wing/.hermes/mcp-servers/ads-mcp/.ads-mcp/config.json` |

## MCP config.json 写入内容

登录成功后自动写入以下字段（`credentials` 保留不动）：

```json
{
  "ads": {
    "server": { "url": "http://ads:8080" },
    "token": {
      "value": "eyJ...",
      "expires": 1746001800,
      "loginTime": 1746000000,
      "usedBy": "deerflow"
    }
  }
}
```

## 核心改动

`deer-flow/backend/app/gateway/auth_middleware.py` 中增加 1 行 Extension Hook：

```python
if getattr(request.state, "_ads_authenticated", False):
    return await call_next(request)
```

## 安装

自动通过 `sitecustomize.py` 注入，无需手动安装。部署时确保：

1. `deerflow_extensions` 目录在 Python `sys.path` 中（Docker 通过 `PYTHONPATH=/app` + volume 挂载）
2. `sitecustomize.py` 在 site-packages 中（Docker 通过 entrypoint.sh 创建符号链接）

## 卸载

1. 删除 `auth_middleware.py` 中新增的 1 行守卫
2. 删除 `deerflow_extensions/ads_auth/` 目录
3. 删除 Docker 环境变量 `ADS_BASE_URL`、`ADS_MCP_CONFIG_PATH`
4. 重启服务

## 前端对应

前端登录页和 Next.js 中间件位于 [frontend/extensions/ads_auth/](../../frontend/extensions/ads_auth/README.md)。
