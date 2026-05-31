from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_strict_blind_replacement_evidence_quality_audit as mod


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


def _pdb(path: Path, *, residue: str = "ALA", x: float = 1.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"ATOM      1  CA  {residue} A   1       {x:8.3f}{2.0:8.3f}{3.0:8.3f}  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _patch_rows(tmp_path: Path, benchmark: str, *, complete: bool) -> list[dict[str, str]]:
    files = {
        "prediction_pdb": tmp_path / "prediction" / "replacement_prediction.pdb",
        "native_pdb": tmp_path / "native" / "replacement_native.pdb",
        "native_authority_ref": tmp_path / "authority" / "native_authority.md",
        "no_leak_evidence_ref": tmp_path / "no_leak" / "no_leak_evidence.md",
        "ablation_manifest_ref": tmp_path / "ablation" / "ablation_manifest.json",
        "calibration_values_ref": tmp_path / "calibration" / "calibration_values.json",
    }
    if complete:
        _pdb(files["prediction_pdb"], residue="ALA", x=1.0)
        _pdb(files["native_pdb"], residue="GLY", x=4.0)
        files["native_authority_ref"].parent.mkdir(parents=True, exist_ok=True)
        files["native_authority_ref"].write_text("authoritative native source for HIST_READY", encoding="utf-8")
        files["no_leak_evidence_ref"].parent.mkdir(parents=True, exist_ok=True)
        files["no_leak_evidence_ref"].write_text("independent no leak evidence for HIST_READY", encoding="utf-8")
        files["ablation_manifest_ref"].parent.mkdir(parents=True, exist_ok=True)
        files["ablation_manifest_ref"].write_text('{"layers":["recursive"]}\n', encoding="utf-8")
        files["calibration_values_ref"].parent.mkdir(parents=True, exist_ok=True)
        files["calibration_values_ref"].write_text('{"selected_model_rank":1}\n', encoding="utf-8")
    return [
        {
            "queue_rank": "1",
            "required_benchmark_id": benchmark,
            "field_name": field,
            "field_kind": "file",
            "recommended_value": str(path) if complete else "",
            "source_status": "present" if complete else "missing",
            "source_path": str(path),
            "destination_intake_csv": str(tmp_path / "replacement_candidate_intake.csv"),
            "operator_action": "review",
            "notes": "test",
        }
        for field, path in files.items()
    ]


def _args(tmp_path: Path) -> list[str]:
    return [
        "--dropzones-json",
        str(tmp_path / "dropzones.json"),
        "--audit-dir",
        str(tmp_path / "audit"),
        "--out-json",
        str(tmp_path / "quality.json"),
        "--out-csv",
        str(tmp_path / "quality.csv"),
        "--out-md",
        str(tmp_path / "QUALITY.md"),
    ]


def test_quality_audit_marks_complete_distinct_evidence_ready(tmp_path: Path) -> None:
    benchmark = "hist_REQUIRED_MONOMER_001"
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    _write_csv(patch_csv, _patch_rows(tmp_path / "dropzone", benchmark, complete=True))
    _write_json(
        tmp_path / "dropzones.json",
        {
            "summary": {"strict_blind_replacement_evidence_dropzones_status": "ready"},
            "rows": [
                {
                    "queue_rank": 1,
                    "required_benchmark_id": benchmark,
                    "required_target_id": "HIST_READY",
                    "scope": "monomer",
                    "patch_preview_csv": str(patch_csv),
                }
            ],
        },
    )

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))
    mod.write_outputs(mod.parse_args(_args(tmp_path)), payload)

    assert payload["summary"]["strict_blind_replacement_evidence_quality_audit_status"] == (
        "strict_blind_evidence_quality_ready_for_operator_review"
    )
    assert payload["summary"]["ready_for_quality_review_count"] == 1
    assert payload["summary"]["prediction_native_distinct_count"] == 1
    row = payload["rows"][0]
    assert row["quality_status"] == "ready_for_operator_quality_review"
    assert row["file_present_count"] == 6
    assert row["pdb_valid_count"] == 2
    assert row["supporting_valid_count"] == 4
    assert row["prediction_native_relation"] == "distinct_sha256_pass"
    assert (tmp_path / "audit" / "01_hist_required_monomer_001" / "QUALITY_AUDIT.md").is_file()
    assert "Claim Boundary" in (tmp_path / "QUALITY.md").read_text(encoding="utf-8")


def test_quality_audit_reports_missing_files(tmp_path: Path) -> None:
    benchmark = "hist_REQUIRED_MONOMER_001"
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    _write_csv(patch_csv, _patch_rows(tmp_path / "dropzone", benchmark, complete=False))
    _write_json(
        tmp_path / "dropzones.json",
        {
            "summary": {},
            "rows": [
                {
                    "queue_rank": 1,
                    "required_benchmark_id": benchmark,
                    "required_target_id": "HIST_MISSING",
                    "scope": "monomer",
                    "patch_preview_csv": str(patch_csv),
                }
            ],
        },
    )

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_evidence_quality_audit_status"] == (
        "awaiting_strict_blind_evidence_quality_files"
    )
    assert payload["summary"]["awaiting_evidence_files_count"] == 1
    assert payload["summary"]["file_missing_count"] == 6
    assert payload["rows"][0]["quality_status"] == "awaiting_evidence_files"
    assert "prediction_pdb:file_missing" in payload["rows"][0]["blockers"]


def test_quality_audit_blocks_identical_prediction_native(tmp_path: Path) -> None:
    benchmark = "hist_REQUIRED_MONOMER_001"
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    rows = _patch_rows(tmp_path / "dropzone", benchmark, complete=True)
    prediction_path = next(row["source_path"] for row in rows if row["field_name"] == "prediction_pdb")
    for row in rows:
        if row["field_name"] == "native_pdb":
            row["source_path"] = prediction_path
            row["recommended_value"] = prediction_path
    _write_csv(patch_csv, rows)
    _write_json(
        tmp_path / "dropzones.json",
        {
            "summary": {},
            "rows": [
                {
                    "queue_rank": 1,
                    "required_benchmark_id": benchmark,
                    "required_target_id": "HIST_IDENTICAL",
                    "scope": "monomer",
                    "patch_preview_csv": str(patch_csv),
                }
            ],
        },
    )

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_evidence_quality_audit_status"] == (
        "blocked_evidence_quality"
    )
    assert payload["summary"]["prediction_native_identical_count"] == 1
    assert payload["rows"][0]["quality_status"] == "blocked_evidence_quality"
    assert "prediction_native_identical_file" in payload["rows"][0]["blockers"]
