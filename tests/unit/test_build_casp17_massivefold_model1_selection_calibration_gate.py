import json
from pathlib import Path

from tools.casp17 import build_casp17_massivefold_model1_selection_calibration_gate as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_builds_model1_selection_calibration_gate(tmp_path):
    ledger_json = tmp_path / "score_ledger.json"
    _write_json(
        ledger_json,
        {
            "summary": {
                "massivefold_critical_rerank_score_ledger_status": (
                    "massivefold_critical_rerank_score_ledger_ready_external_only"
                )
            },
            "rows": [
                {
                    "ledger_rank": 1,
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "risk_score": "64",
                    "risk_band": "calibrate_before_model1_freeze",
                    "rerank_action": "run_targeted_probe_then_freeze_model1_if_consistent",
                    "model1_filename": "r2350_model1.cif",
                    "model1_protocol": "woPaired",
                    "ledger_md": "ledger/r2350.md",
                },
                {
                    "ledger_rank": 2,
                    "target_group": "protein_complex",
                    "target_id": "H2312",
                    "risk_score": "48",
                    "risk_band": "critical_watch_with_targeted_probe",
                    "rerank_action": "keep_in_critical_batch_and_rescore_after_probe",
                    "model1_filename": "h2312_model1.pdb",
                    "model1_protocol": "afm_basic_v1",
                    "ledger_md": "ledger/h2312.md",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--score-ledger-json",
            str(ledger_json),
            "--out-dir",
            str(tmp_path / "gates"),
            "--out-json",
            str(tmp_path / "gates.json"),
            "--out-csv",
            str(tmp_path / "gates.csv"),
            "--out-md",
            str(tmp_path / "GATES.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_model1_selection_calibration_gate_status"] == (
        "massivefold_model1_selection_calibration_gate_ready_external_only"
    )
    assert summary["freeze_gate_status"] == "model1_freeze_blocked_by_calibration"
    assert summary["gate_count"] == 2
    assert summary["ready_gate_count"] == 2
    assert summary["hold_model1_freeze_count"] == 1
    assert summary["watch_probe_count"] == 1
    assert summary["probe_required_count"] == 2
    assert summary["freeze_ready_count"] == 0
    assert summary["first_gate_target_id"] == "R2350"
    assert summary["first_gate_decision"] == "hold_model1_freeze_probe_required"

    rows = payload["rows"]
    assert rows[0]["target_id"] == "R2350"
    assert rows[0]["probe_type"] == "top5_rerank_consistency_probe"
    assert rows[1]["model1_freeze_decision"] == "conditional_watch_probe_before_final_model1"
    assert (tmp_path / "gates" / "01_rna_hybrid_r2350" / "CALIBRATION_GATE.md").exists()
    assert "no-native" in (tmp_path / "GATES.md").read_text(encoding="utf-8")


def test_marks_partial_when_score_ledger_or_row_is_blocked(tmp_path):
    ledger_json = tmp_path / "score_ledger.json"
    _write_json(
        ledger_json,
        {
            "summary": {
                "massivefold_critical_rerank_score_ledger_status": (
                    "massivefold_critical_rerank_score_ledger_partial"
                )
            },
            "rows": [
                {
                    "ledger_rank": 1,
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "risk_score": "64",
                    "risk_band": "calibrate_before_model1_freeze",
                    "blockers": "source_score_blocked",
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--score-ledger-json",
            str(ledger_json),
            "--out-dir",
            str(tmp_path / "gates"),
            "--out-json",
            str(tmp_path / "gates.json"),
            "--out-csv",
            str(tmp_path / "gates.csv"),
            "--out-md",
            str(tmp_path / "GATES.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_model1_selection_calibration_gate_status"] == (
        "massivefold_model1_selection_calibration_gate_partial"
    )
    assert payload["summary"]["ready_gate_count"] == 0
    assert payload["summary"]["blocked_gate_count"] == 1
    assert payload["rows"][0]["gate_status"] == "blocked_model1_selection_gate"
