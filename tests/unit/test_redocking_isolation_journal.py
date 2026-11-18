import json
import sys
import pytest
from tools import redocking_isolation as isolation


def test_interrupted_checkpoint_retains_previous_atomic_event(tmp_path, monkeypatch):
    journal = isolation.AtomicJournal(tmp_path / "journal", {"case_id": "synthetic", "seed": 7})
    journal.emit({"stage": "load", "phase": "complete"})
    before = isolation.read_checkpoint(journal.directory)
    original = isolation.os.replace
    def interrupted(src, dst):
        if str(dst).endswith("checkpoint.json"):
            raise OSError("synthetic publish interruption")
        return original(src, dst)
    monkeypatch.setattr(isolation.os, "replace", interrupted)
    with pytest.raises(OSError, match="interruption"):
        journal.emit({"stage": "search", "phase": "start"})
    assert isolation.read_checkpoint(journal.directory) == before
    assert json.loads((journal.directory / "event-000002.json").read_text())["event"]["stage"] == "search"


def test_corrupt_checkpoint_is_rejected(tmp_path):
    journal = isolation.AtomicJournal(tmp_path / "journal", {"seed": 9})
    journal.emit({"stage": "load", "phase": "complete"})
    path = journal.directory / "checkpoint.json"
    checkpoint = json.loads(path.read_text())
    checkpoint["last_event"]["phase"] = "forged"
    path.write_text(json.dumps(checkpoint))
    with pytest.raises(isolation.IsolationError, match="integrity"):
        isolation.read_checkpoint(journal.directory)


def test_budget_failure_keeps_committed_checkpoint(tmp_path):
    journal = isolation.AtomicJournal(tmp_path / "journal", {}, max_events=1)
    journal.emit({"stage": "one"})
    before = isolation.read_checkpoint(journal.directory)
    with pytest.raises(isolation.IsolationError, match="budget"):
        journal.emit({"stage": "two"})
    assert isolation.read_checkpoint(journal.directory) == before


def test_killed_worker_preserves_durable_phase_not_partial_json(tmp_path):
    directory = tmp_path / "journal"
    code = ("from tools.redocking_isolation import AtomicJournal;from pathlib import Path;import time;"
            f"p=Path({str(directory)!r});j=AtomicJournal(p,{{'case_id':'synthetic','seed':13}});"
            "j.emit({'stage':'preparation','phase':'start'});"
            "(p/'incomplete.pending').write_text('{');time.sleep(30)")
    result = isolation.supervise([sys.executable, "-c", code], tmp_path / "process",
                                 isolation.Limits(.7, poll_seconds=.025, terminate_grace_seconds=.05))
    assert result["termination"] == "wall_timeout" and result["cleanup_complete"]
    checkpoint = isolation.read_checkpoint(directory)
    assert checkpoint["last_sequence"] == 1
    assert checkpoint["last_event"] == {"phase": "start", "stage": "preparation"}
    assert (directory / "incomplete.pending").read_text() == "{"


def test_existing_journal_is_not_reused(tmp_path):
    isolation.AtomicJournal(tmp_path / "journal", {})
    with pytest.raises(FileExistsError):
        isolation.AtomicJournal(tmp_path / "journal", {})
