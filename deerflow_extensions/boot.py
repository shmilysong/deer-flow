"""
boot.py — Unified extension injection entry point.

All four deerflow_extensions modules are loaded here, so app.py,
deerflow_entry.py, and Docker entrypoint.sh only need a single call
instead of copy-pasting try/except blocks for each extension.

Called from:
  - app.py lifespan:       boot_all_extensions(app=app)
  - deerflow_entry.py:     boot_topic_guardrail_early(ext_internal)
  - Docker entrypoint.sh:  python3 -c "from deerflow_extensions.boot import boot_all_extensions; boot_all_extensions()"

Each extension's startup.py / patch_manager.py has its own
_installed / _APPLIED guard — safe to call multiple times.
"""
import os
import sys
import logging

_logger = logging.getLogger("Boot")

_EXTENSIONS = [
    ("data_collection",  False),   # monkey-patch, no app needed
    ("ads_auth",         True),    # app.include_router()
    ("env_settings",     True),    # app.include_router()
    ("topic_guardrail",  False),   # apply_all() — own _APPLIED guard
]


def _resolve_project_root() -> str | None:
    """Locate the project root directory.

    Tries (in order):
      1. PyInstaller frozen → sys.executable parent
      2. CWD  = <project>/backend        → ../
      3. CWD  = <project>                → ./
    """
    if getattr(sys, "frozen", False):
        me = os.path.dirname(os.path.abspath(sys.executable))
        cand = os.path.join(me, "_internal", "deerflow_extensions")
        if os.path.isdir(cand):
            return me

    cwd = os.getcwd()
    candidates = [
        os.path.join(cwd, ".."),
        cwd,
    ]
    for cand in candidates:
        cand = os.path.normpath(cand)
        if os.path.isdir(os.path.join(cand, "deerflow_extensions")):
            return cand
    return None


def boot_all_extensions(app=None, ext_internal=None):
    """Boot all registered extensions. Idempotent at individual extension level."""
    root = _resolve_project_root()
    if root and root not in sys.path:
        sys.path.insert(0, root)

    results = {}
    for name, needs_app in _EXTENSIONS:
        ext_internal_arg = ext_internal if name == "topic_guardrail" else None
        try:
            _boot_one(name, app if needs_app else None, ext_internal_arg)
            results[name] = "✅"
        except ImportError:
            _logger.warning("[Boot] %s not found, disabled", name)
            results[name] = "⚠️ skipped"
        except Exception as e:
            _logger.warning("[Boot] %s failed: %s", name, e)
            results[name] = f"❌ {e}"

    summary = " ".join(f"{k}{v}" for k, v in results.items())
    _logger.info("[Boot] Complete: %s", summary)


def boot_topic_guardrail_early(ext_internal=None):
    """Apply topic_guardrail patches BEFORE app module is imported.

    Required by PyInstaller (deerflow_entry.py) because the 43+ static
    imports and the subsequent 'from app.gateway.app import app' may
    trigger prompt.py / agent.py module loading before the lifespan
    would run.
    """
    try:
        from deerflow_extensions.patch_manager import apply_all
        apply_all(ext_internal=ext_internal)
        _logger.info("[Boot] topic_guardrail early-boot applied")
    except ImportError:
        _logger.warning("[Boot] topic_guardrail not found, early-boot skipped")
    except Exception as e:
        _logger.warning("[Boot] topic_guardrail early-boot failed: %s", e)


def _boot_one(name: str, app=None, ext_internal=None):
    """Boot a single extension by name."""
    if name == "data_collection":
        from deerflow_extensions.data_collection.startup import install_data_collection
        install_data_collection()
    elif name == "ads_auth":
        from deerflow_extensions.ads_auth.startup import install_ads_auth
        install_ads_auth(app=app)
    elif name == "env_settings":
        from deerflow_extensions.env_settings.startup import install_env_settings
        install_env_settings(app=app)
    elif name == "topic_guardrail":
        from deerflow_extensions.patch_manager import apply_all
        apply_all(ext_internal=ext_internal)
