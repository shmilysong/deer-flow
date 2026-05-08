# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['app', 'app.gateway', 'app.gateway.app', 'app.gateway.deps', 'app.gateway.config', 'app.gateway.authz', 'app.gateway.services', 'app.gateway.auth_middleware', 'app.gateway.csrf_middleware', 'app.gateway.internal_auth', 'app.gateway.langgraph_auth', 'app.gateway.path_utils', 'app.gateway.utils', 'app.gateway.routers', 'app.gateway.routers.agents', 'app.gateway.routers.artifacts', 'app.gateway.routers.assistants_compat', 'app.gateway.routers.auth', 'app.gateway.routers.channels', 'app.gateway.routers.feedback', 'app.gateway.routers.mcp', 'app.gateway.routers.memory', 'app.gateway.routers.models', 'app.gateway.routers.runs', 'app.gateway.routers.skills', 'app.gateway.routers.suggestions', 'app.gateway.routers.thread_runs', 'app.gateway.routers.threads', 'app.gateway.routers.uploads', 'app.gateway.auth', 'app.gateway.auth.repositories', 'app.gateway.auth.repositories.base', 'app.gateway.auth.repositories.sqlite', 'app.channels', 'app.channels.service', 'app.channels.manager', 'app.channels.base', 'app.channels.commands', 'app.channels.message_bus', 'app.channels.store', 'app.channels.dingtalk', 'app.channels.discord', 'app.channels.feishu', 'app.channels.slack', 'app.channels.telegram', 'app.channels.wechat', 'app.channels.wecom', 'langchain', 'langchain_core', 'langgraph', 'langgraph.runtime', 'langchain_openai', 'langchain_anthropic', 'langchain_deepseek', 'langchain_google_genai', 'deerflow.models.patched_openai', 'deerflow.models.patched_deepseek', 'deerflow.models.patched_minimax', 'deerflow.models.vllm_provider', 'deerflow.models.mindie_provider', 'deerflow.models.claude_provider', 'deerflow.models.openai_codex_provider', 'deerflow.sandbox.local', 'deerflow.sandbox.tools', 'deerflow.community.aio_sandbox', 'deerflow.community.ddg_search', 'deerflow.community.serper', 'deerflow.community.tavily', 'deerflow.community.infoquest', 'deerflow.community.exa', 'deerflow.community.firecrawl', 'deerflow.community.jina_ai', 'deerflow.community.image_search', 'deerflow.tools.builtins', 'deerflow.tools.builtins.tool_search', 'deerflow.tools.skill_manage_tool', 'deerflow.tools.builtins.invoke_acp_agent_tool', 'deerflow.guardrails.builtin', 'deerflow.skills.storage.local_skill_storage', 'deerflow.runtime', 'deerflow.runtime.converters', 'deerflow.runtime.journal', 'deerflow.runtime.serialization', 'deerflow.runtime.user_context', 'deerflow.runtime.checkpointer', 'deerflow.runtime.checkpointer.async_provider', 'deerflow.runtime.checkpointer.provider', 'deerflow.runtime.events', 'deerflow.runtime.events.store', 'deerflow.runtime.events.store.base', 'deerflow.runtime.events.store.db', 'deerflow.runtime.events.store.jsonl', 'deerflow.runtime.events.store.memory', 'deerflow.runtime.runs', 'deerflow.runtime.runs.manager', 'deerflow.runtime.runs.schemas', 'deerflow.runtime.runs.worker', 'deerflow.runtime.runs.store', 'deerflow.runtime.runs.store.base', 'deerflow.runtime.runs.store.memory', 'deerflow.runtime.store', 'deerflow.runtime.store.async_provider', 'deerflow.runtime.store.provider', 'deerflow.runtime.store._sqlite_utils', 'deerflow.runtime.stream_bridge', 'deerflow.runtime.stream_bridge.async_provider', 'deerflow.runtime.stream_bridge.base', 'deerflow.runtime.stream_bridge.memory', 'deerflow.persistence', 'deerflow.persistence.base', 'deerflow.persistence.engine', 'deerflow.persistence.feedback', 'deerflow.persistence.feedback.model', 'deerflow.persistence.feedback.sql', 'deerflow.persistence.models', 'deerflow.persistence.models.run_event', 'deerflow.persistence.run', 'deerflow.persistence.run.model', 'deerflow.persistence.run.sql', 'deerflow.persistence.thread_meta', 'deerflow.persistence.thread_meta.base', 'deerflow.persistence.thread_meta.memory', 'deerflow.persistence.thread_meta.model', 'deerflow.persistence.thread_meta.sql', 'deerflow.persistence.user', 'deerflow.persistence.user.model']
hiddenimports += collect_submodules('langchain')
hiddenimports += collect_submodules('langchain_core')
hiddenimports += collect_submodules('langgraph')
hiddenimports += collect_submodules('deerflow')


a = Analysis(
    ['deerflow_entry.py'],
    pathex=['.', 'packages/harness'],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests', 'docs', 'tkinter', 'matplotlib'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='deerflow-gateway',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='deerflow-gateway',
)
