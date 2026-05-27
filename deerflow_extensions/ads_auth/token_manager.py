import json
import os
import time

from deerflow_extensions.ads_auth.config import ADS_BASE_URL, MCP_CONFIG_PATH

_ads_tokens: dict[str, str] = {}


async def save_token(user_id: str, token: str):
    _ads_tokens[user_id] = token


async def get_token(user_id: str) -> str | None:
    return _ads_tokens.get(user_id)


async def remove_token(user_id: str):
    _ads_tokens.pop(user_id, None)


async def sync_to_mcp_config(ads_token: str):
    if not MCP_CONFIG_PATH:
        return

    config_path = os.path.expanduser(MCP_CONFIG_PATH)

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError:
        return

    if "ads" not in config:
        config["ads"] = {}
    if "server" not in config["ads"]:
        config["ads"]["server"] = {}

    config["ads"]["server"]["url"] = ADS_BASE_URL

    now = int(time.time())
    config["ads"]["token"] = {
        "value": ads_token,
        "expires": now + 1800,
        "loginTime": now,
        "usedBy": "deerflow",
    }

    tmp = config_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(config, f, indent=2)
    os.rename(tmp, config_path)
