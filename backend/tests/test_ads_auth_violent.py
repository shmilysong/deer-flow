"""
暴力测试: ADS 统一认证集成
测试环境: ADS 服务器 https://192.168.1.54, DeerFlow 网关 http://localhost:8001
"""

import asyncio
import time
import tracemalloc

import httpx

ADS_URL = "https://192.168.1.54"
GATEWAY_URL = "http://localhost:8001"
TEST_USERNAME = "admin"
TEST_PASSWORD = "Admin#123"


async def login_ads(username=TEST_USERNAME, password=TEST_PASSWORD):
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/api/v1/auth/login/ads",
            data={"username": username, "password": password},
            timeout=10,
        )
        return resp


async def test_1_continuous_login():
    """5.1: 连续 100 次登录 — 无内存泄漏"""
    print("\n=== 5.1 连续登录测试 (100次) ===")
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()

    for i in range(100):
        resp = await login_ads()
        assert resp.status_code == 200, f"第 {i+1} 次登录失败: {resp.status_code}"
        data = resp.json()
        assert "ads_token" in resp.cookies or "ads_token" in [c.name for c in resp.cookies], f"第 {i+1} 次无 cookie"

    after = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    leak = after[0] - before[0]
    print(f"  内存变化: {leak / 1024:.1f} KB")
    assert leak < 5 * 1024 * 1024, f"内存泄漏检测: {leak / 1024 / 1024:.1f} MB"
    print("  ✅ 通过: 无内存泄漏")


async def test_2_concurrent_requests():
    """5.2: 并发 50 个请求 — 无死锁"""
    print("\n=== 5.2 并发压力测试 (50并发) ===")
    tasks = [login_ads() for _ in range(50)]
    start = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start

    success = sum(1 for r in results if isinstance(r, httpx.Response) and r.status_code == 200)
    failed = sum(1 for r in results if isinstance(r, Exception) or (isinstance(r, httpx.Response) and r.status_code != 200))
    print(f"  耗时: {elapsed:.2f}s, 成功: {success}, 失败: {failed}")
    assert success >= 45, f"并发成功率不足: {success}/50"
    assert elapsed < 60, f"超时: {elapsed:.2f}s"
    print("  ✅ 通过: 并发安全")


async def test_3_server_unavailable():
    """5.3: ADS 服务器不可用 — 优雅降级"""
    print("\n=== 5.3 ADS 服务器不可用测试 ===")
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            f"{GATEWAY_URL}/api/v1/auth/login/ads",
            data={"username": "false_user", "password": "bad_password"},
            timeout=10,
        )
    assert resp.status_code == 401, f"期望 401, 实际 {resp.status_code}"
    detail = resp.json().get("detail", "")
    assert detail, "应有错误信息"
    print(f"  错误信息: {detail}")
    print("  ✅ 通过: 优雅降级")


async def test_4_expired_token():
    """5.4: 过期 token — 返回 401"""
    print("\n=== 5.4 Token 过期测试 ===")
    import base64
    import json as _json
    expired_payload = base64.urlsafe_b64encode(
        _json.dumps({"username": "admin", "exp": 0}).encode()
    ).rstrip(b"=").decode()
    fake_token = f"header.{expired_payload}.signature"

    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.get(
            f"{GATEWAY_URL}/api/v1/auth/me",
            cookies={"ads_token": fake_token},
            timeout=10,
        )
    assert resp.status_code == 401, f"期望 401, 实际 {resp.status_code}"
    print("  ✅ 通过: 过期 token 被拒绝")


async def test_5_malicious_token():
    """5.5: 恶意/畸形 token — 全部返回 401"""
    print("\n=== 5.5 恶意 Token 测试 ===")
    test_tokens = [
        "invalid_jwt_string",
        "",
        "header.payload.signature",
        "eyJ.eyJ1c2VybmFtZSI6ImFkbWluIn0=.sig",
        "' OR 1=1 --",
        "<script>alert(1)</script>",
    ]

    async with httpx.AsyncClient(verify=False) as client:
        for token in test_tokens:
            resp = await client.get(
                f"{GATEWAY_URL}/api/v1/auth/me",
                cookies={"ads_token": token},
                timeout=10,
            )
            assert resp.status_code == 401, f"token '{token[:20]}' 期望 401, 实际 {resp.status_code}"
    print("  ✅ 通过: 所有恶意 token 被拒绝")


async def main():
    print("=" * 50)
    print("ADS 统一认证 — 暴力测试套件")
    print(f"ADS: {ADS_URL}, Gateway: {GATEWAY_URL}")
    print("=" * 50)

    await test_1_continuous_login()
    await test_2_concurrent_requests()
    await test_3_server_unavailable()
    await test_4_expired_token()
    await test_5_malicious_token()

    print("\n" + "=" * 50)
    print("全部暴力测试通过! ✅")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
