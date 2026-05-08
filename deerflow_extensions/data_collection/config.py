"""Configuration module for data collection.

Configuration source priority (highest to lowest):
  1. Standalone YAML file (e.g., data_collection.yaml)
  2. DeerFlow config.yaml `data_collection` section
  3. Environment variables (DATA_COLLECTION_*)
  4. DEFAULT_CONFIG defaults
"""

import os
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "output_dir": "./data_collection_logs",
    "buffer_size": 500,
    "flush_interval_sec": 5.0,
    "max_file_size_mb": 100,
    "collect_agent_input": True,
    "collect_model_output": True,
    "collect_tool_calls": True,
    "collect_intermediate_state": False,
    "collect_final_response": True,
    "role_extract_mode": "auto",
}

_ENV_VAR_MAP: dict[str, tuple[str, callable]] = {
    "DATA_COLLECTION_ENABLED": ("enabled", lambda v: v.lower() == "true"),
    "DATA_COLLECTION_OUTPUT_DIR": ("output_dir", str),
    "DATA_COLLECTION_BUFFER_SIZE": ("buffer_size", int),
    "DATA_COLLECTION_FLUSH_INTERVAL": ("flush_interval_sec", float),
    "DATA_COLLECTION_ROLE_EXTRACT_MODE": ("role_extract_mode", str),
}


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load data collection configuration from available sources.

    Priority:
      1. Standalone YAML file specified by config_path
      2. DeerFlow config.yaml `data_collection` section
      3. Environment variable overrides
      4. DEFAULT_CONFIG fallback values

    Args:
        config_path: Optional path to a standalone YAML configuration file.

    Returns:
        Merged configuration dictionary.
    """
    config = dict(DEFAULT_CONFIG)

    # Priority 1: Standalone YAML file
    if config_path and os.path.exists(config_path):
        try:
            import yaml as _yaml
            with open(config_path, encoding="utf-8") as f:
                external = _yaml.safe_load(f) or {}
                external_dc = external.get("data_collection", {})
                if external_dc:
                    config.update(external_dc)
                    return _apply_env_overrides(config)
        except Exception:
            pass

    # Priority 2: DeerFlow config.yaml data_collection section
    try:
        from deerflow.config.app_config import get_app_config

        app_cfg = get_app_config()
        app_cfg_dict = app_cfg.model_dump() if hasattr(app_cfg, "model_dump") else {}
        dc = app_cfg_dict.get("data_collection", {})
        if dc:
            config.update(dc)
    except Exception:
        pass

    # Priority 3: Environment variable overrides (always applied)
    return _apply_env_overrides(config)


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Apply environment variable overrides to the config dict in-place.

    Only env vars that are actually set in the environment will override.
    """
    for env_name, (key, converter) in _ENV_VAR_MAP.items():
        if env_name in os.environ:
            try:
                config[key] = converter(os.environ[env_name])
            except (ValueError, TypeError):
                pass
    return config
