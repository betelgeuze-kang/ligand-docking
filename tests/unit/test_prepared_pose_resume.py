"""Durable restart, corruption and concurrency controls with actual CPU physics."""
from __future__ import annotations

import copy
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from betelgeuze_engine.product import prepared_rigid_poses as poses
from betelgeuze_engine.product import prepared_pose_journal as store
from tools.product import score_prepared_cross_interactions as consumer
from tests.unit.test_prepared_rigid_poses import _request, _pose


def evaluate(request, path, resume=False):
    return consumer.evaluate_request(request, checkpoint_dir=path, resume=resume)


def numerical_rows(report):
    rows = copy.deepcopy(report["rows"])
    for row in rows:
        row.pop("cost", None)
        row.get("pose_geometry_observation", {}).pop("cost", None)
        if "result" in row:
            row["result"].pop("cost", None)
    # Check the persisted JSON contract: the existing evaluator contains tuples,
    # which are JSON arrays on both uninterrupted and resumed runs. No numeric
    # values or tolerances are altered for this comparison.
    return json.dumps(rows, sort_keys=True, allow_nan=False)


def test_completed_resume_never_recomputes_and_keeps_failures(tmp_path, monkeypatch):
    request = _request(tmp_path)
    request["poses"] += [_pose("invalid", -4.0)]
    journal = tmp_path / "checkpoint"
    fresh = evaluate(request, journal)
    assert fresh["denominator"] == dict(requested=3, evaluated=2, failed=1, skipped=0)
    def forbidden(*_, **__):
        pytest.fail("committed row reached physics or preparation")
    monkeypatch.setattr(poses, "evaluate_prepared_cross_interaction", forbidden)
    monkeypatch.setattr(poses, "load_prepared_gromacs_components", forbidden)
    resumed = evaluate(request, journal, resume=True)
    assert numerical_rows(resumed) == numerical_rows(fresh)
    assert resumed["execution"] == fresh["execution"]
    assert resumed["denominator"] == fresh["denominator"]
    assert resumed["preparation_observation"]["successful_loads"] == 0
    assert resumed["preparation_observation"]["numerical_results_reused"] is True
    assert resumed["resume_observation"]["restored_rows"] == 3
    assert resumed["resume_observation"]["newly_completed_rows"] == 0
    assert resumed["resume_observation"]["attempt"] == 2
    assert resumed["scientifically_validated"] is resumed["customer_execution"] is False


def test_interrupt_after_commit_recovers_only_remaining_candidates(tmp_path, monkeypatch):
    request, journal = _request(tmp_path), tmp_path / "checkpoint"
    original = store.PoseJournal.commit
    def interrupted(self, row, shared, execution):
        original(self, row, shared, execution)
        raise KeyboardInterrupt("synthetic stop after durable commit")
    with monkeypatch.context() as patch:
        patch.setattr(store.PoseJournal, "commit", interrupted)
        with pytest.raises(KeyboardInterrupt):
            evaluate(request, journal)
    called = []
    original_score = poses.evaluate_prepared_cross_interaction
    def score(*a, **kw):
        called.append(1)
        return original_score(*a, **kw)
    monkeypatch.setattr(poses, "evaluate_prepared_cross_interaction", score)
    resumed = evaluate(request, journal, resume=True)
    assert len(called) == 1
    assert resumed["resume_observation"]["restored_rows"] == 1
    assert resumed["resume_observation"]["newly_completed_rows"] == 1
    continuous = consumer.evaluate_request(request)
    assert numerical_rows(resumed) == numerical_rows(continuous)
    assert resumed["denominator"] == continuous["denominator"]


def test_uncommitted_transaction_rolls_back_and_recomputes(tmp_path, monkeypatch):
    request, journal = _request(tmp_path), tmp_path / "checkpoint"
    original_set = store.PoseJournal._set
    def crash(self, key, value):
        if key == "completed_count":
            raise KeyboardInterrupt("interrupted within SQLite transaction")
        return original_set(self, key, value)
    with monkeypatch.context() as patch:
        patch.setattr(store.PoseJournal, "_set", crash)
        with pytest.raises(KeyboardInterrupt):
            evaluate(request, journal)
    with closing(sqlite3.connect(journal / "completion.sqlite3")) as db:
        assert db.execute("SELECT count(*) FROM poses").fetchone()[0] == 0
    resumed = evaluate(request, journal, resume=True)
    assert resumed["resume_observation"]["restored_rows"] == 0
    assert resumed["resume_observation"]["newly_completed_rows"] == 2


@pytest.mark.parametrize("change", ["pose", "order", "pocket", "partition", "reuse", "source_bytes", "runtime", "source_code"])
def test_changed_contract_is_rejected_without_rewriting_completion(tmp_path, monkeypatch, change):
    request, journal = _request(tmp_path), tmp_path / "checkpoint"
    evaluate(request, journal)
    before = hashlib.sha256((journal / "completion.sqlite3").read_bytes()).hexdigest()
    if change == "pose":
        request["poses"][0]["translation_angstrom"][0] = 0.1
    elif change == "order":
        request["poses"].reverse()
    elif change == "pocket":
        request["evaluation"]["pocket_radius_angstrom"] += 1
    elif change == "partition":
        request["execution"]["projection_partition"] = "spatial_median_v1"
    elif change == "reuse":
        request["execution"]["preparation_reuse"] = "none"
    elif change == "source_bytes":
        ref = next(store._source_refs(request["prepared_input"]))
        source = Path(ref["path"])
        source.write_bytes(source.read_bytes() + b"\n")
    else:
        binding = store._runtime_binding()
        binding["precision" if change == "runtime" else "sources"] = "different"
        monkeypatch.setattr(store, "_runtime_binding", lambda: binding)
    with pytest.raises(ValueError, match="checkpoint_request_input_runtime_mismatch"):
        evaluate(request, journal, resume=True)
    assert hashlib.sha256((journal / "completion.sqlite3").read_bytes()).hexdigest() == before


@pytest.mark.parametrize("mutation", ["row", "delete", "gap", "shared", "execution"])
def test_corrupt_checkpoint_is_not_silently_repaired(tmp_path, mutation):
    request, journal = _request(tmp_path), tmp_path / "checkpoint"
    evaluate(request, journal)
    with closing(sqlite3.connect(journal / "completion.sqlite3")) as db:
        if mutation == "row":
            db.execute("UPDATE poses SET payload='{}' WHERE ordinal=0")
        elif mutation == "delete":
            db.execute("DELETE FROM poses WHERE ordinal=1")
        elif mutation == "gap":
            db.execute("DELETE FROM poses WHERE ordinal=0")
        else:
            db.execute("UPDATE meta SET value='{}' WHERE key=?", (mutation,))
        db.commit()
    with pytest.raises(ValueError, match="checkpoint_"):
        evaluate(request, journal, resume=True)


def test_concurrent_process_cannot_reuse_same_active_request(tmp_path):
    request, journal = _request(tmp_path), tmp_path / "checkpoint"
    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps(request))
    with store.PoseJournal(journal, request):
        code = '''
import json, sys
from betelgeuze_engine.product.prepared_pose_journal import PoseJournal
try:
    with PoseJournal(sys.argv[1], json.loads(__import__("pathlib").Path(sys.argv[2]).read_text()), resume=True):
        raise RuntimeError('incorrectly acquired active journal')
except ValueError as error:
    assert str(error) == 'checkpoint_request_already_running', str(error)
'''
        proc = subprocess.run([sys.executable, "-B", "-c", code, str(journal), str(request_file)],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr


def test_real_process_death_then_cli_resume_matches_uninterrupted(tmp_path):
    request = _request(tmp_path)
    request["poses"] += [_pose("failed", -4.0)]
    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps(request))
    journal, ready = tmp_path / "checkpoint", tmp_path / "committed"
    child = '''
import os, sys
from pathlib import Path
from betelgeuze_engine.product.prepared_pose_journal import PoseJournal
from tools.product.score_prepared_cross_interactions import main
original=PoseJournal.commit
def die(self, row, shared, execution):
    original(self, row, shared, execution)
    Path(sys.argv[4]).write_text('committed')
    os._exit(75)
PoseJournal.commit=die
main(['--request',sys.argv[1],'--output',sys.argv[2],'--checkpoint-dir',sys.argv[3],'--output-format','compact'])
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    stopped_output = tmp_path / "stopped.json"
    proc = subprocess.run([sys.executable, "-B", "-c", child, str(request_file), str(stopped_output),
                           str(journal), str(ready)], env=env, capture_output=True, text=True)
    assert proc.returncode == 75, proc.stderr
    assert ready.exists() and not stopped_output.exists()
    def run(output, extra):
        result = subprocess.run([sys.executable, "-B", "-m", "tools.product.score_prepared_cross_interactions",
                                 "--request", str(request_file), "--output", str(output),
                                 "--output-format", "compact", *extra], env=env, capture_output=True, text=True)
        assert result.returncode == 2, result.stdout + result.stderr  # preserved physical failure
        return json.loads(output.read_text())
    resumed = run(tmp_path / "resumed.json", ["--checkpoint-dir", str(journal), "--resume"])
    continuous = run(tmp_path / "continuous.json", [])
    assert resumed["denominator"] == continuous["denominator"]
    assert numerical_rows(resumed) == numerical_rows(continuous)
    assert resumed["resume_observation"]["restored_rows"] == 1
    assert resumed["resume_observation"]["newly_completed_rows"] == 2


def test_duplicate_ids_remain_failed_after_resume(tmp_path):
    request = _request(tmp_path)
    request["poses"][1]["pose_id"] = request["poses"][0]["pose_id"]
    journal = tmp_path / "checkpoint"
    first = evaluate(request, journal)
    second = evaluate(request, journal, resume=True)
    assert first["execution"] == second["execution"] is None
    assert first["denominator"] == second["denominator"] == dict(requested=2, evaluated=0, failed=2, skipped=0)
    assert first["rows"] == second["rows"]


def test_all_physics_failures_preserve_execution_declaration(tmp_path):
    request = _request(tmp_path)
    request["poses"] = [_pose("outside", 100)]
    journal = tmp_path / "checkpoint"
    first = evaluate(request, journal)
    second = evaluate(request, journal, resume=True)
    assert first["execution"] == second["execution"] == request["execution"]
    assert first["rows"] == second["rows"]


@pytest.mark.parametrize("kind", ["existing", "missing", "symlink", "insecure", "hardlink_db"])
def test_checkpoint_path_safety(tmp_path, kind):
    request, directory = _request(tmp_path), tmp_path / "checkpoint"
    if kind == "missing":
        with pytest.raises(FileNotFoundError):
            evaluate(request, directory, resume=True)
        return
    evaluate(request, directory)
    if kind == "existing":
        with pytest.raises(FileExistsError):
            evaluate(request, directory)
        return
    if kind == "symlink":
        link = tmp_path / "alias"
        link.symlink_to(directory, target_is_directory=True)
        directory = link
    elif kind == "insecure":
        directory.chmod(0o755)
    else:
        (tmp_path / "db-alias").hardlink_to(directory / "completion.sqlite3")
    with pytest.raises((ValueError, OSError)):
        evaluate(request, directory, resume=True)
