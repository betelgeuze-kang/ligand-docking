from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_strict_blind_replacement_evidence_action_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "queue_rank",
                "required_benchmark_id",
                "field_name",
                "field_kind",
                "recommended_value",
                "source_status",
                "source_path",
                "destination_intake_csv",
                "operator_action",
                "notes",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _patch_rows(tmp_path: Path, benchmark: str, *, present: bool) -> list[dict[str, str]]:
    files = {
        "prediction_pdb": tmp_path / "prediction" / "replacement_prediction.pdb",
        "native_pdb": tmp_path / "native" / "replacement_native.pdb",
        "native_authority_ref": tmp_path / "authority" / "native_authority.md",
        "no_leak_evidence_ref": tmp_path / "no_leak" / "no_leak_evidence.md",
        "ablation_manifest_ref": tmp_path / "ablation" / "ablation_manifest.json",
        "calibration_values_ref": tmp_path / "calibration" / "calibration_values.json",
    }
    if present:
        for path in files.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("present\n", encoding="utf-8")
    return [
        {
            "queue_rank": "1",
            "required_benchmark_id": benchmark,
            "field_name": field,
            "field_kind": "file",
            "recommended_value": str(path) if present else "",
            "source_status": "present" if present else "missing",
            "source_path": str(path),
            "destination_intake_csv": str(tmp_path / "replacement_candidate_intake.csv"),
            "operator_action": "review",
            "notes": "test",
        }
        for field, path in files.items()
    ]


def _dropzone_payload(patch_csv: Path, benchmark: str = "hist_REQUIRED_MONOMER_001") -> dict:
    return {
        "summary": {"strict_blind_replacement_evidence_dropzone_status": "partial"},
        "rows": [
            {
                "queue_rank": 1,
                "required_benchmark_id": benchmark,
                "required_target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "dropzone_folder": str(patch_csv.parent),
                "patch_preview_csv": str(patch_csv),
            }
        ],
    }


def _quality_payload(*, blocker: str = "", status: str = "awaiting_evidence_files") -> dict:
    return {
        "summary": {"strict_blind_replacement_evidence_quality_audit_status": status},
        "rows": [
            {
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "quality_status": status,
                "blockers": blocker,
            }
        ],
    }


def _args(tmp_path: Path) -> list[str]:
    return [
        "--dropzones-json",
        str(tmp_path / "dropzones.json"),
        "--quality-json",
        str(tmp_path / "quality.json"),
        "--out-json",
        str(tmp_path / "actions.json"),
        "--out-csv",
        str(tmp_path / "actions.csv"),
        "--out-md",
        str(tmp_path / "ACTIONS.md"),
    ]


def test_action_board_expands_missing_dropzone_files(tmp_path: Path) -> None:
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    _write_csv(patch_csv, _patch_rows(tmp_path / "dropzone", "hist_REQUIRED_MONOMER_001", present=False))
    _write_json(tmp_path / "dropzones.json", _dropzone_payload(patch_csv))
    _write_json(tmp_path / "quality.json", _quality_payload())

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_replacement_evidence_action_board_status"] == (
        "awaiting_strict_blind_evidence_actions"
    )
    assert summary["action_count"] == 6
    assert summary["open_missing_file_count"] == 6
    assert summary["prediction_pdb_missing_count"] == 1
    assert summary["first_open_action_id"] == "strict_blind_evidence_001"
    assert summary["first_open_field"] == "prediction_pdb"
    assert payload["rows"][0]["action_status"] == "open_missing_file"
    assert (tmp_path / "actions.csv").is_file()
    assert "Claim Boundary" in (tmp_path / "ACTIONS.md").read_text(encoding="utf-8")


def test_action_board_marks_present_files_ready(tmp_path: Path) -> None:
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    _write_csv(patch_csv, _patch_rows(tmp_path / "dropzone", "hist_REQUIRED_MONOMER_001", present=True))
    _write_json(tmp_path / "dropzones.json", _dropzone_payload(patch_csv))
    _write_json(tmp_path / "quality.json", _quality_payload(status="ready_for_operator_quality_review"))

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_evidence_action_board_status"] == (
        "strict_blind_evidence_actions_ready_for_quality_audit"
    )
    assert payload["summary"]["ready_for_quality_audit_count"] == 6
    assert payload["summary"]["open_missing_file_count"] == 0
    assert {row["action_status"] for row in payload["rows"]} == {"ready_for_quality_audit"}


def test_action_board_blocks_quality_failures(tmp_path: Path) -> None:
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    _write_csv(patch_csv, _patch_rows(tmp_path / "dropzone", "hist_REQUIRED_MONOMER_001", present=True))
    _write_json(tmp_path / "dropzones.json", _dropzone_payload(patch_csv))
    _write_json(
        tmp_path / "quality.json",
        _quality_payload(blocker="prediction_pdb:pdb_has_no_protein_atoms", status="blocked_evidence_quality"),
    )

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_evidence_action_board_status"] == (
        "blocked_evidence_action_review"
    )
    assert payload["summary"]["blocked_count"] == 1
    assert payload["rows"][0]["action_status"] == "blocked_quality_review"
    assert payload["rows"][0]["quality_blocker"] == "pdb_has_no_protein_atoms"
