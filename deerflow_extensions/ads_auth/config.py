import os
import sys
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: set env vars from KEY=VAL lines if not already set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("\"'")
        if key not in os.environ:
            os.environ[key] = val


# Try to find .env relative to this file (deerflow_extensions/ads_auth/config.py -> project root)
_proj_root = Path(__file__).resolve().parent.parent.parent
_load_dotenv(_proj_root / ".env")

ADS_BASE_URL: str = os.getenv("ADS_BASE_URL", "http://ads:8080")

MCP_CONFIG_PATH: str = os.getenv("ADS_MCP_CONFIG_PATH", "~/.config/deer-flow/ads-mcp.json")
