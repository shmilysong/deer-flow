# DeerFlow 部署使用指南

## 目录

- [1. 产物清单](#1-产物清单)
- [2. 服务器前置条件](#2-服务器前置条件)
- [3. 启动前的配置](#3-启动前的配置)
- [4. 启动服务](#4-启动服务)
- [5. 停止服务](#5-停止服务)
- [6. 查看运行状态](#6-查看运行状态)
- [7. 端口说明与访问](#7-端口说明与访问)
- [8. 数据采集](#8-数据采集)
- [9. MCP 工具](#9-mcp-工具)
- [10. 常见问题](#10-常见问题)

---

## 1. 产物清单

```
release/
├── README.md                      # 本指南
├── config.yaml                    # 主配置文件
├── config.example.yaml            # 配置模板
├── .env.example                   # 环境变量模板（部署后根据此文件创建 .env）
├── extensions_config.json         # MCP 服务器配置
├── extensions_config.example.json # MCP 配置模板
│
├── backend-bin/                   # 后端服务
│   └── deerflow-gateway/
│       └── deerflow-gateway       # 可执行文件（入口）
│
├── frontend/                      # 前端服务（standalone 自包含，无 node_modules）
│   └── .next/                     # 构建产物 + 运行时依赖
│       └── standalone/server.js   # 前端入口
│
├── scripts/                       # 工具脚本
│   ├── deerflow.sh                 # 服务管理（启动/停止）
│   └── wait-for-port.sh           # 端口等待（供 deerflow.sh 调用）
│
├── nginx/                         # Nginx 配置
├── skills/                        # Agent Skills
├── ads-agent-mcp/                 # ADS MCP（可选）
│
└── data_collection_logs/          # 数据采集输出（运行时自动生成）
```

---

## 2. 服务器前置条件

开始前请确认服务器已安装以下软件：

| 依赖 | 用途 | 安装命令（Ubuntu/Debian） |
|------|------|--------------------------|
| **Node.js 18+** | 前端 standalone 运行 + ADS MCP | `curl -fsSL https://deb.nodesource.com/setup_20.x \| bash - && apt install -y nodejs` |
| **lsof** | deerflow.sh 端口检测 | `apt install -y lsof` |

> 后端为 PyInstaller 编译的 ELF 二进制，自带 Python 运行时，**服务器无需安装 Python/pnpm/uv**。

---

## 3. 启动前的配置

### 3.1 创建 .env 文件

从模板复制并编辑：

```bash
cp .env.example .env
vi .env
```

至少需要配置一个模型的 API Key：

```bash
# DeepSeek API Key（默认模型，必须）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

其他可选 Key 参考 `.env.example` 中的注释。

### 3.2 检查 config.yaml

`config.yaml` 已配置好，确认关键字段：

```yaml
models:
  - name: deepseek-chat
    api_key: $DEEPSEEK_API_KEY   # 引用 .env 中的变量
    supports_thinking: true       # 启用 Pro / Ultra 模式

skills:
  path: ./skills                  # Skills 目录（相对路径）

data_collection:
  enabled: true
  output_dir: ./data_collection_logs
```

如需添加更多模型，在 `models` 段落后追加（格式参考 `config.example.yaml`）。

### 3.3 检查 MCP 配置

`extensions_config.json` 定义了 MCP 工具服务器：

```json
{
  "mcpServers": {
    "ads": {
      "enabled": true,
      "type": "stdio",
      "command": "node",
      "args": ["../ads-agent-mcp/dist/index.js"],
      "description": "ADS云桌面管理系统"
    },
    "deeprag": {
      "enabled": true,
      "type": "http",
      "url": "http://192.168.1.56:86/mcp",
      "description": "DeepRAG 知识库检索"
    }
  }
}
```

- **ADS MCP**：相对路径 `../ads-agent-mcp/dist/index.js`，如路径不符则需修改
- **DeepRAG**：HTTP 连接远程 MCP 服务器

### 3.4 启动前清单

| 项目 | 必须 | 说明 |
|------|------|------|
| `release/.env.example` → 创建 `.env` | ✅ | 根据模板创建，填入 API Key |
| `release/config.yaml` | ✅ | 已自动配置 |
| `release/extensions_config.json` | ✅ | 已自动配置 |
| `release/backend-bin/deerflow-gateway/deerflow-gateway` | ✅ | 后端可执行文件 |
| `release/frontend/.next/` | ✅ | 前端构建 |

---

## 4. 启动服务

> **推荐使用 `scripts/deerflow.sh` 管理服务**，无需手动分别启停前后端。

### 4.1 一键启动（推荐）

在 release 目录下执行：

```bash
cd /path/to/release/

# 启动（后台运行）
./scripts/deerflow.sh
```

启动后会自动等待前后端就绪，输出以下信息即表示成功：

```
✓ Gateway 已就绪 (localhost:8001)
✓ Frontend 已就绪 (localhost:3000)
```

日志文件：`logs/gateway.log`、`logs/frontend.log`

### 4.2 分别启动（手动控制）

如需要分开启动以分别查看日志：

**启动后端：**

```bash
cd /path/to/release/
DEER_FLOW_CONFIG_PATH=$(pwd)/config.yaml ./backend-bin/deerflow-gateway/deerflow-gateway
```

启动成功日志：

```
INFO:     Started server process [3]
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
[DataCollection] System installed via monkey-patch (agent only)
[DataCollection] System installed successfully at startup
```

**启动前端（新开终端）：**

```bash
cd /path/to/release/frontend
PORT=3000 node .next/standalone/server.js
```

启动成功日志：

```
▲ Next.js 16.1.7
✓ Ready in 131ms
- Local: http://localhost:3000
```

---

## 5. 停止服务

### 5.1 一键停止（推荐）

```bash
cd /path/to/release/
./scripts/deerflow.sh --stop
```

### 5.2 手动停止

```bash
pkill -f "deerflow-gateway"     # 停止后端
pkill -f "server\.js"            # 停止前端（standalone 进程）

# 或按端口强制停止
kill -9 $(lsof -ti :8001) 2>/dev/null   # 后端
kill -9 $(lsof -ti :3000) 2>/dev/null   # 前端
```

---

## 6. 查看运行状态

```bash
# 进程检查
ps aux | grep -E "deerflow-gateway|next"

# 端口检查
lsof -i :8001 -i :3000

# 后端连通性测试
curl -s -o /dev/null -w "Backend: HTTP %{http_code}" http://localhost:8001/

# 前端连通性测试
curl -s -o /dev/null -w "Frontend: HTTP %{http_code}" http://localhost:3000/
```

后端返回 `HTTP 401`（需登录），前端返回 `HTTP 200`，表示服务正常。

---

## 7. 端口说明与访问

| 端口 | 服务 | 说明 |
|------|------|------|
| **8001** | Gateway API | 后端 REST API + Agent 运行时 |
| **3000** | Frontend | 前端 Web 页面 |
| **2026** | Nginx | 反向代理（如配置） |

### 访问入口

- **直接访问**：`http://服务器IP:3000/`
- **代理访问**（有 Nginx）：`http://服务器IP:2026/`

首次访问需完成管理员账户设置（`/setup` 页面）。

---

## 8. 数据采集

数据采集模块已集成在后端中，启动后自动运行。

### 配置

`config.yaml` 中：

```yaml
data_collection:
  enabled: true
  output_dir: ./data_collection_logs
```

### 输出目录

```
data_collection_logs/
├── daily/
│   └── train_data_20260508.jsonl
├── archive/
└── raw/
```

### 验证

后端启动日志包含以下内容即表示采集正常：

```
[DataCollection] System installed via monkey-patch (agent only)
[DataCollection] System installed successfully at startup
```

---

## 9. MCP 工具

MCP 工具由 Agent 在对话中自动调用，定义在 `extensions_config.json` 中。

### 验证工具可用性

需先通过 `/setup` 创建管理员账户，然后调用 API：

```bash
curl -X POST http://localhost:8001/api/langgraph/tools \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin_token>" \
  -d '{}'
```

响应中应包含 MCP 工具（如 `ads_*`、`deeprag_*` 等）。

---

## 10. 常见问题

### 10.1 前端访问返回 401

首次部署需设置管理员账户：访问 `http://服务器IP:3000/setup` 按引导创建。

### 10.2 Pro / Ultra 模式不可选

`config.yaml` 中模型缺少 `supports_thinking: true`：

```yaml
models:
  - name: deepseek-chat
    ...
    supports_thinking: true
```

### 10.3 ADS MCP 报 ENOENT

`extensions_config.json` 中 `args` 路径指向的目录不存在：

```json
"args": ["../ads-agent-mcp/dist/index.js"]
```

请确保 `ads-agent-mcp/` 在 release 同级，或修改路径。

### 10.4 后端启动报 "No config file found"

未设 `DEER_FLOW_CONFIG_PATH` 环境变量：

```bash
DEER_FLOW_CONFIG_PATH=/path/to/release/config.yaml \
  ./backend-bin/deerflow-gateway/deerflow-gateway
```

### 10.5 前端启动报 "Cannot find module"

standalone 模式出此错误说明 `.next/` 构建不完整。重新执行编译脚本或确认 `next.config.js` 中有 `output: "standalone"`。

### 10.6 数据采集日志报 "Flush failed"

检查 `config.yaml` 中 `output_dir` 路径是否存在且有写权限。

### 10.7 如何更新版本？

1. 在开发机上重新编译生成 `release/`
2. 上传新 `release/` 目录到服务器
3. 复制旧版 `release/.env` 到新版
4. 复制旧版 `release/config.yaml` 中的模型配置到新版（如需保留自定义模型）
5. 停旧服务，启新服务
