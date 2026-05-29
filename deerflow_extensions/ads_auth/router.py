from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm

from deerflow_extensions.ads_auth.ads_auth import ads_login
from deerflow_extensions.ads_auth.token_manager import save_token, sync_to_mcp_config
import base64, json, time

router = APIRouter(tags=["ads-auth"])


@router.post("/login/ads")
async def login_ads(
    form_data: OAuth2PasswordRequestForm = Depends(),
    response: Response = Response(),
):
    result = await ads_login(form_data.username, form_data.password)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])

    ads_token = result["ads_token"]

    # 解码 JWT payload 提取 exp
    parts = ads_token.split(".")
    if len(parts) == 3:
        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        exp = payload.get("exp")
        max_age = max(int(exp - time.time()), 0) if exp else 1800
    else:
        max_age = 1800

    # 统一只设置 access_token，不再设置 ads_token
    response.set_cookie(
        key="access_token",
        value=ads_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=max_age,
    )

    await save_token(form_data.username, ads_token)
    await sync_to_mcp_config(ads_token)

    return {
        "msg": "登录成功",
        "token_type": "bearer",
        "expires_in": max_age,
    }
