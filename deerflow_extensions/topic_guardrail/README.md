# TopicGuardrail — 回答范围限制扩展

## 概述

限制智能客服 Agent 只回答**公司业务**和**技术相关**内容，杜绝敏感内容和无关话题。采用 L1 角色身份 + L2 输入检查 + L3 输出检查 + L4 工具护栏的四层纵深防御。

## 架构

```
Layer 1: System Prompt <role> 身份认同（编译后可通过 role_definition.txt 覆盖）
  → 告诉 LLM 它是什么领域的专家（东方亿盟技术顾问）
  → 超出领域的问题"不了解"而非"被禁止"
  → 参考：Anthropic Role Prompting 最佳实践
  → 文件: role_definition.txt（部署后直接编辑，重启生效）

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
| `role_definition.txt` | **运行时角色定义**，编译后直接编辑此文件 + 重启即可微调回答范围 |
| `topic_guardrail_provider.py` | GuardrailProvider 实现，denied_tools 检查 |
| `sensitive_word_middleware.py` | L2/L3 敏感词输入输出检查中间件（AC自动机） |
| `topics.yaml` | 话题规则配置：denied_tools / wordlist |
| `wordlist/base_sensitive_words.txt` | 基础敏感词库（14,072词，从开源 Sensitive-lexicon 合并去重） |
| `wordlist/custom_sensitive_words.txt` | 公司自定义敏感词（模板，按需填写） |
| `wordlist/whitelist.txt` | 白名单（防止业务关键词被敏感词库误杀） |

## 集成方式

通过 DeerFlow 原生 GuardrailMiddleware + sitecustomize.py 注入，**完全零侵入 core 源码**。

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

## 角色定义维护

`role_definition.txt` 包含 `<role>` 标签内的全部内容。部署后微调流程：

```bash
# 1. 服务器上直接编辑角色定义
vi /usr/xccloud/deerflow/backend-bin/_internal/deerflow_extensions/topic_guardrail/role_definition.txt

# 2. 重启服务
systemctl restart deerflow
```

**无需重新编译，无需重新打包**。文件不存在时自动使用编译时默认角色（prompt.py 中的定义）。

## 依赖

- `pyahocorasick` — AC自动机匹配引擎（C实现，万字文本匹配 < 1ms）

## 代码侵入说明

| 文件 | 改动 | 风险 |
|------|------|------|
| `config.yaml` | 启用 `guardrails.enabled: true` | ✅ 用户配置 |

**零核心源码侵入**：所有改动均在 `deerflow_extensions/` 扩展目录内，不修改任何 `backend/` 文件。
