import logging
import os
import re
from pathlib import Path

import yaml
from dotenv import dotenv_values, find_dotenv, set_key
from fastapi import APIRouter, HTTPException
from httpx import AsyncClient
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/env-settings", tags=["env-settings"])


class ProviderInfo(BaseModel):
    id: str = Field(description="Provider identifier")
    name: str = Field(description="Provider display name")
    default_base_url: str = Field(description="Default API base URL")
    default_models: list[str] = Field(description="Preset model list")
    key_exists: bool = Field(description="Whether API key is set")
    key_masked: str = Field(default="", description="Masked API key")
    base_url: str = Field(default="", description="Current base URL")
    model: str = Field(default="", description="Current model")


class EnvSettingsResponse(BaseModel):
    providers: dict[str, ProviderInfo] = Field(description="Map of provider ID to provider info")


class EnvSettingsUpdateRequest(BaseModel):
    provider: str = Field(description="Provider identifier")
    api_key: str = Field(description="Plain-text API key", min_length=1)
    base_url: str | None = Field(default=None, description="Custom base URL")
    model: str | None = Field(default=None, description="Selected model")


class EnvSettingsUpdateResponse(BaseModel):
    success: bool = Field(default=True)
    message: str = Field(default="API Key saved successfully")


class VerifyResponse(BaseModel):
    valid: bool = Field(description="Whether the API key is valid")
    message: str = Field(description="Human-readable verification result")


class DeleteResponse(BaseModel):
    success: bool = Field(default=True)
    message: str = Field(default="Config cleared")


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
    if not config_path:
        logger.warning("config.yaml not found, skipping model registration")
        return None

    meta = PROVIDERS[provider_id]
    template = PROVIDER_CONFIG_TEMPLATE.get(provider_id)
    if not template:
        return None

    model_slug = _slugify(model_name)
    entry_name = f"{provider_id}-{model_slug}"

    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}

    models: list = cfg.get("models", [])
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

    with open(config_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Registered model %s to config.yaml", entry_name)
    return entry_name


def _remove_models_from_config(provider_id: str) -> int:
    """从 config.yaml 删除该厂商注册的所有模型条目。返回删除数。"""
    config_path = _get_config_path()
    if not config_path:
        return 0

    prefix = f"{provider_id}-"

    with open(config_path) as f:
        cfg = yaml.safe_load(f) or {}

    models: list = cfg.get("models", [])
    before = len(models)
    models = [m for m in models if not (isinstance(m, dict) and m.get("name", "").startswith(prefix))]
    removed = before - len(models)

    if removed == 0:
        return 0

    cfg["models"] = models
    with open(config_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Removed %d model(s) for %s from config.yaml", removed, provider_id)
    return removed


def _get_env_path() -> Path:
    env_path = find_dotenv()
    if not env_path:
        raise FileNotFoundError(".env file not found in project tree")
    return Path(env_path)


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


@router.get(
    "",
    response_model=EnvSettingsResponse,
    summary="读取所有厂商环境变量设置",
    description="返回所有 AI 厂商的 API Keys 状态（值已掩码处理）",
)
async def get_env_settings() -> EnvSettingsResponse:
    providers = {}
    for provider_id, meta in PROVIDERS.items():
        providers[provider_id] = _build_provider_info(provider_id, meta)
    return EnvSettingsResponse(providers=providers)


@router.put(
    "",
    response_model=EnvSettingsUpdateResponse,
    summary="更新厂商环境变量",
    description="将指定厂商的 API Key / Base URL / Model 写入 .env，并在 config.yaml 中注册模型",
)
async def update_env_settings(request: EnvSettingsUpdateRequest) -> EnvSettingsUpdateResponse:
    _validate_provider(request.provider)
    meta = PROVIDERS[request.provider]
    prefix = meta["env_prefix"]
    key = request.api_key.strip()
    if not key:
        raise HTTPException(status_code=422, detail="API Key cannot be empty")
    try:
        _write_env_value(f"{prefix}_API_KEY", key)
        base_url = request.base_url or meta["default_base_url"]
        if request.base_url is not None:
            _write_env_value(f"{prefix}_BASE_URL", request.base_url)
        msg = f"{meta['name']} API Key saved successfully"
        if request.model:
            _write_env_value(f"{prefix}_MODEL", request.model)
            registered = _register_model_to_config(request.provider, request.model, base_url)
            if registered:
                msg += "，模型已注册到 config.yaml，刷新后可在聊天中使用"
            else:
                msg += "（config.yaml 未找到，仅保存 Key）"
        return EnvSettingsUpdateResponse(success=True, message=msg)
    except Exception as e:
        logger.error("Failed to save API Key: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save API Key: {str(e)}")


@router.delete(
    "/{provider}",
    response_model=DeleteResponse,
    summary="清除厂商配置",
    description="从 .env 文件中删除指定厂商的 API_KEY、BASE_URL、MODEL 三个变量，并移除 config.yaml 中对应的模型条目",
)
async def delete_env_settings(provider: str) -> DeleteResponse:
    _validate_provider(provider)
    prefix = PROVIDERS[provider]["env_prefix"]
    try:
        _unset_env_value(f"{prefix}_API_KEY")
        _unset_env_value(f"{prefix}_BASE_URL")
        _unset_env_value(f"{prefix}_MODEL")
        removed = _remove_models_from_config(provider)
        msg = f"已清除 {PROVIDERS[provider]['name']} 的配置"
        if removed:
            msg += f"，已从聊天模型列表中移除 {removed} 个模型"
        return DeleteResponse(success=True, message=msg)
    except FileNotFoundError:
        return DeleteResponse(success=True, message=".env file not found, nothing to clear")
    except Exception as e:
        logger.error("Failed to clear config for %s: %s", provider, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear config: {str(e)}")


@router.post(
    "/{provider}/verify",
    response_model=VerifyResponse,
    summary="验证厂商 API Key",
    description="通过向该厂商 API 发送测试请求验证 Key 连通性",
)
async def verify_provider_key(provider: str) -> VerifyResponse:
    _validate_provider(provider)
    meta = PROVIDERS[provider]
    prefix = meta["env_prefix"]
    api_key = _read_env_value(f"{prefix}_API_KEY")
    if not api_key:
        return VerifyResponse(valid=False, message="API Key 未配置")
    base_url = _read_env_value(f"{prefix}_BASE_URL") or meta["default_base_url"]
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
            else:
                return VerifyResponse(valid=False, message=f"验证失败 (HTTP {resp.status_code})")
    except Exception as e:
        return VerifyResponse(valid=False, message=f"网络错误: {str(e)}")
