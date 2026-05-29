import logging
import os
from pathlib import Path

from dotenv import dotenv_values, find_dotenv, set_key
from fastapi import APIRouter, HTTPException
from httpx import AsyncClient
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/env-settings", tags=["env-settings"])


class EnvSettingValue(BaseModel):
    exists: bool = Field(description="Whether the env var is set in .env file")
    masked_value: str = Field(default="", description="Masked display value, e.g. 'sk-****23ea'")
    configured: bool = Field(description="Whether a non-empty value exists")


class EnvSettingsResponse(BaseModel):
    DEEPSEEK_API_KEY: EnvSettingValue = Field(description="DeepSeek API key status")


class EnvSettingsUpdateRequest(BaseModel):
    DEEPSEEK_API_KEY: str = Field(description="Plain-text DeepSeek API key", min_length=1)


class EnvSettingsUpdateResponse(BaseModel):
    success: bool = Field(default=True)
    message: str = Field(default="API Key saved successfully")


class VerifyResponse(BaseModel):
    valid: bool = Field(description="Whether the API key is valid")
    message: str = Field(description="Human-readable verification result")


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
    env_path = _get_env_path()
    values = dotenv_values(env_path)
    return values.get(key, "")


def _write_env_value(key: str, value: str) -> None:
    env_path = _get_env_path()
    set_key(str(env_path), key, value, quote_mode="always")
    os.environ[key] = value
    logger.info("Updated %s in .env file", key)


@router.get(
    "",
    response_model=EnvSettingsResponse,
    summary="读取环境变量设置",
    description="返回 .env 文件中配置的 API Keys（值已掩码处理）",
)
async def get_env_settings() -> EnvSettingsResponse:
    try:
        raw_value = _read_env_value("DEEPSEEK_API_KEY")
        exists = raw_value != ""
        return EnvSettingsResponse(
            DEEPSEEK_API_KEY=EnvSettingValue(
                exists=exists,
                masked_value=_mask_value(raw_value) if exists else "",
                configured=exists,
            )
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "",
    response_model=EnvSettingsUpdateResponse,
    summary="更新环境变量",
    description="将 API Key 写入 .env 文件并刷新运行时环境变量",
)
async def update_env_settings(request: EnvSettingsUpdateRequest) -> EnvSettingsUpdateResponse:
    key = request.DEEPSEEK_API_KEY.strip()
    if not key:
        raise HTTPException(status_code=422, detail="API Key cannot be empty")
    if not key.startswith("sk-"):
        raise HTTPException(status_code=422, detail="DeepSeek API Key should start with 'sk-'")
    try:
        _write_env_value("DEEPSEEK_API_KEY", key)
        return EnvSettingsUpdateResponse(
            success=True,
            message="API Key saved successfully",
        )
    except Exception as e:
        logger.error("Failed to save API Key: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save API Key: {str(e)}")


DEEPSEEK_MODELS_URL = "https://api.deepseek.com/models"


@router.post(
    "/deepseek/verify",
    response_model=VerifyResponse,
    summary="验证 DeepSeek API Key",
    description="向 DeepSeek API 发送测试请求验证 API Key 是否有效",
)
async def verify_deepseek_key() -> VerifyResponse:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "") or _read_env_value("DEEPSEEK_API_KEY")
    if not api_key:
        return VerifyResponse(valid=False, message="API Key is not configured")
    try:
        async with AsyncClient(timeout=10) as client:
            resp = await client.get(
                DEEPSEEK_MODELS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                return VerifyResponse(valid=True, message="API Key is valid and reachable")
            elif resp.status_code == 401:
                return VerifyResponse(valid=False, message="API Key is invalid (401 Unauthorized)")
            else:
                return VerifyResponse(valid=False, message=f"Verification failed with HTTP {resp.status_code}")
    except Exception as e:
        return VerifyResponse(valid=False, message=f"Network error: {str(e)}")
