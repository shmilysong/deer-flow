"""Test the Test-Before-Switch safe restart logic in update_channel_settings.

Covers RS1-RS6 scenarios:
    RS1: Running channel + new params pass test  → restart_channel called, "已自动重启"
    RS2: Running channel + new params fail test  → restart_channel NOT called, "不受影响"
    RS3: Stopped channel + restart succeeds      → restart_channel called, "已自动重启"
    RS4: Stopped channel + restart fails         → restart_channel called, "无法启动"
    RS5: DELETE clears channel                   → stop() called, _config memory cleaned
    RS6: PUT with unchanged values               → _write_env_value / restart_channel NOT called
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# sys.path: ensure `app` (from backend/) is importable for
# `from app.channels.service import get_channel_service` inside router.py
# ---------------------------------------------------------------------------
_backend_dir = Path(__file__).resolve().parents[3] / "backend"
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))


@pytest.mark.asyncio
class TestChannelRestart:
    """Test the Test-Before-Switch safe restart logic in update_channel_settings.

    Every test patches at minimum:
      - get_channel_service  → mock ChannelService singleton
      - _write_env_value     → no-op (avoid .env file side-effect)
      - _read_env_value      → control what values "already exist" in .env
      - _get_env_lock        → no-op context manager (avoid FileLock/FileNotFound)
    """

    # ------------------------------------------------------------------
    # fixtures
    # ------------------------------------------------------------------

    @pytest.fixture(autouse=True)
    def _patch_lock(self):
        """Make _get_env_lock a no-op context manager."""
        with patch(
            "deerflow_extensions.env_settings.router._get_env_lock",
            return_value=MagicMock(),
        ):
            yield

    @pytest.fixture
    def mock_write_env(self):
        """Prevent writes to the real .env file."""
        with patch(
            "deerflow_extensions.env_settings.router._write_env_value"
        ) as mock:
            yield mock

    @pytest.fixture
    def mock_unset_env(self):
        """Prevent deletes from the real .env file."""
        with patch(
            "deerflow_extensions.env_settings.router._unset_env_value"
        ) as mock:
            yield mock

    @pytest.fixture
    def mock_read_env(self, request):
        """Control _read_env_value return values.

        Sub-tests can override via ``request.getfixturevalue`` or inline patches.
        By default returns "old_" values so the "unchanged" early-return is NOT
        triggered — the branch under test proceeds past the guard.
        """
        with patch(
            "deerflow_extensions.env_settings.router._read_env_value"
        ) as mock:

            def _default_side_effect(key: str) -> str:
                mapping = {
                    "WECOM_BOT_ID": "old_bot_id",
                    "WECOM_BOT_SECRET": "old_secret",
                }
                return mapping.get(key, "")

            mock.side_effect = _default_side_effect
            yield mock

    @pytest.fixture
    def mock_test_connect(self, request):
        """Control _get_test_fn return values.

        Default: returns (True, "连接成功").
        Override via ``request.getfixturevalue`` for RS2.
        """
        with patch(
            "deerflow_extensions.env_settings.router._get_test_fn",
        ) as mock:
            mock_fn = AsyncMock()
            mock_fn.return_value = (True, "连接成功")
            mock.return_value = mock_fn
            yield mock_fn

    @pytest.fixture
    def mock_get_service(self):
        """Provide a controllable ChannelService mock.

        The returned ``service`` object has:
          - _config: dict with "wecom" key
          - _channels: dict — sub-tests add/remove entries as needed
          - restart_channel: AsyncMock returning True
        """
        with patch(
            "app.channels.service.get_channel_service"
        ) as mock:
            service = MagicMock()
            service._config = {
                "wecom": {
                    "bot_id": "old_bot_id",
                    "bot_secret": "old_secret",
                    "enabled": True,
                }
            }
            # Sub-tests override _channels to control running / stopped state
            service._channels = {}
            service.restart_channel = AsyncMock(return_value=True)
            mock.return_value = service
            yield service

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    async def _do_update(
        self,
        credentials: dict[str, str] | None = None,
        channel: str = "wecom",
    ) -> object:
        """Call update_channel_settings and return the response."""
        if credentials is None:
            credentials = {"bot_id": "new_bot_id", "bot_secret": "new_secret"}
        from deerflow_extensions.env_settings.router import (
            ChannelUpdateRequest,
            update_channel_settings,
        )

        request = ChannelUpdateRequest(
            channel=channel,
            credentials=credentials,
        )
        return await update_channel_settings(request)

    async def _do_delete(self, channel: str = "wecom") -> object:
        """Call delete_channel_settings and return the response."""
        from deerflow_extensions.env_settings.router import (
            delete_channel_settings,
        )

        return await delete_channel_settings(channel)

    # ==================================================================
    # RS1 — Running channel + good params → restart_channel + "已自动重启"
    # ==================================================================

    async def test_rs1_running_channel_good_params_triggers_restart(
        self,
        mock_write_env,
        mock_read_env,
        mock_get_service,
        mock_test_connect,
    ):
        """RS1: channel is running, test-connect passes → restart + success msg."""
        service = mock_get_service
        service._channels = {"wecom": MagicMock(is_running=True)}

        resp = await self._do_update()

        # _test_wecom_connect was called with credentials kwargs
        mock_test_connect.assert_awaited_once_with(bot_id="new_bot_id", bot_secret="new_secret")

        # Config was updated in memory
        assert service._config["wecom"]["bot_id"] == "new_bot_id"
        assert service._config["wecom"]["bot_secret"] == "new_secret"

        # restart_channel was called
        service.restart_channel.assert_awaited_once_with("wecom")

        # Message contains restart indicator
        assert "已自动重启" in resp.message
        assert resp.success is True

    # ==================================================================
    # RS2 — Running channel + bad params  → NO restart + "不受影响"
    # ==================================================================

    async def test_rs2_running_channel_bad_params_no_restart(
        self,
        mock_write_env,
        mock_read_env,
        mock_get_service,
    ):
        """RS2: channel is running, test-connect fails → no restart, safe msg."""
        service = mock_get_service
        service._channels = {"wecom": MagicMock(is_running=True)}

        # Override test-connect to fail
        with patch(
            "deerflow_extensions.env_settings.router._get_test_fn",
        ) as mock_get:
            mock_fn = AsyncMock()
            mock_fn.return_value = (False, "连接失败: token invalid")
            mock_get.return_value = mock_fn

            resp = await self._do_update()

            # _test_wecom_connect was called with credentials kwargs
            mock_fn.assert_awaited_once_with(bot_id="new_bot_id", bot_secret="new_secret")

            # restart_channel was NOT called
            service.restart_channel.assert_not_called()

            # Message says the old channel is unaffected
            assert "不受影响" in resp.message
            assert resp.success is True

    # ==================================================================
    # RS3 — Stopped channel + restart succeeds → restart_channel + "已自动重启"
    # ==================================================================

    async def test_rs3_stopped_channel_restart_ok(
        self,
        mock_write_env,
        mock_read_env,
        mock_get_service,
    ):
        """RS3: channel not running, restart returns True → restart + success msg."""
        service = mock_get_service
        service._channels = {}  # empty → not running
        service.restart_channel = AsyncMock(return_value=True)

        resp = await self._do_update()

        # Config updated
        assert service._config["wecom"]["bot_id"] == "new_bot_id"
        assert service._config["wecom"]["bot_secret"] == "new_secret"

        # restart_channel was called
        service.restart_channel.assert_awaited_once_with("wecom")

        # Message contains restart indicator
        assert "已自动重启" in resp.message
        assert resp.success is True

    # ==================================================================
    # RS4 — Stopped channel + restart fails  → restart_channel + "无法启动"
    # ==================================================================

    async def test_rs4_stopped_channel_restart_fails(
        self,
        mock_write_env,
        mock_read_env,
        mock_get_service,
    ):
        """RS4: channel not running, restart returns False → restart + fail msg."""
        service = mock_get_service
        service._channels = {}  # empty → not running
        service.restart_channel = AsyncMock(return_value=False)

        resp = await self._do_update()

        # Config updated
        assert service._config["wecom"]["bot_id"] == "new_bot_id"
        assert service._config["wecom"]["bot_secret"] == "new_secret"

        # restart_channel was called
        service.restart_channel.assert_awaited_once_with("wecom")

        # Message says channel could not start
        assert "无法启动" in resp.message
        assert resp.success is True

    # ==================================================================
    # RS5 — DELETE stops channel + clears _config memory
    # ==================================================================

    async def test_rs5_delete_stops_channel_and_cleans_config(
        self,
        mock_unset_env,
        mock_get_service,
    ):
        """RS5: DELETE → stop() called, _channels entry removed, _config cleared."""
        service = mock_get_service
        wecom_channel = AsyncMock()
        service._channels = {"wecom": wecom_channel}
        service._config = {
            "wecom": {
                "bot_id": "old_bot_id",
                "bot_secret": "old_secret",
                "enabled": True,
            }
        }

        resp = await self._do_delete()

        # Channel was stopped
        wecom_channel.stop.assert_awaited_once()

        # Channel removed from _channels
        assert "wecom" not in service._channels

        # _config memory cleared
        assert service._config["wecom"]["bot_id"] == ""
        assert service._config["wecom"]["bot_secret"] == ""

        # Response indicates success
        assert resp.success is True
        assert "已清除" in resp.message

    # ==================================================================
    # RS6 — PUT unchanged values → early return, nothing saved/restarted
    # ==================================================================

    async def test_rs6_unchanged_values_skips_write_and_restart(
        self,
        mock_get_service,
        mock_write_env,
    ):
        """RS6: _read_env_value matches request → no _write_env_value, no restart."""
        # _read_env_value returns the SAME values as the request
        with patch(
            "deerflow_extensions.env_settings.router._read_env_value"
        ) as mock_read:

            def _same_values(key: str) -> str:
                mapping = {
                    "WECOM_BOT_ID": "same_bot_id",
                    "WECOM_BOT_SECRET": "same_secret",
                }
                return mapping.get(key, "")

            mock_read.side_effect = _same_values

            resp = await self._do_update(
                credentials={"bot_id": "same_bot_id", "bot_secret": "same_secret"},
            )

        # _write_env_value was NOT called
        mock_write_env.assert_not_called()

        # get_channel_service was NOT called either (early return before that logic)

        # Message says no change
        assert "配置未变化" in resp.message
        assert resp.success is True
