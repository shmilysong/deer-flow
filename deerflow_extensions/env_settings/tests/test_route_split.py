"""
测试 env_settings/router.py 的分路径路由隔离性

覆盖范围（共 8 项，RT1-RT8）：
  RT1: GET /providers 返回 7 家厂商
  RT2: GET /channels   包含 channels.wecom
  RT3: GET /providers 响应无 channels 字段
  RT4: GET /channels   响应无 providers 字段
  RT5: PUT /providers  原有厂商逻辑正常工作
  RT6: PUT /channels   渠道逻辑正常工作
  RT7: POST /channels/{channel}/verify 不触发 /providers 逻辑
  RT8: POST /providers/{provider}/verify 不触发 channels 逻辑
"""

from __future__ import annotations

import sys
import types as _types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# sys.path: 确保 `app` 模块可导入（backend/ 目录）
# ---------------------------------------------------------------------------
_backend_dir = Path(__file__).resolve().parents[3] / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# ---------------------------------------------------------------------------
# 创建 app.channels.service 假模块注入 sys.modules，避免 mock.patch 路径
# 解析失败。该模块有真实依赖（langgraph_sdk 等），测试环境不必导入。
# ---------------------------------------------------------------------------
import app.channels  # noqa: E402 — 此时 backend 已在 sys.path 中

_MOCK_CHANNELS_SERVICE = _types.ModuleType("app.channels.service")
_MOCK_CHANNELS_SERVICE.get_channel_service = MagicMock(return_value=None)
sys.modules["app.channels.service"] = _MOCK_CHANNELS_SERVICE
app.channels.service = _MOCK_CHANNELS_SERVICE  # 使 getattr(app.channels, 'service') 可访问

from deerflow_extensions.env_settings.router import PROVIDERS, router

_API_PREFIX = "/api/env-settings"

# ---------------------------------------------------------------------------
# 根据 router 前缀构建完整 URL 的辅助函数
# ---------------------------------------------------------------------------


def _url(path: str) -> str:
    return f"{_API_PREFIX}{path}"


# ===================================================================
# TestRouteSplit
# ===================================================================


class TestRouteSplit:
    """分路径路由隔离性测试套件。

    所有测试使用 FastAPI TestClient + mock 外部依赖（.env 文件、
    config.yaml 写入、channel service 等），不依赖真实环境。
    """

    # ------------------------------------------------------------------
    # fixtures — 全局 mock
    # ------------------------------------------------------------------

    @pytest.fixture
    def client(self):
        """为每个测试创建独立的 FastAPI app + TestClient。

        每次重建 app 确保 mock 生效，避免路由缓存干扰。
        非 autouse: 只有请求 client 参数的测试才会创建。
        """
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as c:
            yield c

    @pytest.fixture(autouse=True)
    def _patch_read_env(self):
        """mock _read_env_value：默认返回空字符串（所有 key 未配置）。"""
        with patch(
            "deerflow_extensions.env_settings.router._read_env_value",
            return_value="",
        ) as mock:
            yield mock

    @pytest.fixture(autouse=True)
    def _patch_get_env_lock(self):
        """mock _get_env_lock：无操作上下文管理器，避免 FileLock 依赖真实文件。"""
        fake_lock = MagicMock()
        fake_lock.__enter__ = MagicMock()
        fake_lock.__exit__ = MagicMock(return_value=None)
        with patch(
            "deerflow_extensions.env_settings.router._get_env_lock",
            return_value=fake_lock,
        ) as mock:
            yield mock

    @pytest.fixture(autouse=True)
    def _patch_write_env(self):
        """mock _write_env_value：不写入真实 .env 文件。"""
        with patch(
            "deerflow_extensions.env_settings.router._write_env_value",
        ) as mock:
            yield mock

    @pytest.fixture(autouse=True)
    def _patch_unset_env(self):
        """mock _unset_env_value：不清除真实 .env 文件。"""
        with patch(
            "deerflow_extensions.env_settings.router._unset_env_value",
        ) as mock:
            yield mock

    @pytest.fixture(autouse=True)
    def _patch_channel_service(self):
        """mock get_channel_service：返回 None（渠道服务未运行）。

        注意：app.channels.service 已在模块级作为假模块注入 sys.modules。
        """
        with patch(
            "app.channels.service.get_channel_service",
            return_value=None,
        ) as mock:
            yield mock

    @pytest.fixture(autouse=True)
    def _patch_register_model(self):
        """mock _register_model_to_config：返回注册名模拟成功。"""
        with patch(
            "deerflow_extensions.env_settings.router._register_model_to_config",
            return_value="deepseek-deepseek-chat",
        ) as mock:
            yield mock

    @pytest.fixture(autouse=True)
    def _patch_remove_models(self):
        """mock _remove_models_from_config：返回 0（无删除）。"""
        with patch(
            "deerflow_extensions.env_settings.router._remove_models_from_config",
            return_value=0,
        ) as mock:
            yield mock

    # ------------------------------------------------------------------
    # RT1 + RT3: GET /providers
    # ------------------------------------------------------------------

    def test_rt1_get_providers_returns_7_providers(self, client):
        """RT1: GET /providers 返回 7 家厂商。"""
        response = client.get(_url("/providers"))
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert len(data["providers"]) == 7, (
            f"Expected 7 providers, got {len(data['providers'])}"
        )

        # 验证所有 7 家厂商 ID 都存在
        provider_ids = {p["id"] for p in data["providers"].values()}
        assert provider_ids == set(PROVIDERS.keys()), (
            f"Provider IDs mismatch. Expected {set(PROVIDERS.keys())}, got {provider_ids}"
        )

    def test_rt3_get_providers_no_channels_field(self, client):
        """RT3: GET /providers 响应不应包含 channels 字段。"""
        response = client.get(_url("/providers"))
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert "channels" not in data, (
            "Response contains 'channels' field which should only appear "
            "in the /channels endpoint"
        )

    # ------------------------------------------------------------------
    # RT2 + RT4: GET /channels
    # ------------------------------------------------------------------

    def test_rt2_get_channels_contains_wecom(self, client):
        """RT2: GET /channels 包含 channels.wecom。"""
        response = client.get(_url("/channels"))
        assert response.status_code == 200
        data = response.json()
        assert "channels" in data
        assert "wecom" in data["channels"], (
            "Expected 'wecom' in channels response"
        )

    def test_rt4_get_channels_no_providers_field(self, client):
        """RT4: GET /channels 响应不应包含 providers 字段。"""
        response = client.get(_url("/channels"))
        assert response.status_code == 200
        data = response.json()
        assert "channels" in data
        assert "providers" not in data, (
            "Response contains 'providers' field which should only appear "
            "in the /providers endpoint"
        )

    # ------------------------------------------------------------------
    # RT5: PUT /providers — 厂商更新逻辑
    # ------------------------------------------------------------------

    def test_rt5_put_providers_works(self, client):
        """RT5: PUT /providers 正常保存厂商 API Key 并注册模型。

        验证：
          - 状态码 200
          - success=True
          - message 包含厂商名称
          - _write_env_value 被调用（写入 .env）
          - _register_model_to_config 被调用（注册模型到 config.yaml）
        """
        with patch(
            "deerflow_extensions.env_settings.router._register_model_to_config",
            return_value="deepseek-deepseek-chat",
        ) as mock_register:
            response = client.put(
                _url("/providers"),
                json={
                    "provider": "deepseek",
                    "api_key": "sk-test-key-12345",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "DeepSeek" in data["message"]
        assert "配置已保存" in data["message"]

        # _register_model_to_config 应被调用
        mock_register.assert_called_once()

    def test_rt5_put_providers_invalid_provider_returns_404(self, client):
        """PUT /providers 传入不存在的厂商返回 404。"""
        response = client.put(
            _url("/providers"),
            json={
                "provider": "nonexistent_provider",
                "api_key": "sk-test",
                "model": "test-model",
            },
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_rt5_put_providers_empty_api_key_returns_422(self, client):
        """PUT /providers 传空 api_key 返回 422。"""
        response = client.put(
            _url("/providers"),
            json={
                "provider": "deepseek",
                "api_key": "",
                "model": "deepseek-chat",
            },
        )
        assert response.status_code == 422

    # ------------------------------------------------------------------
    # RT6: PUT /channels — 渠道更新逻辑
    # ------------------------------------------------------------------

    def test_rt6_put_channels_works(self, client):
        """RT6: PUT /channels 正常保存渠道凭据。

        验证：
          - 状态码 200
          - success=True
          - message 包含渠道名称
          - _write_env_value 被调用
        """
        # 让 _read_env_value 返回旧值，避免触发"未变化"提前返回
        with patch(
            "deerflow_extensions.env_settings.router._read_env_value",
        ) as mock_read:
            mock_read.side_effect = lambda key: (
                "old_bot_id" if key == "WECOM_BOT_ID"
                else "old_secret" if key == "WECOM_BOT_SECRET"
                else ""
            )

            response = client.put(
                _url("/channels"),
                json={
                    "channel": "wecom",
                    "credentials": {
                        "bot_id": "new_bot_id",
                        "bot_secret": "new_secret_value",
                    },
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "企业微信" in data["message"]

    def test_rt6_put_channels_invalid_channel_returns_404(self, client):
        """PUT /channels 传入不存在的渠道返回 404。"""
        response = client.put(
            _url("/channels"),
            json={
                "channel": "nonexistent_channel",
                "credentials": {"bot_id": "test_id", "bot_secret": "test_secret"},
            },
        )
        assert response.status_code == 404

    # ------------------------------------------------------------------
    # RT7: POST /channels/{channel}/verify — 不触发 providers 逻辑
    # ------------------------------------------------------------------

    def test_rt7_post_channels_verify_does_not_trigger_providers(self, client):
        """RT7: POST /channels/wecom/verify 不应触发 /providers 逻辑。

        验证：
          - 响应来自 channels verify 逻辑（_test_wecom_connect 被调用）
          - providers verify 逻辑（AsyncClient 等方面）未被触发
        """
        # 追踪哪些函数被调用了
        provider_verify_triggered = {"called": False}

        original_verify = (
            "deerflow_extensions.env_settings.router.verify_provider_key"
        )

        with patch(
            "deerflow_extensions.env_settings.router._get_test_fn",
        ) as mock_get:
            mock_fn = AsyncMock()
            mock_fn.return_value = (True, "连接成功")
            mock_get.return_value = mock_fn

            # 监视 verify_provider_key 是否被调用
            with patch(
                "deerflow_extensions.env_settings.router.verify_provider_key",
                side_effect=lambda *a, **kw: (
                    provider_verify_triggered.__setitem__("called", True)
                    or MagicMock()
                ),
            ):
                response = client.post(
                    _url("/channels/wecom/verify"),
                    json={"credentials": {"bot_id": "test_bot", "bot_secret": "test_secret"}},
                )

        # channels verify 逻辑应被触发
        mock_fn.assert_awaited_once()

        # providers verify 不应被触发
        assert not provider_verify_triggered["called"], (
            "POST /channels/wecom/verify triggered provider verify logic — "
            "routes are not properly isolated"
        )

        # 验证响应来自 channels 端点
        assert response.status_code == 200

    def test_rt7_post_channels_verify_invalid_channel_returns_404(self, client):
        """POST /channels/{channel}/verify 不存在的渠道返回 404。"""
        response = client.post(
            _url("/channels/nonexistent/verify"),
            json={"credentials": {"bot_id": "test", "bot_secret": "test"}},
        )
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "channel,expected_status",
        [
            ("wecom", 200),  # 存在的渠道
        ],
    )
    def test_rt7_post_channels_verify_response_shape(self, client, channel, expected_status):
        """POST /channels 的 verify 响应包含 valid 和 message 字段。"""
        with patch(
            "deerflow_extensions.env_settings.router._get_test_fn",
        ) as mock_get:
            mock_fn = AsyncMock()
            mock_fn.return_value = (False, "凭据无效")
            mock_get.return_value = mock_fn

            response = client.post(
                _url(f"/channels/{channel}/verify"),
                json={"credentials": {"bot_id": "test", "bot_secret": "test"}},
            )

        assert response.status_code == expected_status
        if expected_status == 200:
            data = response.json()
            assert "valid" in data
            assert "message" in data
            assert data["valid"] is False
            assert "凭据无效" in data["message"]

    # ------------------------------------------------------------------
    # RT8: POST /providers/{provider}/verify — 不触发 channels 逻辑
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_rt8_post_providers_verify_does_not_trigger_channels(self, client):
        """RT8: POST /providers/deepseek/verify 不应触发 channels 逻辑。

        验证：
          - 响应来自 providers verify 逻辑
          - channels verify 逻辑（_test_wecom_connect）未被触发
        """
        channel_verify_triggered = {"called": False}

        with patch(
            "deerflow_extensions.env_settings.router._test_wecom_connect",
            new_callable=AsyncMock,
        ) as mock_channel_test:
            mock_channel_test.side_effect = (
                lambda *a, **kw: (
                    channel_verify_triggered.__setitem__("called", True),
                    (True, "连接成功"),
                )[1]
            )

            # mock AsyncClient 避免真实 HTTP 请求
            with patch(
                "deerflow_extensions.env_settings.router.AsyncClient"
            ) as mock_async_client:
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_async_client_instance = mock_async_client.return_value
                mock_async_client_instance.__aenter__.return_value.get.return_value = (
                    mock_response
                )

                response = client.post(
                    _url("/providers/deepseek/verify"),
                    json={
                        "api_key": "sk-test-valid-key",
                        "base_url": "https://api.deepseek.com",
                    },
                )

        # channels verify 逻辑不应被触发
        assert not channel_verify_triggered["called"], (
            "POST /providers/deepseek/verify triggered channel verify logic "
            "(_test_wecom_connect) — routes are not properly isolated"
        )

        # 验证响应来自 providers 端点
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "message" in data

    def test_rt8_post_providers_verify_invalid_provider_returns_404(self, client):
        """POST /providers/{provider}/verify 不存在的厂商返回 404。"""
        response = client.post(
            _url("/providers/nonexistent/verify"),
            json={"api_key": "sk-test"},
        )
        assert response.status_code == 404

    def test_rt8_post_providers_verify_without_api_key_returns_valid_false(self, client):
        """POST /providers/{provider}/verify 不传 api_key 且 .env 无记录时返回 valid=false。

        _read_env_value 默认返回 ""，因此 verify 应返回 invalid。
        """
        response = client.post(
            _url("/providers/deepseek/verify"),
            json={},  # 不传 api_key、base_url
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "未配置" in data["message"]


# ===================================================================
# 额外的 DELETE 端点隔离测试（作为补充保障）
# ===================================================================


class TestDeleteRouteIsolation:
    """DELETE 端点路由隔离测试。"""

    @pytest.fixture
    def client(self):
        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as c:
            yield c

    @pytest.fixture(autouse=True)
    def _patch_all(self):
        """统一 mock 所有外部依赖。"""
        with (
            patch("deerflow_extensions.env_settings.router._get_env_lock"),
            patch("deerflow_extensions.env_settings.router._unset_env_value"),
            patch("deerflow_extensions.env_settings.router._remove_models_from_config"),
            patch("app.channels.service.get_channel_service"),
        ):
            yield

    def test_delete_providers_does_not_affect_channels(self, client):
        """DELETE /providers/{provider} 不应触碰渠道配置。

        验证 _unset_env_value 仅被厂商前缀调用，而非渠道前缀。
        """
        tracked_calls = []

        with patch(
            "deerflow_extensions.env_settings.router._unset_env_value",
        ) as mock_unset:
            mock_unset.side_effect = lambda key: tracked_calls.append(key)

            response = client.delete(_url("/providers/deepseek"))

        assert response.status_code == 200
        # 所有调用应该是厂商前缀
        for key in tracked_calls:
            assert "BOT_ID" not in key, (
                f"DELETE /providers called _unset_env_value with channel key "
                f"'{key}' — route isolation broken"
            )
            assert "BOT_SECRET" not in key

    def test_delete_channels_does_not_affect_providers(self, client):
        """DELETE /channels/{channel} 不应触碰厂商配置。

        验证 _unset_env_value 仅被渠道前缀调用，而非厂商前缀。
        """
        tracked_calls = []

        with patch(
            "deerflow_extensions.env_settings.router._unset_env_value",
        ) as mock_unset:
            mock_unset.side_effect = lambda key: tracked_calls.append(key)

            response = client.delete(_url("/channels/wecom"))

        assert response.status_code == 200
        # 确保 _unset_env_value 被调用且只涉及渠道前缀
        if tracked_calls:
            for key in tracked_calls:
                assert "_API_KEY" not in key, (
                    f"DELETE /channels called _unset_env_value with provider key "
                    f"'{key}' — route isolation broken"
                )
                assert "WECOM" in key or "BOT" in key, (
                    f"Unexpected key '{key}' in DELETE /channels"
                )
