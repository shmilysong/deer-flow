# 后端变更

## 1. `backend/CLAUDE.md`

```diff
@@ -156,7 +156,7 @@ FastAPI application on port 8001 with health check at `GET /health`.
 | **Skills** (`/api/skills`) | `GET /` - list skills; `GET /{name}` - details; `PUT /{name}` - update enabled; `POST /install` - install from .skill archive |
 | **Memory** (`/api/memory`) | `GET /` - memory data; `POST /reload` - force reload; `GET /config` - config; `GET /status` - config + data |
 | **Uploads** (`/api/threads/{id}/uploads`) | `POST /` - upload files (auto-converts PDF/PPT/Excel/Word); `GET /list` - list; `DELETE /{filename}` - delete |
-| **Artifacts** (`/api/threads/{id}/artifacts`) | `GET /{path}` - serve artifacts; `?download=true` for download with citation removal |
+| **Artifacts** (`/api/threads/{id}/artifacts`) | `GET /{path}` - serve artifacts; `?download=true` for file download |

 Proxied through nginx: `/api/langgraph/*` → LangGraph, all other `/api/*` → Gateway.
```

- **第 159 行**：表格中 Artifacts 描述由「download with citation removal」改为「file download」。

---

## 2026-06-01: API Keys 配置界面优化 — 后端

### `deerflow_extensions/env_settings/` — 路由迁移（路由从 `app/gateway/routers/env_settings.py` 迁至扩展目录）

**原因**: 零侵入原则——原本的 `env_settings.py` 在官方路由目录内，与上游源码混杂。

**改动**:
- **新建** `deerflow_extensions/env_settings/__init__.py` — 包文件
- **新建** `deerflow_extensions/env_settings/router.py` — 完整多厂商路由（7 个厂商的 GET/PUT/DELETE/verify）
- **新建** `deerflow_extensions/env_settings/startup.py` — `install_env_settings(app)` 注入函数
- **删除** `backend/app/gateway/routers/env_settings.py` — 旧文件（已迁移）
- **修改** `backend/app/gateway/app.py` — 删 import + include_router，加扩展注入块

### 新增能力（与之前一致）

- 支持 7 个国产大模型厂商管理：DeepSeek、Kimi、Doubao、Qwen、MiniMax、GLM、硅基流动
- 服务商下拉选择器
- 模型下拉选择（预置 + 自定义输入）
- 自定义请求地址（可选）
- Key 连通性验证
- 一键清除厂商全部配置
- `.env` 文件缺失时正常降级

---

## 2. `backend/packages/harness/deerflow/agents/lead_agent/prompt.py`

```diff
@@ -240,34 +240,8 @@ You have access to skills that provide optimized workflows for specific tasks. E
 - Action-Oriented: Focus on delivering results, not explaining processes
 </response_style>
 
-<citations_format>
-After web_search, ALWAYS include citations in your output:
-
-1. Start with a `<citations>` block in JSONL format listing all sources
-2. In content, use FULL markdown link format: [Short Title](full_url)
-
-**CRITICAL - Citation Link Format:**
-- CORRECT: `[TechCrunch](https://techcrunch.com/ai-trends)` - full markdown link with URL
-- WRONG: `[arXiv:2502.19166]` - missing URL, will NOT render as link
-- WRONG: `[Source]` - missing URL, will NOT render as link
-

## 2026-06-02: data_collection 过滤改分流标记

### `clean_and_aggregate.py` — DataCleaner 架构升级

**原因**: `filter_error_cases` 和 `filter_short_response` 直接丢弃错误/短回复数据，但这些数据是 Bad Case 分析的核心素材。

**改动**:
- `filter_error_cases()` → `tag_errors()` — 标记 `has_error=True` 而非丢弃
- `filter_short_response()` → `tag_short_response()` — 标记 `short_reply=True` 而非丢弃
- `clean()` → `process()` — 返回 `(clean, flagged)` 二元组实现数据分流
- `run_daily_pipeline()` — 新增 `flagged/{date}/flagged_data.jsonl` 输出，stats 新增 `flagged` 统计块
- `filter_incomplete` 和 `deduplicate` 保持不变

**影响**: 错误和短回复数据不再丢失，可用于 Bad Case 分析管线。训练集数据质量不变（只有无标签的 clean 数据进训练集）。

**测试覆盖**: 47 个单元测试（含 22 个新增暴力测试）全部通过。
-**Rules:**
-- Every citation MUST be a complete markdown link with URL: `[Title](https://...)`
-- Write content naturally, add citation link at end of sentence/paragraph
-- NEVER use bare brackets like `[arXiv:xxx]` or `[Source]` without URL
-
-**Example:**
-<citations>
-{{"id": "cite-1", "title": "AI Trends 2026", "url": "https://techcrunch.com/ai-trends", "snippet": "Tech industry predictions"}}
-{{"id": "cite-2", "title": "OpenAI Research", "url": "https://openai.com/research", "snippet": "Latest AI research developments"}}
-</citations>
-The key AI trends for 2026 include enhanced reasoning capabilities and multimodal integration [TechCrunch](https://techcrunch.com/ai-trends). Recent breakthroughs in language models have also accelerated progress [OpenAI](https://openai.com/research).
-</citations_format>
-
-
 <critical_reminders>
 - **Clarification First**: ALWAYS clarify unclear/missing/ambiguous requirements BEFORE starting work - never assume or guess
-- **Web search citations**: When you use web_search (or synthesize subagent results that used it), you MUST output the `<citations>` block and [Title](url) links as specified in citations_format so citations display for the user.
 {subagent_reminder}- Skill First: Always load the relevant skill before starting **complex** tasks.
```

```diff
@@ -341,7 +315,6 @@ def apply_prompt_template(subagent_enabled: bool = False) -> str:
     # Add subagent reminder to critical_reminders if enabled
     subagent_reminder = (
         "- **Orchestrator Mode**: You are a task orchestrator - decompose complex tasks into parallel sub-tasks and launch multiple subagents simultaneously. Synthesize results, don't execute directly.\n"
-        "- **Citations when synthesizing**: When you synthesize subagent results that used web search or cite sources, you MUST include a consolidated `<citations>` block (JSONL format) and use [Title](url) markdown links in your response so citations display correctly.\n"
         if subagent_enabled
         else ""
     )
```

- **删除**：`<citations_format>...</citations_format>` 整段（原约 243–266 行）、critical_reminders 中「Web search citations」一条、`apply_prompt_template` 中「Citations when synthesizing」一行。

---

## 3. `backend/app/gateway/routers/artifacts.py`

```diff
@@ -1,12 +1,10 @@
-import json
 import mimetypes
-import re
 import zipfile
 from pathlib import Path
 from urllib.parse import quote
 
-from fastapi import APIRouter, HTTPException, Request, Response
-from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
+from fastapi import APIRouter, HTTPException, Request
+from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
 
 from app.gateway.path_utils import resolve_thread_virtual_path
```

- **第 1 行**：删除 `import json`。
- **第 3 行**：删除 `import re`。
- **第 6–7 行**：`fastapi` 中去掉 `Response`；`fastapi.responses` 中增加 `Response`（保留二进制 inline 返回用）。

```diff
@@ -24,40 +22,6 @@ def is_text_file_by_content(path: Path, sample_size: int = 8192) -> bool:
         return False
 
 
-def _extract_citation_urls(content: str) -> set[str]:
-    """Extract URLs from <citations> JSONL blocks. Format must match frontend core/citations/utils.ts."""
-    urls: set[str] = set()
-    for match in re.finditer(r"<citations>([\s\S]*?)</citations>", content):
-        for line in match.group(1).split("\n"):
-            line = line.strip()
-            if line.startswith("{"):
-                try:
-                    obj = json.loads(line)
-                    if "url" in obj:
-                        urls.add(obj["url"])
-                except (json.JSONDecodeError, ValueError):
-                    pass
-    return urls
-
-
-def remove_citations_block(content: str) -> str:
-    """Remove ALL citations from markdown (blocks, [cite-N], and citation links). Used for downloads."""
-    if not content:
-        return content
-
-    citation_urls = _extract_citation_urls(content)
-
-    result = re.sub(r"<citations>[\s\S]*?</citations>", "", content)
-    if "<citations>" in result:
-        result = re.sub(r"<citations>[\s\S]*$", "", result)
-    result = re.sub(r"\[cite-\d+\]", "", result)
-
-    for url in citation_urls:
-        result = re.sub(rf"\[[^\]]+\]\({re.escape(url)}\)", "", result)
-
-    return re.sub(r"\n{3,}", "\n\n", result).strip()
-
-
 def _extract_file_from_skill_archive(zip_path: Path, internal_path: str) -> bytes | None:
```

- **删除**：`_extract_citation_urls`、`remove_citations_block` 两个函数（约 25–62 行）。

```diff
@@ -172,24 +136,9 @@ async def get_artifact(thread_id: str, path: str, request: Request) -> FileRespo
 
     # Encode filename for Content-Disposition header (RFC 5987)
     encoded_filename = quote(actual_path.name)
-    
-    # Check if this is a markdown file that might contain citations
-    is_markdown = mime_type == "text/markdown" or actual_path.suffix.lower() in [".md", ".markdown"]
-    
+
     # if `download` query parameter is true, return the file as a download
     if request.query_params.get("download"):
-        # For markdown files, remove citations block before download
-        if is_markdown:
-            content = actual_path.read_text()
-            clean_content = remove_citations_block(content)
-            return Response(
-                content=clean_content.encode("utf-8"),
-                media_type="text/markdown",
-                headers={
-                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
-                    "Content-Type": "text/markdown; charset=utf-8"
-                }
-            )
         return FileResponse(path=actual_path, filename=actual_path.name, media_type=mime_type, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"})
 
     if mime_type and mime_type == "text/html":
```

- **删除**：`is_markdown` 判断及「markdown 时读文件 + remove_citations_block + Response」分支；download 时统一走 `FileResponse`。

---

## 4. `backend/packages/harness/deerflow/subagents/builtins/general_purpose.py`

```diff
@@ -24,21 +24,10 @@ Do NOT use for simple, single-step operations.""",
 - Do NOT ask for clarification - work with the information provided
 </guidelines>
 
-<citations_format>
-If you used web_search (or similar) and cite sources, ALWAYS include citations in your output:
-1. Start with a `<citations>` block in JSONL format listing all sources (one JSON object per line)
-2. In content, use FULL markdown link format: [Short Title](full_url)
-- Every citation MUST be a complete markdown link with URL: [Title](https://...)
-- Example block:
-<citations>
-{"id": "cite-1", "title": "...", "url": "https://...", "snippet": "..."}
-</citations>
-</citations_format>
-
 <output_format>
 When you complete the task, provide:
 1. A brief summary of what was accomplished
-2. Key findings or results (with citation links when from web search)
+2. Key findings or results
 3. Any relevant file paths, data, or artifacts created
 4. Issues encountered (if any)
 </output_format>
```

- **删除**：`<citations_format>...</citations_format>` 整段。
- **第 40 行**：第 2 条由「Key findings or results (with citation links when from web search)」改为「Key findings or results」。

---

## 5. 新增 `deerflow_extensions/data_collection/`（18个文件）

**核心模块（5个）：**

| 文件 | 说明 |
|------|------|
| `__init__.py` | 包入口 |
| `collector.py` | 核心采集器，异步旁路写入JSONL，6个采集点P1-P6 |
| `config.py` | 配置加载，3级优先级（独立YAML > config.yaml > 环境变量） |
| `middleware.py` | 数据采集中间件，继承 langchain AgentMiddleware，4个钩子方法 |
| `startup.py` | monkey-patch启动注入，幂等保护+异常静默降级 |

**离线脚本（4个）：**

| 文件 | 说明 |
|------|------|
| `scripts/clean_and_aggregate.py` | 每日清洗→去重→过滤→聚合为OpenAI messages格式 |
| `scripts/validate_format.py` | LlamaFactory格式验证器，7条规则校验 |
| `scripts/export_formats.py` | 多格式导出（llamafactory_messages/sharegpt/alpaca_simple） |
| `scripts/quality_dashboard.py` | 数据质量日报 |

**单元测试（5个）：**

| 文件 | 说明 |
|------|------|
| `tests/test_collector.py` | 采集器测试（record方法/单例/异常安全/缓冲区flush） |
| `tests/test_config.py` | 配置加载测试（默认值/环境变量/文件回退） |
| `tests/test_validate_format.py` | 格式验证测试（13个用例覆盖全部验证规则） |
| `tests/test_export_formats.py` | 多格式导出测试（16个用例） |
| `tests/test_clean_and_aggregate.py` | 清洗聚合测试（28个用例） |

- 总计 **81个单元测试**全部通过。
- 所有模块零外部依赖，仅使用Python标准库。

## 6. 修改 `backend/app/gateway/app.py`

```diff
@@ -24,4 +24,32 @@
 from deerflow.config.app_config import get_app_config
 
+# Configure logging
+logging.basicConfig(
+    level=logging.INFO,
+    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
+    datefmt="%Y-%m-%d %H:%M:%S",
+)
+
+logger = logging.getLogger(__name__)
+
+# Data collection system (zero-injection, monkey-patch based)
+import os as _os
+import sys as _sys
+_ext_path = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), "..", "..", ".."))
+if _ext_path not in _sys.path:
+    _sys.path.insert(0, _ext_path)
+try:
+    from deerflow_extensions.data_collection.startup import install_data_collection
+    install_data_collection()
+    logger.info("[DataCollection] System installed successfully at startup")
+except ImportError:
+    logger.warning("[DataCollection] Package not found, data collection is disabled")
+except Exception as _e:
+    logger.warning(f"[DataCollection] Install failed: {_e}")
+
+
 @asynccontextmanager
```

- **第26-33行**：logging配置从第42行移至此处（解决日志初始化顺序问题）。
- **第35-48行**：新增 sys.path修复 + 采集系统注入。通过 `os.path` 追溯到项目根目录加入 `sys.path`，确保 `deerflow_extensions` 可被import。try/except保护，Import失败或异常时不中断DeerFlow启动。

## 7. 新增 ADS 统一认证系统 — 后端模块

**后端扩展目录** `deerflow_extensions/ads_auth/`:

| 文件 | 说明 |
|------|------|
| `__init__.py` | 包标记 |
| `config.py` | 从环境变量 `ADS_BASE_URL` 读取 ADS 地址 |
| `ads_auth.py` | 调 ADS `/jwt/login` 拿 JWT |
| `middleware.py` | ADSProxyMiddleware，唯一认证关口 |
| `router.py` | `POST /login/ads` 端点 |
| `token_manager.py` | token 存储 + 写 MCP config.json |
| `startup.py` | 中间件安装逻辑（幂等，try/except 降级） |
| `sitecustomize.py` | Python 自启动入口 |

**前置扩展** `deerflow_extensions/sitecustomize.py`:
- 合并加载 `data_collection` + `ads_auth` 两个扩展

**核心改动（1 行）**:

| 文件 | 行 | 说明 |
|------|----|------|
| `backend/app/gateway/auth_middleware.py` | +3 | `if getattr(request.state, "_ads_authenticated", False): return await call_next(request)` |

**测试文件**:

| 文件 | 说明 |
|------|------|
| `backend/tests/test_ads_auth_violent.py` | 5 个暴力测试项目：连续100次、并发50、服务器不可用、过期、恶意token |

**总变更统计**:

| 项目 | 数量 |
|------|------|
| 新增文件 | 15（后端8 + 前端7） |
| 修改文件 | 3（auth_middleware.py + docker-compose-dev.yaml + entrypoint.sh） |
| 零侵入验证 | ✅ 删除 `auth_middleware.py` 3行 + `docker-compose-dev.yaml` 4行 + `entrypoint.sh` 1行即可完全卸载 |

---

## 9. 2026-06-03: 角色定义外部化（v6）— 零侵入

### `deerflow_extensions/topic_guardrail/role_definition.txt` — 新增运行时角色定义文件

**原因**: `prompt.py` 编译进 PyInstaller 二进制后无法修改，将 `<role>` 角色定义移到扩展目录的独立文件。

**改动**:
- **新建** `deerflow_extensions/topic_guardrail/role_definition.txt` — 运行时角色定义（部署后直接编辑，重启生效）
- **修改** `deerflow_extensions/sitecustomize.py` — 追加第三个 monkey-patch 块，拦截 `apply_prompt_template`，读取 `role_definition.txt` 替换 `<role>` 区块
- **新建** `deerflow_extensions/topic_guardrail/tests/test_role_externalization.py` — 15 个暴力测试用例覆盖所有边界和注入场景

**特点**:
- 零核心源码侵入（全在 `deerflow_extensions/` 扩展目录）
- 文件不存在时静默使用编译时默认值（优雅降级）
- 15/15 暴力测试全部通过

---

## 10. 2026-06-03: deerflow_entry.py — PyInstaller 入口扩展注入 + 路径修复

### `backend/deerflow_entry.py` — 核心源码改动

**原因**：
1. `sitecustomize.py` 只被标准 CPython 解释器自动加载，PyInstaller 二进制不加载它 → 生产环境 3 个 patch 不生效
2. 原 `_ext_internal` 路径检测只匹配 dev 模式（`backend/deerflow_extensions/`），不匹配 frozen 模式（`_internal/deerflow_extensions/`）

**改动**：

| 改动 | 行号 | 说明 |
|------|------|------|
| `_ext_internal` 路径检测 | L20-L34 | 优先查找 `_internal/deerflow_extensions/`，fallback 到 dev 路径 |
| 第 11 节新增 3 个 patch | L164-L226 | SensitiveWordMiddleware / IMMUTABLE CONSTRAINT / Role override |

**配套修复**：
- `deerflow_extensions/sitecustomize.py` — `__file__` → `realpath(__file__)` 修复 symlink 路径问题

**影响**：生产部署（PyInstaller 二进制）现在能正确加载全部 TopicGuardrail 功能。

---

## Appendix：ADS 认证迭代历史

### 早期方案（已过时，被当前方案取代）

**ADS 认证迭代：零侵入优化 + 循环修复**

> **⚠️ 本节描述的是早期方案（ADSProxyMiddleware + scope 通信），已在后续迭代中全部重写。当前实际方案见上文第7节。**

**SSR 兼容 — Cookie 双写** (`deerflow_extensions/ads_auth/router.py`):
- 登录时同时设 `ads_token` + `access_token` 两个 HttpOnly Cookie
- `access_token` 兼容原有 `server.ts` 的 `cookieStore.get("access_token")`

**中间件双接受** (`deerflow_extensions/ads_auth/middleware.py`):
- 第 49 行：`request.cookies.get("ads_token") or request.cookies.get("access_token")`
- 两个 cookie 名都接受，原有 Newtork AuthMiddleware hook 不变

**核心源码改动**: **0 行新增**。所有逻辑均在扩展目录中实现。

### 当前方案来源：认证修复演进

**动机**: 登录后 `/auth/me` 返回 500 (`User.email` 必须是有效域名) 或 401 (`invalid_signature`)。ADSToken 用 ADS 服务器的 secret 签发，DeerFlow 原生 JWT 验证用 `AUTH_JWT_SECRET`，两者不兼容。

**修复内容**:

| Bug | 根因 | 修复 |
|-----|------|------|
| User.email 无效 | `ads.local` 不是合法 TLD | 改用 `example.com` |
| Cookie 不保存 | `secure=True` 阻止 HTTP 保存 | 改为 `secure=False` |
| /auth/me 500 | Pydantic 验证 `id=username` 不是 UUID | 不传 `id`，让 `default_factory=uuid4` 自动生成 |
| /auth/me 401 | 原生 JWT 验证用 `AUTH_JWT_SECRET` 检查 ADS token | 在 AuthMiddleware 内联 ADS JWT decode，直接提取 payload |
| /auth/me 401 (下游route) | `get_current_user_from_request` 重新解码 cookie 用原生 secret | `deps.py` 先查 `request.state.user`（5行守卫） |
| /auth/me 401 (cookie丢失) | ASGI 层 ADSProxyMiddleware 读取 `scope["headers"]` 后干扰 Starlette cookie 解析 | 移除 ADSProxyMiddleware，AuthMiddleware 直接读 `request.cookies` |
| ADS_BASE_URL 没生效 | `serve.sh` source `.env`，但 `uv run` 不传递 shell 环境变量 | `config.py` 增加 `_load_dotenv()` 自动加载 `.env` |
| Thread 404 | `User.id=uuid4()` 每次请求不同 → authz 拒绝访问 | 用 `uuid5("ads-{username}")` 确定性 UUID |
| Cross-site auth 403 | 浏览器带 `Origin: http://localhost:2026` → backend 看到 `Host: localhost:8001`，CSRF 中间件判断跨域 | 改为"仅当 `GATEWAY_CORS_ORIGINS` 配置时才检查" |
| Thread 404 (部署) | `deerflow_entry.py` 双重 `create_app()` → ADS 路由注册到错误实例 | 改为直接 `from app.gateway.app import app` |
| cp 摊平结构 (部署) | `cp -r src/* dst/` 丢失目录层级，`server-release.sh` 路径不匹配 | 用 `cp -r src/dir dst/` 整体复制 |
| 8001 端口僵尸进程 | `trae-sandbox` 多级 bwrap 进程 `--die-with-parent` | 手动清理后迁移到 8002 测试 |

**核心源码改动**（9 个文件）:
- `app.py` — ADS 路由注册块（try/except 包裹）
- `auth_middleware.py` — 内联 JWT decode + 确定性 UUID（~28 行）
- `csrf_middleware.py` — frozenset 加 `/login/ads`（1 行）
- `deps.py` — `get_current_user_from_request` 先查 `request.state.user`（6 行守卫）
- `docker-compose-dev.yaml` — 加 `ADS_BASE_URL` 环境变量
- `next.config.js` — `rewrites()` 改为 `{beforeFiles, afterFiles, fallback}` 格式
- `middleware.ts` — 从 1 行 re-export 改为 37 行内联
- `types.ts` — `buildLoginUrl` 返回 `/ads-login` 替代 `/login`
- `.env.example` — 新增 `GATEWAY_CORS_ORIGINS` + ADS 配置示例

**扩展目录改动**（不侵入核心）:
- `router.py` — cookie `secure=True → False`
- `startup.py` — 不再注册 ADSProxyMiddleware
- `config.py` — 增加 `.env` 自动加载

---

## 8. 新增 env-settings 路由

**动机**: 提供环境变量设置管理 API，支持前端在 SettingsDialog 中直接配置 DeepSeek API Key 并验证连通性。

### 核心改动

**B1：`backend/app/gateway/app.py` — env_settings 路由注册**

| 位置 | 行号 | 改动 |
|------|------|------|
| import | L20 | `from app.gateway.routers import ... env_settings ...` |
| openapi_tags | L314-L316 | 新增 `env-settings` 标签描述 |
| include_router | L413-L414 | `app.include_router(env_settings.router)` |

### 配套模块（后端核心，非补丁）

**`backend/app/gateway/routers/env_settings.py`**（136 行，3 个端点）：

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/env-settings` | 读取环境变量（值已掩码） |
| `PUT` | `/api/env-settings` | 更新 DeepSeek API Key 并写入 `.env` |
| `POST` | `/api/env-settings/deepseek/verify` | 验证 Key 有效性 |

### 配套前端模块

`frontend/src/core/env-settings/`（5 个文件）：types / api / hooks / page / extension，通过 `registerSettingsExtension()` 向 SettingsDialog 注入 API Keys 设置页面。

### 2026-06-02: Env Settings Bug 修复

**文件**: `deerflow_extensions/env_settings/router.py`（全部在扩展目录，零侵入）

| 修复 | 改动 | 原因 |
|------|------|------|
| **model 必填** | `str \| None = None` → `str` (`min_length=1`) | 空 model 也能保存，保存后不注册 config.yaml |
| **429 限流检测** | verify 端点新增 `status_code == 429` 分支 | 频繁验证时"网络错误"不明确 |
| **详细日志** | `_register_model_to_config` + `_remove_models_from_config` 增加详细文件读写日志 | 清除后重保存模型不出现，需日志定位 |
| **异常处理** | try/except 包裹所有 config.yaml 文件读写 | 防止文件损坏或权限问题时崩溃 |
| **PUT 简化** | 移除 `if request.model` 判断 | model 已必填，无需可选分支 |

**暴力测试结果**：15 项后端测试全部通过（空 model 422、硅基保存/验证/删除/循环 3 次、连续验证 5 次无网络错误、config.yaml 同步注册/清理）。

---

### 详细补丁

详细补丁记录见 `@./docs/patches/settings-dialog-ext/backend.md`（补丁标签 B1）

---

## 2026-05-29: 首屏闪屏修复 + ADS JWT 安全加固

### `backend/app/gateway/auth_middleware.py` — ADS JWT exp 验证

**改动**: 在 ADS JWT 解码段（L84-L90）新增 `exp` 字段提取和过期判断。如果 token 过期则跳过 ADS 认证路径，回退到原生 JWT 验证。

**原因**: 安全漏洞修复——已过期的 ADS JWT 也能通过认证。

### `deerflow_extensions/ads_auth/router.py` — 动态 max_age + 统一 cookie 名

**改动**:
1. 解码 JWT payload 提取 `exp`，动态计算 `max_age = max(exp - time.time(), 0)`
2. 统一只设置 `access_token`，不再同时设置 `ads_token`

**原因**: cookie 寿命与 JWT 对齐；统一 cookie 命名消除前端中间件/SSR/后端各层 cookie 名不一致的隐患。

---

## 11. 2026-06-04: TopicGuardrail 角色注入架构升级

### 问题背景
- 本地开发模式和 PyInstaller 打包模式下角色注入完全不生效
- 根因 #1：`app.py` 缺少 topic_guardrail 的 try/except 注入块（已有 data_collection/ads_auth/env_settings）
- 根因 #2：函数 monkeypatch（替换 `apply_prompt_template` 引用）在 `from X import Y` 导入模式下不可靠

### 改动

#### `deerflow_extensions/patch_manager.py` — `_patch_role()` 重写
- **架构升级**：从替换函数引用改为替换模块级字符串 `SYSTEM_PROMPT_TEMPLATE`
- 原理：Python 函数通过 `LOAD_GLOBAL` 字节码动态查找模块全局变量，修改后所有调用者不论如何导入都立即生效
- 保留 mtime 缓存、内容校验、空文件/过短告警

#### `backend/app/gateway/app.py` — 新增第 4 个扩展注入块
- 在 `env_settings` 注入之后、`AuthMiddleware` 之前添加 TopicGuardrail try/except 注入
- 与 `data_collection`/`ads_auth`/`env_settings` 的注入模式完全一致

### 测试覆盖
- 25 个单元测试（7 个维度）：模板替换基础、极端内容、错误恢复、并发安全、幂等性、与其他 patch 不冲突、Python LOAD_GLOBAL 语义验证
- API 端到端测试脚本（19 个用例）：基础功能、重启持久化、并发/稳定性、回归验证
- 嵌入模式验证：直接调用 `apply_prompt_template()` 确认 prompt 含东方亿盟角色定义

### 连带修复：duplicate middleware 问题

**根因**：`sitecustomize.py` 用 `from patch_manager import apply_all`（`sys.modules['patch_manager']`），而 `app.py` 用 `from deerflow_extensions.patch_manager import apply_all`（`sys.modules['deerflow_extensions.patch_manager']`），Python 视为两个不同模块对象，`_APPLIED` 幂等保护失效，导致 SensitiveWordMiddleware 被注入两次。

**修复**：
- `sitecustomize.py`、`deerflow_entry.py` 统一为 `from deerflow_extensions.patch_manager import apply_all`
- `_patch_sensitive_word()` 加 `isinstance` 双重守卫

### 验证
```bash
grep "TopicGuardrail.*Patches:" logs/gateway.log     # ✅ 应含 3 个 ✅
grep "SYSTEM_PROMPT_TEMPLATE updated" logs/gateway.log  # 角色注入成功
cd backend && PYTHONPATH=.:../deerflow_extensions:packages/harness uv run python3 \
  -m pytest ../deerflow_extensions/topic_guardrail/tests/test_role_injection_fix.py -v  # 25/25
```

---

## 12. 2026-06-04: Boot Loader — 扩展注入统一入口

### 问题背景
- 4 个扩展的注入逻辑分散在 `app.py`（50+ 行重复 try/except）、`deerflow_entry.py`（5 行）、3 个 `sitecustomize.py`（含 2 个死代码）中
- 每次加新扩展需在多处各写一份 sys.path + try/except 模板代码

### 改动

#### `deerflow_extensions/boot.py` — 新增统一 Boot Loader
**风险**: ✅ 零（全在扩展目录）
- `boot_all_extensions(app)` — 按序加载 data_collection → ads_auth → env_settings → topic_guardrail
- `boot_topic_guardrail_early(ext_internal)` — PyInstaller 专用 pre-import 注入
- 统一日志格式 `[Boot]`，统一 try/except 错误隔离

#### `app.py` — 注入逻辑精简
- 删除 57 行重复代码，改为 `boot_all_extensions(app=app)` 一次调用
- **修复**：Boot Loader 代码块缺少 `import sys`，导致 `NameError`。已添加 `import sys as _sys`

#### `deerflow_entry.py` — 精简
- `from patch_manager import apply_all` → `from deerflow_extensions.boot import boot_topic_guardrail_early`

#### `entrypoint.sh` — 移除 sitecustomize
- 删除 `ln -s .../sitecustomize.py` symlink，改为 `python3 -c boot_all_extensions()` 直接调用

#### 删除 3 个死 sitecustomize.py
- `deerflow_extensions/sitecustomize.py`、`ads_auth/sitecustomize.py`、`data_collection/sitecustomize.py` — 全部删除（从未被 Gateway 主进程加载）

### 验证
```bash
python3 -m pytest .../test_boot_loader.py -v  # 26/26
```

---

## 13. 2026-06-04: 敏感词检测纵深防御（v7）

### 变更范围
全部在 `deerflow_extensions/topic_guardrail/` 扩展目录，零核心源码侵入。

### 新增文件
- `text_preprocessor.py` — 输入文本预处理模块
- `wordlist/pinyin_variants.txt` — 拼音/英文变体黑名单
- `tests/test_text_preprocessor.py` — 17 个单元测试
- `tests/test_sensitive_word_middleware.py` — 14 个单元测试
- `tests/test_sensitive_word_bypass.py` — 34 个暴力测试用例
- `tests/run_violent_tests.sh` — API 批量测试脚本

### 核心改动
| 改动 | 文件 | 说明 |
|------|------|------|
| Fail-Closed 加固 | `sensitive_word_middleware.py` | `except AttributeError: pass` → `except Exception: return True`；`_automaton is None` → CRITICAL 日志 + 拒绝 |
| TextPreprocessor 集成 | `sensitive_word_middleware.py` + `text_preprocessor.py` | NFC归一化→零宽清除→全角→半角→空格压缩→单字母间隙压缩→lowercase→拼音检测 |
| 拼音变体词源 | `_build_automaton()` 加第三词源 | 加载 `pinyin_variants.txt` |
| 审计日志 | `_build_blocked()` | `AUDIT|BLOCKED|reason=...|ts=...` |
| 语义审核 | `_semantic_check()` | 可选集成（默认关闭） |
| L1 硬约束 | `role_definition.txt` | `STRICTLY FORBIDDEN` 禁止事项 |
| 词库补全 | `custom_sensitive_words.txt` | 特朗普、川普、拜登等 |
| 配置升级 | `topics.yaml` | `pinyin_variants`、`semantic_guard`、`audit` |

### 测试结果
65/65 全部通过，零误杀：全类绕过手法防御有效，正常 IT 问题完全不受影响。

---

## 14. 2026-06-04: PyInstaller 数据文件路径修复

### 问题
PyInstaller `--onedir` 模式下，模块在 `_internal/topic_guardrail/`，数据文件在 `_internal/deerflow_extensions/topic_guardrail/`，路径错位导致 `topics.yaml` 和 `wordlist/*.txt` 找不到，`SensitiveWordMiddleware` 初始化失败。

### 修改
| 文件 | 改动 |
|------|------|
| `sensitive_word_middleware.py` | `_load_config()` + `_resolve_word_path()` 增加 PyInstaller fallback |
| `build-backend-on-server.sh` | 新增 2 行 `--add-data` 映射到模块路径 |

### 修复策略（双重保障）
- **方案 A（运行时 fallback）**：代码自动尝试 `deerflow_extensions/` 前缀路径
- **方案 B（构建时 `--add-data`）**：编译时直接将数据文件映射到 `topic_guardrail/` 模块目录

### 测试结果
7/7 全部通过（PF01-PF04 路径 fallback + P01-P03/P06 功能回归）
