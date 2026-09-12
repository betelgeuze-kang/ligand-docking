"""Empty catalogues are observed no-ops, never successful model execution.

Uses real streaming and CPU workflow consumers with fresh synthetic inputs only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from betelgeuze_product import local_research_workflow as workflow
from tests.unit.test_local_research_workflow import request, selector, physics
from tests.unit.test_public_assay_selector_shadow import _row


# A successfully read catalogue with no data rows is a no-op, not inference.
def _empty_catalogue(tmp_path, monkeypatch, kind):
    config = selector(tmp_path, monkeypatch, [_row()])
    path = Path(config["ligand_csv"])
    header = path.read_bytes().splitlines(keepends=True)[0]
    variants = {
        "empty": b"",
        "header": header,
        "wrong_header": b"unrelated_column\n",
        "duplicate_header": b"smiles,smiles\n",
        "bom_only": b"\xef\xbb\xbf",
        "bom_header": b"\xef\xbb\xbf" + header,
    }
    path.write_bytes(variants[kind])
    config["input_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return config


@pytest.mark.parametrize("kind", ["empty", "header", "wrong_header", "duplicate_header", "bom_only", "bom_header"])
@pytest.mark.parametrize("chunk_size", [1, 256])
def test_zero_row_catalogue_is_not_successful_inference(tmp_path, monkeypatch, kind, chunk_size):
    from betelgeuze_engine.product import public_assay_streaming as streaming
    config = _empty_catalogue(tmp_path, monkeypatch, kind)
    output = tmp_path / "shadow.json"
    result = streaming.run_pre_docking_shadow(
        ligand_csv=config["ligand_csv"], ligand_sdf="", docking_request_json="",
        resume_stage3_only=False, checkpoint=config["checkpoint"],
        checkpoint_sha256=config["checkpoint_sha256"], output_json=str(output), chunk_size=chunk_size)
    saved = json.loads(output.read_text())
    for payload in (result, saved):
        assert payload["status"] == "not_evaluated"
        assert payload["reason"] == "no_csv_data_rows"
        assert payload["requested_rows"] == payload["evaluated_rows"] == payload["unsupported_rows"] == 0
        assert payload["input_sha256"] == config["input_sha256"]
    assert result["sidecar_status"] == "written"
    assert saved["rows"] == []


@pytest.mark.parametrize("kind", ["empty", "header", "bom_header"])
def test_empty_shadow_preserves_physics_and_resume_without_false_success(tmp_path, monkeypatch, kind):
    from betelgeuze_product.local_research_verify import verify_run
    from betelgeuze_engine.product import prepared_rigid_poses as poses
    r, run = request(tmp_path), tmp_path / "run"
    r["assay_shadow"] = _empty_catalogue(tmp_path, monkeypatch, kind)
    first = workflow.run_workflow(r, run_dir=run)
    assert first["status"] == "partial_or_failed" and first["exit_code"] == 2
    assert first["physics"]["denominator"] == dict(requested=2, evaluated=2, failed=0, skipped=0)
    assert first["assay_shadow"]["status"] == "not_evaluated"
    assert first["assay_shadow"]["reason"] == "no_csv_data_rows"
    assert first["backend_executed"] == "cpu"
    assert first["model_promoted"] is False and first["combined_score"] is None
    def forbidden(*args, **kwargs):
        pytest.fail("completed physics was recomputed")
    monkeypatch.setattr(poses, "evaluate_prepared_cross_interaction", forbidden)
    second = workflow.run_workflow(r, run_dir=run, resume=True)
    assert second["status"] == "partial_or_failed" and second["exit_code"] == 2
    assert second["backend_executed"] is None
    assert second["physics"]["resume_observation"]["restored_rows"] == 2
    assert physics(run, 1)["rows"] == physics(run, 2)["rows"]
    checked = verify_run(run)
    assert checked["status"] == "intact" and checked["workflow_exit_code"] == 2
    assert checked["execution_performed"] is False
    assert "no_csv_data_rows" in (run / "attempt-000002/report.html").read_text()


def test_empty_catalogue_keeps_model_failure_and_known_zero_denominator(tmp_path, monkeypatch):
    from betelgeuze_engine.product import public_assay_streaming as streaming
    config = _empty_catalogue(tmp_path, monkeypatch, "header")
    Path(config["checkpoint"]).unlink()
    output = tmp_path / "no-model.json"
    result = streaming.run_pre_docking_shadow(
        ligand_csv=config["ligand_csv"], ligand_sdf="", docking_request_json="",
        resume_stage3_only=False, checkpoint=config["checkpoint"],
        checkpoint_sha256=config["checkpoint_sha256"], output_json=str(output))
    assert result["status"] == "not_evaluated"
    assert result["reason"].startswith("model_unavailable:")
    assert result["requested_rows"] == result["evaluated_rows"] == result["unsupported_rows"] == 0
    assert json.loads(output.read_text())["rows"] == []


def test_changed_empty_source_is_unknown_not_verified_zero(tmp_path, monkeypatch):
    from betelgeuze_engine.product import public_assay_streaming as streaming
    from betelgeuze_engine.product import public_assay_selector_shadow as owner
    config = _empty_catalogue(tmp_path, monkeypatch, "empty")
    real = owner.load_public_assay_selector
    def changed(*args, **kwargs):
        model = real(*args, **kwargs)
        Path(config["ligand_csv"]).write_text("changed_after_snapshot\n")
        return model
    monkeypatch.setattr(owner, "load_public_assay_selector", changed)
    output = tmp_path / "changed.json"
    result = streaming.run_pre_docking_shadow(
        ligand_csv=config["ligand_csv"], ligand_sdf="", docking_request_json="",
        resume_stage3_only=False, checkpoint=config["checkpoint"],
        checkpoint_sha256=config["checkpoint_sha256"], output_json=str(output))
    assert result["status"] == "not_evaluated" and result["requested_rows"] is None
    assert result["unsupported_rows"] is None
    assert json.loads(output.read_text())["rows"] == []


def test_nonempty_unsupported_rows_are_not_discarded_as_empty(tmp_path, monkeypatch):
    from betelgeuze_engine.product import public_assay_streaming as streaming
    config = selector(tmp_path, monkeypatch, [_row(smiles=""), _row(endpoint="Kd")])
    output = tmp_path / "unsupported.json"
    result = streaming.run_pre_docking_shadow(
        ligand_csv=config["ligand_csv"], ligand_sdf="", docking_request_json="",
        resume_stage3_only=False, checkpoint=config["checkpoint"],
        checkpoint_sha256=config["checkpoint_sha256"], output_json=str(output), chunk_size=1)
    assert result["status"] == "completed"  # enumeration completed; not an overall success
    assert result["requested_rows"] == result["unsupported_rows"] == 2
    assert result["evaluated_rows"] == 0
    assert [row["row_index"] for row in json.loads(output.read_text())["rows"]] == [0, 1]


def test_writer_does_not_publish_success_for_zero_row_completed_shadow(tmp_path, monkeypatch):
    # Invalid producer output is rejected before finalization. This does not
    # modify or reseal any saved receipt.
    r, run = request(tmp_path), tmp_path / "run"
    r["assay_shadow"] = selector(tmp_path, monkeypatch, [_row()])
    original = workflow._shadow_status
    def invalid(*args, **kwargs):
        result = original(*args, **kwargs)
        result.update(status="completed", requested_rows=0, evaluated_rows=0, unsupported_rows=0)
        return result
    monkeypatch.setattr(workflow, "_shadow_status", invalid)
    with pytest.raises(ValueError, match="empty_completed_shadow"):
        workflow.run_workflow(r, run_dir=run)
    assert not (run / "attempt-000001/complete.json").exists()
    assert json.loads((run / "attempt-000001/report.json").read_text())["status"] == "running"


def test_shadow_summary_does_not_copy_untrusted_reason_text(tmp_path, monkeypatch):
    from betelgeuze_engine.product import public_assay_streaming as streaming
    config = selector(tmp_path, monkeypatch, [_row()])
    def failure(**kwargs):
        return dict(status="not_evaluated", requested_rows=None, evaluated_rows=0,
                    unsupported_rows=None, sidecar_status="failed", input_sha256=config["input_sha256"],
                    reason="private-input-path-and-model-details")
    monkeypatch.setattr(streaming, "run_pre_docking_shadow", failure)
    result = workflow._shadow_status(config, tmp_path / "unused.json")
    assert "private-input-path" not in json.dumps(result)
