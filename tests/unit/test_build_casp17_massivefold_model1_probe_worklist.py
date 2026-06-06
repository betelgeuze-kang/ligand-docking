import json
from pathlib import Path

from tools.casp17 import build_casp17_massivefold_model1_probe_worklist as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_builds_model1_probe_worklist(tmp_path):
    gate_json = tmp_path / "gate.json"
    _write_json(
        gate_json,
        {
            "summary": {
                "massivefold_model1_selection_calibration_gate_status": (
                    "massivefold_model1_selection_calibration_gate_ready_external_only"
                )
            },
            "rows": [
                {
                    "gate_rank": 1,
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "risk_score": "64",
                    "model1_freeze_decision": "hold_model1_freeze_probe_required",
                    "probe_required": "true",
                    "probe_type": "top5_rerank_consistency_probe",
                    "probe_exit_criterion": "model1 remains top candidate after rescore",
                    "model1_filename": "r2350_model1.cif",
                    "model1_protocol": "woPaired",
                    "calibration_gate_md": "gate/r2350.md",
                },
                {
                    "gate_rank": 2,
                    "target_group": "protein_complex",
                    "target_id": "H2312",
                    "risk_score": "48",
                    "model1_freeze_decision": "conditional_watch_probe_before_final_model1",
                    "probe_required": "true",
                    "probe_type": "lightweight_rescore_probe",
                    "probe_exit_criterion": "no new high-risk flag appears",
                    "model1_filename": "h2312_model1.pdb",
                    "model1_protocol": "afm_basic_v1",
                    "calibration_gate_md": "gate/h2312.md",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--calibration-gate-json",
            str(gate_json),
            "--out-dir",
            str(tmp_path / "worklist"),
            "--out-json",
            str(tmp_path / "worklist.json"),
            "--out-csv",
            str(tmp_path / "worklist.csv"),
            "--out-md",
            str(tmp_path / "WORKLIST.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_model1_probe_worklist_status"] == (
        "massivefold_model1_probe_worklist_ready_external_only"
    )
    assert summary["workitem_count"] == 2
    assert summary["ready_workitem_count"] == 2
    assert summary["top5_rerank_consistency_probe_count"] == 1
    assert summary["lightweight_rescore_probe_count"] == 1
    assert summary["priority1_workitem_count"] == 1
    assert summary["priority2_workitem_count"] == 1
    assert summary["first_workitem_target_id"] == "R2350"
    assert summary["freeze_unlock_policy"] == "freeze_after_probe_allowed_only_if_exit_criterion_passes"

    rows = payload["rows"]
    assert rows[0]["probe_priority"] == 1
    assert rows[0]["probe_type"] == "top5_rerank_consistency_probe"
    assert "low_confidence_fraction" in rows[0]["scoring_features"]
    assert rows[1]["probe_priority"] == 2
    assert (tmp_path / "worklist" / "01_rna_hybrid_r2350" / "PROBE_WORKITEM.md").exists()
    assert "no-native" in (tmp_path / "WORKLIST.md").read_text(encoding="utf-8")


def test_marks_partial_when_gate_or_row_is_blocked(tmp_path):
    gate_json = tmp_path / "gate.json"
    _write_json(
        gate_json,
        {
            "summary": {
                "massivefold_model1_selection_calibration_gate_status": (
                    "massivefold_model1_selection_calibration_gate_partial"
                )
            },
            "rows": [
                {
                    "gate_rank": 1,
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "risk_score": "64",
                    "model1_freeze_decision": "hold_model1_freeze_probe_required",
                    "probe_required": "true",
                    "probe_type": "top5_rerank_consistency_probe",
                    "blockers": "gate_blocked",
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--calibration-gate-json",
            str(gate_json),
            "--out-dir",
            str(tmp_path / "worklist"),
            "--out-json",
            str(tmp_path / "worklist.json"),
            "--out-csv",
            str(tmp_path / "worklist.csv"),
            "--out-md",
            str(tmp_path / "WORKLIST.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_model1_probe_worklist_status"] == (
        "massivefold_model1_probe_worklist_partial"
    )
    assert payload["summary"]["ready_workitem_count"] == 0
    assert payload["summary"]["blocked_workitem_count"] == 1
    assert payload["rows"][0]["probe_status"] == "probe_blocked"
