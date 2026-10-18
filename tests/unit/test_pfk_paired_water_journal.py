"""Durability failures must not make interrupted paired work reusable."""
import os

import pytest

from tools.pfk_paired_water_eight_dof.journal import DispatchError, StageJournal, inspect


def test_fsync_after_complete_start_row_never_calls_stage_or_allows_retry(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    journal = StageJournal(path, {"WL": 2})
    original = os.fsync

    def fail_journal_fsync(fd):
        if fd == journal.fd:
            raise OSError("injected fsync failure after append")
        return original(fd)

    monkeypatch.setattr(os, "fsync", fail_journal_fsync)
    called = []
    with pytest.raises(OSError, match="injected"):
        journal.invoke("WL", lambda: called.append(True))
    assert not called
    assert journal.poisoned and journal.pending
    with pytest.raises(DispatchError, match="retry forbidden"):
        journal.invoke("WL", lambda: called.append(True))
    journal.close()
    result = inspect(path, {"WL": 2})
    assert result["pending"] == {"WL": 1}
    assert result["total_started_calls"] is None
    assert result["automatic_retry_admitted"] is False


def test_fsync_after_complete_finish_preserves_runtime_publication_uncertainty(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    journal = StageJournal(path, {"WL": 2})
    original = os.fsync
    writes = 0

    def fail_finish_fsync(fd):
        nonlocal writes
        if fd == journal.fd:
            writes += 1
            if writes == 2:
                raise OSError("injected finished-row fsync failure")
        return original(fd)

    monkeypatch.setattr(os, "fsync", fail_finish_fsync)
    called = []
    with pytest.raises(OSError, match="finished-row"):
        journal.invoke("WL", lambda: called.append("returned"))
    assert called == ["returned"]
    assert journal.poisoned and journal.publication_uncertain
    assert journal.pending == {"WL": 1}
    # Complete readable finish bytes do not prove that their fsync succeeded.
    readable = inspect(path, {"WL": 2})
    assert readable["counts"]["WL"]["finished"] == 1
    with pytest.raises(DispatchError, match="retry forbidden"):
        journal.invoke("WL", lambda: called.append("reissued"))
    assert called == ["returned"]
    journal.close()


def test_failed_callable_is_counted_and_cannot_be_reissued(tmp_path):
    path = tmp_path / "events.jsonl"
    journal = StageJournal(path, {"WL": 2})

    def fail():
        raise KeyboardInterrupt("completed failed synthetic dispatch")

    with pytest.raises(KeyboardInterrupt):
        journal.invoke("WL", fail)
    with pytest.raises(DispatchError, match="retry forbidden"):
        journal.invoke("WL", lambda: None)
    journal.close()
    result = inspect(path, {"WL": 2})
    assert result["total_work_known"]
    assert result["counts"]["WL"] == {"started": 1, "finished": 1, "succeeded": 0, "failed": 1}


def test_partial_tail_or_modified_record_cannot_be_reported_as_known(tmp_path):
    path = tmp_path / "events.jsonl"
    journal = StageJournal(path, {"WL": 1})
    assert journal.invoke("WL", lambda: 23) == 23
    journal.close()
    raw = path.read_bytes()
    assert inspect(path, {"WL": 1})["total_started_calls"] == 1
    path.write_bytes(raw + b'{"unfinished":')
    assert inspect(path, {"WL": 1})["total_started_calls"] is None
    path.write_bytes(raw.replace(b'"success":true', b'"success":false'))
    result = inspect(path, {"WL": 1})
    assert result["errors"] and result["total_started_calls"] is None


def test_existing_run_and_exhausted_budget_never_dispatch(tmp_path):
    path = tmp_path / "events.jsonl"
    journal = StageJournal(path, {"WL": 1})
    journal.invoke("WL", lambda: None)
    called = []
    with pytest.raises(DispatchError, match="exhausted"):
        journal.invoke("WL", lambda: called.append(True))
    assert not called
    journal.close()
    with pytest.raises(FileExistsError):
        StageJournal(path, {"WL": 1})
