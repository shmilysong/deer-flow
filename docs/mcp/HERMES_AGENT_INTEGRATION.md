# Hermes Agent 集成 — DeerFlow 改造参考

> **WING**
> **初稿：2026-05-12**

---

## 目录

- [一、架构概述](#一架构概述)
- [二、范围限定](#二范围限定)
- [三、文件结构](#三文件结构)
- [四、community/hermes\_agent/ 工具包开发](#四communityhermes_agent-工具包开发)
- [五、在工具注册链中集成](#五在工具注册链中集成)
- [六、配置方式](#六配置方式)
- [七、Skill 自动同步机制](#七skill-自动同步机制)
- [八、任务权责与决策流程](#八任务权责与决策流程)
- [九、可剥离设计](#九可剥离设计)
- [十、进阶：方案 B — MCP Server 包装器](#十进阶方案-b--mcp-server-包装器)

---

## 一、架构概述

### 1.1 「鹿神合体」新范式

```
┌──────────────────────────────────────────────────────────────────┐
│                        DeerFlow（鹿）                             │
│                       主执行者 + 决策者                            │
│                                                                  │
│  ┌────────────────────┐    ┌──────────────────────────────────┐  │
│  │   Lead Agent (LLM)  │    │         工具层(Tools)             │  │
│  │                     │───▶│                                  │  │
│  │  system prompt 指导  │    │  ┌──────────┐  ┌──────────────┐│  │
│  │  优先级：找Skill→    │    │  │ ADS MCP  │  │ DeepRAG MCP  ││  │
│  │  评估→创建→优化     │    │  └──────────┘  └──────────────┘│  │
│  └────────────────────┘    └──────────────────────────────────┘  │
│           │                        │                             │
│           │ ① invoke_hermes_create │ ② invoke_hermes_optimize    │
│           ▼                        ▼                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Hermes Agent（神）—— 教练                      │   │
│  │                                                          │   │
│  │  创建模式: GEPA 记录完整执行经验 → 生成通用 Skill           │   │
│  │  优化模式: GEPA 再次执行 + 对比旧 Skill → 生成 v2          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              审计系统（audit system）                       │   │
│  │  每次 Skill 执行 → 记录审计日志 → 自评 → 决策是否优化      │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 一句话定位

**DeerFlow 是主执行者和决策者，Hermes 是教练**。

- **DeerFlow** 用自己的 MCP 工具（ADS、DeepRAG）执行任务、记录审计、自评决策
- **Hermes** 只在两个时机介入：创建新 Skill（`invoke_hermes_create`）和优化已有 Skill（`invoke_hermes_optimize`）
- **执行权始终在 DeerFlow 手中**，她不是传话筒

### 1.3 数据流：Skill 全生命周期

```
【阶段一：创建】
  DeerFlow 遇到 ≥5 步新任务且无匹配 Skill
    → invoke_hermes_create(task) → Hermes 完整执行
    → GEPA 记录完整心智状态 → 生成通用 SKILL.md（参数化）
    → skill_sync 同步到 skills/public/

【阶段二：独立使用】
  DeerFlow 再次遇到同类任务
    → 在 skills/public/ 中找到匹配 Skill
    → 按 Skill 的通用步骤自行适配参数 → 用自己的 MCP 执行
    → 记录审计日志（audit.py）
    → 4 维度自评：成功率 / 效率 / 质量 / 满意度

【阶段三：持续优化】
  自评总分 < 8 且使用次数 < 5（前期激进策略）
    → invoke_hermes_optimize(skill_name, audit_data)
    → Hermes 再次完整执行该任务
    → GEPA 记录最新经验 → 与旧 SKILL.md 对比
    → 生成优化版 v2 → 覆盖旧版本
```

### 1.4 范围限定

**以上所有规则仅适用于 ADS MCP 和 DeepRAG MCP 的工具**。其他 MCP Server 和内置工具不受此规则影响。

### 1.5 可剥离设计原则

从第一天起遵循三层可剥离：
- **配置层**：`communityTools.hermes_agent.enabled = false` → 工具消失
- **工具层**：全部代码在 `community/` 目录，不碰核心
- **Skill 层**：同步后的 SKILL.md 是普通 Markdown，不依赖 Hermes

---

## 二、范围限定

**Hermes 集成只在处理 ADS MCP 和 DeepRAG MCP 工具时生效。** 其他 MCP Server 和内置工具完全不受影响。

具体来说：
- Lead Agent 只在任务涉及 ADS MCP 或 DeepRAG MCP 的工具时，才进入 Skill 判断流程
- `invoke_hermes_create` 只用于生成涉及 ADS/DeepRAG 的 Skill
- `invoke_hermes_optimize` 只优化涉及 ADS/DeepRAG 的 Skill
- 其他工具（搜索、沙箱、文件等）保持原样，不参与任何 Hermes 流程

---

## 三、文件结构

### 3.1 新增文件

```
deer-flow/
├── backend/
│   └── packages/harness/deerflow/community/hermes_agent/   ← 新增目录
│       ├── __init__.py              # 包入口，导出 2 个工具构建函数
│       ├── cli_wrapper.py           # 核心：Hermes CLI 子进程封装
│       │                            # 含 build_hermes_create_tool()
│       │                            # 含 build_hermes_optimize_tool()
│       ├── audit.py                 # 审计日志系统（新增！）
│       │                            # log_skill_execution()
│       │                            # get_recent_records()
│       │                            # get_skill_stats()
│       ├── optimizer.py             # 自评与优化决策（新增！）
│       │                            # self_evaluate()
│       │                            # should_trigger_optimization()
│       └── skill_sync.py            # Skill 检测 + 同步 + 通用性检查
│
├── scripts/
│   └── sync_mcp_config.sh          ← 新增：MCP 配置一键同步脚本
│
└── skills/public/                   # 自动同步目标目录（已有，无需修改）
    ├── terminal-inspection-report/ # ← Hermes 生成的通用 Skill
    └── ...
```

### 3.2 修改文件

| 文件 | 改动量 | 说明 |
|------|--------|------|
| `deerflow/tools/tools.py` | +15 行 | 在 `get_available_tools()` 中注册 2 个 Hermes 工具 |
| `agents/lead_agent/prompts.py` | +30 行 | 注入 `SYSTEM_PROMPT_SKILL_RULES`（4 条优先级规则） |
| `extensions_config.json` | +10 行 | 加入 `communityTools.hermes_agent` 配置段 |

---

## 四、community/hermes_agent/ 工具包开发

### 4.1 `__init__.py` — 包入口

```python
"""Hermes Agent integration — create & optimize skills via CLI subprocess."""

from .cli_wrapper import build_hermes_create_tool, build_hermes_optimize_tool

__all__ = ["build_hermes_create_tool", "build_hermes_optimize_tool"]
```

### 4.2 `cli_wrapper.py` — 两个核心工具

与旧版不同，此处不再只有一个 `invoke_hermes` 工具，而是拆分为**两个独立工具**：

| 工具 | 函数 | 用途 | 调用时机 |
|------|------|------|---------|
| `invoke_hermes_create` | `build_hermes_create_tool()` | 让 Hermes 完整执行一次任务，GEPA 生成 Skill | 首次遇到 ≥5 步新任务且无匹配 Skill |
| `invoke_hermes_optimize` | `build_hermes_optimize_tool()` | 让 Hermes 再次执行，GEPA 对比旧 Skill 后升级 | 自评总分 < 8 且使用次数 < 5 时 |

```python
"""Hermes CLI wrapper — wraps `hermes run` into two LangChain StructuredTools."""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from .audit import get_recent_records
from .optimizer import self_evaluate, should_trigger_optimization
from .skill_sync import sync_hermes_skills

logger = logging.getLogger(__name__)

# ── 输入 Schema ────────────────────────────────────────────

class HermesCreateInput(BaseModel):
    task: str = Field(description="要交给 Hermes Agent 执行并学会的任务描述。"
                                   "适合 ≥5 步的复杂任务。"
                                   "Hermes 会完整执行并自动生成通用的 SKILL.md。")

class HermesOptimizeInput(BaseModel):
    skill_name: str = Field(description="要优化的 Skill 名称")
    task: str = Field(description="原始任务描述，用于让 Hermes 重新执行以获取最新经验")

# ── 通用逻辑 ──────────────────────────────────────────────

def _check_hermes_installed(hermes_path: str) -> str:
    """解析 Hermes 二进制路径，未安装时抛出友好的错误信息。"""
    resolved = shutil.which(hermes_path) or shutil.which("hermes")
    if not resolved:
        raise FileNotFoundError(
            f"Hermes Agent 未找到（路径: {hermes_path}）。"
            "请先安装: pip install hermes-agent"
        )
    return resolved


def _build_universal_prompt(original_task: str) -> str:
    """在任务描述末尾追加通用性约束，确保 Hermes 生成参数化的 Skill。"""
    return f"""
{original_task}

【重要：Skill 通用性要求】
在你完成任务后，GEPA 会自动生成 SKILL.md。请确保生成的 Skill 满足以下要求：
1. **参数化**：所有具体值（终端编号、搜索关键词等）必须写成参数占位符，
   如 {终端ID}、{搜索主题}
2. **步骤抽象**：步骤描述必须是通用方法，不能引用具体实例
   ✅ "查询指定终端的运行状态"
   ❌ "查询86号终端的运行状态"
3. **适用范围**：description 中写明适用场景大类，而非单个任务
4. **输入说明**：明确说明该 Skill 需要哪些输入参数
"""


async def _run_hermes_task(hermes_bin: str, task: str, timeout: int,
                           hermes_env: dict | None) -> tuple[str, str, float]:
    """执行 hermes run 并返回 (stdout, stderr, elapsed_seconds)。"""
    t0 = time.time()
    proc = await asyncio.create_subprocess_exec(
        hermes_bin, "run", task,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**os.environ, **(hermes_env or {})},
    )
    stdout, stderr = await proc.communicate(timeout=timeout)
    elapsed = time.time() - t0
    return stdout.decode().strip(), stderr.decode().strip(), elapsed

# ── 工具 1：invoke_hermes_create ─────────────────────────

def build_hermes_create_tool(hermes_path: str, sync_target: str,
                              timeout: int = 300,
                              hermes_env: dict | None = None) -> BaseTool:
    """构建 invoke_hermes_create 工具——让 Hermes 创建通用 Skill。"""
    hermes_bin = _check_hermes_installed(hermes_path)
    skills_dir = Path(sync_target).expanduser().resolve()
    hermes_skills_dir = Path.home() / ".hermes" / "skills"
    last_sync_mtime: float = 0.0

    description = (
        "让 Hermes Agent 完整执行一次复杂任务（≥5步），"
        "GEPA 会自动记录执行经验并生成通用的 SKILL.md 技能文档。"
        "生成的 Skill 是参数化的通用版本，适用于一类场景而非单次任务。"
        "适用场景：首次遇到的复杂任务、需要学会的重复性工作流。"
        "不适用：4步以下的简单任务、已有匹配 Skill 的任务。"
    )

    async def _invoke(task: str) -> str:
        nonlocal last_sync_mtime
        prompt = _build_universal_prompt(task)
        stdout, stderr, elapsed = await _run_hermes_task(
            hermes_bin, prompt, timeout, hermes_env)

        if not stdout and stderr:
            return json.dumps({"status": "error", "error": stderr,
                               "elapsed_seconds": round(elapsed, 2)})

        new_skills = sync_hermes_skills(
            hermes_skills_dir=hermes_skills_dir,
            deerflow_skills_dir=skills_dir,
            last_sync_mtime=last_sync_mtime,
            check_universality=True,
        )
        last_sync_mtime = time.time()

        return json.dumps({
            "status": "success",
            "result": stdout,
            "elapsed_seconds": round(elapsed, 2),
            "new_skills": new_skills,
        })

    return StructuredTool.from_function(
        name="invoke_hermes_create",
        description=description,
        coroutine=_invoke,
        args_schema=HermesCreateInput,
    )

# ── 工具 2：invoke_hermes_optimize ───────────────────────

def build_hermes_optimize_tool(hermes_path: str, sync_target: str,
                                timeout: int = 300,
                                hermes_env: dict | None = None) -> BaseTool:
    """构建 invoke_hermes_optimize 工具——让 Hermes 优化已有 Skill。"""
    hermes_bin = _check_hermes_installed(hermes_path)
    skills_dir = Path(sync_target).expanduser().resolve()

    description = (
        "让 Hermes Agent 再次完整执行一次已有 Skill 对应的任务，"
        "GEPA 会对比最新执行经验与旧 SKILL.md，自动生成优化版 v2。"
        "适用场景：Skill 执行质量不理想、需要升级到新版。"
    )

    async def _invoke(skill_name: str, task: str) -> str:
        # 读取旧 SKILL.md 作为背景
        old_skill_path = skills_dir / skill_name / "SKILL.md"
        old_skill = old_skill_path.read_text() if old_skill_path.exists() else "（无旧版本）"

        # 获取最近审计记录
        recent_audit = get_recent_records(skill_name, 10)
        audit_summary = json.dumps(recent_audit, indent=2) if recent_audit else "（无审计数据）"

        optimize_prompt = f"""
{task}

【背景：当前 Skill 版本】
{old_skill}

【背景：最近执行审计】
{audit_summary}

请再次完整执行此任务。执行完毕后：
1. GEPA 会自动记录最新执行经验
2. 与上述旧 SKILL.md 对比差异
3. 生成优化版（修复问题、改进步骤、提升通用性）
"""

        stdout, stderr, elapsed = await _run_hermes_task(
            hermes_bin, optimize_prompt, timeout, hermes_env)

        if not stdout and stderr:
            return json.dumps({"status": "error", "error": stderr,
                               "elapsed_seconds": round(elapsed, 2)})

        # 同步优化后的新版 Skill
        hermes_skills_dir = Path.home() / ".hermes" / "skills"
        new_skills = sync_hermes_skills(
            hermes_skills_dir=hermes_skills_dir,
            deerflow_skills_dir=skills_dir,
            last_sync_mtime=0.0,
            check_universality=True,
        )

        return json.dumps({
            "status": "success",
            "result": stdout,
            "elapsed_seconds": round(elapsed, 2),
            "optimized_skill": skill_name if skill_name in new_skills else None,
        })

    return StructuredTool.from_function(
        name="invoke_hermes_optimize",
        description=description,
        coroutine=_invoke,
        args_schema=HermesOptimizeInput,
    )
```

**关键设计要点**：

| 要点 | 说明 |
|------|------|
| **两个独立工具** | `invoke_hermes_create` 负责首次创建，`invoke_hermes_optimize` 负责持续优化 |
| **通用性约束** | `_build_universal_prompt()` 确保 Hermes 生成参数化的通用 Skill |
| **审计数据驱动** | `invoke_hermes_optimize` 自动读取最近审计记录作为优化背景 |
| **旧版本对比** | 优化时读取旧 SKILL.md，让 GEPA 对比差异后升级 |
| **Scope 限定** | 实际使用时，Lead Agent 只在涉及 ADS/DeepRAG 时才调用这两个工具 |

---

### 4.3 `audit.py` — 审计日志系统（新增）

每次 DeerFlow 使用 Skill 执行任务后，记录到审计表：

```python
"""Skill execution audit logging."""

import json
from pathlib import Path
from datetime import datetime, timezone

AUDIT_DIR = Path.home() / ".hermes" / "audit"


def log_skill_execution(
    skill_name: str,
    status: str,           # "success" | "partial" | "failed"
    steps_count: int,
    retries_count: int,
    user_feedback: str | None = None,
):
    """记录一次 Skill 执行到审计表（JSONL 格式）。"""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "skill_name": skill_name,
        "status": status,
        "steps_count": steps_count,
        "retries_count": retries_count,
        "user_feedback": user_feedback,
    }
    with open(AUDIT_DIR / f"{skill_name}.jsonl", "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_recent_records(skill_name: str, n: int = 10) -> list[dict]:
    """获取某个 Skill 最近的 N 条审计记录。"""
    audit_file = AUDIT_DIR / f"{skill_name}.jsonl"
    if not audit_file.exists():
        return []
    with open(audit_file) as f:
        lines = f.readlines()
    return [json.loads(line) for line in lines[-n:]]


def get_skill_stats(skill_name: str) -> dict:
    """计算某个 Skill 的执行统计。"""
    records = get_recent_records(skill_name, 100)
    total = len(records)
    if total == 0:
        return {"total": 0, "success_rate": 0.0}
    successes = sum(1 for r in records if r["status"] == "success")
    return {
        "total": total,
        "success_rate": successes / total,
        "avg_retries": sum(r.get("retries_count", 0) for r in records) / total,
    }
```

---

### 4.4 `optimizer.py` — 自评与优化决策（新增）

```python
"""Skill execution self-evaluation and optimization trigger."""


def self_evaluate(execution_result: dict) -> dict:
    """4 维度自评（每个 0-10 分）。

    由 Lead Agent 的 LLM 在每次使用 Skill 后调用，基于执行结果自行评分。

    评价维度：
    - success_rate: 所有步骤是否都成功了？
    - efficiency: 有没有不必要的步骤或重试？
    - result_quality: 返回结果的质量如何？
    - user_satisfaction: 用户是否满意？
    """
    evaluation = execution_result.get("evaluation", {})
    scores = {
        "success_rate": min(max(evaluation.get("success_rate", 10), 0), 10),
        "efficiency": min(max(evaluation.get("efficiency", 8), 0), 10),
        "result_quality": min(max(evaluation.get("result_quality", 8), 0), 10),
        "user_satisfaction": min(max(evaluation.get("user_satisfaction", 8), 0), 10),
    }
    total_score = sum(scores.values()) / 4
    return {"scores": scores, "total_score": round(total_score, 1)}


def should_trigger_optimization(skill_name: str, total_score: float,
                                 usage_count: int) -> tuple[bool, str]:
    """判断是否应触发 Hermes 优化 Skill。

    前期激进策略（usage_count < 5）：总分 < 8 就优化
    后期保守策略（usage_count >= 5）：总分 < 5 或趋势下降才优化
    """
    if usage_count < 5:
        if total_score < 8:
            return True, f"前期激进优化：总分 {total_score} < 8（使用 {usage_count} 次）"
    else:
        if total_score < 5:
            return True, f"后期保守优化：总分 {total_score} < 5"
        # 趋势下降检测
        recent = _get_recent_avg(skill_name, 5)
        older = _get_recent_avg(skill_name, 10)
        if recent and older and recent < older - 1.0:
            return True, f"趋势下降：最近5次平均 {recent}，之前10次平均 {older}"
    return False, ""


def _get_recent_avg(skill_name: str, n: int) -> float | None:
    """获取最近 N 次自评的平均分（从审计日志估算）。"""
    from .audit import get_recent_records
    records = get_recent_records(skill_name, n)
    if not records:
        return None
    scores = []
    for r in records:
        # 从 status 推导粗略分数
        if r["status"] == "success":
            scores.append(9.0)
        elif r["status"] == "partial":
            scores.append(5.0)
        else:
            scores.append(2.0)
    return sum(scores) / len(scores)
```

---

### 4.5 `skill_sync.py` — Skill 检测与同步（增强版）

在原有基础上增加 `check_universality()` 通用性检查：

```python
"""检测 Hermes 自动生成的 Skill 并同步到 DeerFlow。"""

import logging
import re
import shutil
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def sync_hermes_skills(
    hermes_skills_dir: Path,
    deerflow_skills_dir: Path,
    last_sync_mtime: float = 0.0,
    check_universality: bool = True,
) -> List[str]:
    """同步 Hermes 新生成的 Skill 到 DeerFlow。

    Args:
        hermes_skills_dir: Hermes 的 Skill 目录 (~/.hermes/skills/)
        deerflow_skills_dir: DeerFlow 的 Skill 目录 (skills/public/)
        last_sync_mtime: 上次同步时间戳
        check_universality: 是否检查 Skill 的通用性

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

        skill_mtime = skill_md.stat().st_mtime
        if skill_mtime <= last_sync_mtime:
            continue

        # 基础质量门禁
        if not _passes_quality_gate(skill_md):
            logger.info(f"Skill {skill_dir.name} 未通过基础质量检查，跳过")
            continue

        # 通用性检查（仅对创建模式启用）
        if check_universality and not _check_universality(skill_md):
            logger.warning(f"Skill {skill_dir.name} 不够通用（包含具体实例），跳过同步")
            continue

        target = deerflow_skills_dir / skill_dir.name / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_md, target)
        logger.info(f"已同步 Skill: {skill_dir.name} -> {target}")
        synced.append(skill_dir.name)

    return synced


def _passes_quality_gate(skill_md: Path) -> bool:
    """基础质量检查：description 非空且>=10字符。"""
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


def _check_universality(skill_md: Path) -> bool:
    """通用性检查：SKILL.md 不得包含具体终端编号或硬编码关键词。"""
    content = skill_md.read_text()

    # 检查是否包含具体编号（如 86号、100号等）
    specific_ids = re.findall(r'\b(\d{2,4})\s*[号#]', content)
    if specific_ids:
        logger.warning(f"Skill 包含具体编号 {specific_ids}，不够通用")
        return False

    # 检查是否包含硬编码搜索关键词
    hardcoded = re.findall(r'搜索[：:"]?\s*["\'""]?([^"\'""\n]{2,10})["\'""]?', content)
    for kw in hardcoded:
        if kw and not kw.startswith("{") and not kw.endswith("}"):
            logger.warning(f"Skill 包含硬编码关键词 '{kw}'")
            return False

    return True
```

**同步机制要点**：

| 机制 | 说明 |
|------|------|
| **增量同步** | 通过 `last_sync_mtime` 记录上次同步时间，只处理更新的 Skill |
| **基础质量门禁** | `_passes_quality_gate()` 确保 description 非空 |
| **通用性检查** | `_check_universality()` 确保 SKILL.md 不含具体编号或硬编码关键词 |
| **优化模式跳过** | 优化时 `check_universality=False`（旧版本已通过检查，只做覆盖） |

---

## 五、在工具注册链中集成

### 5.1 修改 `tools.py` —— 注册 2 个 Hermes 工具

仿照 `invoke_acp_agent_tool` 的注册模式，在 `get_available_tools()` 中追加：

**修改位置**：[`deerflow/tools/tools.py`](file:///home/wing/wing/emto/2026/2026.3/DeerFlow/deer-flow/backend/packages/harness/deerflow/tools/tools.py#L141-L156)

在现有的 ACP Agent 注册块之后追加：

```python
# 在 tools.py 的 get_available_tools() 函数中，ACP 注册代码之后追加：

# Add Hermes Agent tools if configured
hermes_tools: list[BaseTool] = []
try:
    extensions_config = ExtensionsConfig.from_file()
    raw = extensions_config.model_extra or {}
    hermes_cfg = raw.get("communityTools", {}).get("hermes_agent", {})
    if hermes_cfg.get("enabled", True):
        from deerflow.community.hermes_agent import (
            build_hermes_create_tool,
            build_hermes_optimize_tool,
        )

        path = hermes_cfg.get("hermes_path", "hermes")
        target = hermes_cfg.get("sync_target", "./skills/public/")
        timeout = hermes_cfg.get("timeout", 300)

        hermes_tools.append(build_hermes_create_tool(path, target, timeout))
        hermes_tools.append(build_hermes_optimize_tool(path, target, timeout))
        logger.info(f"Including hermes tools (hermes_path={path})")
except Exception as e:
    logger.warning(f"Failed to load Hermes Agent tools: {e}")

# 然后将 hermes_tools 加入 all_tools：
all_tools = loaded_tools + builtin_tools + mcp_tools + acp_tools + hermes_tools
```

**注意**：`model_extra` 是 Pydantic v2 的保留字段，用于存储 schema 未声明的额外 JSON 键值。`extensions_config.json` 中的 `communityTools` 字段不在 `ExtensionsConfig` 的模型字段中，因此会存入 `model_extra`。

### 5.2 注入 System Prompt

在 `agents/lead_agent/prompts.py` 中，向 Lead Agent 的 system prompt 注入 Skill 使用规则。这是让 LLM **自主决策**的关键——不是写死代码逻辑，而是通过规则让 LLM 自己判断：

```python
SYSTEM_PROMPT_SKILL_RULES = """
## Skill 使用规则（仅针对 ADS MCP 和 DeepRAG MCP）

在执行涉及 ADS MCP 或 DeepRAG MCP 的任务时，遵循以下优先级：

### 优先级 1：先在 skills/public/ 中找匹配的 Skill
- 如果有 Skill 匹配当前任务 → 直接按 Skill 的通用步骤执行
- Skill 是指导你如何完成任务的文档，你需要自行将抽象步骤适配到当前场景

### 优先级 2：如果没有匹配的 Skill
- 先估算任务需要多少步
  - ≤ 4 步 → 直接用 MCP 工具执行，不创建 Skill
  - ≥ 5 步 → 调用 invoke_hermes_create 让 Hermes 创建通用 Skill

### 优先级 3：使用 Skill 后自评
每次使用 Skill 执行完任务后，自动评估：
- 执行是否完全成功？
- 执行效率如何（步骤是否冗余）？
- 结果质量是否满意？
- 如果是前期（该 Skill 累计使用 < 5 次），只要不是完全满意
  就调用 invoke_hermes_optimize 让 Hermes 优化

### 优先级 4：Skill 必须是通用的
当 Skill 中的指令过于特化（如写了具体的终端编号），
请自行适配为当前场景的参数。Skill 是做一类事的通用方法，
不是做某件事的固定脚本。

### 重要
以上规则仅适用于 ADS MCP 和 DeepRAG MCP 的工具，其他工具不受影响。
"""
```

### 5.3 注册模式对比

| 方面 | ACP Agent | Hermes Agent（新） |
|------|-----------|-------------------|
| **配置来源** | `config.yaml` 的 `acp_agents` | `extensions_config.json` 的 `communityTools.hermes_agent` |
| **工具建造** | `build_invoke_acp_agent_tool(agents)` | `build_hermes_create_tool()` + `build_hermes_optimize_tool()` |
| **启动方式** | `spawn_agent_process`（ACP 协议） | `subprocess`（CLI 子进程） |
| **MCP 透传** | ✅ 自动透传 | ❌ Hermes 用自己的 MCP 配置 |
| **Skill 同步** | ❌ 无 | ✅ 自动同步（含通用性检查） |
| **配置开关** | `acp_agents` 为空时不注册 | `enabled: false` 时跳过 |

---

## 六、配置方式

### 6.1 `extensions_config.json`

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
      "sync_target": "./skills/public/",
      "timeout": 300,
      "hermes_env": {
        "HERMES_CONFIG_PATH": "/home/wing/.hermes/config.yaml"
      }
    }
  },
  "skills": {}
}
```

### 6.2 配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `enabled` | 总开关，设为 `false` 则完全不加载 Hermes 工具 | `true` |
| `hermes_path` | Hermes 二进制路径 | `"hermes"`（从 PATH 查找） |
| `sync_target` | DeerFlow 中 Skill 的存储目录 | `"./skills/public/"` |
| `timeout` | Hermes 子进程超时（秒） | `300` |
| `hermes_env` | 额外环境变量 | `null` |

> **注意**：原来的 `min_calls`、`auto_sync_skills`、`keep_alive` 等配置项已移除。这些逻辑已内置到代码中：Skill 创建阈值固定为 ≥5 原子操作（由 Lead Agent 的 LLM 判断），同步始终启用，子进程始终按需启动。

---

## 七、Skill 自动同步机制

### 7.1 同步时机

| 触发条件 | 说明 |
|---------|------|
| **创建后同步** | `invoke_hermes_create` 返回时自动检测并同步 |
| **优化后同步** | `invoke_hermes_optimize` 返回时自动检测并覆盖 |
| **增量检测** | 只处理修改时间比上次同步新的 Skill |
| **通用性检查** | 新创建的 Skill 必须通过 `_check_universality()` 检查 |

### 7.2 同步流程

```
Hermes GEPA 生成/优化 SKILL.md
    │
    ▼
sync_hermes_skills() 在工具返回时触发
    │
    ├─ 1. 扫描 ~/.hermes/skills/ 目录
    ├─ 2. 对比 last_sync_mtime，过滤已同步的
    ├─ 3. 基础质量检查（description 非空）
    ├─ 4. 通用性检查（无具体编号/硬编码关键词）← 新增！
    ├─ 5. 复制到 deer-flow/skills/public/<name>/SKILL.md
    └─ 6. 更新 last_sync_mtime = now
```

### 7.3 质量门禁

| 检查项 | 标准 | 未达标处理 |
|--------|------|-----------|
| SKILL.md 存在 | 文件必须存在 | 跳过该目录 |
| description 非空 | YAML frontmatter 中 >=10 字符 | 跳过，日志记录 |
| 修改时间新 | 比上次同步的 mtime 新 | 跳过（已同步） |
| **通用性**（创建模式） | 无具体编号、无硬编码关键词 | **跳过，告警日志** |

### 7.4 通用 Skill 示例

一个合格的通用 SKILL.md 长这样：

```markdown
# 终端巡检报告生成

## 名称
terminal-inspection-report

## 描述
查询指定终端的运行状态，在知识库中搜索相关文档，
生成巡检报告。适用于终端状态巡检 + 知识库检索场景。

## 输入参数
- {终端ID}: 要巡检的终端编号
- {搜索主题}: 在知识库中搜索的主题关键词
- {报告格式}: 输出报告格式（表格/文档/文本）

## 执行步骤
1. 调用 ADS MCP 的查询工具，获取 {终端ID} 的运行状态
2. 调用 DeepRAG MCP 的搜索工具，搜索 {搜索主题} 的相关文档
3. 将终端状态和搜索文档整理为 {报告格式} 格式输出

## 示例
输入：终端ID=86号, 搜索主题=运维手册, 报告格式=表格
输出：终端86号运行状态 + 运维相关文档的表格汇总
```

**关键**：步骤使用 `{参数占位符}`，示例单独列出不绑死。

### 7.5 可剥离性保证

Hermes 生成的 SKILL.md 只是**普通的 Markdown 文件**，不包含任何 Hermes 特定的代码或导入。一旦同步到 `skills/public/`，它就是 DeerFlow 的原生 Skill，与手工编写的 Skill **没有区别**。

**即使 Hermes 被卸载**，已同步的 Skill 依然在 DeerFlow 中正常工作。

---

## 八、任务权责与决策流程

### 8.1 圣上六道御旨

| # | 御旨 | 技术实现 |
|---|------|---------|
| ① | 不是简单三步，尽可能找 Skill | Lead Agent 按 system prompt 优先级 1 执行 |
| ② | 无 Skill 自行决定是否创建 | Lead Agent 判断 ≥5 步且值得学才创建 |
| ③ | 用后自评 + 低阈值优化 | 4 维度自评 + 前期激进优化策略 |
| ④ | 仅限 ADS/DeepRAG | system prompt 明确限定范围 |
| ⑤ | 阈值 ≥5 步 | ≤4 直接执行，≥5 走 Skill 流程 |
| ⑥ | Skill 必须通用普世 | 创建时加 prompt 约束 + 同步时通用性检查 |

### 8.2 决策流程图

```
用户提问
    │
    ▼
DeerFlow Lead Agent（遵循 system prompt）
    │
    ├─ 判断 1：涉及 ADS MCP 或 DeepRAG MCP？
    │   ├─ 否 → 正常执行（不涉及 Hermes）
    │   └─ 是 ↓
    │
    ├─ 判断 2：原子操作 ≥ 5 个？
    │   ├─ 否（≤4 步）→ 直接调 MCP 工具执行
    │   └─ 是 ↓
    │
    ├─ 判断 3：有匹配的 Skill 吗？
    │   ├─ 是 → 用 Skill 执行 → 自评 → 低阈值优化判断
    │   └─ 否 ↓
    │
    ├─ 判断 4：是否值得创建 Skill？
    │   ├─ 是 → invoke_hermes_create(task)
    │   │       → Hermes 完整执行 + GEPA 生成通用 Skill
    │   │       → 同步到 skills/public/
    │   └─ 否 → 直接调 MCP 工具执行（不创建 Skill）
    │
    └─ 返回结果给用户
```

### 8.3 每个 Skill 使用后的闭环

```python
# Lead Agent 每次使用 Skill 后自动执行：

# 1. 记录审计
log_skill_execution(
    skill_name="terminal-inspection-report",
    status="success",           # 或 "partial" / "failed"
    steps_count=5,
    retries_count=0,
)

# 2. 4 维度自评
eval_result = self_evaluate({
    "evaluation": {
        "success_rate": 9,      # 步骤都成功了
        "efficiency": 7,        # 但有个步骤可以合并
        "result_quality": 8,    # 报告质量不错
        "user_satisfaction": 7, # 用户说"还行"
    }
})
# total_score = 7.8

# 3. 判断是否优化
should_opt, reason = should_trigger_optimization(
    skill_name="terminal-inspection-report",
    total_score=7.8,
    usage_count=3,              # 第 3 次使用，< 5
)
# should_opt = True（7.8 < 8，激进策略触发）

# 4. 触发优化
# → 调用 invoke_hermes_optimize(skill_name="terminal-inspection-report", ...)
```

### 8.4 完整示例

```
第一次：用户问 ≥5 步复杂任务
  "查终端86号状态，搜知识库，做报告，发企微，备份"
  → DeerFlow 判断：5步 ≥5，无 Skill → invoke_hermes_create
  → Hermes 完整执行 + GEPA 生成通用 Skill
  → DeerFlow 返回结果："已学会，下次可直接用"

第二次：同类任务，不同终端
  "查终端100号状态，搜文档，做报告发企微备份"
  → DeerFlow 找到匹配 Skill → 自行适配终端编号
  → 执行后自评 7.8分 < 8（使用 1 次）→ invoke_hermes_optimize
  → Hermes 再次执行 → GEPA 对比旧 Skill → 生成 v2
  → Skill 自动升级，下次更好

第三次及以后：同类任务
  "查终端200号，搜故障处理文档，做报告发企微"
  → Skill 已经过多次优化，质量稳定
  → 自评 9+ 分 → 不触发优化
  → 秒出结果
```

### 8.5 与 ACP Agent 的关系

ACP Agent 和 Hermes Agent 在 DeerFlow 中**不冲突**，可以同时配置：

- **ACP Agent**：调用外部标准 Agent（如 codex），用于标准化的外部系统集成
- **Hermes Agent**：本地 Skill 自动生成，用于 ADS/DeepRAG 的自进化

两者使用不同的配置字段（`acp_agents` vs `communityTools`）和不同的工具名称（`invoke_acp_agent` vs `invoke_hermes_create` / `invoke_hermes_optimize`），Lead Agent 根据任务自动选择合适的工具。

---

## 九、可剥离设计

### 9.1 三层剥离

```
┌──────────────┐  剥离 Hermes 时：
│  配置层       │  ┌─ communityTools.hermes_agent.enabled = false
│              │  │   一句话关掉，两个工具都消失
│ config.yaml  │  │
└──────┬───────┘  │
       │          │
┌──────▼───────┐  │
│  工具层       │  │  community/hermes_agent/ 目录代码成"死代码"
│              │  │  但不会被加载，零影响
│ community/   │  │
└──────┬───────┘  │
       │          │
┌──────▼───────┐  │
│  Skill 层     │  │  已同步的 SKILL.md → DeerFlow 原生 Skill
│              │  │  不依赖 Hermes！
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

# 2. 重启 DeerFlow 使配置生效
# invoke_hermes_create 和 invoke_hermes_optimize 工具不再出现

# 3. 已同步的 Skill 不受影响
# skills/public/ 下已有的 Skill 继续可用
# 它们只是普通的 Markdown 文件
```

---

## 十、进阶：方案 B — MCP Server 包装器

如果当前方案稳定运行后需要协议统一，可考虑将 Hermes 包装为 MCP Server。

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
> **更新：2026-05-12**（基于圣上六道御旨的最终设计）
>
> 本文档对应实施计划：[hermes-skill-generator-plan.md](file:///home/wing/wing/emto/2026/2026.3/DeerFlow/.trae/documents/hermes-skill-generator-plan.md) 方案 A（CLI Wrapper）
>
> 配套文档：
> - [HERMES_AGENT_DEPLOY.md](../operations/HERMES_AGENT_DEPLOY.md) — 人工操作参考
> - [hermes-skill-final-design.md](file:///home/wing/wing/emto/2026/2026.3/DeerFlow/.trae/documents/hermes-skill-final-design.md) — 最终设计文档
