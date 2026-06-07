from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_strict_blind_replacement_evidence_dropzones as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _intake_payload() -> dict:
    return {
        "summary": {
            "strict_blind_replacement_intake_status": "awaiting_strict_blind_replacement_intake",
            "intake_slot_count": 2,
        },
        "rows": [
            {
                "queue_rank": 1,
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "metric_profile": "TM,GDT_TS,CA_lDDT",
                "intake_csv": "casp17/historical_seed_strict_blind_replacement_intake/01/replacement_candidate_intake.csv",
            },
            {
                "queue_rank": 2,
                "required_benchmark_id": "hist_REQUIRED_COMPLEX_001",
                "required_target_id": "REQUIRED_COMPLEX_001",
                "scope": "complex",
                "metric_profile": "TM,DockQ,IPS",
                "intake_csv": "casp17/historical_seed_strict_blind_replacement_intake/02/replacement_candidate_intake.csv",
            },
        ],
    }


def _args(tmp_path: Path) -> list[str]:
    return [
        "--intake-json",
        str(tmp_path / "intake.json"),
        "--dropzone-dir",
        str(tmp_path / "dropzones"),
        "--out-json",
        str(tmp_path / "dropzones.json"),
        "--out-csv",
        str(tmp_path / "dropzones.csv"),
        "--out-md",
        str(tmp_path / "DROPZONES.md"),
    ]


def test_evidence_dropzones_expand_intake_rows_into_file_and_operator_requirements(tmp_path: Path) -> None:
    _write_json(tmp_path / "intake.json", _intake_payload())
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["strict_blind_replacement_evidence_dropzone_status"] == (
        "awaiting_strict_blind_evidence_files"
    )
    assert payload["summary"]["dropzone_count"] == 2
    assert payload["summary"]["ready_for_intake_patch_count"] == 0
    assert payload["summary"]["awaiting_file_count"] == 2
    assert payload["summary"]["file_required_count"] == 12
    assert payload["summary"]["file_present_count"] == 0
    assert payload["summary"]["file_missing_count"] == 12
    assert payload["summary"]["operator_value_required_count"] == 20
    assert payload["summary"]["patch_preview_count"] == 2

    folder = tmp_path / "dropzones" / "01_hist_required_monomer_001"
    assert (folder / "prediction").is_dir()
    assert (folder / "native").is_dir()
    assert (folder / "authority").is_dir()
    assert (folder / "no_leak").is_dir()
    assert (folder / "ablation").is_dir()
    assert (folder / "calibration").is_dir()
    patch_rows = _read_csv(folder / "replacement_intake_patch_preview.csv")
    assert len(patch_rows) == 16
    by_field = {row["field_name"]: row for row in patch_rows}
    assert by_field["prediction_pdb"]["source_status"] == "missing"
    assert by_field["prediction_pdb"]["source_path"].endswith("prediction/replacement_prediction.pdb")
    assert by_field["replacement_target_id"]["source_status"] == "operator_required"
    assert "Claim Boundary" in (tmp_path / "DROPZONES.md").read_text(encoding="utf-8")


def test_evidence_dropzones_report_ready_file_set_without_mutating_intake(tmp_path: Path) -> None:
    _write_json(tmp_path / "intake.json", {"summary": {}, "rows": [_intake_payload()["rows"][0]]})
    folder = tmp_path / "dropzones" / "01_hist_required_monomer_001"
    for relative in [
        "prediction/replacement_prediction.pdb",
        "native/replacement_native.pdb",
        "authority/native_authority.md",
        "no_leak/no_leak_evidence.md",
        "ablation/ablation_manifest.json",
        "calibration/calibration_values.json",
    ]:
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("operator supplied evidence\n", encoding="utf-8")
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["strict_blind_replacement_evidence_dropzone_status"] == (
        "strict_blind_evidence_files_ready_for_intake_patch"
    )
    assert payload["summary"]["ready_for_intake_patch_count"] == 1
    assert payload["summary"]["file_present_count"] == 6
    assert payload["summary"]["file_missing_count"] == 0
    assert payload["rows"][0]["dropzone_status"] == "ready_for_intake_patch_review"
    assert payload["rows"][0]["file_present_count"] == 6
    assert not (tmp_path / "casp17" / "historical_seed_strict_blind_replacement_intake").exists()


def test_evidence_dropzones_report_missing_intake_input(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_evidence_dropzone_status"] == "blocked_missing_input"
    assert "strict_blind_replacement_intake_json_missing" in payload["summary"]["input_blockers"]
