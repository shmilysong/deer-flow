import asyncio
import logging
import os
import re
from pathlib import Path

import yaml
from dotenv import dotenv_values, find_dotenv, set_key
from fastapi import APIRouter, HTTPException
from filelock import FileLock
from httpx import AsyncClient
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_ENV_LOCK_PATH: str | None = None
router = APIRouter(prefix="/api/env-settings", tags=["env-settings"])


class ChannelInfo(BaseModel):
    id: str
    name: str
    enabled: bool = Field(default=False)
    running: bool = Field(default=False)
    bot_id_exists: bool = Field(default=False)
    bot_id_masked: str = Field(default="")
    bot_secret_exists: bool = Field(default=False)
    error: str = Field(default="")


class ChannelUpdateRequest(BaseModel):
    channel: str = Field(min_length=1)
    bot_id: str = Field(min_length=1)
    bot_secret: str = Field(min_length=1)


class ProviderInfo(BaseModel):
    id: str = Field(description="Provider identifier")
    name: str = Field(description="Provider display name")
    default_base_url: str = Field(description="Default API base URL")
    default_models: list[str] = Field(description="Preset model list")
    key_exists: bool = Field(description="Whether API key is set")
    key_masked: str = Field(default="", description="Masked API key")
    base_url: str = Field(default="", description="Current base URL")
    model: str = Field(default="", description="Current model")


class ProviderSettingsResponse(BaseModel):
    providers: dict[str, ProviderInfo] = Field(description="Map of provider ID to provider info")


class ProviderSettingsUpdateRequest(BaseModel):
    provider: str = Field(description="Provider identifier")
    api_key: str = Field(description="Plain-text API key", min_length=1)
    base_url: str | None = Field(default=None, description="Custom base URL")
    model: str = Field(description="Selected model", min_length=1)


class EnvSettingsUpdateResponse(BaseModel):
    success: bool = Field(default=True)
    message: str = Field(default="API Key saved successfully")


class VerifyRequest(BaseModel):
    api_key: str | None = Field(default=None, description="API key to verify (uses saved key from .env if empty)")
    base_url: str | None = Field(default=None, description="Base URL to verify against (uses saved URL or default if empty)")


class VerifyResponse(BaseModel):
    valid: bool = Field(description="Whether the API key is valid")
    message: str = Field(description="Human-readable verification result")


class DeleteResponse(BaseModel):
    success: bool = Field(default=True)
    message: str = Field(default="Config cleared")


class ChannelVerifyRequest(BaseModel):
    bot_id: str | None = Field(default=None)
    bot_secret: str | None = Field(default=None)


class ChannelSettingsResponse(BaseModel):
    channels: dict[str, ChannelInfo]


PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "env_prefix": "DEEPSEEK",
        "default_base_url": "https://api.deepseek.com",
        "default_models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "moonshot": {
        "name": "Kimi",
        "env_prefix": "MOONSHOT",
        "default_base_url": "https://api.moonshot.cn/v1",
        "default_models": ["kimi-k2.5", "kimi-k2.5-thinking"],
    },
    "volcengine": {
        "name": "Doubao",
        "env_prefix": "VOLCENGINE",
        "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_models": ["doubao-seed-1-8-251228", "doubao-pro-32k-250315"],
    },
    "dashscope": {
        "name": "Qwen",
        "env_prefix": "DASHSCOPE",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"],
    },
    "minimax": {
        "name": "MiniMax",
        "env_prefix": "MINIMAX",
        "default_base_url": "https://api.minimax.io/v1",
        "default_models": ["MiniMax-M2.5", "MiniMax-M2.5-highspeed", "MiniMax-M2.7"],
    },
    "zhipuai": {
        "name": "GLM",
        "env_prefix": "ZHIPUAI",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_models": ["glm-4-plus", "glm-4-air", "glm-4-flash"],
    },
    "siliconflow": {
        "name": "硅基流动",
        "env_prefix": "SILICONFLOW",
        "default_base_url": "https://api.siliconflow.cn/v1",
        "default_models": ["Qwen/Qwen2.5-72B-Instruct-128K", "deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1"],
    },
}

# Each provider's config.yaml model entry template.
# Key: provider_id → (use class path, extra fields dict)
PROVIDER_CONFIG_TEMPLATE = {
    "deepseek":      {"use": "langchain_deepseek:ChatDeepSeek",                              "extra": {}},
    "moonshot":      {"use": "langchain_openai:ChatOpenAI",                                  "extra": {}},
    "volcengine":    {"use": "deerflow.models.patched_deepseek:PatchedChatDeepSeek",         "extra": {}},
    "dashscope":     {"use": "langchain_openai:ChatOpenAI",                                  "extra": {}},
    "minimax":       {"use": "langchain_openai:ChatOpenAI",                                  "extra": {}},
    "zhipuai":       {"use": "langchain_openai:ChatOpenAI",                                  "extra": {}},
    "siliconflow":   {"use": "langchain_openai:ChatOpenAI",                                  "extra": {}},
}


_CHANNEL_META: dict[str, dict[str, str]] = {
    "wecom": {
        "name": "企业微信",
        "env_prefix": "WECOM",
    },
}


def _get_config_path() -> str | None:
    """查找 config.yaml 文件路径（与 DeerFlow 优先级一致）。"""
    env_path = os.environ.get("DEER_FLOW_CONFIG_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    for candidate in ("config.yaml", "backend/config.yaml"):
        candidate_path = os.path.join(os.path.dirname(__file__), "..", "..", candidate)
        if os.path.isfile(candidate_path):
            return os.path.normpath(candidate_path)
    return None


def _slugify(name: str) -> str:
    """将模型名转为 slug（小写字母数字和短横线）。"""
    slug = re.sub(r"[^a-zA-Z0-9]", "-", name).lower()
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def _register_model_to_config(provider_id: str, model_name: str, base_url: str) -> str | None:
    """向 config.yaml 追加模型条目。返回注册的 name 或 None。"""
    config_path = _get_config_path()
    logger.info("_register_model_to_config: config_path=%s, provider_id=%s, model_name=%s, base_url=%s",
                 config_path, provider_id, model_name, base_url)
    if not config_path:
        logger.warning("config.yaml not found, skipping model registration")
        return None

    meta = PROVIDERS[provider_id]
    template = PROVIDER_CONFIG_TEMPLATE.get(provider_id)
    if not template:
        logger.warning("No config template for provider %s", provider_id)
        return None

    model_slug = _slugify(model_name)
    entry_name = f"{provider_id}-{model_slug}"

    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("Failed to read config.yaml: %s", e, exc_info=True)
        return None

    models: list = cfg.get("models", [])
    logger.info("Current models in config.yaml: %d entries", len(models))

    if any(isinstance(m, dict) and m.get("name") == entry_name for m in models):
        logger.info("Model %s already in config.yaml, skipping", entry_name)
        return entry_name

    new_entry = {
        "name": entry_name,
        "display_name": f"{model_name} ({meta['name']})",
        "use": template["use"],
        "model": model_name,
        "api_key": f"${meta['env_prefix']}_API_KEY",
    }
    if base_url:
        new_entry["base_url"] = base_url
    new_entry.update(template["extra"])

    models.append(new_entry)
    cfg["models"] = models

    try:
        with open(config_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("Registered model %s to config.yaml (total models: %d)", entry_name, len(models))
    except Exception as e:
        logger.error("Failed to write config.yaml: %s", e, exc_info=True)
        return None

    return entry_name


def _remove_models_from_config(provider_id: str) -> int:
    """从 config.yaml 删除该厂商注册的所有模型条目。返回删除数。"""
    config_path = _get_config_path()
    logger.info("_remove_models_from_config: config_path=%s, provider_id=%s", config_path, provider_id)
    if not config_path:
        logger.warning("config.yaml not found, cannot remove models")
        return 0

    prefix = f"{provider_id}-"

    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("Failed to read config.yaml for removal: %s", e, exc_info=True)
        return 0

    models: list = cfg.get("models", [])
    before = len(models)
    logger.info("Before removal: %d models in config.yaml", before)
    models = [m for m in models if not (isinstance(m, dict) and m.get("name", "").startswith(prefix))]
    removed = before - len(models)

    if removed == 0:
        logger.info("No models to remove for provider %s", provider_id)
        return 0

    cfg["models"] = models
    try:
        with open(config_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("Removed %d model(s) for %s from config.yaml (remaining: %d)", removed, provider_id, len(models))
    except Exception as e:
        logger.error("Failed to write config.yaml after removal: %s", e, exc_info=True)
        return 0

    return removed


def _get_env_path() -> Path:
    env_path = find_dotenv()
    if not env_path:
        raise FileNotFoundError(".env file not found in project tree")
    return Path(env_path)


def _get_env_lock() -> FileLock:
    lock_path = _ENV_LOCK_PATH or str(_get_env_path().with_suffix(".env.lock"))
    return FileLock(lock_path, timeout=5)


def _mask_value(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return value[:3] + "****" + value[-4:]


def _read_env_value(key: str) -> str:
    try:
        env_path = _get_env_path()
        values = dotenv_values(env_path)
        return values.get(key, "")
    except FileNotFoundError:
        return ""


def _write_env_value(key: str, value: str) -> None:
    env_path = _get_env_path()
    set_key(str(env_path), key, value, quote_mode="always")
    os.environ[key] = value
    logger.info("Updated %s in .env file", key)


def _unset_env_value(key: str) -> None:
    env_path = _get_env_path()
    set_key(str(env_path), key, "", quote_mode="always")
    os.environ.pop(key, None)
    logger.info("Cleared %s from .env file", key)


def _validate_provider(provider_id: str) -> None:
    if provider_id not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")


def _build_provider_info(provider_id: str, meta: dict) -> ProviderInfo:
    prefix = meta["env_prefix"]
    api_key = _read_env_value(f"{prefix}_API_KEY")
    base_url = _read_env_value(f"{prefix}_BASE_URL")
    model = _read_env_value(f"{prefix}_MODEL")
    exists = api_key != ""
    return ProviderInfo(
        id=provider_id,
        name=meta["name"],
        default_base_url=meta["default_base_url"],
        default_models=meta["default_models"],
        key_exists=exists,
        key_masked=_mask_value(api_key) if exists else "",
        base_url=base_url,
        model=model,
    )


def _build_channel_info(channel_id: str, meta: dict) -> ChannelInfo:
    prefix = meta["env_prefix"]
    bot_id = _read_env_value(f"{prefix}_BOT_ID")
    bot_secret = _read_env_value(f"{prefix}_BOT_SECRET")

    enabled = False
    running = False
    try:
        from app.channels.service import get_channel_service
        service = get_channel_service()
        if service:
            status = service.get_status()
            ch_status = status["channels"].get(channel_id, {})
            enabled = ch_status.get("enabled", False)
            running = ch_status.get("running", False)
    except Exception:
        pass

    return ChannelInfo(
        id=channel_id,
        name=meta["name"],
        enabled=enabled,
        running=running,
        bot_id_exists=bool(bot_id),
        bot_id_masked=_mask_value(bot_id) if bot_id else "",
        bot_secret_exists=bool(bot_secret),
    )


async def _test_wecom_connect(bot_id: str, bot_secret: str) -> tuple[bool, str]:
    try:
        from aibot import WSClient, WSClientOptions
        client = WSClient(WSClientOptions(bot_id=bot_id, secret=bot_secret))

        loop = asyncio.get_running_loop()
        auth_future = loop.create_future()

        def _on_authenticated():
            if not auth_future.done():
                auth_future.set_result(True)

        def _on_error(error: Exception):
            if not auth_future.done():
                auth_future.set_exception(error)

        client.on("authenticated", _on_authenticated)
        client.on("error", _on_error)

        await client.connect()

        try:
            await asyncio.wait_for(auth_future, timeout=10.0)
            return (True, "连接成功")
        except asyncio.TimeoutError:
            return (False, "认证超时，请检查 Bot ID 和 Secret")
        finally:
            client.disconnect()
    except ImportError:
        return (False, "wecom-aibot-python-sdk 未安装")
    except Exception as e:
        return (False, f"连接失败: {str(e)}")


def _sanitize_channel_input(bot_id: str, bot_secret: str) -> tuple[str, str]:
    from fastapi import HTTPException
    bot_id = bot_id.strip()
    bot_secret = bot_secret.strip()
    if not bot_id:
        raise HTTPException(status_code=422, detail="Bot ID cannot be empty")
    if not bot_secret:
        raise HTTPException(status_code=422, detail="Bot Secret cannot be empty")
    return (bot_id, bot_secret)


def _set_channel_enabled_in_config(channel_id: str, enabled: bool) -> bool:
    """在 config.yaml 中设置 channels.<channel_id>.enabled = true/false。

    如果 channels 区块或 channel 区块不存在则自动创建。
    返回是否写入成功，失败时仅日志警告（不阻止主流程）。
    """
    config_path = _get_config_path()
    if not config_path:
        logger.warning("config.yaml not found, skip channel enabled toggle")
        return False

    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("Failed to read config.yaml: %s", e, exc_info=True)
        return False

    channels = cfg.setdefault("channels", {})
    channel_cfg = channels.setdefault(channel_id, {})

    if channel_cfg.get("enabled") == enabled:
        return True

    channel_cfg["enabled"] = enabled
    channels[channel_id] = channel_cfg
    cfg["channels"] = channels

    try:
        with open(config_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info("[Audit] config.yaml channels.%s.enabled set to %s", channel_id, enabled)
    except Exception as e:
        logger.error("Failed to write config.yaml: %s", e, exc_info=True)
        return False

    return True


@router.get(
    "/providers",
    response_model=ProviderSettingsResponse,
    summary="读取所有厂商环境变量设置",
    description="返回所有 AI 厂商的 API Keys 状态（值已掩码处理）",
)
async def get_provider_settings() -> ProviderSettingsResponse:
    providers = {}
    for provider_id, meta in PROVIDERS.items():
        providers[provider_id] = _build_provider_info(provider_id, meta)
    return ProviderSettingsResponse(providers=providers)


@router.put(
    "/providers",
    response_model=EnvSettingsUpdateResponse,
    summary="更新厂商环境变量",
    description="将指定厂商的 API Key / Base URL / Model 写入 .env，并在 config.yaml 中注册模型",
)
async def update_provider_settings(request: ProviderSettingsUpdateRequest) -> EnvSettingsUpdateResponse:
    _validate_provider(request.provider)
    meta = PROVIDERS[request.provider]
    prefix = meta["env_prefix"]
    key = request.api_key.strip()
    if not key:
        raise HTTPException(status_code=422, detail="API Key cannot be empty")
    try:
        with _get_env_lock():
            _write_env_value(f"{prefix}_API_KEY", key)
            base_url = request.base_url or meta["default_base_url"]
            if request.base_url is not None:
                _write_env_value(f"{prefix}_BASE_URL", request.base_url)
            model = request.model.strip()
            _write_env_value(f"{prefix}_MODEL", model)
        registered = _register_model_to_config(request.provider, model, base_url)
        msg = f"{meta['name']} 配置已保存"
        if registered:
            msg += "，模型已注册到 config.yaml，刷新后可在聊天中使用"
        else:
            msg += "（config.yaml 未找到，仅保存 Key）"
        return EnvSettingsUpdateResponse(success=True, message=msg)
    except Exception as e:
        logger.error("Failed to save API Key: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save API Key: {str(e)}")


@router.delete(
    "/providers/{provider}",
    response_model=DeleteResponse,
    summary="清除厂商配置",
    description="从 .env 文件中删除指定厂商的 API_KEY、BASE_URL、MODEL 三个变量，并移除 config.yaml 中对应的模型条目",
)
async def delete_provider_settings(provider: str) -> DeleteResponse:
    _validate_provider(provider)
    prefix = PROVIDERS[provider]["env_prefix"]
    removed = _remove_models_from_config(provider)
    try:
        with _get_env_lock():
            _unset_env_value(f"{prefix}_API_KEY")
            _unset_env_value(f"{prefix}_BASE_URL")
            _unset_env_value(f"{prefix}_MODEL")
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error("Failed to clear env for %s: %s", provider, e, exc_info=True)
    msg = f"已清除 {PROVIDERS[provider]['name']} 的配置"
    if removed:
        msg += f"，已从聊天模型列表中移除 {removed} 个模型"
    return DeleteResponse(success=True, message=msg)


@router.post(
    "/providers/{provider}/verify",
    response_model=VerifyResponse,
    summary="验证厂商 API Key",
    description="通过向该厂商 API 发送测试请求验证 Key 连通性",
)
async def verify_provider_key(provider: str, request: VerifyRequest = None) -> VerifyResponse:
    _validate_provider(provider)
    meta = PROVIDERS[provider]
    prefix = meta["env_prefix"]
    api_key = request.api_key.strip() if request and request.api_key else _read_env_value(f"{prefix}_API_KEY")
    if not api_key:
        return VerifyResponse(valid=False, message="API Key 未配置")
    base_url = (request.base_url.strip() if request and request.base_url else None) or _read_env_value(f"{prefix}_BASE_URL") or meta["default_base_url"]
    verify_url = base_url.rstrip("/") + "/models"
    try:
        async with AsyncClient(timeout=10) as client:
            resp = await client.get(
                verify_url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                return VerifyResponse(valid=True, message=f"{meta['name']} API Key is valid and reachable")
            elif resp.status_code == 401:
                return VerifyResponse(valid=False, message=f"{meta['name']} API Key is invalid (401 Unauthorized)")
            elif resp.status_code == 403:
                return VerifyResponse(valid=False, message=f"{meta['name']} API Key 无权限 (403 Forbidden)")
            elif resp.status_code == 404:
                return VerifyResponse(valid=True, message=f"{meta['name']} API Key 格式正确（端点返回 404，密钥可能有效）")
            elif resp.status_code == 429:
                return VerifyResponse(valid=False, message=f"{meta['name']} API 请求过于频繁，请稍后重试")
            else:
                return VerifyResponse(valid=False, message=f"验证失败 (HTTP {resp.status_code})")
    except Exception as e:
        logger.error("Verify %s failed: %s", provider, e, exc_info=True)
        return VerifyResponse(valid=False, message=f"网络错误: {str(e)}")


@router.get(
    "/channels",
    response_model=ChannelSettingsResponse,
    summary="读取所有渠道配置",
    description="返回所有 IM 渠道的凭据状态和运行状态（Key 已掩码处理）",
)
async def get_channels() -> ChannelSettingsResponse:
    channels = {}
    for channel_id, meta in _CHANNEL_META.items():
        channels[channel_id] = _build_channel_info(channel_id, meta)
    return ChannelSettingsResponse(channels=channels)


@router.put(
    "/channels",
    response_model=EnvSettingsUpdateResponse,
    summary="更新渠道凭据",
    description="保存渠道 Bot ID/Secret 到 .env，含值不变跳过 + 输入裁剪 + Test-Before-Switch 安全重启 + 审计日志",
)
async def update_channel_settings(request: ChannelUpdateRequest) -> EnvSettingsUpdateResponse:
    channel_id = request.channel
    if channel_id not in _CHANNEL_META:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found")

    meta = _CHANNEL_META[channel_id]
    prefix = meta["env_prefix"]

    # 输入裁剪
    try:
        bot_id, bot_secret = _sanitize_channel_input(request.bot_id, request.bot_secret)
    except HTTPException:
        raise

    # 值不变跳过
    existing_id = _read_env_value(f"{prefix}_BOT_ID")
    existing_secret = _read_env_value(f"{prefix}_BOT_SECRET")
    if existing_id == bot_id and existing_secret == bot_secret:
        return EnvSettingsUpdateResponse(success=True, message="配置未变化，无需更新")

    try:
        with _get_env_lock():
            _write_env_value(f"{prefix}_BOT_ID", bot_id)
            _write_env_value(f"{prefix}_BOT_SECRET", bot_secret)

        # 审计日志
        logger.info("[Audit] channel.%s.save | bot_id=%s", channel_id, _mask_value(bot_id) if bot_id else "")

        # Test-Before-Switch 安全重启
        msg = f"{meta['name']} 配置已保存"
        try:
            from app.channels.service import get_channel_service
            service = get_channel_service()
            if service and "wecom" in service._config:
                channel_running = "wecom" in service._channels and service._channels["wecom"].is_running

                if channel_running:
                    ok, err = await _test_wecom_connect(bot_id, bot_secret)
                    if ok:
                        service._config["wecom"]["bot_id"] = bot_id
                        service._config["wecom"]["bot_secret"] = bot_secret
                        await service.restart_channel("wecom")
                        msg += "，渠道已自动重启"
                    else:
                        msg += f"（新参数校验失败：{err}，旧渠道正常运行不受影响）"
                else:
                    service._config["wecom"]["bot_id"] = bot_id
                    service._config["wecom"]["bot_secret"] = bot_secret
                    ok = await service.restart_channel("wecom")
                    msg += "，渠道已自动重启" if ok else "（新参数仍无法启动渠道）"
            else:
                msg += "（ChannelService 未运行，重启 DeerFlow 后生效）"
        except Exception as e:
            msg += "（渠道热重启失败，请手动重启）"
            logger.warning("[Audit] channel.%s.restart_failed | %s", channel_id, e)

        # 自动设置 config.yaml 中 channels.<channel_id>.enabled = true
        if _set_channel_enabled_in_config(channel_id, True):
            msg += "，已修改 config.yaml"
        else:
            msg += "（config.yaml 写入失败，如需开机自启请手动设置）"

        return EnvSettingsUpdateResponse(success=True, message=msg)
    except Exception as e:
        logger.error("Failed to save channel %s: %s", channel_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.delete(
    "/channels/{channel}",
    response_model=DeleteResponse,
    summary="清除渠道配置",
    description="清除渠道凭据，同步停止运行中的渠道，清理内存配置",
)
async def delete_channel_settings(channel: str) -> DeleteResponse:
    if channel not in _CHANNEL_META:
        raise HTTPException(status_code=404, detail=f"Channel '{channel}' not found")

    meta = _CHANNEL_META[channel]
    prefix = meta["env_prefix"]

    try:
        with _get_env_lock():
            _unset_env_value(f"{prefix}_BOT_ID")
            _unset_env_value(f"{prefix}_BOT_SECRET")
    except FileNotFoundError:
        pass

    msg = f"已清除 {meta['name']} 的配置"

    try:
        from app.channels.service import get_channel_service
        service = get_channel_service()
        if service:
            if channel in service._channels:
                await service._channels[channel].stop()
                del service._channels[channel]
                msg += "，渠道已停止运行"
            if channel in service._config:
                service._config[channel]["bot_id"] = ""
                service._config[channel]["bot_secret"] = ""
    except Exception:
        pass

    logger.info("[Audit] channel.%s.delete", channel)

    _set_channel_enabled_in_config(channel, False)
    msg += "，已禁用开机自启"

    return DeleteResponse(success=True, message=msg)


@router.post(
    "/channels/{channel}/verify",
    response_model=VerifyResponse,
    summary="验证渠道连通性",
    description="通过 WebSocket 连接测试验证渠道凭据",
)
async def verify_channel_settings(channel: str, request: ChannelVerifyRequest = None) -> VerifyResponse:
    if channel not in _CHANNEL_META:
        raise HTTPException(status_code=404, detail=f"Channel '{channel}' not found")

    meta = _CHANNEL_META[channel]
    prefix = meta["env_prefix"]

    bot_id = request.bot_id.strip() if request and request.bot_id else _read_env_value(f"{prefix}_BOT_ID")
    bot_secret = request.bot_secret.strip() if request and request.bot_secret else _read_env_value(f"{prefix}_BOT_SECRET")

    if not bot_id or not bot_secret:
        return VerifyResponse(valid=False, message="Bot ID 和 Secret 未完整配置")

    valid, message = await _test_wecom_connect(bot_id, bot_secret)
    result = "valid" if valid else "invalid"
    logger.info("[Audit] channel.%s.verify | result=%s", channel, result)
    return VerifyResponse(valid=valid, message=message)
