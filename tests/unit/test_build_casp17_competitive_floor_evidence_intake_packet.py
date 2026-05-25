from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_evidence_intake_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_evidence_intake_finds_single_dropzone_file_patch_candidate(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    core = folder / "evidence_dropzone" / "files" / "core"
    core.mkdir(parents=True)
    placed = core / "T9001_prediction.pdb"
    placed.write_text("ATOM\n", encoding="utf-8")
    row_fill = folder / "row_fill.csv"
    _write_csv(
        row_fill,
        [
            {
                "benchmark_id": "hist_REQUIRED_MONOMER_001",
                "target_id": "REQUIRED_MONOMER_001",
                "prediction_pdb": "REQUIRED_prediction.pdb",
                "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
            }
        ],
    )
    dropzone = tmp_path / "dropzone.json"
    _write_json(
        dropzone,
        {
            "summary": {"dropzone_status": "open_actions", "dropzone_count": 1},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "action_rank": 1,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "evidence_class": "core_file",
                    "template_column": "prediction_pdb",
                    "blocker": "prediction_pdb_placeholder",
                    "source_row_fill_csv": str(row_fill),
                    "dropzone_folder": str(folder / "evidence_dropzone"),
                    "dropzone_class_folder": str(core),
                    "drop_path": str(core / "<HISTORICAL_TARGET_ID>_prediction.pdb"),
                },
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "action_rank": 2,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "evidence_class": "provenance",
                    "template_column": "leakage_clearance",
                    "blocker": "leakage_clearance_requires_no_leak_clearance",
                    "source_row_fill_csv": str(row_fill),
                    "dropzone_folder": str(folder / "evidence_dropzone"),
                    "dropzone_class_folder": str(folder / "evidence_dropzone" / "provenance"),
                    "drop_path": "",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--dropzone-json",
            str(dropzone),
            "--out-json",
            str(tmp_path / "intake.json"),
            "--out-csv",
            str(tmp_path / "intake.csv"),
            "--out-md",
            str(tmp_path / "INTAKE.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["intake_status"] == "ready_for_operator_patch"
    assert payload["summary"]["patch_candidate_count"] == 1
    assert payload["summary"]["awaiting_operator_value_count"] == 1
    assert payload["rows"][0]["intake_status"] == "patch_candidate"
    assert payload["rows"][0]["recommended_value"].endswith("T9001_prediction.pdb")
    assert (folder / "ROW_FILL_PATCH_CANDIDATE.csv").is_file()
    assert (folder / "EVIDENCE_INTAKE.md").is_file()
    patch_rows = _read_csv(folder / "ROW_FILL_PATCH_CANDIDATE.csv")
    assert patch_rows[0]["template_column"] == "prediction_pdb"
    assert patch_rows[0]["recommended_value"].endswith("T9001_prediction.pdb")


def test_evidence_intake_ready_when_dropzone_has_no_open_rows(tmp_path: Path) -> None:
    dropzone = tmp_path / "dropzone.json"
    _write_json(dropzone, {"summary": {"dropzone_status": "ready", "dropzone_count": 0}, "rows": []})
    args = mod.parse_args(["--dropzone-json", str(dropzone)])

    payload = mod.build_payload(args)

    assert payload["summary"]["intake_status"] == "ready"
    assert payload["summary"]["action_count"] == 0
    assert payload["rows"] == []


def test_evidence_intake_uses_cleared_value_ledger_patch_candidate(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(
        row_fill,
        [{"benchmark_id": "hist_REQUIRED_MONOMER_001", "target_id": "REQUIRED_MONOMER_001"}],
    )
    _write_csv(
        folder / "FIELD_VALUE_LEDGER.csv",
        [
            {
                "template_column": "target_id",
                "evidence_class": "target_identity",
                "current_value": "REQUIRED_MONOMER_001",
                "proposed_value": "T9001",
                "evidence_ref": "local/no_leak/T9001.md",
                "operator_clearance": "ready_for_row_fill",
                "ledger_status": "ready_for_row_fill",
                "next_action": "use this target_id",
            }
        ],
    )
    dropzone = tmp_path / "dropzone.json"
    _write_json(
        dropzone,
        {
            "summary": {"dropzone_status": "open_actions", "dropzone_count": 1},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "action_rank": 1,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "evidence_class": "target_identity",
                    "template_column": "target_id",
                    "blocker": "target_id_placeholder",
                    "source_row_fill_csv": str(row_fill),
                    "dropzone_folder": str(folder / "evidence_dropzone"),
                    "dropzone_class_folder": str(folder / "evidence_dropzone" / "target_identity"),
                    "drop_path": "",
                }
            ],
        },
    )
    args = mod.parse_args(["--dropzone-json", str(dropzone)])

    payload = mod.build_payload(args)

    assert payload["summary"]["intake_status"] == "ready_for_operator_patch"
    assert payload["summary"]["patch_candidate_count"] == 1
    assert payload["rows"][0]["intake_status"] == "patch_candidate"
    assert payload["rows"][0]["recommended_value"] == "T9001"


def test_evidence_intake_prefers_canonical_file_path_from_cleared_target_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    folder = tmp_path / "casp17" / "competitive_floor_batch_current" / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(row_fill, [{"target_id": "REQUIRED_MONOMER_001", "prediction_pdb": "REQUIRED_prediction.pdb"}])
    _write_csv(
        folder / "FIELD_VALUE_LEDGER.csv",
        [
            {
                "template_column": "target_id",
                "evidence_class": "target_identity",
                "current_value": "REQUIRED_MONOMER_001",
                "proposed_value": "T9001",
                "evidence_ref": "local/no_leak/T9001.md",
                "operator_clearance": "ready_for_row_fill",
                "ledger_status": "ready_for_row_fill",
                "next_action": "use this target_id",
            }
        ],
    )
    canonical = tmp_path / "runs" / "casp17_historical_benchmark_predictions_current" / "T9001_prediction.pdb"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("HEADER TEST\nATOM      1  CA  ALA A   1       0.0   0.0   0.0\nEND\n", encoding="utf-8")
    core = folder / "evidence_dropzone" / "files" / "core"
    dropzone = tmp_path / "dropzone.json"
    _write_json(
        dropzone,
        {
            "summary": {"dropzone_status": "open_actions", "dropzone_count": 1},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "action_rank": 1,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "evidence_class": "core_file",
                    "template_column": "prediction_pdb",
                    "blocker": "prediction_pdb_placeholder",
                    "source_row_fill_csv": str(row_fill),
                    "dropzone_folder": str(folder / "evidence_dropzone"),
                    "dropzone_class_folder": str(core),
                    "drop_path": str(core / "<HISTORICAL_TARGET_ID>_prediction.pdb"),
                }
            ],
        },
    )
    args = mod.parse_args(["--dropzone-json", str(dropzone)])

    payload = mod.build_payload(args)

    assert payload["summary"]["patch_candidate_count"] == 1
    assert payload["rows"][0]["intake_status"] == "patch_candidate"
    assert payload["rows"][0]["recommended_value"] == "runs/casp17_historical_benchmark_predictions_current/T9001_prediction.pdb"
    assert "priority_001_REQUIRED_MONOMER_001" not in payload["rows"][0]["recommended_value"]
