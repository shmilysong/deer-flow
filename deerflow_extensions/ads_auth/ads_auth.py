import httpx
from deerflow_extensions.ads_auth.config import ADS_BASE_URL


async def ads_login(username: str, password: str) -> dict:
    if not ADS_BASE_URL:
        return {"success": False, "error": "ADS_BASE_URL 未配置"}

    url = f"{ADS_BASE_URL.rstrip('/')}/jwt/login"

    async with httpx.AsyncClient(verify=False) as client:
        try:
            resp = await client.post(
                url,
                data={"username": username, "password": password},
                timeout=10,
            )
            result = resp.json()
        except httpx.TimeoutException:
            return {"success": False, "error": "ADS 服务器超时"}
        except httpx.RequestError as e:
            return {"success": False, "error": f"ADS 服务器不可达: {e}"}

    if result.get("code") != 0:
        return {"success": False, "error": result.get("msg", "登录失败")}

    return {
        "success": True,
        "ads_token": result["token"],
        "username": username,
    }
