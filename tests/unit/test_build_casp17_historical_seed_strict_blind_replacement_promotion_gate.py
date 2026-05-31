from __future__ import annotations

import json
from pathlib import Path

from tools import build_casp17_historical_seed_strict_blind_replacement_promotion_gate as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _intake_row(rank: int, benchmark: str, *, ready: bool) -> dict:
    return {
        "queue_rank": rank,
        "required_benchmark_id": benchmark,
        "required_target_id": benchmark.replace("hist_", "").upper(),
        "scope": "monomer" if "MONOMER" in benchmark else "complex",
        "metric_profile": "TM,GDT_TS,CA_lDDT",
        "preflight_status": "ready_for_strict_blind_preflight" if ready else "awaiting_operator_input",
        "filled_field_count": 16 if ready else 0,
        "missing_field_count": 0 if ready else 16,
    }


def _file_rows(benchmark: str, *, status: str) -> list[dict]:
    return [
        {
            "queue_rank": 1,
            "required_benchmark_id": benchmark,
            "field_name": field,
            "field_kind": "file",
            "import_status": status,
        }
        for field in [
            "prediction_pdb",
            "native_pdb",
            "native_authority_ref",
            "no_leak_evidence_ref",
            "ablation_manifest_ref",
            "calibration_values_ref",
        ]
    ]


def _operator_rows(benchmark: str, *, status: str) -> list[dict]:
    return [
        {
            "queue_rank": 1,
            "required_benchmark_id": benchmark,
            "field_name": f"operator_field_{index}",
            "gate_status": status,
        }
        for index in range(10)
    ]


def _args(tmp_path: Path) -> list[str]:
    return [
        "--intake-json",
        str(tmp_path / "intake.json"),
        "--evidence-import-gate-json",
        str(tmp_path / "file_gate.json"),
        "--operator-value-gate-json",
        str(tmp_path / "operator_gate.json"),
        "--gate-dir",
        str(tmp_path / "promotion"),
        "--out-json",
        str(tmp_path / "promotion.json"),
        "--out-csv",
        str(tmp_path / "promotion.csv"),
        "--out-md",
        str(tmp_path / "PROMOTION.md"),
    ]


def test_promotion_gate_marks_only_complete_slots_ready(tmp_path: Path) -> None:
    ready_benchmark = "hist_REQUIRED_MONOMER_001"
    blocked_benchmark = "hist_REQUIRED_COMPLEX_001"
    _write_json(
        tmp_path / "intake.json",
        {
            "summary": {"strict_blind_replacement_intake_status": "partial"},
            "rows": [
                _intake_row(1, ready_benchmark, ready=True),
                _intake_row(2, blocked_benchmark, ready=False),
            ],
        },
    )
    _write_json(
        tmp_path / "file_gate.json",
        {
            "summary": {"strict_blind_replacement_evidence_import_gate_status": "partial"},
            "rows": _file_rows(ready_benchmark, status="already_applied")
            + _file_rows(blocked_benchmark, status="awaiting_file"),
        },
    )
    _write_json(
        tmp_path / "operator_gate.json",
        {
            "summary": {"strict_blind_replacement_operator_value_gate_status": "partial"},
            "rows": _operator_rows(ready_benchmark, status="already_applied")
            + _operator_rows(blocked_benchmark, status="awaiting_operator_value"),
        },
    )

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["strict_blind_replacement_promotion_gate_status"] == (
        "awaiting_strict_blind_replacement_promotion"
    )
    assert payload["summary"]["slot_count"] == 2
    assert payload["summary"]["ready_for_competitive_proof_count"] == 1
    assert payload["summary"]["awaiting_file_evidence_count"] == 1
    assert payload["summary"]["awaiting_operator_values_count"] == 1
    assert payload["summary"]["awaiting_intake_preflight_count"] == 1
    assert payload["summary"]["file_awaiting_action_count"] == 6
    assert payload["summary"]["operator_awaiting_action_count"] == 10
    assert payload["summary"]["first_open_phase"] == "file_evidence"
    by_id = {row["required_benchmark_id"]: row for row in payload["rows"]}
    assert by_id[ready_benchmark]["promotion_status"] == "ready_for_competitive_proof"
    assert by_id[ready_benchmark]["ready_for_competitive_proof"] == "true"
    assert by_id[blocked_benchmark]["promotion_status"] == "awaiting_file_evidence"
    assert "file_evidence_missing:6" in by_id[blocked_benchmark]["blockers"]
    assert "operator_values_missing:10" in by_id[blocked_benchmark]["blockers"]
    assert (tmp_path / "promotion" / "01_hist_required_monomer_001" / "PROMOTION_GATE.md").is_file()
    assert "Claim Boundary" in (tmp_path / "PROMOTION.md").read_text(encoding="utf-8")


def test_promotion_gate_reports_ready_apply_before_intake_ready(tmp_path: Path) -> None:
    benchmark = "hist_REQUIRED_MONOMER_001"
    _write_json(
        tmp_path / "intake.json",
        {"summary": {}, "rows": [_intake_row(1, benchmark, ready=False)]},
    )
    _write_json(
        tmp_path / "file_gate.json",
        {"summary": {}, "rows": _file_rows(benchmark, status="ready_to_apply")},
    )
    _write_json(
        tmp_path / "operator_gate.json",
        {"summary": {}, "rows": _operator_rows(benchmark, status="ready_to_apply")},
    )

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["rows"][0]["promotion_status"] == "awaiting_apply"
    assert "file_import_apply_required:6" in payload["rows"][0]["blockers"]
    assert "operator_value_apply_required:10" in payload["rows"][0]["blockers"]


def test_promotion_gate_reports_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_promotion_gate_status"] == "blocked_missing_input"
    assert "strict_blind_replacement_intake_json_missing" in payload["summary"]["input_blockers"]
