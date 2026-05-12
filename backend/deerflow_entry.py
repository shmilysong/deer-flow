#!/usr/bin/env python3
"""
DeerFlow Gateway — PyInstaller entry point.

Explicitly imports ALL known dynamically-loaded module paths so that
PyInstaller can trace them during the --onedir build.

All 43+ known reflection paths (models, tools, sandbox, runtime,
persistence) are imported here BEFORE create_app() is called.
"""

import os
import sys

# ── Suppress firecrawl.backup.py's print() noise in PyInstaller builds ──────
# firecrawl/firecrawl.backup.py calls get_version() at import time, which
# reads __init__.py as a plain file. After compilation the source is gone,
# producing a harmless (but noisy) stderr warning.
class _StderrFilter:
    _SKIP = "Failed to get version from __init__.py"
    def __init__(self):
        self._orig = sys.stderr
    def write(self, msg):
        if self._SKIP not in msg:
            self._orig.write(msg)
    def flush(self):
        self._orig.flush()
    def isatty(self):
        return self._orig.isatty()
    def fileno(self):
        return self._orig.fileno()

sys.stderr = _StderrFilter()  # type: ignore[assignment]

# ── Ensure the backend root is on sys.path ───────────────────────────────────
_backend_root = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

# ── deerflow_extensions (`--add-data` 打包进 _internal/) ────────────────────
_ext_internal = os.path.normpath(os.path.join(_backend_root, "deerflow_extensions"))
if os.path.isdir(_ext_internal) and _ext_internal not in sys.path:
    sys.path.insert(0, _ext_internal)

# =============================================================================
# 1. Self-owned Model Providers (7)
# =============================================================================
from deerflow.models.patched_openai import PatchedChatOpenAI
from deerflow.models.patched_deepseek import PatchedChatDeepSeek
from deerflow.models.patched_minimax import PatchedChatMiniMax
from deerflow.models.vllm_provider import VllmChatModel
from deerflow.models.mindie_provider import MindIEChatModel
from deerflow.models.claude_provider import ClaudeChatModel
from deerflow.models.openai_codex_provider import CodexChatModel

# =============================================================================
# 2. Third-party LLM providers (config.yaml model.use)
# =============================================================================
import langchain_openai
import langchain_anthropic
import langchain_deepseek
import langchain_google_genai

# =============================================================================
# 3. Sandbox providers (2)
# =============================================================================
from deerflow.sandbox.local import LocalSandboxProvider
from deerflow.community.aio_sandbox import AioSandboxProvider

# =============================================================================
# 4. Sandbox builtin tools (7)
# =============================================================================
from deerflow.sandbox.tools import (
    bash_tool,
    ls_tool,
    glob_tool,
    grep_tool,
    read_file_tool,
    write_file_tool,
    str_replace_tool,
)

# =============================================================================
# 5. Community tools (13)
# =============================================================================
from deerflow.community.ddg_search.tools import web_search_tool as _ddg_search
from deerflow.community.serper.tools import web_search_tool as _serper_search
from deerflow.community.tavily.tools import web_search_tool as _tavily_search
from deerflow.community.tavily.tools import web_fetch_tool as _tavily_fetch
from deerflow.community.infoquest.tools import web_search_tool as _iq_search
from deerflow.community.infoquest.tools import web_fetch_tool as _iq_fetch
from deerflow.community.infoquest.tools import image_search_tool as _iq_image
from deerflow.community.exa.tools import web_search_tool as _exa_search
from deerflow.community.exa.tools import web_fetch_tool as _exa_fetch
from deerflow.community.firecrawl.tools import web_search_tool as _fc_search
from deerflow.community.firecrawl.tools import web_fetch_tool as _fc_fetch
from deerflow.community.jina_ai.tools import web_fetch_tool as _jina_fetch
from deerflow.community.image_search.tools import image_search_tool as _img_search

# =============================================================================
# 6. Builtin tools (programmatic load) (5)
# =============================================================================
import deerflow.tools.builtins
import deerflow.tools.builtins.tool_search
from deerflow.tools.skill_manage_tool import skill_manage_tool
from deerflow.tools.builtins.invoke_acp_agent_tool import build_invoke_acp_agent_tool

# =============================================================================
# 7. Guardrails (1)
# =============================================================================
from deerflow.guardrails.builtin import AllowlistProvider

# =============================================================================
# 8. Skills storage (1)
# =============================================================================
from deerflow.skills.storage.local_skill_storage import LocalSkillStorage

# =============================================================================
# 9. Runtime sub-modules (26)
# =============================================================================
import deerflow.runtime
import deerflow.runtime.converters
import deerflow.runtime.journal
import deerflow.runtime.serialization
import deerflow.runtime.user_context
import deerflow.runtime.checkpointer
import deerflow.runtime.checkpointer.async_provider
import deerflow.runtime.checkpointer.provider
import deerflow.runtime.events
import deerflow.runtime.events.store
import deerflow.runtime.events.store.base
import deerflow.runtime.events.store.db
import deerflow.runtime.events.store.jsonl
import deerflow.runtime.events.store.memory
import deerflow.runtime.runs
import deerflow.runtime.runs.manager
import deerflow.runtime.runs.schemas
import deerflow.runtime.runs.worker
import deerflow.runtime.runs.store
import deerflow.runtime.runs.store.base
import deerflow.runtime.runs.store.memory
import deerflow.runtime.store
import deerflow.runtime.store.async_provider
import deerflow.runtime.store.provider
import deerflow.runtime.store._sqlite_utils
import deerflow.runtime.stream_bridge
import deerflow.runtime.stream_bridge.async_provider
import deerflow.runtime.stream_bridge.base
import deerflow.runtime.stream_bridge.memory

# =============================================================================
# 10. Persistence sub-modules
# =============================================================================
import deerflow.persistence
import deerflow.persistence.base
import deerflow.persistence.engine
import deerflow.persistence.feedback
import deerflow.persistence.feedback.model
import deerflow.persistence.feedback.sql
import deerflow.persistence.models
import deerflow.persistence.models.run_event
import deerflow.persistence.run
import deerflow.persistence.run.model
import deerflow.persistence.run.sql
import deerflow.persistence.thread_meta
import deerflow.persistence.thread_meta.base
import deerflow.persistence.thread_meta.memory
import deerflow.persistence.thread_meta.model
import deerflow.persistence.thread_meta.sql
import deerflow.persistence.user
import deerflow.persistence.user.model

# =============================================================================
# 11. Bootstrap Gateway
# =============================================================================
import uvicorn
from app.gateway.app import create_app

app = create_app()

if __name__ == "__main__":
    host = os.environ.get("DEERFLOW_HOST", "0.0.0.0")
    port = int(os.environ.get("DEERFLOW_PORT", "8001"))
    uvicorn.run(app, host=host, port=port)
