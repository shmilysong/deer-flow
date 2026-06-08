# 企微配置指南

企业微信通道使用 WebSocket 方式连接，无需公网 IP。

## 创建企业微信应用

### 1. 获取企业信息

1. 登录 [企业微信管理后台](https://work.weixin.qq.com/)
2. 进入「我的企业」
3. 获取「企业 ID」

### 2. 创建应用

1. 进入「应用管理」
2. 点击「创建自建应用」
3. 填写应用名称和描述
4. 选择可信域名（用于 OAuth）
5. 创建后获取 `AgentId`

### 3. 获取应用 Secret

1. 在应用详情页
2. 点击「查看」获取 `Secret`

### 4. 配置应用功能

1. 在应用详情中开启「机器人」功能
2. 确保应用具有「发消息」和「接收消息」权限

## 配置 config.yaml

```yaml
channels:
  langgraph_url: http://localhost:2024
  gateway_url: http://localhost:8001

  wecom:
    enabled: true
    bot_id: $WECOM_BOT_ID
    bot_secret: $WECOM_BOT_SECRET

  session:
    assistant_id: lead_agent
    config:
      recursion_limit: 100
    context:
      thinking_enabled: true
```

## 配置环境变量

在 `.env` 文件中添加：

```bash
WECOM_BOT_ID=your_bot_id
WECOM_BOT_SECRET=your_bot_secret
```

## 图形化配置（推荐）

DeerFlow 提供了可视化的渠道配置页面，无需手动编辑 `.env` 文件：

1. 打开 DeerFlow 设置面板 → **"渠道配置"** 标签页
2. 输入企业微信 Bot ID 和 Bot Secret
3. 点击 **"验证连通性"** 测试凭据可用性
4. 点击 **"保存"** — 配置自动写入 `.env` 并热重启渠道

此功能由 `env-settings` 扩展提供，后端 API 路径为 `/api/env-settings/channels/*`。保存配置时会自动启用渠道（修改 `config.yaml` 的 `channels.wecom.enabled: true`），清除配置时自动禁用。无需手动编辑 `config.yaml`。

## Docker 部署配置

```yaml
channels:
  langgraph_url: http://langgraph:2024
  gateway_url: http://gateway:8001

  wecom:
    enabled: true
    bot_id: $WECOM_BOT_ID
    bot_secret: $WECOM_BOT_SECRET
```

## 安装依赖

确保已安装 `wecom-aibot-python-sdk`：

```bash
cd backend
uv add wecom-aibot-python-sdk
```

## 功能特性

- **消息类型**：支持文本、图片、文件、混合消息
- **WebSocket 连接**：实时双向通信
- **流式响应**：支持流式输出显示「Working on it...」
- **文件上传**：支持图片和文件传输

## 文件限制

| 类型 | 大小限制 |
|------|----------|
| 图片 | 2MB |
| 文件 | 20MB |

## 故障排查

### 1. 无法连接

- 确认 `bot_id` 和 `bot_secret` 正确
- 检查网络是否可以访问企业微信服务器

### 2. WebSocket 连接失败

- 确认应用已开启「机器人」功能
- 检查是否需要配置可信 IP

### 3. 消息发送失败

- 确认应用具有「发消息」权限
- 检查是否被限流

### 4. 依赖问题

确保安装了正确版本的 SDK：

```bash
uv add wecom-aibot-python-sdk==0.1.6
```

### 5. Token 获取失败

- 在企业微信管理后台确认 Secret 正确
- 确认应用没有被禁用

## 安全建议

1. **保护 Secret**：将 Secret 存储在环境变量中
2. **配置可信 IP**：在企业微信管理后台设置可信 IP
3. **限制用户**：通过 `allowed_users` 限制访问（如果支持）

## 相关文档

- [企业微信开发文档](https://developer.work.weixin.qq.com/document/)
- [wecom-aibot-python-sdk](https://github.com/WeComRobotic/wecom-aibot-python-sdk)
