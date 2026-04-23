import os
from pathlib import Path

from tools import run_live_unseen_supervisor as sup


def test_recover_stale_lock_removes_dead_owner(tmp_path: Path):
    lock = tmp_path / "loop.lock"
    lock.write_text("999999\n", encoding="utf-8")
    out = sup._recover_stale_lock(str(lock))
    assert out["checked"] is True
    assert out["recovered"] is True
    assert lock.exists() is False


def test_recover_stale_lock_keeps_live_owner(tmp_path: Path):
    lock = tmp_path / "loop.lock"
    lock.write_text(f"{int(os.getpid())}\n", encoding="utf-8")
    out = sup._recover_stale_lock(str(lock))
    assert out["checked"] is True
    assert out["recovered"] is False
    assert out["reason"] == "owner_alive"
    assert lock.exists() is True
