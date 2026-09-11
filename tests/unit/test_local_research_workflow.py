"""Real CPU consumers with new synthetic inputs; no protected/public datasets."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

import pytest

from betelgeuze_engine.product import local_research_workflow as workflow
from betelgeuze_engine.product import rocm_diagnostic as rocm
from tests.unit.test_prepared_rigid_poses import _request
from tests.unit.test_public_assay_selector_shadow import _checkpoint, _row


def request(tmp_path):
    return {"schema_version": workflow.SCHEMA, "backend": "cpu",
            "prepared_request": _request(tmp_path), "assay_shadow": None}


def selector(tmp_path, monkeypatch, rows):
    checkpoint, digest = _checkpoint(tmp_path, monkeypatch)
    path = tmp_path / "catalogue.csv"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {"ligand_csv": str(path), "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "checkpoint": str(checkpoint), "checkpoint_sha256": digest, "chunk_size": 1}


def physics(run, attempt):
    return json.loads((run / f"attempt-{attempt:06d}" / "physics.json").read_text())


def test_actual_physics_with_separate_streaming_shadow(tmp_path, monkeypatch):
    r = request(tmp_path)
    r["assay_shadow"] = selector(tmp_path, monkeypatch, [_row(), _row(smiles=""), _row()])
    before = copy.deepcopy(r)
    run = tmp_path / "run"
    result = workflow.run_workflow(r, run_dir=run)
    assert r == before
    assert result["exit_code"] == 2
    assert result["physics"]["denominator"] == dict(requested=2, evaluated=2, failed=0, skipped=0)
    assert result["assay_shadow"]["requested_rows"] == 3
    assert result["assay_shadow"]["evaluated_rows"] == 2
    sidecar = json.loads((run / "attempt-000001" / "assay-shadow.json").read_text())
    assert [row["row_index"] for row in sidecar["rows"]] == [0, 1, 2]
    assert sidecar["rows"][1]["predicted_negative_log10_molar_IC50"] is None
    assert result["combined_score"] is None
    assert result["same_prepared_or_assay_state_verified"] is False
    assert result["backend_executed"] == "cpu"
    for item in result["artifacts"].values():
        assert workflow._hash_file(run / "attempt-000001" / item["name"]) == item["sha256"]


def test_completed_resume_does_not_recompute_physics(tmp_path, monkeypatch):
    from betelgeuze_engine.product import prepared_rigid_poses as poses
    r = request(tmp_path)
    run = tmp_path / "run"
    a = workflow.run_workflow(r, run_dir=run)
    assert a["exit_code"] == 0
    def forbidden(*args, **kwargs):
        pytest.fail("completed physics was recomputed")
    monkeypatch.setattr(poses, "evaluate_prepared_cross_interaction", forbidden)
    b = workflow.run_workflow(r, run_dir=run, resume=True)
    assert b["exit_code"] == 0 and b["attempt"] == 2
    assert b["backend_executed"] is None
    assert b["physics"]["resume_observation"]["restored_rows"] == 2
    assert physics(run, 1)["rows"] == physics(run, 2)["rows"]
    assert b["physics"]["preparation_observation"]["attempts"] == 0
    assert (run / "attempt-000001" / "report.html").is_file()


def test_interrupted_second_pose_resumes_committed_first_pose(tmp_path, monkeypatch):
    from betelgeuze_engine.product import prepared_rigid_poses as poses
    r = request(tmp_path)
    real = poses.evaluate_prepared_cross_interaction
    calls = []
    def interrupt(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise KeyboardInterrupt("test interruption")
        return real(*args, **kwargs)
    monkeypatch.setattr(poses, "evaluate_prepared_cross_interaction", interrupt)
    run = tmp_path / "interrupted"
    with pytest.raises(KeyboardInterrupt):
        workflow.run_workflow(r, run_dir=run)
    assert json.loads((run / "attempt-000001/report.json").read_text())["status"] == "running"
    calls.clear()
    def counted(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)
    monkeypatch.setattr(poses, "evaluate_prepared_cross_interaction", counted)
    result = workflow.run_workflow(r, run_dir=run, resume=True)
    assert result["exit_code"] == 0 and len(calls) == 1
    monkeypatch.setattr(poses, "evaluate_prepared_cross_interaction", real)
    workflow.run_workflow(r, run_dir=tmp_path / "continuous")
    for left, right in zip(physics(run, 2)["rows"], physics(tmp_path / "continuous", 1)["rows"]):
        assert left["result"] == right["result"]
        assert left["evaluated_ligand_coordinates_angstrom"] == right["evaluated_ligand_coordinates_angstrom"]


@pytest.mark.parametrize("field", ["backend", "poses", "evaluation"])
def test_changed_request_is_not_a_resume(tmp_path, field):
    r = request(tmp_path)
    run = tmp_path / "run"
    workflow.run_workflow(r, run_dir=run)
    if field == "backend":
        r["backend"] = "hip_safe"
    elif field == "poses":
        r["prepared_request"]["poses"].reverse()
    else:
        r["prepared_request"]["evaluation"]["dielectric"] += 1
    with pytest.raises(ValueError, match="workflow_resume_contract_mismatch"):
        workflow.run_workflow(r, run_dir=run, resume=True)
    assert not (run / "attempt-000002").exists()


@pytest.mark.parametrize("backend", ["hip_safe", "hip_fast"])
def test_prepared_hip_request_never_silently_runs_cpu(tmp_path, monkeypatch, backend):
    r = request(tmp_path)
    r["backend"] = backend
    from tools.product import score_prepared_cross_interactions as evaluator
    monkeypatch.setattr(evaluator, "evaluate_request", lambda *a, **k: pytest.fail("CPU fallback"))
    result = workflow.run_workflow(r, run_dir=tmp_path / "run")
    assert result["status"] == "blocked_backend" and result["backend_executed"] is None
    assert result["physics"]["status"] == "not_run"
    assert result["rocm_observation"]["native_backend_qualified"] is False


def test_failed_shadow_does_not_discard_valid_physics(tmp_path, monkeypatch):
    r = request(tmp_path)
    r["assay_shadow"] = selector(tmp_path, monkeypatch, [_row()])
    Path(r["assay_shadow"]["checkpoint"]).write_bytes(b"changed checkpoint")
    result = workflow.run_workflow(r, run_dir=tmp_path / "run")
    assert result["physics"]["denominator"]["evaluated"] == 2
    assert result["assay_shadow"]["status"] == "failed"
    assert "changed checkpoint" not in json.dumps(result)
    assert result["exit_code"] == 2


def test_failed_pose_remains_failed_after_resume(tmp_path):
    r = request(tmp_path)
    r["prepared_request"]["poses"][1]["translation_angstrom"] = [-4., 0., 0.]
    run = tmp_path / "run"
    a = workflow.run_workflow(r, run_dir=run)
    b = workflow.run_workflow(r, run_dir=run, resume=True)
    assert a["exit_code"] == b["exit_code"] == 2
    assert b["physics"]["denominator"] == dict(requested=2, evaluated=1, failed=1, skipped=0)
    assert physics(run, 1)["rows"] == physics(run, 2)["rows"]


def test_new_cli_process_and_resume(tmp_path):
    r = request(tmp_path)
    path = tmp_path / "input.json"
    path.write_text(json.dumps(r))
    run = tmp_path / "run"
    command = [sys.executable, "-m", "betelgeuze_engine.product.local_research_workflow",
               "--request", str(path), "--run-dir", str(run)]
    for suffix in ([], ["--resume"]):
        proc = subprocess.run(command + suffix, capture_output=True, text=True, timeout=90)
        assert proc.returncode == 0, proc.stdout + proc.stderr
    assert physics(run, 1)["rows"] == physics(run, 2)["rows"]
    assert json.loads((run / "attempt-000002/report.json").read_text())["cost"]["peak_rss_scope"].startswith("process_lifetime")


def test_existing_run_is_not_overwritten(tmp_path):
    r = request(tmp_path)
    run = tmp_path / "run"
    workflow.run_workflow(r, run_dir=run)
    before = workflow._hash_file(run / "attempt-000001/report.json")
    with pytest.raises(FileExistsError):
        workflow.run_workflow(r, run_dir=run)
    assert workflow._hash_file(run / "attempt-000001/report.json") == before


@pytest.mark.parametrize("kind", ["run_symlink", "binding_symlink", "non_private"])
def test_run_path_checks(tmp_path, kind):
    r = request(tmp_path)
    run = tmp_path / "run"
    workflow.run_workflow(r, run_dir=run)
    if kind == "run_symlink":
        link = tmp_path / "link"
        link.symlink_to(run, target_is_directory=True)
        run = link
    elif kind == "binding_symlink":
        path = run / "request.json"
        outside = tmp_path / "copy.json"
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
    else:
        run.chmod(0o755)
    with pytest.raises((OSError, ValueError)):
        workflow.run_workflow(r, run_dir=run, resume=True)


def test_html_is_escaped_not_executable():
    report = dict(status="<script>alert(1)</script>", backend_requested="cpu", backend_executed="cpu")
    output = workflow._html_report(report)
    assert "<script>" not in output and "&lt;script&gt;" in output
    assert "default-src 'none'" in output


@pytest.mark.parametrize("patch", [{"unexpected": 1}, {"backend": "cuda"}, {"schema_version": "other"}])
def test_unknown_workflow_contract_rejected(tmp_path, patch):
    r = request(tmp_path)
    r.update(patch)
    with pytest.raises(ValueError):
        workflow.run_workflow(r, run_dir=tmp_path / "run")
    assert not (tmp_path / "run").exists()


@pytest.mark.parametrize("value", ["0", 0, 4097, True])
def test_invalid_chunk_size(tmp_path, monkeypatch, value):
    r = request(tmp_path)
    r["assay_shadow"] = selector(tmp_path, monkeypatch, [_row()])
    r["assay_shadow"]["chunk_size"] = value
    with pytest.raises(ValueError):
        workflow.run_workflow(r, run_dir=tmp_path / "run")


def test_no_probe_does_not_load_ml_runtime(monkeypatch):
    monkeypatch.setattr(rocm.importlib, "import_module", lambda *a: pytest.fail("unexpected Torch import"))
    result = rocm.diagnose_rocm()
    assert result["status"] == "not_probed" and result["device_count"] is None


def test_nvidia_or_cpu_torch_is_not_amd(monkeypatch):
    class Forbidden:
        def is_available(self):
            pytest.fail("non-HIP runtime must not execute CUDA")
    monkeypatch.setattr(rocm.importlib, "import_module", lambda *a: types.SimpleNamespace(
        version=types.SimpleNamespace(hip=None), cuda=Forbidden()))
    result = rocm.diagnose_rocm(probe=True)
    assert result["status"] == "unavailable_not_torch_hip_build"
    assert result["native_backend_qualified"] is False


def test_hip_build_without_device_is_unavailable(monkeypatch):
    monkeypatch.setattr(rocm.importlib, "import_module", lambda *a: types.SimpleNamespace(
        version=types.SimpleNamespace(hip="synthetic-test-version"),
        cuda=types.SimpleNamespace(is_available=lambda: False)))
    result = rocm.diagnose_rocm(probe=True)
    assert result["status"] == "unavailable_torch_hip_device"


def test_probe_failure_does_not_echo_private_exception(monkeypatch):
    def fail(*args):
        raise RuntimeError("/private/customer/model")
    monkeypatch.setattr(rocm.importlib, "import_module", fail)
    result = rocm.diagnose_rocm(probe=True)
    assert result["status"] == "probe_failed"
    assert "/private" not in json.dumps(result)


def test_probe_flag_must_be_boolean():
    with pytest.raises(ValueError):
        rocm.diagnose_rocm(probe="yes")


def test_diagnose_cli_is_lightweight_and_not_native_qualification():
    proc = subprocess.run([sys.executable, "-m", "betelgeuze_engine.product.local_research_workflow",
                           "--diagnose-only"], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["native_backend_qualified"] is False
    assert result["probe_backend"] is None


def test_request_json_duplicate_or_nonfinite_is_rejected(tmp_path, capsys):
    path = tmp_path / "bad.json"
    for contents in ('{"backend":"cpu","backend":"hip_safe"}', '{"x":NaN}'):
        path.write_text(contents)
        assert workflow.main(["--request", str(path), "--run-dir", str(tmp_path / "unused")]) == 2
        assert str(path) not in capsys.readouterr().out
        assert not (tmp_path / "unused").exists()
