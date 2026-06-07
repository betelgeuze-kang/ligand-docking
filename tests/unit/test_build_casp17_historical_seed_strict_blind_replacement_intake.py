from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_strict_blind_replacement_intake as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _queue_payload() -> dict:
    return {
        "summary": {
            "strict_blind_replacement_queue_status": "strict_blind_replacement_queue_open",
            "scaffold_slot_count": 2,
            "requirement_field_count": 32,
        },
        "rows": [
            {
                "queue_rank": 1,
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "metric_profile": "TM,GDT_TS,CA_lDDT",
            },
            {
                "queue_rank": 2,
                "required_benchmark_id": "hist_REQUIRED_COMPLEX_001",
                "required_target_id": "REQUIRED_COMPLEX_001",
                "scope": "complex",
                "metric_profile": "TM,DockQ,IPS",
            },
        ],
    }


def _args(tmp_path: Path) -> list[str]:
    return [
        "--queue-json",
        str(tmp_path / "queue.json"),
        "--intake-dir",
        str(tmp_path / "intake"),
        "--out-json",
        str(tmp_path / "intake.json"),
        "--out-csv",
        str(tmp_path / "intake.csv"),
        "--out-md",
        str(tmp_path / "INTAKE.md"),
    ]


def test_strict_blind_replacement_intake_creates_fail_closed_templates(tmp_path: Path) -> None:
    _write_json(tmp_path / "queue.json", _queue_payload())
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["strict_blind_replacement_intake_status"] == (
        "awaiting_strict_blind_replacement_intake"
    )
    assert payload["summary"]["intake_slot_count"] == 2
    assert payload["summary"]["required_field_count"] == 32
    assert payload["summary"]["filled_field_count"] == 0
    assert payload["summary"]["missing_field_count"] == 32
    assert payload["summary"]["ready_for_preflight_count"] == 0
    assert payload["summary"]["blocked_or_awaiting_count"] == 2
    assert payload["summary"]["created_template_count"] == 2
    assert payload["summary"]["first_open_benchmark_id"] == "hist_REQUIRED_MONOMER_001"

    first_intake = tmp_path / "intake" / "01_hist_required_monomer_001" / "replacement_candidate_intake.csv"
    first_preflight = tmp_path / "intake" / "01_hist_required_monomer_001" / "replacement_candidate_preflight.csv"
    assert first_intake.is_file()
    assert first_preflight.is_file()
    intake_rows = _read_csv(first_intake)
    assert intake_rows[0]["replacement_target_id"] == "REQUIRED_CLOSED_HISTORICAL_TARGET_ID"
    preflight_rows = _read_csv(first_preflight)
    assert preflight_rows[0]["preflight_status"] == "awaiting_operator_input"
    assert "replacement_target_id_required" in preflight_rows[0]["blockers"]
    assert "prediction_generated_before_native_release_required" in preflight_rows[0]["blockers"]
    assert "Claim Boundary" in (tmp_path / "INTAKE.md").read_text(encoding="utf-8")


def test_strict_blind_replacement_intake_accepts_filled_pre_native_candidate(tmp_path: Path) -> None:
    _write_json(tmp_path / "queue.json", {"summary": {}, "rows": [_queue_payload()["rows"][0]]})
    intake_dir = tmp_path / "intake"
    folder = intake_dir / "01_hist_required_monomer_001"
    prediction = tmp_path / "prediction.pdb"
    native = tmp_path / "native.pdb"
    native_authority = tmp_path / "native_authority.md"
    no_leak = tmp_path / "no_leak.md"
    ablation = tmp_path / "ablation.json"
    calibration = tmp_path / "calibration.json"
    prediction.write_text(
        "ATOM      1  CA  ALA A   1       0.000   1.000   2.000  1.00 70.00           C  \n",
        encoding="utf-8",
    )
    native.write_text(
        "ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00 70.00           C  \n",
        encoding="utf-8",
    )
    for path in (native_authority, no_leak, ablation, calibration):
        path.write_text("operator evidence\n", encoding="utf-8")
    _write_csv(
        folder / "replacement_candidate_intake.csv",
        [
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "metric_profile": "TM,GDT_TS,CA_lDDT",
                "replacement_target_id": "HIST_CLOSED_001",
                "replacement_benchmark_id": "hist_CLOSED_001",
                "target_identity_non_current_historical": "true",
                "prediction_pdb": str(prediction),
                "native_pdb": str(native),
                "native_authority_ref": str(native_authority),
                "prediction_created_at": "2025-01-01",
                "native_release_date": "2025-02-01",
                "prediction_generated_before_native_release": "true",
                "no_leak_evidence_ref": str(no_leak),
                "public_template_or_native_used_for_prediction": "false",
                "other_team_model_used": "false",
                "post_release_information_used": "false",
                "ablation_manifest_ref": str(ablation),
                "calibration_values_ref": str(calibration),
                "operator_clearance": "clear",
                "operator": "tester",
                "notes": "filled strict-blind candidate",
            }
        ],
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["strict_blind_replacement_intake_status"] == (
        "strict_blind_replacement_intake_ready"
    )
    assert payload["summary"]["ready_for_preflight_count"] == 1
    assert payload["summary"]["filled_field_count"] == 16
    assert payload["summary"]["missing_field_count"] == 0
    assert payload["summary"]["preserved_template_count"] == 1
    assert payload["rows"][0]["preflight_status"] == "ready_for_strict_blind_preflight"
    assert payload["rows"][0]["blockers"] == ""


def test_strict_blind_replacement_intake_reports_missing_queue_input(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_intake_status"] == "blocked_missing_input"
    assert "strict_blind_replacement_queue_json_missing" in payload["summary"]["input_blockers"]
