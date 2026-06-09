"""
测试 env_settings/router.py 中的渠道辅助函数

覆盖范围（共 14 项用例，细分为 16 个测试函数）：
  UT1-UT2:  正常保存 WeCom 凭据（_write_env_value + .env 写入 + os.environ 同步）
  UT3-UT4:  读取已存在 / 不存在配置（_read_env_value）
  UT5-UT7:  掩码函数测试（正常长度 / 短 <=8 / 空字符串）
  UT8:      清除不存在的配置不抛异常
  UT9:      .env 有注释和无关变量时写入后保留
  UT10:     超长字段（1024 字符）写入成功
  UT11:     值不变跳过写入（重复写入同一值不产生重复行）
  UT12:     存量校验（写入后读取对比完全一致）
  UT13:     输入裁剪（"  abc  " → "abc"）
  UT14:     trim 后为空 → 不写入（HTTPException）
"""

import os
import sys
from pathlib import Path
from unittest import mock

import pytest
from dotenv import set_key
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# 将被测模块所在目录加入 sys.path，以便 import
# ---------------------------------------------------------------------------
_test_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_test_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from router import (
    _mask_value,
    _read_env_value,
    _set_channel_enabled_in_config,
    _unset_env_value,
    _write_env_value,
    _sanitize_channel_credentials,
)

# ---------------------------------------------------------------------------
# fixture：临时 .env 文件 + mock find_dotenv
# ---------------------------------------------------------------------------


@pytest.fixture
def env_file(tmp_path):
    """创建临时 .env 文件并 mock router.find_dotenv 指向它。

    所有依赖 _get_env_path() 的辅助函数（_read_env_value /
    _write_env_value / _unset_env_value）将自动使用此临时文件，
    不影响项目真实 .env。
    """
    env_path = tmp_path / ".env"
    env_path.write_text("")  # 空文件初始

    with mock.patch("router.find_dotenv", return_value=str(env_path)):
        yield env_path


# ---------------------------------------------------------------------------
# UT1-UT2: 正常保存 WeCom 凭据
# ---------------------------------------------------------------------------


class TestWriteEnvValue:
    """_write_env_value —— 写入 .env 文件与同步 os.environ"""

    def test_write_to_dotenv_file(self, env_file):
        """UT1: _write_env_value 将凭据写入 .env 文件"""
        _write_env_value("WECOM_BOT_ID", "test_bot_id")
        _write_env_value("WECOM_BOT_SECRET", "test_bot_secret")

        content = env_file.read_text()
        # set_key 可能使用单引号或双引号，兼容两者
        assert "WECOM_BOT_ID=" in content
        assert "test_bot_id" in content
        assert "WECOM_BOT_SECRET=" in content
        assert "test_bot_secret" in content

    def test_sync_to_os_environ(self, env_file):
        """UT2: _write_env_value 同步到 os.environ"""
        # 清理可能已有的脏值
        os.environ.pop("WECOM_BOT_ID", None)
        os.environ.pop("WECOM_BOT_SECRET", None)

        _write_env_value("WECOM_BOT_ID", "sync_bot_id")
        _write_env_value("WECOM_BOT_SECRET", "sync_bot_secret")

        assert os.environ["WECOM_BOT_ID"] == "sync_bot_id"
        assert os.environ["WECOM_BOT_SECRET"] == "sync_bot_secret"


# ---------------------------------------------------------------------------
# UT3-UT4: 读取已存在 / 不存在配置
# ---------------------------------------------------------------------------


class TestReadEnvValue:
    """_read_env_value —— 从 .env 读取配置"""

    def test_read_existing_key(self, env_file):
        """UT3: 读取已存在的 key 返回正确值"""
        set_key(str(env_file), "WECOM_BOT_ID", "existing_val", quote_mode="always")
        result = _read_env_value("WECOM_BOT_ID")
        assert result == "existing_val"

    def test_read_nonexistent_key(self, env_file):
        """UT4: 读取不存在的 key 返回空字符串"""
        result = _read_env_value("I_DO_NOT_EXIST")
        assert result == ""


# ---------------------------------------------------------------------------
# UT5-UT7: 掩码函数测试
# ---------------------------------------------------------------------------


class TestMaskValue:
    """_mask_value —— 凭据掩码"""

    def test_normal_length(self):
        """UT5: 长度 >8 时保留前 3 + **** + 后 4"""
        result = _mask_value("abcdefghijklm")   # 13 字符
        assert result == "abc****jklm"           # 前3 + **** + 后4

    def test_short_value(self):
        """UT6: 长度 <=8 时返回 ****"""
        assert _mask_value("12345678") == "****"  # 恰好 8
        assert _mask_value("abc") == "****"        # 3
        assert _mask_value("a") == "****"          # 1

    def test_empty_string(self):
        """UT7: 空字符串返回空字符串"""
        assert _mask_value("") == ""


# ---------------------------------------------------------------------------
# UT8: 清除不存在的配置不抛异常
# ---------------------------------------------------------------------------


class TestUnsetEnvValue:
    """_unset_env_value —— 清除配置"""

    def test_unset_nonexistent_key(self, env_file):
        """UT8: 清除不存在的 key 不抛出任何异常"""
        # 不应抛出 FileNotFoundError / KeyError / 等
        _unset_env_value("I_DO_NOT_EXIST")

        # 验证文件仍可用，该 key 不存在
        result = _read_env_value("I_DO_NOT_EXIST")
        assert result == ""


# ---------------------------------------------------------------------------
# UT9: .env 有注释和无关变量时写入后保留
# ---------------------------------------------------------------------------


class TestWritePreservesExisting:
    """在已有内容的 .env 中写入时保留注释和其他变量"""

    def test_preserve_comments_and_other_vars(self, env_file):
        """UT9: 写入新凭据后，注释和其他变量仍然保留"""
        env_file.write_text(
            "# This is a comment\n"
            'EXISTING_KEY="old_value"\n'
            "# Another comment\n"
        )

        _write_env_value("WECOM_BOT_ID", "new_bot_id")

        content = env_file.read_text()
        # 注释保留
        assert "# This is a comment" in content
        assert "# Another comment" in content
        # 原有变量保留（兼容单引号/双引号）
        assert "EXISTING_KEY=" in content
        assert "old_value" in content
        # 新变量写入
        assert "WECOM_BOT_ID=" in content
        assert "new_bot_id" in content


# ---------------------------------------------------------------------------
# UT10: 超长字段（1024 字符）写入成功
# ---------------------------------------------------------------------------


class TestLongValue:
    """超长字段的写入与读取"""

    def test_write_and_read_1024_chars(self, env_file):
        """UT10: 1024 字符的值写入成功并可原样读回"""
        long_value = "x" * 1024

        _write_env_value("LONG_KEY", long_value)
        result = _read_env_value("LONG_KEY")

        assert result == long_value
        assert len(result) == 1024


# ---------------------------------------------------------------------------
# UT11: 值不变跳过写入（重复写入同一值不产生重复行）
# ---------------------------------------------------------------------------


class TestDuplicateWrite:
    """重复写入相同值"""

    def test_duplicate_write_no_duplicate_line(self, env_file):
        """UT11: 重复写入相同值时 .env 中该 key 仅出现一次"""
        _write_env_value("WECOM_BOT_ID", "same_value")
        _write_env_value("WECOM_BOT_ID", "same_value")

        content = env_file.read_text()
        # set_key 会替换已有行，不会追加
        count = content.count("WECOM_BOT_ID")
        assert count == 1, f"期望 1 次出现，实际 {count}"


# ---------------------------------------------------------------------------
# UT12: 存量校验（写入后读取对比完全一致）
# ---------------------------------------------------------------------------


class TestWriteReadConsistency:
    """写入后读取的一致性校验"""

    def test_write_then_read_identical(self, env_file):
        """UT12: 写入的值与读回的值完全一致"""
        test_value = "my_test_bot_id_value_123"
        _write_env_value("WECOM_BOT_ID", test_value)

        result = _read_env_value("WECOM_BOT_ID")
        assert result == test_value


# ---------------------------------------------------------------------------
# UT13-UT14: 输入裁剪
# ---------------------------------------------------------------------------


class TestSanitizeChannelCredentials:
    """_sanitize_channel_credentials —— 输入裁剪与空值校验"""

    CRED_FIELDS = [
        {"key": "bot_id", "label": "Bot ID"},
        {"key": "bot_secret", "label": "Bot Secret"},
    ]
    SINGLE_FIELD = [
        {"key": "bot_token", "label": "Bot Token"},
    ]

    def test_strips_whitespace(self):
        """UT13: 所有字段 trim 空白"""
        cleaned = _sanitize_channel_credentials(
            {"bot_id": "  abc  ", "bot_secret": "  def  "},
            self.CRED_FIELDS,
        )
        assert cleaned["bot_id"] == "abc"
        assert cleaned["bot_secret"] == "def"

    def test_empty_raises(self):
        """UT14: 空值抛 HTTPException(422) 附带字段 label"""
        with pytest.raises(HTTPException) as exc:
            _sanitize_channel_credentials({"bot_id": "  ", "bot_secret": "secret"}, self.CRED_FIELDS)
        assert exc.value.status_code == 422
        assert "Bot ID" in exc.value.detail

        with pytest.raises(HTTPException) as exc:
            _sanitize_channel_credentials({"bot_id": "id", "bot_secret": "  "}, self.CRED_FIELDS)
        assert exc.value.status_code == 422
        assert "Bot Secret" in exc.value.detail

    def test_both_empty_raises(self):
        """全部为空抛 422"""
        with pytest.raises(HTTPException):
            _sanitize_channel_credentials({"bot_id": "", "bot_secret": ""}, self.CRED_FIELDS)

    def test_single_field(self):
        """单字段渠道（如微信 Bot Token）"""
        cleaned = _sanitize_channel_credentials({"bot_token": " my_token "}, self.SINGLE_FIELD)
        assert cleaned["bot_token"] == "my_token"

    def test_single_field_empty_raises(self):
        """单字段空值抛 422"""
        with pytest.raises(HTTPException) as exc:
            _sanitize_channel_credentials({"bot_token": ""}, self.SINGLE_FIELD)
        assert exc.value.status_code == 422
        assert "Bot Token" in exc.value.detail

    def test_extra_fields_ignored(self):
        """多提交的字段被忽略"""
        cleaned = _sanitize_channel_credentials(
            {"bot_id": "id", "bot_secret": "secret", "extra_field": "ignored"},
            self.CRED_FIELDS,
        )
        assert "extra_field" not in cleaned
        assert cleaned["bot_id"] == "id"
        assert cleaned["bot_secret"] == "secret"


# ---------------------------------------------------------------------------
# UT15-UT20: _set_channel_enabled_in_config —— config.yaml 启用/禁用管理
# ---------------------------------------------------------------------------


class TestSetChannelEnabledInConfig:
    """_set_channel_enabled_in_config —— 启用时补齐凭据，禁用时清理凭据"""

    @pytest.fixture
    def config_file(self, tmp_path):
        """创建临时 config.yaml 并 mock _get_config_path 指向它。"""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("channels:\n  wecom:\n    enabled: false\n")
        with mock.patch("router._get_config_path", return_value=str(cfg_path)):
            yield cfg_path

    def _read_cfg(self, cfg_path):
        import yaml
        return yaml.safe_load(cfg_path.read_text())

    # -- enable variants --

    def test_enable_adds_credential_fields(self, config_file):
        """UT15: 启用渠道时自动补齐凭据引用字段"""
        _set_channel_enabled_in_config("wecom", enabled=True)
        cfg = self._read_cfg(config_file)
        wecom = cfg["channels"]["wecom"]
        assert wecom["enabled"] is True
        assert wecom["bot_id"] == "$WECOM_BOT_ID"
        assert wecom["bot_secret"] == "$WECOM_BOT_SECRET"

    def test_enable_idempotent_no_duplicate(self, config_file):
        """UT16: 已补齐的渠道再次启用不重复添加"""
        _set_channel_enabled_in_config("wecom", enabled=True)
        _set_channel_enabled_in_config("wecom", enabled=True)
        cfg = self._read_cfg(config_file)
        wecom = cfg["channels"]["wecom"]
        assert list(wecom.keys()) == ["enabled", "bot_id", "bot_secret"]

    # -- disable variants --

    def test_disable_removes_credential_fields(self, config_file):
        """UT17: 禁用渠道时自动清理凭据引用字段"""
        _set_channel_enabled_in_config("wecom", enabled=True)
        _set_channel_enabled_in_config("wecom", enabled=False)
        cfg = self._read_cfg(config_file)
        wecom = cfg["channels"]["wecom"]
        assert wecom["enabled"] is False
        assert "bot_id" not in wecom
        assert "bot_secret" not in wecom

    def test_disable_idempotent_already_clean(self, config_file):
        """UT18: 已清理的渠道再次禁用不报错"""
        _set_channel_enabled_in_config("wecom", enabled=False)
        cfg = self._read_cfg(config_file)
        wecom = cfg["channels"]["wecom"]
        assert wecom["enabled"] is False
        assert "bot_id" not in wecom

    def test_disable_channel_without_meta_ok(self, config_file):
        """UT19: 禁用 _CHANNEL_META 中不存在的渠道不报错"""
        cfg_path = config_file
        import yaml
        raw = yaml.safe_load(cfg_path.read_text()) or {}
        raw["channels"]["unknown"] = {"enabled": True, "some_key": "val"}
        cfg_path.write_text(yaml.dump(raw))
        _set_channel_enabled_in_config("unknown", enabled=False)
        cfg = self._read_cfg(cfg_path)
        assert cfg["channels"]["unknown"]["enabled"] is False
        assert cfg["channels"]["unknown"].get("some_key") == "val"

    def test_enable_then_disable_then_enable(self, config_file):
        """UT20: 启用→禁用→再启用，凭据字段可重建"""
        _set_channel_enabled_in_config("wecom", enabled=True)
        _set_channel_enabled_in_config("wecom", enabled=False)
        _set_channel_enabled_in_config("wecom", enabled=True)
        cfg = self._read_cfg(config_file)
        wecom = cfg["channels"]["wecom"]
        assert wecom["enabled"] is True
        assert wecom["bot_id"] == "$WECOM_BOT_ID"
        assert wecom["bot_secret"] == "$WECOM_BOT_SECRET"


# ---------------------------------------------------------------------------
# 清理：测试结束后从 os.environ 移除可能残留的测试 key
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def cleanup_test_env_vars():
    """每个测试前后清理测试用环境变量，防止交叉污染。"""
    test_prefixes = ["WECOM_", "FEISHU_", "DINGTALK_", "WECHAT_", "LONG_KEY", "EXISTING_KEY", "I_DO_NOT_EXIST"]
    for key in list(os.environ.keys()):
        if any(key.startswith(p) for p in test_prefixes):
            os.environ.pop(key, None)
    yield
    for key in list(os.environ.keys()):
        if any(key.startswith(p) for p in test_prefixes):
            os.environ.pop(key, None)
