# TopicGuardrail — 回答范围限制扩展（v7 纵深防御）

## 概述

限制智能客服 Agent 只回答**公司业务**和**技术相关**内容，杜绝敏感内容和无关话题。采用 L1 角色身份 + L2 输入预处理/检查 + L3 输出检查 + L4 工具护栏的四层纵深防御架构。

## 架构

```
用户输入
    │
    ▼
┌─────────────────────────────────────────┐
│         SensitiveWordMiddleware          │
│                                          │
│  ┌──────────────┐   ┌──────────────┐    │
│  │ TextPrepro-  │──▶│ AC Automaton │    │
│  │ cessor       │   │ (keyword)    │    │
│  │ (v7 NEW)     │   │              │    │
│  │ - NFC归一化  │   │ - 词源合并   │    │
│  │ - 零宽清除  │   │ - 白名单排除 │    │
│  │ - 拼音检测  │   │ - fail-closed│    │
│  │ - 全角→半角 │   │              │    │
│  │ - 单字母压缩│   └──────┬───────┘    │
│  └──────────────┘          │            │
│                       HIT? ┤            │
│                       → BLOCK           │
│                       → PASS            │
└───────────────────────┬─────────────────┘
                        │
                        ▼
[L1: System Prompt <role> 身份认同]
  → 告诉 LLM 它是什么领域的专家（东方亿盟技术顾问）
  → 超出领域的问题"不了解"而非"被禁止"
  → 文件: role_definition.txt（部署后直接编辑，重启生效）

  （如果调用了工具）
                        ▼
[L4: TopicGuardrailProvider]
  → bash           → ❌ 直接禁止
  → 其他所有工具   → ✅ 全部放行
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `role_definition.txt` | **运行时角色定义**，编译后直接编辑此文件 + 重启即可微调回答范围 |
| `topic_guardrail_provider.py` | GuardrailProvider 实现，denied_tools 检查 |
| `sensitive_word_middleware.py` | L2/L3 敏感词检查中间件（AC自动机 + fail-closed + 审计日志） |
| `text_preprocessor.py` | **v7 新增**：输入文本预处理（Unicode归一化、零宽字符清除、拼音检测、全角→半角） |
| `topics.yaml` | 话题规则配置：denied_tools / wordlist / audit |
| `wordlist/base_sensitive_words.txt` | 基础敏感词库（14,072+词，从开源 Sensitive-lexicon 合并去重） |
| `wordlist/custom_sensitive_words.txt` | 公司自定义敏感词（含政治人物、拼音变体补全） |
| `wordlist/whitelist.txt` | 白名单（防止业务关键词被敏感词库误杀） |

## v7 新增功能

### 1. Fail-Closed 策略
- AC自动机初始化失败（`_automaton is None`）→ **拒绝所有输入** + CRITICAL 日志
- AC自动机运行时异常 → **拒绝所有输入** + exception 日志
- **解决了** `except AttributeError: pass` 导致的敏感词检测完全失效问题

### 2. TextPreprocessor（文本预处理）
自动消除常见绕过手法：
- Unicode NFC 归一化（防声调符号拆分）
- 零宽字符清除（`\u200B-ZWS`, `\u200C-ZWNJ`, `\u200D-ZWJ`, `\uFEFF-BOM`）
- 全角英文字母 → 半角
- 连续空格压缩
- 单字母间隙压缩（`X I J I N P I N G` → `xijinping`）
- `.lower()` 统一小写
- 拼音正则检测（`xi jin ping`、`t r u m p`、`xi da da`）

### 3. 词库补全
`custom_sensitive_words.txt` 追加拼音/英文变体及缺失政治人物：
```
xijinping, xi jin ping, trump, donald trump, jinping, xidada
特朗普, 川普, 拜登, 普京, 金正恩, 泽连斯基, 奥巴马, 克林顿, 希拉里
```

### 4. 审计日志
每次拒绝记录结构化日志：
```
AUDIT|BLOCKED|reason=ac_automaton|ts=2026-06-04T12:00:00
```

### 5. L1 角色硬约束
`role_definition.txt` 追加 `STRICTLY FORBIDDEN` 禁止事项清单：
- 不得以政治人物名称命名模板/分区/终端
- 遇到涉及上述内容的请求直接拒绝

## 集成方式

通过 `deerflow_extensions/boot.py` 统一 Boot Loader 注入，**完全零侵入 core 源码**：

| 入口 | 适用模式 | 机制 |
|------|---------|------|
| `backend/app/gateway/app.py` | 本地开发 + Docker Gateway | lifespan 内 `boot_all_extensions(app=app)` |
| `backend/deerflow_entry.py` | PyInstaller 打包 | pre-import 阶段 `boot_topic_guardrail_early(ext_internal)` |
| `deerflow_extensions/entrypoint.sh` | Docker LangGraph | `python3 -c` 直接调用 `boot_all_extensions()` |

所有入口 **不依赖 sitecustomize 机制**。各扩展自身的 `_installed`/`_APPLIED` 保证幂等。

### 角色注入机制（V6 架构升级）

`_patch_role()` 采用**模板字符串替换**而非函数 monkeypatch：

```python
# ✅ 当前方案：替换模块级字符串
_prompt.SYSTEM_PROMPT_TEMPLATE = new_template

# ❌ 旧方案：替换函数引用（受 from X import Y 时序影响）
_prompt.apply_prompt_template = _patched_apply
```

**config.yaml**：

```yaml
guardrails:
  enabled: true
  fail_closed: true
  provider:
    use: deerflow_extensions.topic_guardrail.topic_guardrail_provider:TopicGuardrailProvider
    config:
      config_path: topics.yaml
```

## 词库维护

| 文件 | 维护方式 | 格式 |
|------|---------|------|
| `base_sensitive_words.txt` | 只读，定期从上游开源项目同步 | 每行一个词，UTF-8 |
| `custom_sensitive_words.txt` | 手动维护，存放公司特有敏感词 | 每行一个词，UTF-8 |
| `whitelist.txt` | 手动维护，补充业务关键词防止误杀 | 每行一个词，UTF-8 |

**注意**：单字词（"法""党""帝"等46个）已从基础词库中过滤。如需恢复请放入 `custom_sensitive_words.txt`。

## 角色定义维护

`role_definition.txt` 包含 `<role>` 标签内的全部内容。部署后微调流程：

```bash
# 1. 服务器上直接编辑角色定义
vi /usr/xccloud/deerflow/backend-bin/_internal/deerflow_extensions/topic_guardrail/role_definition.txt

# 2. 重启服务
systemctl restart deerflow
```

**无需重新编译，无需重新打包**。文件不存在时自动使用编译时默认角色。

## 依赖

- `pyahocorasick` — AC自动机匹配引擎（C实现，万字文本匹配 < 1ms）

## 代码侵入说明

| 文件 | 改动 | 风险 |
|------|------|------|
| `config.yaml` | 启用 `guardrails.enabled: true` | ✅ 用户配置 |

**零核心源码侵入**：所有改动均在 `deerflow_extensions/` 扩展目录内，不修改任何 `backend/` 文件。
