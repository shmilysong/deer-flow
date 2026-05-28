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

## 附录：ADS 认证迭代历史

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
