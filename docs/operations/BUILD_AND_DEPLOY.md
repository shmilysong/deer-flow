# DeerFlow 编译与部署指南

> 本文档整理了 DeerFlow 项目所有编译方式、产物说明及部署到 56 服务器的完整流程。
>
> **当前主要工作流**：本机编译前端并打包 release → 后端在 56 服务器上编译 → 服务器上启动服务。
>
> 关联脚本：
> - `scripts/build-release.sh` — 一键编译 release 产物
> - `backend/build-backend.sh` — 本机后端 PyInstaller 编译
> - `backend/scripts/build-backend-on-server.sh` — 服务器端后端 PyInstaller 编译
> - `scripts/server-release.sh` — Release 服务管理（start/stop）
> - `scripts/wait-for-port.sh` — 端口等待检测工具

---

## 1. 编译脚本总览

| 脚本 | 路径 | 用途 |
|------|------|------|
| `build-release.sh` | `scripts/build-release.sh` | 一键编译完整 release 产物（前端 + 后端 PyInstaller） |
| `build-backend.sh` | `backend/build-backend.sh` | 仅编译后端 PyInstaller 二进制（在本机执行） |
| `build-backend-on-server.sh` | `backend/scripts/build-backend-on-server.sh` | 在目标服务器上编译后端二进制（不含 Python3.12 时自动源码安装） |
| `server-release.sh` | `scripts/server-release.sh` | Release 服务管理脚本（start/stop） |
| `wait-for-port.sh` | `scripts/wait-for-port.sh` | 端口等待检测工具 |

---

## 2. 编译方式详解

### 2.1 ⭐ 主要方式：本机编译前端 + 56 服务器编译后端（推荐）

这是项目当前的主要工作流。前端在本机构建（速度快），后端在 56 服务器上使用服务器 CPU 架构编译 PyInstaller 二进制（确保兼容性）。

#### Step 1：本机 — 编译前端并打包 release（跳过 PyInstaller）

```bash
# 在 deer-flow 项目根目录执行
cd /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow

# 编译前端 + 打包 release（跳过耗时的后端 PyInstaller）
./scripts/build-release.sh --skip-backend
```

**产物**：`release/` 目录，包含：
- `frontend/` — Next.js standalone 生产构建（无 node_modules）
- `backend-bin/` — **空目录占位**（后续由服务器编译产物填充）
- `skills/` — Agent skills
- `ads-agent-mcp/` — ADS MCP（如检测到已构建）
- `scripts/` — 服务管理脚本（deerflow.sh + wait-for-port.sh）
- `nginx/` — Nginx 配置
- `config.yaml` / `config.example.yaml` — 主配置 + 模板
- `extensions_config.json` / `extensions_config.example.json` — MCP 配置 + 模板
- `.env.example` — 环境变量模板

#### Step 2：本机 — 传输到 56 服务器

```bash
# 2a. 将 release 产物传到服务器
rsync -avz --progress -e 'ssh -p 2222' \
  /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/release/ \
  root@192.168.1.56:/usr/xccloud/deerflow/

# 2b. 将后端源码 + deerflow_extensions 传到服务器（供编译用）
sudo rsync -avz --progress --no-g --no-o -e 'ssh -p 2222' \
  /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/backend/ \
  /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/deerflow_extensions \
  root@192.168.1.56:/usr/xccloud/deerflow/source/
```

#### Step 3：服务器 — 编译后端 PyInstaller 二进制

```bash
# SSH 登录 56 服务器
ssh -p 2222 root@192.168.1.56

# 进入源码目录
cd /usr/xccloud/deerflow/source

# 执行服务器编译脚本（如无 Python3.12 会从源码编译安装）
bash backend/scripts/build-backend-on-server.sh

# 编译完成后，将产物复制到 release 目录
cp -r backend/dist/deerflow-gateway /usr/xccloud/deerflow/backend-bin/
```

> **注意**：`build-backend-on-server.sh` 会自动处理以下事项：
> - 检查 Python 3.12 是否存在，不存在则从源码编译安装
> - 修复共享库路径（`LD_LIBRARY_PATH`）
> - 创建独立虚拟环境（`.venv-server`）
> - 降级 numpy 到 1.x（兼容旧 CPU）
> - 编译完成后退出虚拟环境

#### Step 4：服务器 — 配置并启动服务

```bash
cd /usr/xccloud/deerflow

# 创建主配置
cp config.example.yaml config.yaml
vim config.yaml  # 编辑 API keys + 添加 supports_thinking: true

# 检查并修改 MCP 配置
vim extensions_config.json  # 确认 ADS MCP 路径为 ../ads-agent-mcp/

# 启动服务（后台运行）
./scripts/deerflow.sh

# 查看启动日志
tail -f logs/gateway.log
tail -f logs/frontend.log

# 停止服务
./scripts/deerflow.sh --stop
```

---

### 2.2 备选方式 A：本机全量编译（前端 + 后端）

适用于开发机与服务器架构/OS 一致，或需要完整 release 包的场景。

```bash
cd /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow
./scripts/build-release.sh
```

**耗时**：PyInstaller 编译约 5-15 分钟。
**产物**：`release/` 目录（`backend-bin/` 包含 ELF 二进制）。

---

### 2.3 备选方式 B：纯后端编译（本机独立编译）

仅编译后端二进制，不涉及前端。

```bash
cd /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/backend
bash build-backend.sh
```

**产物**：`backend/dist/deerflow-gateway/`
- `deerflow-gateway` — ELF 可执行文件（含嵌入式 Python 解释器）
- `_internal/` — 编译后的 `.pyc` / `.so`（无 `.py` 源码）

**启动验证**：
```bash
DEER_FLOW_CONFIG_PATH=/path/to/config.yaml ./backend/dist/deerflow-gateway/deerflow-gateway
curl http://127.0.0.1:8001/health
```

---

### 2.4 备选方式 C：全量编译后直接传输到 56 服务器

前提：已在本机完成全量编译（方法 2.2）。

```bash
# 传输完整 release 到服务器
rsync -avz --progress -e 'ssh -p 2222' \
  /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/release/ \
  root@192.168.1.56:/usr/xccloud/deerflow/

# 注意：这种方式要求本机和服务器架构 / OS 一致，否则后端二进制无法运行
```

---

## 3. 56 服务器传输命令汇总

| 场景 | 命令 |
|------|------|
| **传输 release 产物**（主要使用） | `rsync -avz --progress -e 'ssh -p 2222' release/ root@192.168.1.56:/usr/xccloud/deerflow/` |
| **传输后端源码**（服务端编译） | `sudo rsync -avz --progress --no-g --no-o -e 'ssh -p 2222' backend/ deerflow_extensions root@192.168.1.56:/usr/xccloud/deerflow/source/` |

> **注意**：第二条命令使用了 `sudo`，因为访问 deer-flow 目录需要特定权限。请根据实际权限情况决定。

---

## 4. Release 产物清单

执行 `./scripts/build-release.sh` 后在 `release/` 目录产生的完整文件列表：

```
release/
├── frontend/                    # Next.js standalone 构建产物
│   ├── .next/                   # Next.js 构建缓存
│   │   ├── standalone/          # standalone 模式产物（含 server.js）
│   │   │   ├── server.js       # 前端入口（node 运行）
│   │   │   └── .next/static/   # 静态资源
│   │   └── static/              # 构建静态资源
│   ├── public/                  # 公共静态资源
│   ├── next.config.js           # Next.js 配置
│   └── src/
│       └── env.js               # 环境变量配置（next.config.js import 用）
├── backend-bin/                 # PyInstaller 编译产物
│   └── deerflow-gateway/
│       ├── deerflow-gateway     # ELF 可执行文件（入口）
│       └── _internal/           # 编译后的 .pyc / .so
├── skills/                      # Agent skills（rsync 复制）
├── ads-agent-mcp/               # ADS MCP（可选，如有构建）
│   ├── dist/
│   ├── node_modules/
│   └── .ads-mcp/config.json
├── scripts/
│   ├── deerflow.sh              # 服务管理脚本（原名 server-release.sh）
│   └── wait-for-port.sh         # 端口等待工具
├── nginx/
│   └── server.conf              # Nginx 配置（放入 /etc/nginx/conf.d/）
├── config.yaml                  # 主配置（skills.path 已修正为 ./skills）
├── config.example.yaml          # 配置模板
├── extensions_config.json       # MCP 配置（URL 已修正为 127.0.0.1）
├── extensions_config.example.json # MCP 配置模板
├── .env.example                 # 环境变量模板
└── README.md                    # 部署使用说明（来自 docs/operations/USE_GUIDE.md）
```

---

## 5. 快速决策表

| 你的场景 | 推荐方式 | 参考章节 |
|---------|---------|---------|
| 🏆 **日常工作流** | 本机编译前端 → 56 编译后端 | 2.1（主要方式） |
| 本机和服务器架构一致，想一次搞定 | 本机全量编译 | 2.2（备选 A） |
| 只想编译后端测试 | 本机纯后端编译 | 2.3（备选 B） |
| 已在本机完成全量编译，直接部署 | 全量编译后传输 | 2.4（备选 C） |

---

## 6. 常见问题

### Q: 编译后端时提示 Python 3.12 找不到？
`build-backend-on-server.sh` 会自动从源码编译安装 Python 3.12.9，耗时约 5-10 分钟。
若服务器已安装 Python 3.12，会自动检测并跳过安装步骤。

### Q: 编译或启动时 numpy 报 CPU 指令集不兼容？
```
RuntimeError: NumPy was built with baseline optimizations:
(X86_V2) but your machine doesn't support:
(X86_V2).
```

**根因**：编译机和运行机的 CPU 架构不一致。NumPy 在安装时检测当前 CPU 启用高级指令集优化，PyInstaller 编译后无法在旧 CPU 上降级。

**已修复（2026-05-12）**：`build-backend.sh` 和 `build-backend-on-server.sh` 均已内置 numpy 降级，编译时自动执行 `uv pip install "numpy<2"`，**无需手动降级**。

如果仍然遇到，说明脚本不是最新版本，拉取最新脚本后直接编译即可。

详细排查见 `OPERATIONS.md` → NumPy CPU 指令集不兼容。

### Q: 前端启动报 Module not found: @/...？
检查 `release/frontend/` 是否包含 `tsconfig.json`、`postcss.config.js`、`components.json`、`styles/` 文件。这些是 Next.js 路径别名和样式所必需的。

### Q: 启动后 Pro/Ultra 模式灰色不可选？
`config.yaml` 中模型配置缺少 `supports_thinking: true`，添加后重启即可。

---

## 5. Release 常见坑点

### 5.1 `deerflow_entry.py` 必须 import 模块级 `app`，不能调 `create_app()`

```python
# ✅ 正确
from app.gateway.app import app

# ❌ 错误 — 导致双重 create_app()，ADS 路由注册到错误实例 → 404
from app.gateway.app import create_app
app = create_app()
```

**根因**：`import create_app` 触发模块级 `app = create_app()`（App #1），显式调用又创建 App #2。`install_ads_auth()` 有 `_installed` 防重入，只在 App #1 生效 → uvicorn 运行 App #2 → 404。

### 5.2 `cp` 必须用整个目录复制，不加 `/*`

```bash
# ✅ 正确 — 保持 backend-bin/deerflow-gateway/(二进制+_internal/) 结构
rm -rf /usr/xccloud/deerflow/backend-bin
cp -r dist/deerflow-gateway /usr/xccloud/deerflow/backend-bin/

# ❌ 错误 — 摊平结构，server-release.sh 路径不匹配
cp -r dist/deerflow-gateway/* /usr/xccloud/deerflow/backend-bin/
```

服务器编译脚本 `@./backend/scripts/build-backend-on-server.sh` 头部已包含完整注意事项。

---

**最后更新**：2026-06-02
**关联文件**：
- `scripts/build-release.sh`
- `backend/build-backend.sh`
- `backend/scripts/build-backend-on-server.sh`
- `scripts/server-release.sh`
- `docs/operations/DEPLOYMENT_KNOWN_ISSUES.md`
