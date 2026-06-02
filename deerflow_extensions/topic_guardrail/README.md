# TopicGuardrail — 回答范围限制扩展

## 概述

限制智能客服 Agent 只回答**公司业务**和**技术相关**内容，杜绝敏感内容和无关话题。采用 L1 角色身份 + L2 输入检查 + L3 输出检查 + L4 工具护栏的四层纵深防御。

## 架构

```
Layer 1: System Prompt <role> 身份认同（核心改动）
  → 告诉 LLM 它是什么领域的专家（东方亿盟技术顾问）
  → 超出领域的问题"不了解"而非"被禁止"
  → 参考：Anthropic Role Prompting 最佳实践
  → 文件: backend/packages/harness/deerflow/agents/lead_agent/prompt.py（~20行侵入）

Layer 2: SensitiveWordMiddleware.before_model（v5 新增）
  → 在 LLM 调用前检查用户输入文本
  → AC自动机 + 白名单 + 正则三层过滤
  → 命中敏感词 → 直接返回拒绝消息，不调用 LLM

Layer 3: SensitiveWordMiddleware.after_model（v5 新增）
  → 在 LLM 调用后检查模型输出文本
  → 同上敏感词引擎
  → 命中敏感词 → 替换为拒绝消息

Layer 4: TopicGuardrailProvider（GuardrailMiddleware，v5 简化）
  → 只判断 denied_tools（工具名黑名单），不做内容检查
  → bash           → ❌ 直接禁止
  → 其他所有工具   → ✅ 全部放行
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `topic_guardrail_provider.py` | GuardrailProvider 实现：AC自动机 + 白名单 + 正则三层过滤 |
| `topics.yaml` | 话题规则配置：denied_tools / content_check_tools / wordlist / patterns |
| `wordlist/base_sensitive_words.txt` | 基础敏感词库（16,669词，从开源 Sensitive-lexicon 合并去重） |
| `wordlist/custom_sensitive_words.txt` | 公司自定义敏感词（模板，按需填写） |
| `wordlist/whitelist.txt` | 白名单（防止业务关键词被敏感词库误杀） |

## 集成方式

通过 DeerFlow 原生 GuardrailMiddleware 加载，无需修改 core 代码（除 prompt.py 外）。

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

**注意**：单字词（"法""党""帝"等46个）已从基础词库中过滤，减少误杀。如需恢复请放入 `custom_sensitive_words.txt`。

## 依赖

- `pyahocorasick` — AC自动机匹配引擎（C实现，万字文本匹配 < 1ms）

## 代码侵入说明

| 文件 | 改动 | 风险 |
|------|------|------|
| `backend/packages/harness/deerflow/agents/lead_agent/prompt.py` | `<role>` 从通用助手改为东方亿盟技术顾问身份定义 ~20行 | ✅ 极低（纯prompt文本） |
| `config.yaml` | 启用 `guardrails.enabled: true` | ✅ 用户配置 |

同步官方上游代码时，检查 `prompt.py` 中"北京东方亿盟科技"是否存在即可。
