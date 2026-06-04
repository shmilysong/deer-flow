# Guardrails: Pre-Tool-Call Authorization

> **Context:** [Issue #1213](https://github.com/bytedance/deer-flow/issues/1213) — DeerFlow has Docker sandboxing and human approval via `ask_clarification`, but no deterministic, policy-driven authorization layer for tool calls. An agent running autonomous multi-step tasks can execute any loaded tool with any arguments. Guardrails add a middleware that evaluates every tool call against a policy **before** execution.

## Why Guardrails

```
Without guardrails:                      With guardrails:

  Agent                                    Agent
    │                                        │
    ▼                                        ▼
  ┌──────────┐                             ┌──────────┐
  │ bash     │──▶ executes immediately     │ bash     │──▶ GuardrailMiddleware
  │ rm -rf / │                             │ rm -rf / │        │
  └──────────┘                             └──────────┘        ▼
                                                         ┌──────────────┐
                                                         │  Provider    │
                                                         │  evaluates   │
                                                         │  against     │
                                                         │  policy      │
                                                         └──────┬───────┘
                                                                │
                                                          ┌─────┴─────┐
                                                          │           │
                                                        ALLOW       DENY
                                                          │           │
                                                          ▼           ▼
                                                      Tool runs   Agent sees:
                                                      normally    "Guardrail denied:
                                                                   rm -rf blocked"
```

- **Sandboxing** provides process isolation but not semantic authorization. A sandboxed `bash` can still `curl` data out.
- **Human approval** (`ask_clarification`) requires a human in the loop for every action. Not viable for autonomous workflows.
- **Guardrails** provide deterministic, policy-driven authorization that works without human intervention.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Middleware Chain                               │
│                                                                      │
│  1. ThreadDataMiddleware     ─── per-thread dirs                     │
│  2. UploadsMiddleware        ─── file upload tracking                │
│  3. SandboxMiddleware        ─── sandbox acquisition                 │
│  4. DanglingToolCallMiddleware ── fix incomplete tool calls           │
│  5. GuardrailMiddleware ◄──── EVALUATES EVERY TOOL CALL             │
│  6. ToolErrorHandlingMiddleware ── convert exceptions to messages     │
│  7-12. (Summarization, Title, Memory, Vision, Subagent, Clarify)    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                         │
                         ▼
           ┌──────────────────────────┐
           │    GuardrailProvider     │  ◄── pluggable: any class
           │    (configured in YAML)  │      with evaluate/aevaluate
           └────────────┬─────────────┘
                        │
              ┌─────────┼──────────────┐
              │         │              │
              ▼         ▼              ▼
         Built-in   OAP Passport    Custom
         Allowlist  Provider        Provider
         (zero dep) (open standard) (your code)
                        │
                  Any implementation
                  (e.g. APort, or
                   your own evaluator)
```

The `GuardrailMiddleware` implements `wrap_tool_call` / `awrap_tool_call` (the same `AgentMiddleware` pattern used by `ToolErrorHandlingMiddleware`). It:

1. Builds a `GuardrailRequest` with tool name, arguments, and passport reference
2. Calls `provider.evaluate(request)` on whatever provider is configured
3. If **deny**: returns `ToolMessage(status="error")` with the reason -- agent sees the denial and adapts
4. If **allow**: passes through to the actual tool handler
5. If **provider error** and `fail_closed=true` (default): blocks the call
6. `GraphBubbleUp` exceptions (LangGraph control signals) are always propagated, never caught

## Three Provider Options

### Option 1: Built-in AllowlistProvider (Zero Dependencies)

The simplest option. Ships with DeerFlow. Block or allow tools by name. No external packages, no passport, no network.

**config.yaml:**
```yaml
guardrails:
  enabled: true
  provider:
    use: deerflow.guardrails.builtin:AllowlistProvider
    config:
      denied_tools: ["bash", "write_file"]
```

This blocks `bash` and `write_file` for all requests. All other tools pass through.

You can also use an allowlist (only these tools are permitted):
```yaml
guardrails:
  enabled: true
  provider:
    use: deerflow.guardrails.builtin:AllowlistProvider
    config:
      allowed_tools: ["web_search", "read_file", "ls"]
```

**Try it:**
1. Add the config above to your `config.yaml`
2. Start DeerFlow: `make dev`
3. Ask the agent: "Use bash to run echo hello"
4. The agent sees: `Guardrail denied: tool 'bash' was blocked (oap.tool_not_allowed)`

### Option 2: OAP Passport Provider (Policy-Based)

For policy enforcement based on the [Open Agent Passport (OAP)](https://github.com/aporthq/aport-spec) open standard. An OAP passport is a JSON document that declares an agent's identity, capabilities, and operational limits. Any provider that reads an OAP passport and returns OAP-compliant decisions works with DeerFlow.

```
┌─────────────────────────────────────────────────────────────┐
│                    OAP Passport (JSON)                        │
│                   (open standard, any provider)              │
│  {                                                           │
│    "spec_version": "oap/1.0",                                │
│    "status": "active",                                       │
│    "capabilities": [                                         │
│      {"id": "system.command.execute"},                       │
│      {"id": "data.file.read"},                               │
│      {"id": "data.file.write"},                              │
│      {"id": "web.fetch"},                                    │
│      {"id": "mcp.tool.execute"}                              │
│    ],                                                        │
│    "limits": {                                               │
│      "system.command.execute": {                             │
│        "allowed_commands": ["git", "npm", "node", "ls"],     │
│        "blocked_patterns": ["rm -rf", "sudo", "chmod 777"]   │
│      }                                                       │
│    }                                                         │
│  }                                                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
               Any OAP-compliant provider
          ┌────────────────┼────────────────┐
          │                │                │
     Your own         APort (ref.      Other future
     evaluator        implementation)  implementations
```

**Creating a passport manually:**

An OAP passport is just a JSON file. You can create one by hand following the [OAP specification](https://github.com/aporthq/aport-spec/blob/main/oap/oap-spec.md) and validate it against the [JSON schema](https://github.com/aporthq/aport-spec/blob/main/oap/passport-schema.json). See the [examples](https://github.com/aporthq/aport-spec/tree/main/oap/examples) directory for templates.

**Using APort as a reference implementation:**

[APort Agent Guardrails](https://github.com/aporthq/aport-agent-guardrails) is one open-source (Apache 2.0) implementation of an OAP provider. It handles passport creation, local evaluation, and optional hosted API evaluation.

```bash
pip install aport-agent-guardrails
aport setup --framework deerflow
```

This creates:
- `~/.aport/deerflow/config.yaml` -- evaluator config (local or API mode)
- `~/.aport/deerflow/aport/passport.json` -- OAP passport with capabilities and limits

**config.yaml (using APort as the provider):**
```yaml
guardrails:
  enabled: true
  provider:
    use: aport_guardrails.providers.generic:OAPGuardrailProvider
```

**config.yaml (using your own OAP provider):**
```yaml
guardrails:
  enabled: true
  provider:
    use: my_oap_provider:MyOAPProvider
    config:
      passport_path: ./my-passport.json
```

Any provider that accepts `framework` as a kwarg and implements `evaluate`/`aevaluate` works. The OAP standard defines the passport format and decision codes; DeerFlow doesn't care which provider reads them.

**What the passport controls:**

| Passport field | What it does | Example |
|---|---|---|
| `capabilities[].id` | Which tool categories the agent can use | `system.command.execute`, `data.file.write` |
| `limits.*.allowed_commands` | Which commands are allowed | `["git", "npm", "node"]` or `["*"]` for all |
| `limits.*.blocked_patterns` | Patterns always denied | `["rm -rf", "sudo", "chmod 777"]` |
| `status` | Kill switch | `active`, `suspended`, `revoked` |

**Evaluation modes (provider-dependent):**

OAP providers may support different evaluation modes. For example, the APort reference implementation supports:

| Mode | How it works | Network | Latency |
|---|---|---|---|
| **Local** | Evaluates passport locally (bash script). | None | ~300ms |
| **API** | Sends passport + context to a hosted evaluator. Signed decisions. | Yes | ~65ms |

A custom OAP provider can implement any evaluation strategy -- the DeerFlow middleware doesn't care how the provider reaches its decision.

**Try it:**
1. Install and set up as above
2. Start DeerFlow and ask: "Create a file called test.txt with content hello"
3. Then ask: "Now delete it using bash rm -rf"
4. Guardrail blocks it: `oap.blocked_pattern: Command contains blocked pattern: rm -rf`

### Option 3: Custom Provider (Bring Your Own)

Any Python class with `evaluate(request)` and `aevaluate(request)` methods works. No base class or inheritance needed -- it's a structural protocol.

```python
# my_guardrail.py

class MyGuardrailProvider:
    name = "my-company"

    def evaluate(self, request):
        from deerflow.guardrails.provider import GuardrailDecision, GuardrailReason

        # Example: block any bash command containing "delete"
        if request.tool_name == "bash" and "delete" in str(request.tool_input):
            return GuardrailDecision(
                allow=False,
                reasons=[GuardrailReason(code="custom.blocked", message="delete not allowed")],
                policy_id="custom.v1",
            )
        return GuardrailDecision(allow=True, reasons=[GuardrailReason(code="oap.allowed")])

    async def aevaluate(self, request):
        return self.evaluate(request)
```

**config.yaml:**
```yaml
guardrails:
  enabled: true
  provider:
    use: my_guardrail:MyGuardrailProvider
```

Make sure `my_guardrail.py` is on the Python path (e.g. in the backend directory or installed as a package).

**Try it:**
1. Create `my_guardrail.py` in the backend directory
2. Add the config
3. Start DeerFlow and ask: "Use bash to delete test.txt"
4. Your provider blocks it

## Implementing a Provider

### Required Interface

```
┌──────────────────────────────────────────────────┐
│              GuardrailProvider Protocol            │
│                                                   │
│  name: str                                        │
│                                                   │
│  evaluate(request: GuardrailRequest)              │
│      -> GuardrailDecision                         │
│                                                   │
│  aevaluate(request: GuardrailRequest)   (async)   │
│      -> GuardrailDecision                         │
└──────────────────────────────────────────────────┘

┌──────────────────────────┐    ┌──────────────────────────┐
│     GuardrailRequest      │    │    GuardrailDecision      │
│                           │    │                           │
│  tool_name: str           │    │  allow: bool              │
│  tool_input: dict         │    │  reasons: [GuardrailReason]│
│  agent_id: str | None     │    │  policy_id: str | None    │
│  thread_id: str | None    │    │  metadata: dict           │
│  is_subagent: bool        │    │                           │
│  timestamp: str           │    │  GuardrailReason:         │
│                           │    │    code: str              │
└──────────────────────────┘    │    message: str           │
                                └──────────────────────────┘
```

### DeerFlow Tool Names

These are the tool names your provider will see in `request.tool_name`:

| Tool | What it does |
|---|---|
| `bash` | Shell command execution |
| `write_file` | Create/overwrite a file |
| `str_replace` | Edit a file (find and replace) |
| `read_file` | Read file content |
| `ls` | List directory |
| `web_search` | Web search query |
| `web_fetch` | Fetch URL content |
| `image_search` | Image search |
| `present_files` | Present file to user |
| `view_image` | Display image |
| `ask_clarification` | Ask user a question |
| `task` | Delegate to subagent |
| `mcp__*` | MCP tools (dynamic) |

### OAP Reason Codes

Standard codes used by the [OAP specification](https://github.com/aporthq/aport-spec):

| Code | Meaning |
|---|---|
| `oap.allowed` | Tool call authorized |
| `oap.tool_not_allowed` | Tool not in allowlist |
| `oap.command_not_allowed` | Command not in allowed_commands |
| `oap.blocked_pattern` | Command matches a blocked pattern |
| `oap.limit_exceeded` | Operation exceeds a limit |
| `oap.passport_suspended` | Passport status is suspended/revoked |
| `oap.evaluator_error` | Provider crashed (fail-closed) |

### Provider Loading

DeerFlow loads providers via `resolve_variable()` -- the same mechanism used for models, tools, and sandbox providers. The `use:` field is a Python class path: `package.module:ClassName`.

The provider is instantiated with `**config` kwargs if `config:` is set, plus `framework="deerflow"` is always injected. Accept `**kwargs` to stay forward-compatible:

```python
class YourProvider:
    def __init__(self, framework: str = "generic", **kwargs):
        # framework="deerflow" tells you which config dir to use
        ...
```

## Configuration Reference

```yaml
guardrails:
  # Enable/disable guardrail middleware (default: false)
  enabled: true

  # Block tool calls if provider raises an exception (default: true)
  fail_closed: true

  # Passport reference -- passed as request.agent_id to the provider.
  # File path, hosted agent ID, or null (provider resolves from its config).
  passport: null

  # Provider: loaded by class path via resolve_variable
  provider:
    use: deerflow.guardrails.builtin:AllowlistProvider
    config:  # optional kwargs passed to provider.__init__
      denied_tools: ["bash"]
```

## Testing

```bash
cd backend
uv run python -m pytest tests/test_guardrail_middleware.py -v
```

25 tests covering:
- AllowlistProvider: allow, deny, both allowlist+denylist, async
- GuardrailMiddleware: allow passthrough, deny with OAP codes, fail-closed, fail-open, passport forwarding, empty reasons fallback, empty tool name, protocol isinstance check
- Async paths: awrap_tool_call for allow, deny, fail-closed, fail-open
- GraphBubbleUp: LangGraph control signals propagate through (not caught)
- Config: defaults, from_dict, singleton load/reset

## Files

```
packages/harness/deerflow/guardrails/
    __init__.py              # Public exports
    provider.py              # GuardrailProvider protocol, GuardrailRequest, GuardrailDecision
    middleware.py             # GuardrailMiddleware (AgentMiddleware subclass)
    builtin.py               # AllowlistProvider (zero deps)

packages/harness/deerflow/config/
    guardrails_config.py     # GuardrailsConfig Pydantic model + singleton

packages/harness/deerflow/agents/middlewares/
    tool_error_handling_middleware.py  # Registers GuardrailMiddleware in chain

config.example.yaml          # Three provider options documented
tests/test_guardrail_middleware.py  # 25 tests
docs/GUARDRAILS.md           # This file

---

## TopicGuardrail v5 (四层纵深防御)

> **扩展位置**：`deerflow_extensions/topic_guardrail/`（零侵入）
> **依赖**：`pyahocorasick`（AC自动机，C语言实现）

### 解决的问题

限制智能客服 Agent 只回答公司业务和技术相关内容，拒绝敏感/无关话题。采用 L1 角色身份 + L2 输入检查 + L3 输出检查 + L4 工具护栏的四层纵深防御。

### 分层架构

```
用户输入
    │
    ▼
[L1: System Prompt <role> 身份认同]  
    │  告诉 LLM 它是东方亿盟技术顾问
    │  超出领域的问题"不了解"而非"被禁止"
    │  （参考：Anthropic Role Prompting）
    │
    ▼
[L2: SensitiveWordMiddleware.before_model]
    │  在 LLM 调用前检查用户输入文本
    │  AC自动机 + 白名单 + 正则三层过滤
    │  命中敏感词 → 直接返回拒绝消息（不调用 LLM）
    │
    ▼
[L3: SensitiveWordMiddleware.after_model]
    │  在 LLM 调用后检查模型输出文本
    │  同上敏感词引擎
    │  命中敏感词 → 替换为拒绝消息
    │
    ▼
    （如果调用了工具）
    ▼
[L4: TopicGuardrailProvider (GuardrailMiddleware)]
    ├─ bash                → ❌ 直接禁止（denied_tools）
    └─ 其他工具（含 web_search/MCP） → ✅ 全部放行
```

### L1: System Prompt 角色定位

`<role>` 身份定义来自 `role_definition.txt`（运行时覆盖）或 `prompt.py` 的 `SYSTEM_PROMPT_TEMPLATE`（编译时默认）。

**运行时覆盖机制（V6 架构升级）**：

角色注入通过 **`deerflow_extensions/boot.py` 统一 Boot Loader** 确保覆盖所有运行模式：

| 入口 | 适用模式 | 触发方式 |
|------|---------|---------|
| `backend/app/gateway/app.py` | 本地开发 + Docker Gateway | lifespan 内 `boot_all_extensions(app=app)` |
| `backend/deerflow_entry.py` | PyInstaller 打包 | pre-import 阶段 `boot_topic_guardrail_early(ext_internal)` |
| `deerflow_extensions/entrypoint.sh` | Docker LangGraph | `python3 -c` 直接调用 `boot_all_extensions()` |

**已废弃** `sitecustomize.py`（CPython 文档明确此机制用于系统级全站自定义，不适合项目扩展注入）。

**技术细节**：`_patch_role()` 采用**模板字符串替换**而非函数 monkeypatch——直接替换 `SYSTEM_PROMPT_TEMPLATE` 模块级变量。Python 函数通过 `LOAD_GLOBAL` 字节码每次动态查找模块全局变量，修改后所有调用者（不论如何导入）立即生效。免除函数 monkeypatch 在 `from X import Y` 模式下的导入时序脆弱性。

当 `role_definition.txt` 存在时，`apply_prompt_template()` 返回的完整 prompt 中包含文件中的角色定义。文件不存在时静默使用编译时默认值。

**部署后微调流程**：
```bash
# 编辑扩展目录中的角色定义文件
vi /usr/xccloud/deerflow/backend-bin/_internal/deerflow_extensions/topic_guardrail/role_definition.txt
# 重启服务
systemctl restart deerflow
```
无需重新编译，无需重新打包 PyInstaller 二进制。

**设计依据**：业界共识（Anthropic / NeMo / OpenAI / Microsoft）——角色定义是最强力的行为控制手段，模型"乐于助人"的本性会找理由绕过禁止清单，但不会绕过身份认同。

### L2+L3: SensitiveWordMiddleware（新增 v5）

匹配引擎使用 **AC自动机（Aho-Corasick）**，由 `pyahocorasick` 库提供（C 实现，万字文本 < 1ms）。

**文件**: `deerflow_extensions/topic_guardrail/sensitive_word_middleware.py`

**词库结构**：

```
wordlist/
├── base_sensitive_words.txt    # 基础敏感词库（16,715词，覆盖政治/色情/暴力/违法）
├── custom_sensitive_words.txt  # 公司自定义敏感词（可选）
└── whitelist.txt               # 白名单（防止业务词误杀）
```

**判断逻辑**：

```python
class SensitiveWordMiddleware(AgentMiddleware):
    name = "sensitive_word"

    def before_model(self, state, runtime) -> dict | None:
        text = self._get_last_user_message(state)
        if text and self._has_sensitive(text):
            return {"messages": [AIMessage(content="抱歉，您的输入包含不允许的内容。")]}

    def after_model(self, state, runtime) -> dict | None:
        text = self._get_last_ai_message(state)
        if text and self._has_sensitive(text):
            return {"messages": [AIMessage(content="抱歉，您的输入包含不允许的内容。")]}
```

**注入方式**：通过 `patch_manager.py` 的 `_patch_sensitive_word()` 注入到中间件链中，由 `boot.py` Boot Loader 统一触发：

```python
def _patch_sensitive_word():
    # from deerflow_extensions.topic_guardrail.sensitive_word_middleware import SensitiveWordMiddleware
    # import deerflow.agents.lead_agent.agent as _agent_mw
    _orig_build = _agent_mw._build_middlewares

    def _patched_build(config, *args, **kwargs):
        middlewares = _orig_build(config, *args, **kwargs)
        middlewares.insert(-1, SensitiveWordMiddleware())
        return middlewares

    _agent_mw._build_middlewares = _patched_build
```

> **注意**：旧版通过 `sitecustomize.py` 注入的方式已废弃。`sitecustomize.py` 已被删除（CPython 文档明确其用于系统级全站自定义，不适用于项目扩展注入）。当前统一经由 `boot.py` Boot Loader 管理所有扩展注入。

**白名单补偿**：即使敏感词库命中，如果匹配词在白名单中，仍然放行。防止公司业务词被误杀。

**与 v4 的区别**：
- v4：敏感词过滤只在 `TopicGuardrailProvider.evaluate()` 中做，仅覆盖 `web_search/web_fetch` 的搜索词
- v5：敏感词过滤升级为完整的 `AgentMiddleware`，覆盖 **用户输入全文**（L2）和 **模型输出全文**（L3），不限于搜索词
- v5 的 `TopicGuardrailProvider` 仅保留 `denied_tools` 检查，不再做内容检查

### L4: TopicGuardrailProvider（v5 简化版）

**文件**: `deerflow_extensions/topic_guardrail/topic_guardrail_provider.py`

**职责变更**：v5 中只判断工具名是否在禁止列表中，敏感词内容检查已交给 `SensitiveWordMiddleware`：

```python
class TopicGuardrailProvider:
    name = "topic_guardrail"

    def evaluate(self, request: GuardrailRequest) -> GuardrailDecision:
        if request.tool_name in self._denied_tools:
            return deny(reason="topic_guardrail.tool_denied")
        return allow()
```

### 配置方式

**config.yaml**：

```yaml
guardrails:
  enabled: true
  fail_closed: true
  provider:
    use: deerflow_extensions.topic_guardrail.topic_guardrail_provider:TopicGuardrailProvider
    config:
      config_path: deerflow_extensions/topic_guardrail/topics.yaml
```

**SensitiveWordMiddleware** 通过 `patch_manager.py` 自动注入（由 `boot.py` Boot Loader 统一触发），无需额外配置。

**topics.yaml**（v5 已删除 `content_check_tools`）：

```yaml
tool_control:
  denied_tools:
    - bash
  wordlist:
    base: wordlist/base_sensitive_words.txt
    custom: wordlist/custom_sensitive_words.txt
    whitelist: wordlist/whitelist.txt
  patterns:
    - "(习近平|法轮功|台湾独立|六四|天安门)"
    - "(赌博|赌场|六合彩|赌球)"
    - "(毒品|毒药|海洛因|冰毒)"
    - "(色情|裸聊|一夜情)"
```

### 测试

```bash
# 测试 TopicGuardrailProvider（denied_tools 检查）
PYTHONPATH=backend/packages/harness:deerflow_extensions uv run --directory backend \
  python3 -m pytest deerflow_extensions/topic_guardrail/tests/test_topic_guardrail_provider.py -v

# 测试 SensitiveWordMiddleware（L2+L3 敏感词检查）
PYTHONPATH=backend/packages/harness:deerflow_extensions uv run --directory backend \
  python3 -m pytest deerflow_extensions/topic_guardrail/tests/test_sensitive_word_middleware.py -v
```

### v7 纵深防御升级（2026-06-04）

SensitiveWordMiddleware 从基础关键词匹配升级为完整纵深防御体系，解决 v5 的已知局限：

**v7 新增组件**：

| 组件 | 功能 |
|------|------|
| `text_preprocessor.py` | 文本预处理管道：NFC归一化 → 零宽字符清除 → 全角→半角 → 空格压缩 → 单字母间隙压缩 → lowercase |
| 审计日志 | 每次拒绝记录 `AUDIT|BLOCKED|reason=...|ts=...` |

**Fail-Closed 加固**：
- `_automaton is None` → CRITICAL 日志 + 拒绝所有输入
- 任意异常 → exception 日志 + 拒绝所有输入
- 彻底解决 `except AttributeError: pass` 导致敏感词检测静默失效的问题

**词库补全**：
`custom_sensitive_words.txt` 合并政治人物及拼音/英文变体（原 `pinyin_variants.txt` 已删除，内容合并至此）。

**L1 角色硬约束**（`role_definition.txt` 追加）：
```
🚨 STRICTLY FORBIDDEN — 严格禁止：
- 不得以任何政治人物、政治组织名称命名模板、分区、终端或任何系统对象
- 如果用户的请求中涉及上述内容，直接回复"已被系统拒绝"
- 不做任何解释，不追问，不确认
```

### 已知局限

单字词（"法""党""帝"等46个）已从基础词库中过滤以减少误杀。如需恢复，请添加到 `custom_sensitive_words.txt`。
```
