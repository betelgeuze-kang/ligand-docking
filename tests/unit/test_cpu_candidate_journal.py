"""Disk commit boundaries, replay without compute, and hostile saved prefixes."""

import json
import pytest

from betelgeuze_product.cpu_refinement_v1_2.candidate_journal import open_journal
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest


def binding():
    return dict(
        schema_id="cpu_comparison_candidate_journal/1.0.0",
        request_sha256=digest("request"),
        implementation_sha256=digest("source"),
        environment_sha256=digest("environment"),
        candidate_keys=[digest(["baseline", 0]), digest(["refined", 0])],
    )


def validate(key, row):
    if row != {"key": key, "energy": -2.5}:
        raise ResearchError("semantic candidate mismatch")


def forbidden():
    raise AssertionError("committed candidate must not recompute")


def record(b, i):
    return {"key": b["candidate_keys"][i], "energy": -2.5}


def test_interrupted_replay_preserves_prefix_and_unknown_cost(tmp_path):
    b = binding()
    path = tmp_path / "journal"
    with open_journal(path, b, validate_record=validate) as j:
        assert j.evaluate(0, lambda: record(b, 0)) == record(b, 0)
        with pytest.raises(KeyboardInterrupt):
            j.evaluate(1, lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    first = (path / "candidate-00000-record-00000.json").read_bytes()
    with open_journal(path, b, validate_record=validate, resume=True) as j:
        assert j.unknown_attempts == 1
        assert j.evaluate(0, forbidden) == record(b, 0)
        assert j.evaluate(1, lambda: record(b, 1)) == record(b, 1)
        assert j.unknown_attempts == 1
    assert (path / "candidate-00000-record-00000.json").read_bytes() == first
    with pytest.raises(ResearchError, match="lock"):
        j.evaluate(0, forbidden)


@pytest.mark.parametrize(
    "field",
    ["request_sha256", "implementation_sha256", "environment_sha256", "candidate_keys"],
)
def test_changed_binding_rejects_before_compute(tmp_path, field):
    b = binding()
    path = tmp_path / "journal"
    with open_journal(path, b, validate_record=validate):
        pass
    b[field] = (
        list(reversed(b[field])) if field == "candidate_keys" else digest("changed")
    )
    with pytest.raises(ResearchError, match="changed"):
        with open_journal(path, b, validate_record=validate, resume=True):
            forbidden()


@pytest.mark.parametrize(
    "mutation", ["semantic", "index", "digest", "extra", "symlink"]
)
def test_corrupt_commit_rejects(tmp_path, mutation):
    b = binding()
    path = tmp_path / "journal"
    with open_journal(path, b, validate_record=validate) as j:
        j.evaluate(0, lambda: record(b, 0))
    f = path / "candidate-00000-record-00000.json"
    doc = json.loads(f.read_text())
    if mutation == "extra":
        (path / "candidate-99999-record-00000.json").write_text(f.read_text())
    elif mutation == "symlink":
        target = tmp_path / "target"
        target.write_bytes(f.read_bytes())
        f.unlink()
        f.symlink_to(target)
    else:
        if mutation == "semantic":
            doc["payload"]["record"]["energy"] = -99
        elif mutation == "index":
            doc["payload"]["index"] = False
        if mutation != "digest":
            doc["sha256"] = digest(doc["payload"])
        else:
            doc["sha256"] = "0" * 64
        f.write_text(json.dumps(doc))
    with pytest.raises((ValueError, OSError)):
        with open_journal(path, b, validate_record=validate, resume=True):
            forbidden()


def test_partial_commit_retained_and_not_reused(tmp_path):
    b = binding()
    path = tmp_path / "journal"
    with open_journal(path, b, validate_record=validate) as j:
        with pytest.raises(KeyboardInterrupt):
            j.evaluate(0, lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    partial = path / "candidate-00000-record-00000.json.partial"
    partial.write_bytes(b'{"incomplete":')
    with open_journal(path, b, validate_record=validate, resume=True) as j:
        j.evaluate(0, lambda: record(b, 0))
        assert j.unknown_attempts == 1
    assert partial.read_bytes() == b'{"incomplete":'


def test_concurrent_writer_and_out_of_order_rejected(tmp_path):
    b = binding()
    path = tmp_path / "journal"
    with open_journal(path, b, validate_record=validate) as j:
        with pytest.raises(BlockingIOError):
            with open_journal(path, b, validate_record=validate, resume=True):
                forbidden()
        with pytest.raises(ResearchError, match="order"):
            j.evaluate(1, forbidden)
        b["candidate_keys"].reverse()  # caller document must be detached
        j.evaluate(0, lambda: record(binding(), 0))
