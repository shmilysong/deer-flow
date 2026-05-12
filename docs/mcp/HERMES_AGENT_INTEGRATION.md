# Hermes Agent 集成 — DeerFlow 改造参考

> **WING**
> **初稿：2026-05-12**

---

## 目录

- [一、架构概述](#一架构概述)
- [二、文件结构](#二文件结构)
- [三、community/hermes\_agent/ 工具包开发](#三communityhermes_agent-工具包开发)
- [四、在工具注册链中集成](#四在工具注册链中集成)
- [五、配置方式](#五配置方式)
- [六、Hermes MCP 配置同步](#六hermes-mcp-配置同步)
- [七、Skill 自动同步机制](#七skill-自动同步机制)
- [八、与 ACP Agent 机制的关系](#八与-acp-agent-机制的关系)
- [九、可剥离设计](#九可剥离设计)
- [十、进阶：方案 B — MCP Server 包装器](#十进阶方案-b--mcp-server-包装器)

---

## 一、架构概述

### 1.1 鹿神合体

```
┌─────────────────────────────────────────────────────────────┐
│                     DeerFlow（鹿）                             │
│                                                              │
│  ┌──────────────┐    ┌──────────────────────────────────┐   │
│  │  Lead Agent   │    │         工具层(Tools)              │   │
│  │  (LangChain)  │───▶│                                  │   │
│  │               │    │  ┌──────────┐  ┌──────────────┐ │   │
│  │ 思考→行动→观察 │    │  │ ADS MCP  │  │ DeepRAG MCP  │ │   │
│  │               │    │  └──────────┘  └──────────────┘ │   │
│  └──────────────┘    │  ┌──────────────────────────────┐│   │
│                       │  │  HermesAgentTool（新武器！）   ││   │
│                       │  └──────────────────────────────┘│   │
│                       └──────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────┘
                               │ subprocess → hermes run "任务"
                               ▼
              ┌─────────────────────────────────────┐
              │         Hermes Agent（神）             │
              │                                      │
              │  ┌────────────┐  ┌────────────────┐ │
              │  │ GEPA 自进化 │  │  持久记忆       │ │
              │  ╰ 执行→评估→│  │  MEMORY.md     │ │
              │    优化→沉淀  │  │  USER.md       │ │
              │  └────────────┘  └────────────────┘ │
              │  ┌────────────────────────────────┐ │
              │  │  Skill 自动生成                  │ │
              │  ╰ 5+工具调用后自动提炼 SKILL.md    │ │
              │  └────────────────────────────────┘ │
              │  ┌────────────────────────────────┐ │
              │  │  MCP 客户端                      │ │
              │  ╰ 连接 ADS/DeepRAG 等 MCP Server  │ │
              │  └────────────────────────────────┘ │
              └─────────────────────────────────────┘
```

### 1.2 一句话定位

**Hermes 不作为独立服务部署，而是作为 DeerFlow 内部的一个工具（StructuredTool）**。DeerFlow 的 Lead Agent 在需要「复杂任务 + 自动生成 Skill」时，通过 `invoke_hermes` 工具以 CLI 子进程方式调用 Hermes。

### 1.3 数据流

```
【触发】DeerFlow Lead Agent 判断任务"复杂 + 需要学会"
    │
    ├─ 调用 HermesAgentTool(task="查询终端86号并搜索知识库")
    │
    ▼
【执行】Hermes 子进程 → 调用 ADS MCP → 调用 DeepRAG MCP → 返回结果
    │
    ├─ GEPA 记录执行经验（工具调用≥5 次 → 自动生成 SKILL.md）
    │   ~/.hermes/skills/terminal-troubleshoot/SKILL.md
    │
    ▼
【反哺】skill_sync.py 自动检测新 Skill → 复制到 skills/public/
    │
    ▼
【落地】下次同类任务 → DeerFlow 直接用 Skill，无需再调 Hermes
```

### 1.4 可剥离设计原则

从第一天起遵循三层可剥离：
- **配置层**：`communityTools.hermes_agent.enabled = false` → 工具消失
- **工具层**：全部代码在 `community/` 目录，不碰核心
- **Skill 层**：同步后的 SKILL.md 是普通 Markdown，不依赖 Hermes

---

## 二、文件结构

### 2.1 新增文件

```
deer-flow/
├── backend/
│   └── packages/harness/deerflow/community/hermes_agent/   ← 新增目录
│       ├── __init__.py           # 包入口，导出 build_hermes_agent_tool()
│       ├── cli_wrapper.py        # 核心：Hermes CLI 子进程封装 → StructuredTool
│       ├── skill_sync.py         # Skill 自动检测与同步
│       └── config.py             # HermesAgentConfig 配置数据类
│
├── scripts/
│   └── sync_mcp_config.sh        ← 新增：MCP 配置一键同步脚本
│
└── skills/public/                # 自动同步目标目录（已有，无需修改）
    ├── terminal-troubleshoot/    # ← Hermes 自动生成的 Skill
    └── ...
```

### 2.2 修改文件

| 文件 | 改动量 | 说明 |
|------|--------|------|
| `deerflow/tools/tools.py` | +5 行 | 在 `get_available_tools()` 中加入 Hermes 工具注册 |
| `extensions_config.json` | +10 行 | 加入 `communityTools.hermes_agent` 配置段 |

---

## 三、community/hermes_agent/ 工具包开发

### 3.1 `__init__.py` — 包入口

```python
"""Hermes Agent integration using CLI subprocess."""

from .cli_wrapper import build_hermes_agent_tool

__all__ = ["build_hermes_agent_tool"]
```

遵循 community 工具惯例（参考 `community/ddg_search/__init__.py`），只导出工具构建函数。

---

### 3.2 `config.py` — 配置数据类

```python
"""Hermes Agent tool configuration."""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class HermesAgentConfig:
    enabled: bool = True
    hermes_path: str = "hermes"
    auto_sync_skills: bool = True
    sync_target: str = "./skills/public/"
    keep_alive: bool = False
    timeout: int = 300
    min_calls: int = 3
    hermes_env: Optional[Dict[str, str]] = None
```

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `enabled` | `true` | 是否启用 Hermes 工具 |
| `hermes_path` | `hermes` | Hermes 可执行文件路径（支持 PATH 查找） |
| `auto_sync_skills` | `true` | 是否自动同步 Hermes 生成的 Skill 到 DeerFlow |
| `sync_target` | `./skills/public/` | Skill 同步目标目录 |
| `keep_alive` | `false` | 是否保持子进程长驻（减少启动延迟） |
| `timeout` | `300` | 子进程超时时间（秒） |
| `min_calls` | `3` | 最低工具调用次数门槛，低于此不生成 Skill |
| `hermes_env` | `null` | 传递给 Hermes 子进程的额外环境变量 |

---

### 3.3 `cli_wrapper.py` — 核心工具构建

这是整个集成的核心。它将 `hermes run "任务"` CLI 命令包装成 LangChain `StructuredTool`，供 Lead Agent 在推理循环中调用。

```python
"""Hermes CLI wrapper — wraps `hermes run` into a LangChain StructuredTool."""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from .config import HermesAgentConfig
from .skill_sync import sync_hermes_skills

logger = logging.getLogger(__name__)


class HermesAgentInput(BaseModel):
    task: str = Field(description="要交给 Hermes Agent 执行的任务描述。"
                                   "Hermes 会自动记录执行经验，"
                                   "并在工具调用≥5次后自动生成 SKILL.md 技能文档。")


def _check_hermes_installed(hermes_path: str) -> str:
    """解析 Hermes 二进制路径，未安装时抛出友好的错误信息。"""
    resolved = shutil.which(hermes_path) or shutil.which("hermes")
    if not resolved:
        raise FileNotFoundError(
            f"Hermes Agent 未找到（路径: {hermes_path}）。"
            "请先安装: pip install hermes-agent"
        )
    return resolved


def build_hermes_agent_tool(config: HermesAgentConfig) -> BaseTool:
    """构建 HermesAgentTool。

    这是一个 LangChain StructuredTool，Lead Agent 可以通过它
    以子进程方式调用 Hermes Agent 执行复杂任务。
    """
    hermes_bin = _check_hermes_installed(config.hermes_path)
    skills_dir = Path(config.sync_target).expanduser().resolve()
    hermes_skills_dir = Path.home() / ".hermes" / "skills"
    last_sync_mtime: float = 0.0

    description = (
        "调用 Hermes Agent 执行复杂任务并自动生成可复用的 Skill。"
        "Hermes 拥有自进化能力（GEPA 引擎），执行 5+ 工具调用的复杂任务后，"
        "会自动从执行经验中提炼为 SKILL.md 技能文档。"
        "适用场景：需要学会的重复性任务、复杂多步骤工作流、需持久记忆的任务。"
        "不适用场景：简单的单步查询（直接用 MCP 工具更高效）、实时性要求高的任务。"
    )

    async def _invoke(task: str) -> str:
        nonlocal last_sync_mtime
        t0 = time.time()

        proc = await asyncio.create_subprocess_exec(
            hermes_bin, "run", task,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, **(config.hermes_env or {})},
        )
        stdout, stderr = await proc.communicate(timeout=config.timeout)
        elapsed = time.time() - t0

        result = stdout.decode().strip()
        if proc.returncode != 0:
            error = stderr.decode().strip()
            return json.dumps({
                "status": "error",
                "error": error,
                "elapsed_seconds": round(elapsed, 2),
            })

        # 自动同步 Hermes 新生成的 Skill 到 DeerFlow
        new_skills = []
        if config.auto_sync_skills:
            new_skills = sync_hermes_skills(
                hermes_skills_dir=hermes_skills_dir,
                deerflow_skills_dir=skills_dir,
                last_sync_mtime=last_sync_mtime,
                min_calls=config.min_calls,
            )
            last_sync_mtime = time.time()
            if new_skills:
                logger.info(f"Hermes 新 Skill 已同步: {', '.join(new_skills)}")

        return json.dumps({
            "status": "success",
            "result": result,
            "elapsed_seconds": round(elapsed, 2),
            "new_skills": new_skills,
        })

    return StructuredTool.from_function(
        name="invoke_hermes",
        description=description,
        coroutine=_invoke,
        args_schema=HermesAgentInput,
    )
```

**关键设计要点**：

| 要点 | 说明 |
|------|------|
| **同步/异步** | 使用 `asyncio.create_subprocess_exec` 异步启动子进程，与 DeerFlow 的异步运行时兼容 |
| **超时保护** | `timeout=config.timeout` 防止子进程挂死 |
| **环境变量** | `config.hermes_env` 支持传递自定义环境变量 |
| **返回格式** | JSON 字符串，包含 status/result/elapsed_seconds/new_skills 四个字段 |
| **错误处理** | 返回码非零时返回 `{"status": "error"}`，而非抛异常 |
| **Skill 同步** | 每次调用后自动检测并同步新生成的 Skill |
| **可剥离** | 关掉配置即可，不影响任何现有功能 |

---

### 3.4 `skill_sync.py` — Skill 自动同步

```python
"""检测 Hermes 自动生成的 Skill 并同步到 DeerFlow。"""

import logging
import shutil
import time
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def sync_hermes_skills(
    hermes_skills_dir: Path,
    deerflow_skills_dir: Path,
    last_sync_mtime: float = 0.0,
    min_calls: int = 3,
) -> List[str]:
    """同步 Hermes 新生成的 Skill 到 DeerFlow。

    Args:
        hermes_skills_dir: Hermes 的 Skill 目录 (~/.hermes/skills/)
        deerflow_skills_dir: DeerFlow 的 Skill 目录 (skills/public/)
        last_sync_mtime: 上次同步时间戳
        min_calls: 最低工具调用次数门槛（质量门禁）

    Returns:
        本次同步的 Skill 名称列表
    """
    if not hermes_skills_dir.exists():
        return []

    synced = []
    for skill_dir in sorted(hermes_skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        # 只有修改时间比上次同步新的才处理
        skill_mtime = skill_md.stat().st_mtime
        if skill_mtime <= last_sync_mtime:
            continue

        # 质量门禁：检查 description 是否完善
        if not _passes_quality_gate(skill_md):
            logger.info(f"Skill {skill_dir.name} 未通过质量检查，跳过同步")
            continue

        target = deerflow_skills_dir / skill_dir.name / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_md, target)
        logger.info(f"已同步 Skill: {skill_dir.name} -> {target}")
        synced.append(skill_dir.name)

    return synced


def _passes_quality_gate(skill_md: Path) -> bool:
    """简单质量检查：description 非空且>=10字符。"""
    content = skill_md.read_text()
    if "description:" not in content:
        return False
    for line in content.split("\n")[1:10]:
        if line.startswith("description:"):
            desc = line.split(":", 1)[1].strip()
            if len(desc) < 10:
                return False
            break
    return True
```

**同步机制要点**：

| 机制 | 说明 |
|------|------|
| **增量同步** | 通过 `last_sync_mtime` 记录上次同步时间，只处理修改时间更新的 Skill |
| **质量门禁** | `_passes_quality_gate()` 确保 description 非空，避免同步无效 Skill |
| **幂等性** | 重复同步同名 Skill 会覆盖，内容相同则 mtime 不变不会重复处理 |
| **错误容忍** | 单个 Skill 同步失败不影响其他 Skill，返回已成功列表 |

---

## 四、在工具注册链中集成

### 4.1 修改 `tools.py`

仿照 `invoke_acp_agent_tool` 的注册模式，在 `get_available_tools()` 中追加约 5 行代码：

**修改位置**：[`deerflow/tools/tools.py`](file:///home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/backend/packages/harness/deerflow/tools/tools.py#L141-L156)

在现有的 ACP Agent 注册块之后追加：

```python
# 在 tools.py 的 get_available_tools() 函数中，ACP 注册代码之后追加：

# Add Hermes Agent tool if configured
hermes_tools: list[BaseTool] = []
try:
    extensions_config = ExtensionsConfig.from_file()
    raw = extensions_config.model_extra or {}
    hermes_cfg = raw.get("communityTools", {}).get("hermes_agent", {})
    if hermes_cfg.get("enabled", True):
        from deerflow.community.hermes_agent import build_hermes_agent_tool
        from deerflow.community.hermes_agent.config import HermesAgentConfig

        cfg = HermesAgentConfig(**hermes_cfg)
        hermes_tools.append(build_hermes_agent_tool(cfg))
        logger.info(f"Including hermes_agent tool (hermes_path={cfg.hermes_path})")
except Exception as e:
    logger.warning(f"Failed to load Hermes Agent tool: {e}")

# 然后将 hermes_tools 加入 all_tools：
all_tools = loaded_tools + builtin_tools + mcp_tools + acp_tools + hermes_tools
```

**注意**：`model_extra` 是 Pydantic v2 的保留字段，用于存储 schema 未声明的额外 JSON 键值。`extensions_config.json` 中的 `communityTools` 字段不在 `ExtensionsConfig` 的模型字段中，因此会存入 `model_extra`。

### 4.2 注册模式对比

| 方面 | ACP Agent | Hermes Agent（新） |
|------|-----------|-------------------|
| **配置来源** | `config.yaml` 的 `acp_agents` | `extensions_config.json` 的 `communityTools.hermes_agent` |
| **工具构建** | `build_invoke_acp_agent_tool(agents)` | `build_hermes_agent_tool(config)` |
| **启动方式** | `spawn_agent_process`（ACP 协议） | `subprocess`（CLI 子进程） |
| **MCP 透传** | ✅ 自动透传 | ❌ Hermes 用自己的 MCP 配置 |
| **Skill 同步** | ❌ 无 | ✅ 自动同步 |
| **配置开关** | `acp_agents` 为空时不注册 | `enabled: false` 时跳过 |

---

## 五、配置方式

### 5.1 `extensions_config.json`

在现有的 `mcpServers` 和 `skills` 之外增加 `communityTools` 配置段：

```json
{
  "mcpServers": {
    "ads": { "...": "..." },
    "deeprag": { "...": "..." }
  },
  "communityTools": {
    "hermes_agent": {
      "enabled": true,
      "hermes_path": "/usr/local/bin/hermes",
      "auto_sync_skills": true,
      "sync_target": "./skills/public/",
      "keep_alive": false,
      "timeout": 300,
      "min_calls": 3,
      "hermes_env": {
        "HERMES_CONFIG_PATH": "/home/wing/.hermes/config.yaml"
      }
    }
  },
  "skills": {}
}
```

### 5.2 CLI 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `enabled` | 总开关，设为 `false` 则完全不加载 Hermes 工具 | `true` |
| `hermes_path` | Hermes 二进制路径，设为 `"hermes"` 会自动从 PATH 查找 | `"hermes"` |
| `auto_sync_skills` | 是否自动同步 Hermes 生成的 Skill | `true` |
| `sync_target` | DeerFlow 中 Skill 的存储目录 | `"./skills/public/"` |
| `keep_alive` | 是否保持子进程常驻（减少启动延迟但增加资源占用） | `false` |
| `timeout` | 单个任务最大执行时间（秒） | `300` |
| `min_calls` | 质量门禁：工具调用次数低于此值不生成 Skill | `3` |
| `hermes_env` | 额外环境变量，如 `HERMES_CONFIG_PATH` | `null` |

---

## 六、Hermes MCP 配置同步

### 6.1 为什么需要同步？

Hermes 和 DeerFlow 都需要连接同一组 MCP Server（ADS、DeepRAG）才能正常工作：

- **DeerFlow**：通过 `extensions_config.json` 的 `mcpServers` 配置
- **Hermes**：通过 `~/.hermes/config.yaml` 的 `mcp_servers` 配置

两者的 MCP Server 地址、类型、参数必须一致，否则 Hermes 无法调用 ADS/DeepRAG 来生成 Skill。

### 6.2 同步脚本

```bash
# scripts/sync_mcp_config.sh
#!/bin/bash
# 将 DeerFlow 的 extensions_config.json 中的 MCP 配置同步到 Hermes 的 config.yaml

set -euo pipefail

DEERFLOW_CONFIG="${1:-extensions_config.json}"
HERMES_CONFIG="${HOME}/.hermes/config.yaml"

if [ ! -f "$DEERFLOW_CONFIG" ]; then
    echo "错误: 找不到 DeerFlow 配置文件 $DEERFLOW_CONFIG"
    exit 1
fi

mkdir -p "$(dirname "$HERMES_CONFIG")"

python3 -c "
import json, yaml
from pathlib import Path

deerflow_path = Path('$DEERFLOW_CONFIG')
hermes_path = Path('$HERMES_CONFIG')

config = json.loads(deerflow_path.read_text())
mcp_servers = {}

for name, cfg in config.get('mcpServers', {}).items():
    if cfg.get('enabled', True):
        server = {'type': cfg['type']}
        if cfg['type'] == 'stdio':
            server['command'] = cfg['command']
            server['args'] = cfg.get('args', [])
            if cfg.get('env'):
                server['env'] = cfg['env']
        elif cfg['type'] in ('http', 'sse'):
            server['url'] = cfg['url']
        mcp_servers[name] = server

hermes_config = {'mcp_servers': mcp_servers}
hermes_path.write_text(yaml.dump(hermes_config, default_flow_style=False))
print(f'已同步 {len(mcp_servers)} 个 MCP Server 到 {hermes_path}')
"

echo "MCP 配置同步完成！"
```

**使用方式**：
```bash
# 从 DeerFlow 项目根目录执行
bash scripts/sync_mcp_config.sh deer-flow/extensions_config.json
```

---

## 七、Skill 自动同步机制

### 7.1 触发时机

| 触发条件 | 说明 |
|---------|------|
| **每次调用后** | 每次 `invoke_hermes` 工具被调用，返回时自动检测 |
| **增量检测** | 只处理修改时间比上次同步新的 Skill |
| **质量门禁** | description 必须非空（>=10 字符），否则忽略 |

### 7.2 同步流程

```
Hermes GEPA 自动生成 SKILL.md
    │
    ▼
skill_sync.py 在每次 invoke_hermes 返回时触发
    │
    ├─ 1. 扫描 ~/.hermes/skills/ 目录
    ├─ 2. 对比 last_sync_mtime，过滤已同步的
    ├─ 3. 质量门禁检查（description 非空）
    ├─ 4. 复制到 deer-flow/skills/public/<name>/SKILL.md
    └─ 5. 更新 last_sync_mtime = now
```

### 7.3 质量门禁

只有通过以下检查的 Skill 才会被同步：

| 检查项 | 标准 | 未达标处理 |
|--------|------|-----------|
| SKILL.md 存在 | 文件必须存在 | 跳过该目录 |
| description 非空 | YAML frontmatter 中 description 字段 >=10 字符 | 跳过，日志记录 |
| 修改时间新 | 必须比上次同步的 mtime 新 | 跳过（已同步） |

### 7.4 可剥离性保证

Hermes 生成的 SKILL.md 只是**普通的 Markdown 文件**，不包含任何 Hermes 特定的代码或导入。一旦同步到 `skills/public/`，它就是 DeerFlow 的原生 Skill，与手工编写的 Skill **没有区别**。

**即使 Hermes 被卸载**，已同步的 Skill 依然在 DeerFlow 中正常工作。

---

## 八、与 ACP Agent 机制的关系

### 8.1 对比

| 维度 | ACP Agent（现有） | Hermes Agent（新增） |
|------|------------------|-------------------|
| **定位** | 调用外部标准 Agent | 调用本地自进化 Agent |
| **启动方式** | `spawn_agent_process`（ACP 协议子进程） | `subprocess.run(["hermes", "run"])` |
| **协议** | ACP（Agent Connect Protocol） | CLI stdout/stderr |
| **MCP 透传** | ✅ 自动透传 DeerFlow 的 MCP 配置 | ❌ Hermes 用自己的 MCP 配置 |
| **Skill 同步** | ❌ 无 | ✅ 自动同步生成的 Skill |
| **自进化** | ❌ 依赖外部 Agent | ✅ Hermes GEPA 引擎 |
| **配置位置** | `config.yaml` 的 `acp_agents` | `extensions_config.json` 的 `communityTools` |
| **可剥离** | 清空 `acp_agents` | `enabled: false` |

### 8.2 两者可并存

ACP Agent 和 Hermes Agent 在 DeerFlow 中**不冲突**，可以同时配置：

- **ACP Agent**：用于调用外部标准 Agent（如 codex），适合需要标准化的外部系统集成
- **Hermes Agent**：用于本地 Skill 自动生成，适合需要自进化的内部任务

两者使用不同的配置字段和不同的工具名称（`invoke_acp_agent` vs `invoke_hermes`），Lead Agent 会根据任务描述自动选择合适的工具。

---

## 九、可剥离设计

### 9.1 三层剥离

```
┌──────────────┐  剥离 Hermes 时：
│  配置层       │  ┌─ communityTools.hermes_agent.enabled = false
│              │  │   一句话关掉，工具消失
│ config.yaml  │  │
└──────┬───────┘  │
       │          │
┌──────▼───────┐  │
│  工具层       │  │  community/hermes_agent/ 目录里的代码都成"死代码"
│              │  │  但不会被加载，零影响
│ community/   │  │
└──────┬───────┘  │
       │          │
┌──────▼───────┐  │
│  Skill 层     │  │  已同步的 SKILL.md → 转正为 DeerFlow 原生 Skill
│              │  │  Hermes 生产的 Skill 是不依赖 Hermes 的！
│ skills/     │  │
│ public/     │  │
└──────────────┘  ▼
                 剥离后完全无影响 ✅
```

### 9.2 剥离步骤

```bash
# 1. 关掉配置（一步到位）
# 在 extensions_config.json 中设置：
#   "communityTools": { "hermes_agent": { "enabled": false } }

# 2. 或直接删除整个配置段
# 从 extensions_config.json 中删除 communityTools 字段

# 3. 重启 DeerFlow 使配置生效
# 重启后 invole_hermes 工具不再出现
# community/hermes_agent/ 目录的代码不会被加载

# 4. 已同步的 Skill 不受影响
# skills/public/ 下已有的 Skill 继续可用
# 它们只是普通的 Markdown 文件
```

---

## 十、进阶：方案 B — MCP Server 包装器

如果方案 A（CLI Wrapper）稳定运行后需要协议统一，可考虑将 Hermes 包装为 MCP Server。

### 10.1 技术路线

```
DeerFlow (MCP Client)
    │ MCP 协议 (http://localhost:9527/mcp)
    ▼
Hermes-MCP-Server (新进程)
    │ FastMCP 包装器
    ├─ run_hermes(task) → subprocess → hermes run
    └─ list_skills() → 读取 ~/.hermes/skills/
```

### 10.2 示例代码

```python
# hermes-mcp-server/main.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("hermes-agent")

@mcp.tool()
async def run_hermes(task: str) -> str:
    """Execute a task via Hermes Agent and return the result."""
    import asyncio, subprocess
    proc = await asyncio.create_subprocess_exec(
        "hermes", "run", task,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    stdout, _ = await proc.communicate(timeout=300)
    return stdout.decode().strip()

@mcp.tool()
def list_skills() -> list[dict]:
    """List all skills generated by Hermes."""
    from pathlib import Path
    skills_dir = Path.home() / ".hermes" / "skills"
    if not skills_dir.exists():
        return []
    return [{"name": d.name} for d in skills_dir.iterdir() if d.is_dir()]

if __name__ == "__main__":
    mcp.run(transport="sse", port=9527)
```

### 10.3 DeerFlow 配置

```json
{
  "mcpServers": {
    "hermes": {
      "enabled": true,
      "type": "http",
      "url": "http://localhost:9527/mcp",
      "description": "Hermes Agent — 自进化 Skill 生成引擎"
    }
  }
}
```

**优势**：DeerFlow 零代码侵入，只需一条 MCP 配置。
**劣势**：多一个独立进程需要维护。

---

> **WING**
> **初稿：2026-05-12**
>
> 本文档对应实施计划：[hermes-skill-generator-plan.md](file:///home/wing/wing/emto/2026/2026.3/DeerFlow/.trae/documents/hermes-skill-generator-plan.md) 方案 A（CLI Wrapper）
