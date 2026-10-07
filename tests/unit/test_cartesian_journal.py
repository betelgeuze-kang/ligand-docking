"""Durable intent ordering, bounded hostile replay, and immutable checkpoints."""
import json
import os
from pathlib import Path
import stat

import pytest

from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, canonical, digest
from betelgeuze_product.cpu_refinement_v1_3 import journal
from betelgeuze_product.cpu_refinement_v1_3.journal import TrialJournal


@pytest.fixture
def binding():
    return {"request_sha256": digest("synthetic-request"), "solver": {"version": 3}}


def _put(path, value):
    path.write_bytes((canonical(value) + "\n").encode("ascii"))


def _seed(path, binding):
    with TrialJournal(path, binding, True) as j:
        j.save_checkpoint({"accepted": []})
        j.append("objective_started", {"ordinal": 0})
        j.append("objective_finished", {"ordinal": 0, "value": -1.0})
        checkpoint = j.save_checkpoint({"accepted": [0]})
    return checkpoint


def _reseal(value, field):
    value[field] = digest({key: item for key, item in value.items() if key != field})


def test_roundtrip_detaches_payloads_binding_and_snapshots(tmp_path, binding):
    path = tmp_path / "trial"
    original_binding = json.loads(json.dumps(binding))
    pending = {"coordinate": [["0x0.0p+0"]]}
    with TrialJournal(path, binding, True) as j:
        assert j.events == [] and j.result() is None and j.latest_checkpoint() is None
        assert j.head_sha256 == digest(original_binding)
        binding["solver"]["version"] = 99
        started = j.append("objective_started", pending)
        assert started["previous_sha256"] == digest(original_binding)
        started["payload"]["coordinate"][0][0] = "changed-return"
        pending["coordinate"].append(["changed-input"])
        snapshot = j.events
        snapshot[0]["payload"]["coordinate"][0][0] = "changed-snapshot"
        assert j.events[0]["payload"] == {"coordinate": [["0x0.0p+0"]]}
        state = {"accepted": [0]}
        checkpoint = j.save_checkpoint(state)
        checkpoint["state"]["accepted"].append(1)
        state["accepted"].append(2)
        assert j.latest_checkpoint()["state"] == {"accepted": [0]}
        result = {"status": ["pending-unknown"]}
        j.publish_result(result)
        result["status"].append("changed")
        detached = j.result()
        detached["status"].append("changed-again")
        assert j.result() == {"status": ["pending-unknown"]}
    with TrialJournal(path, original_binding, False) as j:
        assert j.event_count == 1
        assert j.events[0]["kind"] == "objective_started"
        assert j.latest_checkpoint()["journal_sha256"] == j.head_sha256
        assert j.result() == {"status": ["pending-unknown"]}
    with pytest.raises(ResearchError, match="closed"):
        j.append("objective_finished", {})


def test_pending_intent_is_preserved_without_automatic_work_or_retry(tmp_path, binding):
    path = tmp_path / "trial"
    with TrialJournal(path, binding, True) as j:
        j.append("restart_started", {"ordinal": 2})
    before = (path / "events.jsonl").read_bytes()
    with TrialJournal(path, binding, False) as j:
        assert [event["kind"] for event in j.events] == ["restart_started"]
        assert j.latest_checkpoint() is None
    assert (path / "events.jsonl").read_bytes() == before


def test_append_is_fsynced_before_return_and_checkpoint_before_directory(tmp_path, binding, monkeypatch):
    path = tmp_path / "trial"
    actual = os.fsync
    calls = []

    def fsync(fd):
        calls.append((fd, stat.S_ISDIR(os.fstat(fd).st_mode)))
        actual(fd)

    with TrialJournal(path, binding, True) as j:
        monkeypatch.setattr(journal.os, "fsync", fsync)
        event = j.append("objective_started", {})
        assert calls == [(j._journal_fd, False)]
        assert json.loads((path / "events.jsonl").read_text()) == event
        calls.clear()
        j.save_checkpoint({"accepted": []})
        assert [directory for _, directory in calls] == [False, True]
        assert calls[-1][0] == j._checkpoints_fd
        calls.clear()
        j.publish_result({"status": "stopped"})
        assert [directory for _, directory in calls] == [False, True]
        assert calls[-1][0] == j._root_fd


def test_failed_fsync_poisons_live_session_and_preserves_unknown_intent(tmp_path, binding, monkeypatch):
    path = tmp_path / "trial"
    with TrialJournal(path, binding, True) as j:
        with monkeypatch.context() as patch:
            patch.setattr(journal.os, "fsync", lambda _: (_ for _ in ()).throw(OSError("fsync fault")))
            with pytest.raises(OSError, match="fsync fault"):
                j.append("objective_started", {"ordinal": 0})
        with pytest.raises(ResearchError, match="damaged"):
            j.append("objective_started", {"ordinal": 0})
    persisted = (path / "events.jsonl").read_bytes()
    with TrialJournal(path, binding, False) as j:
        assert j.event_count == 1  # The write survived; it never authorizes retry.
        assert j.events[0]["kind"] == "objective_started"
    assert (path / "events.jsonl").read_bytes() == persisted


def test_torn_write_is_retained_and_never_truncated(tmp_path, binding, monkeypatch):
    path = tmp_path / "trial"

    def torn(fd, raw):
        os.write(fd, raw[: len(raw) // 2])
        raise OSError("interrupted write")

    with TrialJournal(path, binding, True) as j:
        with monkeypatch.context() as patch:
            patch.setattr(journal, "_write_all", torn)
            with pytest.raises(OSError, match="interrupted"):
                j.append("objective_started", {})
        with pytest.raises(ResearchError, match="damaged"):
            j.save_checkpoint({})
    persisted = (path / "events.jsonl").read_bytes()
    assert persisted and not persisted.endswith(b"\n")
    with pytest.raises(ResearchError, match="truncated"):
        with TrialJournal(path, binding, False):
            pytest.fail("torn journal entered")
    assert (path / "events.jsonl").read_bytes() == persisted


def test_lock_covers_context_and_existing_directory_is_never_recreated(tmp_path, binding):
    path = tmp_path / "trial"
    with TrialJournal(path, binding, True):
        with pytest.raises(BlockingIOError):
            with TrialJournal(path, binding, False):
                pytest.fail("second writer acquired lock")
        with pytest.raises(FileExistsError):
            with TrialJournal(path, binding, True):
                pytest.fail("existing directory recreated")
    with TrialJournal(path, binding, False):
        pass


@pytest.mark.parametrize("mutation", ["truncated", "reorder", "payload", "index", "bool-index", "kind", "kind-list", "chain", "duplicate", "noncanonical", "nonfinite"])
def test_corrupt_event_replay_rejects_without_repair(tmp_path, binding, mutation):
    path = tmp_path / "trial"
    _seed(path, binding)
    file = path / "events.jsonl"
    lines = file.read_bytes().splitlines(keepends=True)
    event = json.loads(lines[0])
    if mutation == "truncated":
        lines[-1] = lines[-1][:-1]
    elif mutation == "reorder":
        lines.reverse()
    elif mutation == "duplicate":
        lines[0] = lines[0].replace(b'"index":0', b'"index":0,"index":0')
    elif mutation == "noncanonical":
        lines[0] = json.dumps(event, indent=2).encode() + b"\n"
    elif mutation == "nonfinite":
        lines[0] = lines[0].replace(b'"ordinal":0', b'"ordinal":NaN')
    else:
        if mutation == "payload":
            event["payload"]["ordinal"] = 900
        elif mutation == "index":
            event["index"] = 4
        elif mutation == "bool-index":
            event["index"] = False
        elif mutation == "kind":
            event["kind"] = "objective_retried"
        elif mutation == "kind-list":
            event["kind"] = []
        else:
            event["previous_sha256"] = digest("different-prefix")
        if mutation != "payload":
            _reseal(event, "event_sha256")
        lines[0] = (canonical(event) + "\n").encode()
    file.write_bytes(b"".join(lines))
    persisted = file.read_bytes()
    with pytest.raises(ResearchError):
        with TrialJournal(path, binding, False):
            pytest.fail("damaged journal entered")
    assert file.read_bytes() == persisted


@pytest.mark.parametrize("mutation", ["binding", "bool-value", "float-value", "extra-field", "digest"])
def test_meta_requires_exact_canonical_binding(tmp_path, binding, mutation):
    path = tmp_path / "trial"
    with TrialJournal(path, binding, True):
        pass
    file = path / "meta.json"
    meta = json.loads(file.read_text())
    if mutation == "binding":
        binding["solver"]["version"] = 4
    elif mutation == "bool-value":
        meta["binding"]["solver"]["version"] = True
        binding["solver"]["version"] = 1
        meta["binding_sha256"] = digest(binding)
    elif mutation == "float-value":
        meta["binding"]["solver"]["version"] = 3.0
    elif mutation == "extra-field":
        meta["unexpected"] = 1
    else:
        meta["binding_sha256"] = digest("changed")
    _put(file, meta)
    with pytest.raises(ResearchError, match="binding"):
        with TrialJournal(path, binding, False):
            pytest.fail("changed binding entered")


def test_checkpoint_zero_and_old_prefix_are_valid_immutable(tmp_path, binding):
    path = tmp_path / "trial"
    with TrialJournal(path, binding, True) as j:
        zero = j.save_checkpoint({"state": 0})
        assert zero["journal_count"] == 0 and zero["journal_sha256"] == digest(binding)
        assert j.save_checkpoint({"state": 0}) == zero
        with pytest.raises(ResearchError, match="immutable"):
            j.save_checkpoint({"state": 1})
        j.append("restart_started", {})
        j.append("restart_finished", {})
    with TrialJournal(path, binding, False) as j:
        assert j.latest_checkpoint() == zero
        assert j.event_count == 2  # Finish without checkpoint is replay's responsibility.
        j.save_checkpoint({"state": 2})
        j.publish_result({"done": True})
        j.publish_result({"done": True})
        with pytest.raises(ResearchError, match="immutable"):
            j.publish_result({"done": False})
        with pytest.raises(ResearchError, match="finalized"):
            j.append("restart_started", {})
        with pytest.raises(ResearchError, match="finalized"):
            j.save_checkpoint({"state": 3})


def test_checkpoint_digest_index_preserves_all_prefixes_and_is_detached(tmp_path, binding):
    path = tmp_path / "trial"
    with TrialJournal(path, binding, True) as j:
        assert j.checkpoint_digests == {}
        zero = j.save_checkpoint({"accepted": []})
        j.append("objective_started", {})
        one = j.save_checkpoint({"accepted": [0]})
        expected = {0: zero["checkpoint_sha256"], 1: one["checkpoint_sha256"]}
        detached = j.checkpoint_digests
        assert detached == expected
        detached[0] = digest("mutated")
        detached[9] = digest("invented")
        del detached[1]
        assert j.checkpoint_digests == expected
    with TrialJournal(path, binding, False) as j:
        assert j.checkpoint_digests == expected
        assert j.latest_checkpoint() == one
    with pytest.raises(ResearchError, match="closed"):
        _ = j.checkpoint_digests


@pytest.mark.parametrize("mutation", ["ahead", "different-prefix", "bool-count", "filename", "state", "partial"])
def test_checkpoint_prefix_and_content_integrity(tmp_path, binding, mutation):
    path = tmp_path / "trial"
    checkpoint = _seed(path, binding)
    file = path / "checkpoints" / "checkpoint-00002.json"
    if mutation == "partial":
        (file.parent / ".checkpoint-00003.json.partial").write_bytes(b"incomplete")
    elif mutation == "filename":
        file.rename(file.with_name("checkpoint-00001.json"))
    else:
        if mutation == "ahead":
            checkpoint["journal_count"] = 3
        elif mutation == "different-prefix":
            checkpoint["journal_sha256"] = digest("unrelated")
        elif mutation == "bool-count":
            checkpoint["journal_count"] = True
        else:
            checkpoint["state"]["accepted"].append(10)
        if mutation != "state":
            _reseal(checkpoint, "checkpoint_sha256")
        _put(file, checkpoint)
    with pytest.raises(ResearchError):
        with TrialJournal(path, binding, False):
            pytest.fail("bad checkpoint entered")


def test_result_must_bind_terminal_prefix_even_if_digest_is_resealed(tmp_path, binding):
    path = tmp_path / "trial"
    _seed(path, binding)
    with TrialJournal(path, binding, False) as j:
        j.publish_result({"done": True})
        earlier_head = j.events[0]["event_sha256"]
    file = path / "result.json"
    result = json.loads(file.read_text())
    result["journal_count"] = 1
    result["journal_sha256"] = earlier_head
    _reseal(result, "result_sha256")
    _put(file, result)
    with pytest.raises(ResearchError, match="terminal prefix"):
        with TrialJournal(path, binding, False):
            pytest.fail("nonterminal result entered")


@pytest.mark.parametrize("name", ["meta.json", "events.jsonl", ".journal.lock", "checkpoints", "checkpoints/checkpoint-00002.json"])
def test_symlink_rejected_at_every_storage_surface(tmp_path, binding, name):
    path = tmp_path / "trial"
    _seed(path, binding)
    file = path / name
    target = tmp_path / "target"
    file.rename(target)
    file.symlink_to(target, target_is_directory=target.is_dir())
    with pytest.raises((ResearchError, OSError)):
        with TrialJournal(path, binding, False):
            pytest.fail("symlink followed")


@pytest.mark.parametrize("position", ["parent", "leaf"])
def test_directory_alias_cannot_bypass_lock_or_binding(tmp_path, binding, position):
    path = tmp_path / "trial"
    _seed(path, binding)
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path if position == "parent" else path, target_is_directory=True)
    requested = alias / "trial" if position == "parent" else alias
    with pytest.raises(OSError):
        with TrialJournal(requested, binding, False):
            pytest.fail("directory alias followed")


@pytest.mark.parametrize("kind", ["hardlink", "fifo", "public-mode"])
def test_nonprivate_or_nonregular_event_file_rejected(tmp_path, binding, kind):
    path = tmp_path / "trial"
    _seed(path, binding)
    file = path / "events.jsonl"
    if kind == "hardlink":
        os.link(file, tmp_path / "hardlink")
    elif kind == "fifo":
        file.unlink()
        os.mkfifo(file, mode=0o600)
    else:
        file.chmod(0o644)
    with pytest.raises(ResearchError):
        with TrialJournal(path, binding, False):
            pytest.fail("unsafe event file entered")


@pytest.mark.parametrize("surface", ["events", "metadata", "parent", "checkpoint", "result"])
def test_live_mutation_detected_before_next_operation(tmp_path, binding, surface):
    path = tmp_path / "trial"
    with TrialJournal(path, binding, True) as j:
        j.append("objective_started", {})
        j.save_checkpoint({"state": 1})
        if surface == "events":
            with (path / "events.jsonl").open("ab") as file:
                file.write(b" ")
        elif surface == "metadata":
            with (path / "meta.json").open("ab") as file:
                file.write(b" ")
        elif surface == "parent":
            path.rename(tmp_path / "moved")
            path.symlink_to(tmp_path / "moved", target_is_directory=True)
        elif surface == "checkpoint":
            with (path / "checkpoints" / "checkpoint-00001.json").open("ab") as file:
                file.write(b" ")
        else:
            j.publish_result({"done": True})
            with (path / "result.json").open("ab") as file:
                file.write(b" ")
        with pytest.raises(ResearchError, match="changed|symlink"):
            j.result()


@pytest.mark.parametrize("surface", ["parent", "metadata", "extra-file"])
def test_mutation_during_replay_rejects_before_context_entry(tmp_path, binding, monkeypatch, surface):
    path = tmp_path / "trial"
    _seed(path, binding)
    replay = TrialJournal._replay

    def altered(self):
        replay(self)
        if surface == "parent":
            path.rename(tmp_path / "moved")
            path.symlink_to(tmp_path / "moved", target_is_directory=True)
        elif surface == "metadata":
            with (path / "meta.json").open("ab") as file:
                file.write(b" ")
        else:
            (path / "unexpected.partial").write_bytes(b"incomplete")

    monkeypatch.setattr(TrialJournal, "_replay", altered)
    with pytest.raises(ResearchError, match="changed|symlink"):
        with TrialJournal(path, binding, False):
            pytest.fail("storage changed during replay but context entered")


def test_append_and_latest_checkpoint_do_not_rescan_history(tmp_path, binding, monkeypatch):
    path = tmp_path / "trial"
    _seed(path, binding)

    def forbidden(*_):
        raise AssertionError("historical replay/read in append loop")

    with TrialJournal(path, binding, False) as j:
        monkeypatch.setattr(journal, "_read_file", forbidden)
        monkeypatch.setattr(journal, "_names", forbidden)
        monkeypatch.setattr(j, "_replay", forbidden)
        for ordinal in range(20):
            j.append("objective_started", {"ordinal": ordinal})
            j.save_checkpoint({"accepted": ordinal})
            j.append("objective_finished", {"ordinal": ordinal})
            assert j.latest_checkpoint()["state"] == {"accepted": ordinal}
        assert j.event_count == 42


def test_size_and_event_caps_are_enforced_before_writing(tmp_path, binding, monkeypatch):
    path = tmp_path / "trial"
    with TrialJournal(path, binding, True) as j:
        monkeypatch.setattr(journal, "MAX_RECORD_BYTES", 512)
        with pytest.raises(ResearchError, match="record capacity"):
            j.append("objective_started", {"padding": "x" * 513})
        assert j.event_count == 0 and (path / "events.jsonl").stat().st_size == 0
        j.append("objective_started", {})
        size = (path / "events.jsonl").stat().st_size
        with monkeypatch.context() as patch:
            patch.setattr(journal, "MAX_JOURNAL_BYTES", size)
            with pytest.raises(ResearchError, match="byte capacity"):
                j.append("objective_finished", {})
        monkeypatch.setattr(journal, "MAX_EVENTS", 1)
        with pytest.raises(ResearchError, match="event capacity"):
            j.append("objective_finished", {})
        assert (path / "events.jsonl").stat().st_size == size


@pytest.mark.parametrize("cap", ["MAX_RECORD_BYTES", "MAX_JOURNAL_BYTES", "MAX_EVENTS"])
def test_replay_is_bounded_by_record_file_and_count_caps(tmp_path, binding, monkeypatch, cap):
    path = tmp_path / "trial"
    _seed(path, binding)
    monkeypatch.setattr(journal, cap, 1)
    with pytest.raises(ResearchError):
        with TrialJournal(path, binding, False):
            pytest.fail("capacity exceeded journal entered")


@pytest.mark.parametrize("payload", [{"value": float("nan")}, {"value": float("inf")}, {"tuple": (1, 2)}, {3: "not-string-key"}, {"path": Path("x")}])
def test_noncanonical_payload_types_rejected(tmp_path, binding, payload):
    with TrialJournal(tmp_path / "trial", binding, True) as j:
        with pytest.raises(ResearchError):
            j.append("objective_started", payload)
        assert j.event_count == 0
