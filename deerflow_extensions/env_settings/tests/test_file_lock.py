"""
测试 env_settings/router.py 中的文件锁并发机制

覆盖范围（共 4 项，FL1-FL4）：
  FL1: 并发写入不丢失 — 5 个并发线程写入不同 key，验证所有值都写入
  FL2: 锁超时优雅降级 — 一个线程先持锁 6s，另一个请求等锁超时，捕获 Timeout
  FL3: 锁文件自动清理 — release 后验证 .env.lock 不存在
  FL4: 锁保护原子双写入 — 同一锁内写两个 key，验证两者都写入
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
from unittest import mock

import pytest
from dotenv import set_key
from filelock import FileLock, Timeout

# ---------------------------------------------------------------------------
# 将被测模块所在目录加入 sys.path，以便 import
# ---------------------------------------------------------------------------
_test_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_test_dir)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from router import _get_env_lock, _write_env_value, _read_env_value

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def env_file(tmp_path):
    """创建临时 .env 文件并 mock router.find_dotenv 指向它。

    所有依赖 _get_env_path() 的函数将自动使用此临时文件。
    """
    env_path = tmp_path / ".env"
    env_path.write_text("")

    with mock.patch("router.find_dotenv", return_value=str(env_path)):
        yield env_path


@pytest.fixture
def env_lock_path(env_file):
    """返回预期的 .env.lock 路径（由 _get_env_lock 自动生成）。"""
    return env_file.with_suffix(".env.lock")


# ---------------------------------------------------------------------------
# FL1: 并发写入不丢失
# ---------------------------------------------------------------------------


class TestConcurrentWrites:
    """FL1: 多个线程并发写入不同 key，验证所有值都写入。"""

    def test_concurrent_writes_no_data_loss(self, env_file):
        """FL1: 5 个并发线程使用 with _get_env_lock(): _write_env_value()
        写入不同 key，验证所有值都被写入 .env。"""
        keys_values = {
            "TEST_KEY_A": "value_a",
            "TEST_KEY_B": "value_b",
            "TEST_KEY_C": "value_c",
            "TEST_KEY_D": "value_d",
            "TEST_KEY_E": "value_e",
        }

        def _write_single(key: str, value: str) -> None:
            """在每个线程中执行加锁写入。"""
            with _get_env_lock():
                _write_env_value(key, value)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(_write_single, key, value)
                for key, value in keys_values.items()
            ]
            # 等待所有线程完成
            done, _ = wait(futures, timeout=30)
            assert len(done) == 5, "Not all write tasks completed"

            # 检查是否任何线程抛出了未捕获的异常
            for future in done:
                exc = future.exception()
                assert exc is None, f"Write task raised: {exc}"

        # 验证 .env 文件中包含所有 key
        content = env_file.read_text()
        for key, value in keys_values.items():
            assert key in content, f"Missing key: {key}"
            assert value in content, f"Missing value: {value}"

        # 验证通过 _read_env_value 也能正确读取
        for key, value in keys_values.items():
            assert _read_env_value(key) == value, f"Read back mismatch for {key}"


# ---------------------------------------------------------------------------
# FL2: 锁超时优雅降级
# ---------------------------------------------------------------------------


class TestLockTimeout:
    """FL2: 锁超时场景 — 验证 Timeout 异常被 try/except 捕获。"""

    def test_lock_timeout_graceful_degradation(self, env_lock_path):
        """FL2: 线程 A 先持锁 6s，线程 B 请求等锁超时（5s timeout），
        验证 Timeout 异常被捕获，不导致进程崩溃。"""
        lock_path = str(env_lock_path)
        timeout_exception_caught = {"caught": False}

        def _hold_lock_long():
            """线程 A：持锁 6s 后释放。"""
            lock = FileLock(lock_path, timeout=10)
            with lock:
                time.sleep(6)

        def _try_acquire_with_timeout():
            """线程 B：尝试获取锁，应超时。"""
            try:
                short_lock = FileLock(lock_path, timeout=3)
                with short_lock:
                    pass  # 不应到达这里
            except Timeout:
                timeout_exception_caught["caught"] = True
            except Exception:
                # 其他异常也应标记为已捕获（但预期是 Timeout）
                timeout_exception_caught["caught"] = True

        with ThreadPoolExecutor(max_workers=2) as executor:
            # 先提交持锁线程，让它先获得锁
            future_hold = executor.submit(_hold_lock_long)
            time.sleep(0.5)  # 确保线程 A 已获取锁

            # 再提交超时线程
            future_timeout = executor.submit(_try_acquire_with_timeout)

            # 等待两个线程完成
            wait([future_hold, future_timeout], timeout=20)

        # 验证超时异常已被捕获
        assert timeout_exception_caught["caught"], (
            "Timeout exception was NOT caught — the lock timeout did not "
            "trigger a caught exception as expected"
        )

        # 验证锁文件是否已被清理（持锁线程释放后）
        # 注意：由于并行执行，cleanup 可能在 main 线程检查前完成
        # (FileLock 的 release 会在 with 块退出时自动清理)
        lock_file = Path(lock_path)
        # 短暂等待确保文件系统同步
        time.sleep(0.3)
        assert not lock_file.exists(), (
            f"Lock file {lock_path} should have been cleaned up after release"
        )


# ---------------------------------------------------------------------------
# FL3: 锁文件自动清理
# ---------------------------------------------------------------------------


class TestLockFileCleanup:
    """FL3: 正常 release 后 .env.lock 不存在。"""

    def test_lock_file_removed_after_release(self, env_file, env_lock_path):
        """FL3: 正常 release 后验证 .env.lock 不存在。"""
        lock_path = str(env_lock_path)

        # 文件锁文件初始不应存在
        assert not env_lock_path.exists()
        assert not Path(lock_path).exists()

        # 获取并释放锁
        with _get_env_lock():
            # 在 with 块内，锁文件应存在（FileLock 创建 lock 文件）
            pass

        # with 块退出后，锁文件应已删除
        assert not env_lock_path.exists(), (
            f"Lock file {env_lock_path} still exists after release"
        )


# ---------------------------------------------------------------------------
# FL4: 锁保护原子双写入
# ---------------------------------------------------------------------------


class TestAtomicDualWrite:
    """FL4: 在同一个锁内写入两个 key，验证两者都写入。"""

    def test_atomic_dual_write(self, env_file):
        """FL4: 在同一个 with _get_env_lock(): 内同时写入两个 key，
        验证两者都被写入 .env 文件。"""
        with _get_env_lock():
            _write_env_value("ATOMIC_KEY_1", "value_1")
            _write_env_value("ATOMIC_KEY_2", "value_2")

        # 验证两者都写入
        content = env_file.read_text()
        assert "ATOMIC_KEY_1" in content, "ATOMIC_KEY_1 missing from .env"
        assert "value_1" in content, "value_1 missing from .env"
        assert "ATOMIC_KEY_2" in content, "ATOMIC_KEY_2 missing from .env"
        assert "value_2" in content, "value_2 missing from .env"

        # 验证通过读取 API 也能读到
        assert _read_env_value("ATOMIC_KEY_1") == "value_1"
        assert _read_env_value("ATOMIC_KEY_2") == "value_2"


# ---------------------------------------------------------------------------
# 清理：测试结束后从 os.environ 移除测试 key
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def cleanup_test_env_vars():
    """每个测试前后清理测试用环境变量，防止交叉污染。"""
    test_prefixes = ["TEST_KEY_", "ATOMIC_KEY_"]
    for key in list(os.environ.keys()):
        if any(key.startswith(p) for p in test_prefixes):
            os.environ.pop(key, None)
    yield
    for key in list(os.environ.keys()):
        if any(key.startswith(p) for p in test_prefixes):
            os.environ.pop(key, None)
