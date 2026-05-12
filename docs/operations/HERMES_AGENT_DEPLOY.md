# Hermes Agent 部署配置参考

> **WING**
> **初稿：2026-05-12**
> **本文档面向人工操作：安装 → 配置 → 验证 → 运维**

---

## 目录

- [一、概述](#一概述)
- [二、部署前检查清单](#二部署前检查清单)
- [三、安装 Hermes Agent](#三安装-hermes-agent)
- [四、配置 Hermes 的 MCP 连接](#四配置-hermes-的-mcp-连接)
- [五、验证 Hermes 独立运行](#五验证-hermes-独立运行)
- [六、在 DeerFlow 中配置对接](#六在-deerflow-中配置对接)
- [七、端到端验证](#七端到端验证)
- [八、日常运维指南](#八日常运维指南)
- [九、卸载与可剥离](#九卸载与可剥离)
- [十、常见问题排查](#十常见问题排查)

---

## 一、概述

### 1.1 架构

```
本机（x86_64）
┌─────────────────────────────────────────────────┐
│  DeerFlow（鹿）                                   │
│    Lead Agent ──→ invoke_hermes 工具              │
│                        │                         │
│                        │ subprocess              │
│                        ▼                         │
│                   Hermes Agent（神）               │
│                        │                         │
│                  ┌─────┴─────┐                   │
│                  ▼           ▼                   │
│            ADS MCP    DeepRAG MCP                │
│            (云桌面)     (知识库检索)                │
└─────────────────────────────────────────────────┘
```

### 1.2 一句话定位

**Hermes Agent 作为 DeerFlow 的「技能生成引擎」**，安装在 DeerFlow 同一台机器上。DeerFlow 的 Lead Agent 在需要时通过 CLI 子进程调用她，她执行复杂任务后自动生成 Skill 并反哺给 DeerFlow。

### 1.3 前置条件

| 条件 | 要求 | 说明 |
|------|------|------|
| **操作系统** | Linux (x86_64) | 当前开发机满足条件 |
| **Python** | 3.11+ | 建议 3.12（与 DeerFlow 一致） |
| **pip/uv** | 可用 | 用于安装 Hermes |
| **DeerFlow** | 已正常运行 | 确保 ADS MCP 和 DeepRAG MCP 已在 DeerFlow 中配置 |

---

## 二、部署前检查清单

动手前先确认以下项 ✅：

- [ ] `uname -m` 输出为 `x86_64`（确认架构）
- [ ] `python3 --version` >= 3.11
- [ ] `pip3 --version` 可用
- [ ] DeerFlow 已正常运行（`docker ps` 或 `make dev`）
- [ ] ADS MCP 已在 [extensions_config.json](file:///home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/extensions_config.json) 中配置 ✅（当前已有）
- [ ] DeepRAG MCP 已配置 ✅（当前已有）
- [ ] 本机能访问 ADS 服务器（`curl http://192.168.1.139:80` 通）
- [ ] 本机能访问 DeepRAG 服务（`curl http://192.168.1.56:86/mcp` 通）

---

## 三、安装 Hermes Agent

### 3.1 安装

```bash
# 建议在独立 virtualenv 中安装，避免污染 DeerFlow 的 Python 环境
python3 -m venv ~/.venvs/hermes
source ~/.venvs/hermes/bin/activate

# 安装 hermes-agent
pip install hermes-agent

# 验证安装
hermes --help
```

如果 `hermes` 命令不在 PATH 中，记下路径：
```bash
which hermes
# 输出示例：/home/wing/.venvs/hermes/bin/hermes
```

### 3.2 创建软链接（可选）

如果想把 `hermes` 命令暴露到全局 PATH：
```bash
sudo ln -s /home/wing/.venvs/hermes/bin/hermes /usr/local/bin/hermes
which hermes
# 应输出：/usr/local/bin/hermes
```

### 3.3 验证安装

```bash
hermes --version
hermes --help
```

正确输出为 Hermes Agent 的帮助信息。

---

## 四、配置 Hermes 的 MCP 连接

Hermes 需要和 DeerFlow 使用**同一组 MCP Server**（ADS、DeepRAG），才能在执行任务时调用这些工具。

### 4.1 创建配置目录和文件

```bash
mkdir -p ~/.hermes
```

创建 `~/.hermes/config.yaml`：

```yaml
# ~/.hermes/config.yaml
# Hermes Agent 的 MCP Server 配置
# 注意：必须与 DeerFlow 的 extensions_config.json 中的 MCP 配置一致

mcp_servers:
  ads:
    type: stdio
    command: node
    args:
      - /app/ads-mcp/dist/index.js
    env:
      ADS_API_BASE_URL: "http://192.168.1.139:80"
      ADS_CONFIG_PATH: "/app/ads-mcp/.ads-mcp/config.json"

  deeprag:
    type: http
    url: "http://192.168.1.56:86/mcp"
```

### 4.2 使用同步脚本（推荐，更安全）

用同步脚本自动从 DeerFlow 配置生成 Hermes 配置：

```bash
# 从 DeerFlow 项目根目录执行
cd /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow
bash scripts/sync_mcp_config.sh extensions_config.json
```

脚本会读取 `extensions_config.json` 中的 `mcpServers`，自动翻译成 Hermes 的 `~/.hermes/config.yaml` 格式。

### 4.3 验证配置文件

```bash
cat ~/.hermes/config.yaml
```

输出应包含 `ads` 和 `deeprag` 两个 MCP Server 的配置。

---

## 五、验证 Hermes 独立运行

### 5.1 验证 MCP 工具加载

```bash
hermes tools list
```

预期输出应包含 ADS MCP 和 DeepRAG MCP 的工具：
- ADS 相关工具（终端查询、开关机、用户管理等）
- DeepRAG 相关工具（知识库检索、文件搜索、同步等）

如果输出为空或报错，说明 MCP 配置有问题，回头检查第四步。

### 5.2 执行测试任务

```bash
# 简单测试：确认 Hermes 基本运行正常
hermes run "hello"

# 测试 ADS MCP 调用
hermes run "查询当前在线的 ADS 终端"

# 测试 DeepRAG MCP 调用
hermes run "在知识库中搜索关于运维的文档"
```

### 5.3 确认 Skill 生成目录存在

```bash
ls ~/.hermes/skills/
# 初始状态为空目录或不存在
# 执行复杂任务后会出现新目录
```

---

## 六、在 DeerFlow 中配置对接

### 6.1 修改 extensions_config.json

在 [extensions_config.json](file:///home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/extensions_config.json) 中增加 `communityTools.hermes_agent` 配置段：

```json
{
  "mcpServers": {
    "ads": {
      "enabled": true,
      "type": "stdio",
      "command": "node",
      "args": ["/app/ads-mcp/dist/index.js"],
      "env": {
        "ADS_API_BASE_URL": "http://192.168.1.139:80",
        "ADS_CONFIG_PATH": "/app/ads-mcp/.ads-mcp/config.json"
      },
      "description": "ADS云桌面管理系统"
    },
    "deeprag": {
      "enabled": true,
      "type": "http",
      "url": "http://192.168.1.56:86/mcp",
      "description": "DeepRAG 知识库检索"
    }
  },
  "communityTools": {
    "hermes_agent": {
      "enabled": true,
      "hermes_path": "/home/wing/.venvs/hermes/bin/hermes",
      "auto_sync_skills": true,
      "sync_target": "./skills/public/",
      "timeout": 300,
      "min_calls": 3
    }
  },
  "skills": {}
}
```

### 6.2 配置项说明

| 配置项 | 填什么 | 说明 |
|--------|--------|------|
| `enabled` | `true` | 总开关 |
| `hermes_path` | `/home/wing/.venvs/hermes/bin/hermes` | 上一节 `which hermes` 的输出 |
| `auto_sync_skills` | `true` | 自动同步 Skill（建议打开） |
| `sync_target` | `./skills/public/` | 同步到 DeerFlow 的公共 Skill 目录 |
| `timeout` | `300` | 单任务超时 5 分钟 |
| `min_calls` | `3` | 工具调用≥3次才生成 Skill |

### 6.3 重启 DeerFlow

使配置生效：

```bash
# Docker 部署
docker compose down
docker compose up -d

# 或本地部署
make restart
```

### 6.4 验证 DeerFlow 日志

```bash
docker logs deer-flow-langgraph --tail 50 | grep -i hermes
# 应看到：Including hermes_agent tool (hermes_path=...)
```

---

## 七、端到端验证

### 7.1 验证清单

- [ ] Hermes 安装完成
- [ ] Hermes MCP 配置正确（`hermes tools list` 可看到 ADS/DeepRAG 工具）
- [ ] DeerFlow 的 `extensions_config.json` 已配置 `communityTools.hermes_agent`
- [ ] DeerFlow 日志显示 Hermes 工具已加载
- [ ] 在 DeerFlow 中提问 "帮我查一下终端状态并搜索知识库，把过程学会"

### 7.2 在 DeerFlow 中触发

在 DeerFlow Web UI 或消息通道中提问：

```
帮我查一下ADS系统中有哪些终端在线，
然后在DeepRAG知识库中搜索 "终端运维" 相关的文档，
把这个过程学会生成一个Skill
```

预期流程：
1. DeerFlow Lead Agent 判断任务复杂 → 调用 `invoke_hermes` 工具
2. Hermes 子进程执行任务 → 调用 ADS MCP + DeepRAG MCP
3. Hermes GEPA 记录执行经验
4. 若工具调用≥5次 → 自动生成 SKILL.md 到 `~/.hermes/skills/`
5. `skill_sync.py` 检测到新 Skill → 同步到 `deer-flow/skills/public/`
6. DeerFlow Lead Agent 返回结果，包含 "新 Skill 已同步" 信息

### 7.3 验证新 Skill

```bash
# 查看 Hermes 生成的 Skill
ls -la ~/.hermes/skills/
cat ~/.hermes/skills/*/SKILL.md | head -20

# 查看同步到 DeerFlow 的 Skill
ls -la /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/skills/public/
cat /home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/skills/public/*/SKILL.md | head -20
```

### 7.4 验证 Skill 可用

在 DeerFlow 中再次提问，内容与之前相似但不完全相同：

```
查一下终端 86 号的状态，然后去知识库找相关的运维手册
```

如果 Lead Agent 直接使用了新同步的 Skill（而非再次调用 Hermes），说明闭环成功。

---

## 八、日常运维指南

### 8.1 查看 Hermes 日志

Hermes Agent 的日志通常输出到 stdout/stderr。通过 DeerFlow 的 `invoke_hermes` 工具调用时，日志会出现在 DeerFlow 进程的日志中：

```bash
docker logs deer-flow-langgraph --tail 50 | grep -i hermes
```

Hermes 自身的本地日志和记忆文件：
```bash
ls -la ~/.hermes/
# memory/     - 持久记忆
# skills/     - 自动生成的 Skill
# config.yaml - MCP 配置
```

### 8.2 更新 MCP 配置

当 DeerFlow 侧的 MCP 配置发生变化时（如 ADS 地址变更），需要同步到 Hermes：

```bash
# 1. 修改 extensions_config.json
# 2. 运行同步脚本
bash scripts/sync_mcp_config.sh deer-flow/extensions_config.json
# 3. Hermes 下次调用时自动读取新配置（无需重启 Hermes）
```

### 8.3 查看和管理 Hermes 生成的 Skill

```bash
# 列出所有 Hermes 生成的 Skill
ls ~/.hermes/skills/

# 查看特定 Skill 内容
cat ~/.hermes/skills/<skill-name>/SKILL.md

# 手动删除（Hermes 下次不会重新生成，除非再次触发）
rm -rf ~/.hermes/skills/<skill-name>/
```

### 8.4 更新 Hermes

```bash
source ~/.venvs/hermes/bin/activate
pip install --upgrade hermes-agent
```

更新后无需重启 DeerFlow，下此调用 `invoke_hermes` 时自动使用新版本。

### 8.5 重启 Hermes

Hermes 没有常驻进程——她是每次被 `invoke_hermes` 调用时以子进程方式启动的。所以 **不需要「重启 Hermes」**。

如果修改了 `~/.hermes/config.yaml`，下一次 `invoke_hermes` 调用会自动使用新配置。

---

## 九、卸载与可剥离

### 9.1 临时关闭

想在 DeerFlow 中临时停用 Hermes 工具，只需修改配置：

```json
{
  "communityTools": {
    "hermes_agent": {
      "enabled": false
    }
  }
}
```

重启 DeerFlow 后 `invoke_hermes` 工具消失，Lead Agent 不再能调用 Hermes。

### 9.2 完全卸载

```bash
# 1. 关掉 DeerFlow 配置
#    在 extensions_config.json 中设置 enabled: false 或删除 communityTools

# 2. 卸载 Hermes（可选）
source ~/.venvs/hermes/bin/activate
pip uninstall hermes-agent -y

# 3. 删除配置文件（可选）
rm -rf ~/.hermes/

# 4. 重启 DeerFlow
docker compose down
docker compose up -d
```

### 9.3 已同步的 Skill 不受影响

Hermes 同步到 `skills/public/` 的 Skill 只是普通 Markdown 文件。**卸载 Hermes 后这些 Skill 依然在 DeerFlow 中正常工作。**

---

## 十、常见问题排查

### 10.1 `hermes` 命令找不到

```
Error: Hermes Agent 未找到（路径: hermes）
```

**原因**：`hermes` 不在 PATH 中。

**解决**：
```bash
# 确认安装位置
find / -name "hermes" -type f 2>/dev/null

# 在 extensions_config.json 中设置完整路径
"hermes_path": "/home/wing/.venvs/hermes/bin/hermes"
```

### 10.2 Hermes MCP 工具列表为空

```
hermes tools list
# 输出为空或报错
```

**原因**：`~/.hermes/config.yaml` 配置错误或 MCP Server 不可达。

**排查**：
```bash
# 检查配置文件
cat ~/.hermes/config.yaml

# 测试 DeepRAG MCP 可达性
curl http://192.168.1.56:86/mcp

# 检查 ADS MCP 路径是否存在
ls -la /app/ads-mcp/dist/index.js
```

### 10.3 Hermes 执行任务超时

```
Error: asyncio.exceptions.TimeoutError
```

**原因**：任务执行超过 300 秒（默认 timeout）。

**解决**：
- 在 `extensions_config.json` 中调大 `timeout` 值
- 或简化任务描述，减少工具调用次数

### 10.4 Skill 未自动同步

**原因**：工具调用次数不足 `min_calls`（默认 3 次）或 description 为空。

**排查**：
```bash
# 检查 Hermes 端是否有 Skill
ls -la ~/.hermes/skills/
cat ~/.hermes/skills/*/SKILL.md | head -5
# 确认 description 字段非空
```

### 10.5 DeerFlow 日志显示 Hermes 工具加载失败

```
Failed to load Hermes Agent tool: ...
```

**原因**：`extensions_config.json` 中的 `communityTools.hermes_agent` 配置格式错误。

**排查**：
```json
// 检查 JSON 格式是否正确
// 确保 communityTools 在 mcpServers 和 skills 的同一层级
// 确保 hermes_path 不是相对路径或不存在
```

### 10.6 Hermes 生成的 Skill 质量不理想

**原因**：GEPA 引擎需要足够的执行经验才能生成高质量 Skill。

**建议**：
- 多执行几次同类复杂任务（5+ 工具调用）
- 任务描述越具体，生成的 Skill 质量越高
- 如果持续不理想，可考虑在 Week 4 的决策点切换到方案 D（自建轻量框架）

---

> **WING**
> **初稿：2026-05-12**
>
> 本文档对应实施计划：[hermes-skill-generator-plan.md](file:///home/wing/wing/emto/2026/2026.3/DeerFlow/.trae/documents/hermes-skill-generator-plan.md) 方案 A（CLI Wrapper）
>
> 关联文档：
> - [HERMES_AGENT_INTEGRATION.md](../mcp/HERMES_AGENT_INTEGRATION.md) — 开发参考（给 AI 助手的）
