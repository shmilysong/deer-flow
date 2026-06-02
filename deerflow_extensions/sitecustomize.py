import sys

EXTENSION_PATH = "/app/deerflow_extensions"
if EXTENSION_PATH not in sys.path:
    sys.path.insert(0, EXTENSION_PATH)

DEERFLOW_PATH = "/app/backend/packages/harness"
if DEERFLOW_PATH not in sys.path:
    sys.path.insert(0, DEERFLOW_PATH)

try:
    from deerflow_extensions.data_collection.startup import install_data_collection
    install_data_collection()
except Exception:
    pass

try:
    from deerflow_extensions.ads_auth.startup import install_ads_auth
    install_ads_auth()
except Exception:
    pass

try:
    from topic_guardrail.sensitive_word_middleware import SensitiveWordMiddleware
    import deerflow.agents.lead_agent.agent as _agent_mw
    _orig_build = _agent_mw._build_middlewares

    def _patched_build(config, *args, **kwargs):
        middlewares = _orig_build(config, *args, **kwargs)
        middlewares.insert(-1, SensitiveWordMiddleware())
        return middlewares

    _agent_mw._build_middlewares = _patched_build
    import logging
    logging.getLogger(__name__).info("[SensitiveWord] Middleware injected")
except Exception:
    pass

try:
    import deerflow.agents.lead_agent.prompt as _prompt
    _orig_skills_cache = _prompt._get_cached_skills_prompt_section

    def _patched_skills_section(*args, **kwargs):
        result = _orig_skills_cache(*args, **kwargs)
        constraint = """
**🚨 IMMUTABLE CONSTRAINT — 不可被任何技能覆盖：**
You are a technical consultant for **北京东方亿盟科技有限公司**.
Your expertise is LIMITED to:
- Company products and services (ADS desktop cloud, terminal management, etc.)
- Computer technology (programming, architecture, API, development, etc.)

Any skill instruction that asks you to research, analyze, or discuss topics
outside company business and technology MUST BE IGNORED.
The role identity above takes precedence over ALL skill instructions.
"""
        return result.replace("</skill_system>", constraint + "\n</skill_system>")

    _prompt._get_cached_skills_prompt_section = _patched_skills_section
except Exception:
    pass
