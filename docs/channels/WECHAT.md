# DeerFlow 绑定个人微信机器人操作手册

## 概述

本手册指导你将 **DeerFlow** 绑定到 **个人微信号**（非企业微信），使 DeerFlow 能以你的微信号作为 AI 机器人自动回复消息。

> **工作原理**：DeerFlow 通过腾讯 iLink 协议（`https://ilinkai.weixin.qq.com`）与你的个人微信号建立长轮询连接。别人给你发微信 → DeerFlow 自动回复 → 回复内容发送回给你。

> **注意**：这不是企业微信机器人。企业微信机器人请参考 [WECOM.md](./WECOM.md)。

---

## 1. 前置准备

### 1.1 你需要准备的

| 项目 | 说明 | 必须/可选 |
|------|------|----------|
| 一个**个人微信号** | 用来扫码绑定，该微信号将成为机器人本体 | **必须** |
| DeerFlow 已部署运行 | DeerFlow 后端需要正常运行中 | **必须** |
| 网络能访问 `ilinkai.weixin.qq.com` | iLink 服务部署在腾讯云上，服务器需能出网访问 | **必须** |
| 微信 iLink Bot Token（可选） | 如果你已经申请了 iLink bot token，可以直接使用 | 可选 |

### 1.2 确认 DeerFlow 渠道组件已安装

```bash
# 进入 backend 目录
cd /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/backend

# 确认依赖已安装（wechat 渠道使用 httpx + cryptography，均为标准依赖）
uv sync
```

### 1.3 准备 config.yaml

编辑 DeerFlow 项目根目录下的 `config.yaml`（通常位于 `deer-flow/config.yaml`），在 `channels` 段添加：

```yaml
channels:
  langgraph_url: http://localhost:2024
  gateway_url: http://localhost:8001

  wechat:
    enabled: true
    # 方式一：QR 码登录（推荐，首次配置用这个）
    qrcode_login_enabled: true
    allowed_users: []               # 空列表 = 允许所有用户
    state_dir: ./.deer-flow/wechat/state
    # 可选：iLink App ID（如有则发送为 iLink-App-Id 请求头）
    ilink_app_id: ""
    # 可选：路由标签（如有则发送为 SKRouteTag 请求头）
    route_tag: ""
```

> **关于 `bot_token` 和 `ilink_bot_id`**：如果你已经拥有 iLink 官方发放的 bot_token，可以在配置中直接填入，并设置 `qrcode_login_enabled: false`。如果没有，使用以上 QR 码配置即可，扫码成功后 token 会自动保存在 `state_dir` 中。

---

## 2. 启动微信渠道

### 2.1 在本地开发环境中启动

如果在本地开发环境中运行：

```bash
# 方式一：通过 make dev 启动（全量服务）
# 从项目根目录启动：
cd /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow
make dev

# 方式二：单独启动后端（如果前端不需要）
cd backend
make gateway
```

启动后观察日志，如果配置正确可以看到：

```
INFO     Channel wechat started
```

### 2.2 在 Docker 中启动

如果使用 Docker 部署：

```yaml
# docker-compose-dev.yaml 的 gateway 服务下
channels:
  langgraph_url: http://langgraph:2024
  gateway_url: http://gateway:8001

  wechat:
    enabled: true
    qrcode_login_enabled: true
    allowed_users: []
    state_dir: ./.deer-flow/wechat/state
```

```bash
cd /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/docker
docker compose down
docker compose up -d

# 查看日志确认 wechat 渠道启动
docker logs deer-flow-gateway --tail 50
```

> 注意：Docker 部署时需确保 `state_dir` 对应的目录已通过 volumes 挂载，否则重启后扫码状态会丢失。

---

## 3. 绑定你的微信号

### 3.1 首次绑定（QR 码扫码）

这是最常用的方式。分为两种情况：

#### 情况 A：本地 Terminal 启动（推荐）

如果使用 `make dev` 或 `make gateway` 在终端中启动，日志中会看到：

```
[WeChat] QR login required. qrcode=https://ilinkai.weixin.qq.com/bot?qrcode=xxx
[WeChat] qrcode_img_content=...
```

日志中会包含一个 **URL 格式的二维码内容**。你需要：

1. **方法一**（推荐）：将日志中的 `qrcode=` 后面的 URL 复制出来，用**另一台设备**的微信扫一扫打开，或者用二维码生成工具将此 URL 转为二维码图片
2. **方法二**：如果有显示 `qrcode_img_content`（base64 编码的二维码图片），解码后直接用微信扫描
3. **扫码时效**：二维码有效期为 **180 秒**（`qrcode_poll_timeout: 180`），超时后会自动重新生成

扫码后，DeerFlow 日志会显示：

```
[WeChat] QR code status: confirmed
[WeChat] bot_token saved to state file
```

表示绑定成功。

#### 情况 B：Docker 部署

Docker 部署时，通过日志查看二维码：

```bash
docker logs deer-flow-gateway 2>&1 | grep "QR login"
```

同样复制 `qrcode=` 后的 URL 进行扫码。

### 3.2 验证绑定状态

通过查看日志确认渠道运行正常：

```bash
# 本地部署
tail -f backend/.deer-flow/wechat/state/wechat-auth.json

# Docker 部署
docker exec deer-flow-gateway cat /app/.deer-flow/wechat/state/wechat-auth.json
```

正常状态文件内容示例：

```json
{
  "status": "confirmed",
  "bot_token": "ilink_xxxxxxxxxxxx",
  "ilink_bot_id": "wx_xxxxxxxx",
  "updated_at": 1234567890
}
```

---

## 4. 验证机器人正常工作

### 4.1 发送测试消息

用**其他微信号**给绑定好的微信号发送一条消息，DeerFlow 应当自动回复。
如果要更快验证，直接给自己的机器人微信号发消息。

### 4.2 查看日志中的消息流转

```bash
# 本地
tail -f backend/logs/*.log | grep "WeChat"

# Docker
docker logs deer-flow-gateway --tail 100 -f | grep "WeChat"
```

正常流程：

```
[WeChat] received message from: <user_id>
[WeChat] dispatching to agent...
[WeChat] agent response: <回复内容>
[WeChat] sent message to: <user_id>
```

### 4.3 检查状态文件

```bash
cat backend/.deer-flow/wechat/state/wechat-auth.json
```

如果 `status` 为 `confirmed`，说明绑定持续有效。

---

## 5. 配置详解

### 5.1 完整配置项

```yaml
channels:
  wechat:
    enabled: true                          # 启用微信渠道
    bot_token: $WECHAT_BOT_TOKEN           # iLink Bot Token（二选一：配这个或用 QR 码）
    ilink_bot_id: $WECHAT_ILINK_BOT_ID    # iLink Bot ID（使用 bot_token 时需要）
    qrcode_login_enabled: true             # QR 码登录（二选一：配这个或用 bot_token）
    allowed_users: []                      # 允许的用户列表（空=允许所有人）
    polling_timeout: 35                    # 长轮询超时（秒，默认 35）
    qrcode_poll_timeout: 180               # 二维码扫码等待超时（秒，默认 180）
    qrcode_poll_interval: 2                # 二维码状态轮询间隔（秒，默认 2）
    state_dir: ./.deer-flow/wechat/state   # 状态文件持久化目录
    ilink_app_id: ""                       # iLink App ID（可选）
    route_tag: ""                          # 路由标签（可选）

    # 以下为可选的文件大小和类型限制
    max_inbound_image_bytes: 20971520      # 入站图片最大字节（20MB）
    max_outbound_image_bytes: 20971520     # 出站图片最大字节（20MB）
    max_inbound_file_bytes: 52428800       # 入站文件最大字节（50MB）
    max_outbound_file_bytes: 52428800      # 出站文件最大字节（50MB）
    allowed_file_extensions:               # 允许的文件后缀
      - ".txt"
      - ".md"
      - ".pdf"
      - ".csv"
      - ".json"
```

### 5.2 使用 Bot Token（替代 QR 码登录）

如果你已经通过 iLink 官方渠道获取了 `bot_token` 和 `ilink_bot_id`，可以在环境变量中配置：

```bash
# .env 文件
WECHAT_BOT_TOKEN=ilink_xxxxxxxxxxxx
WECHAT_ILINK_BOT_ID=wx_xxxxxxxx
```

对应的 config.yaml：

```yaml
channels:
  wechat:
    enabled: true
    bot_token: $WECHAT_BOT_TOKEN
    ilink_bot_id: $WECHAT_ILINK_BOT_ID
    qrcode_login_enabled: false            # 关闭 QR 码登录
```

### 5.3 配置会话参数（可选）

你可以为微信渠道指定不同的 Agent 或参数：

```yaml
channels:
  wechat:
    enabled: true
    qrcode_login_enabled: true
    session:
      assistant_id: lead_agent            # 使用的 Agent（默认）
      context:
        thinking_enabled: false            # 是否启用思考模式
```

---

## 6. 状态文件说明

微信渠道会在 `state_dir` 目录下持久化以下文件：

```
.deer-flow/wechat/state/
├── wechat-auth.json          # 认证信息（bot_token, ilink_bot_id 等）
├── wechat-getupdates.json    # 长轮询游标（用于断连恢复）
└── downloads/                # 接收到的图片/文件缓存
    ├── wechat-image-xxx.png
    └── wechat-file-xxx.pdf
```

**重要**：
- `wechat-auth.json` 中的 `bot_token` 有有效期，过期后渠道会停止运行
- 如果使用 QR 码登录，token 过期后需要重新扫码
- Docker 部署时，请确保 `state_dir` 对应的目录通过 volumes 挂载到宿主机，避免容器重建后丢失状态

---

## 7. 常见问题与排查

### 7.1 渠道启动失败

**症状**：日志显示 `WeChat channel requires bot_token or qrcode_login_enabled`

**原因**：`bot_token` 未设置且 `qrcode_login_enabled` 为 `false`

**解决**：设置 `qrcode_login_enabled: true` 或提供 `bot_token`

### 7.2 二维码扫码后不确认

**症状**：扫码后日志停留在 `pending` 状态，最终超时

**可能原因**：
1. 二维码已过期（默认 180 秒）
2. iLink 服务暂时不可用
3. 服务器网络无法访问 `ilinkai.weixin.qq.com`

**检查方法**：
```bash
# 测试服务器能否访问 iLink
curl -s -o /dev/null -w "%{http_code}" https://ilinkai.weixin.qq.com/ilink/bot/get_bot_qrcode
```

**解决**：确认服务器出网正常，重新启动渠道即可生成新二维码。

### 7.3 Bot Token 过期

**症状**：日志显示 `[WeChat] bot token expired; scan again or update bot_token and restart the channel`

**原因**：iLink 颁发的 bot_token 有有效期

**解决**：
- 如果使用 QR 码登录：渠道会自动停止，重新启动即可重新扫码
- 如果使用 bot_token：需要重新申请并更新配置

### 7.4 消息发送出去但对方收不到

**可能原因**：
1. `context_token` 丢失（需要至少接收过一条消息才能回复）
2. 对方微信号不在 `allowed_users` 列表中
3. 消息包含不支持的格式

**检查**：
```bash
# 查看日志中的发送结果
grep "WeChat" backend/logs/*.log | grep "send"
```

### 7.5 Docker 环境重启后需要重新扫码

**原因**：`state_dir` 未挂载到宿主机，容器重建后状态丢失

**解决**：在 `docker-compose-dev.yaml` 中添加 volume 挂载：

```yaml
gateway:
  volumes:
    - ./.deer-flow/wechat/state:/app/.deer-flow/wechat/state
```

### 7.6 文件传输失败

**症状**：图片或文件无法发送/接收

**检查**：
1. 文件大小是否超过限制（图片 20MB，文件 50MB）
2. 文件类型是否在 `allowed_file_extensions` 列表中
3. iLink 的 CDN 上传/下载是否正常

---

## 8. 生命线管理

### 8.1 重启渠道

```bash
# 通过 API 重启
curl -X POST http://localhost:8001/api/channels/wechat/restart

# 或通过重启整个 DeerFlow
make stop && make dev
```

### 8.2 查看渠道状态

```bash
curl http://localhost:8001/api/channels/
```

预期返回：

```json
{
  "channels": {
    "wechat": {
      "running": true
    }
  }
}
```

### 8.3 清理状态（重新绑定）

如果需要解绑并重新绑定：

```bash
# 停止 DeerFlow
make stop

# 删除状态文件
rm -rf backend/.deer-flow/wechat

# 重新启动
make dev
```

---

## 9. 注意事项

1. **机器人就是你的微信号**：绑定后，你收到的消息都会被 DeerFlow 处理，请确保 `allowed_users` 配置正确
2. **iLink 服务稳定性**：iLink 是腾讯提供的服务，偶尔可能不稳定，请留意日志
3. **二维码安全性**：不要将二维码分享给不信任的人，扫码即获得机器人控制权
4. **网络要求**：服务器必须能够访问 `https://ilinkai.weixin.qq.com`
5. **不支持的消息类型**：视频、语音消息当前不支持，微信红包、转账等系统消息也会被忽略

---

## 10. 相关文档

- [企业微信机器人配置指南](./WECOM.md) — 企业微信机器人（WeCom）
- [渠道系统架构说明](./README.md) — DeerFlow 渠道系统整体架构
- [iLink 接口文档](https://ilinkai.weixin.qq.com/) — 腾讯 iLink 官方文档
