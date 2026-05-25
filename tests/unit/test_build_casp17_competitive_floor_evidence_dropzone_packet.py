from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_evidence_dropzone_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_evidence_dropzone_creates_per_row_manifest_and_guides(tmp_path: Path) -> None:
    folder = tmp_path / "batch" / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    field_guide = folder / "FIELD_GUIDE.md"
    row_fill.parent.mkdir(parents=True)
    row_fill.write_text("benchmark_id,target_id\n", encoding="utf-8")
    field_guide.write_text("# field guide\n", encoding="utf-8")
    worklist = tmp_path / "worklist.json"
    _write_json(
        worklist,
        {
            "summary": {"worklist_status": "open_actions", "row_count": 1, "open_action_count": 4},
            "rows": [
                {
                    "action_rank": 1,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "row_fill_csv": str(row_fill),
                    "field_guide_md": str(field_guide),
                    "evidence_class": "target_identity",
                    "template_column": "benchmark_id",
                    "current_value": "hist_REQUIRED_MONOMER_001",
                    "expected_value": "stable hist_* ID",
                    "blocker": "benchmark_id_placeholder",
                    "recommended_action": "replace benchmark_id",
                    "local_destination_hint": "",
                },
                {
                    "action_rank": 2,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "row_fill_csv": str(row_fill),
                    "field_guide_md": str(field_guide),
                    "evidence_class": "core_file",
                    "template_column": "prediction_pdb",
                    "current_value": "REQUIRED_prediction.pdb",
                    "expected_value": "prediction PDB",
                    "blocker": "prediction_pdb_placeholder",
                    "recommended_action": "place a validated local PDB",
                    "local_destination_hint": "runs/casp17_historical_benchmark_predictions_current/<HISTORICAL_TARGET_ID>_prediction.pdb",
                },
                {
                    "action_rank": 3,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "row_fill_csv": str(row_fill),
                    "field_guide_md": str(field_guide),
                    "evidence_class": "ablation_file",
                    "template_column": "recursive_prediction_pdb",
                    "current_value": "REQUIRED_recursive.pdb",
                    "expected_value": "recursive layer PDB",
                    "blocker": "recursive_prediction_pdb_placeholder",
                    "recommended_action": "place a validated local PDB",
                    "local_destination_hint": "runs/casp17_historical_ablation_predictions_current/recursive/<HISTORICAL_TARGET_ID>TS.pdb",
                },
                {
                    "action_rank": 4,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "row_fill_csv": str(row_fill),
                    "field_guide_md": str(field_guide),
                    "evidence_class": "provenance",
                    "template_column": "leakage_clearance",
                    "current_value": "REQUIRED_NO_LEAK_CLEARANCE",
                    "expected_value": "no_leak",
                    "blocker": "leakage_clearance_requires_no_leak_clearance",
                    "recommended_action": "record no_leak",
                    "local_destination_hint": "",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--worklist-json",
            str(worklist),
            "--out-json",
            str(tmp_path / "dropzone.json"),
            "--out-csv",
            str(tmp_path / "dropzone.csv"),
            "--out-md",
            str(tmp_path / "DROPZONE.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["dropzone_status"] == "open_actions"
    assert payload["summary"]["dropzone_count"] == 1
    assert payload["summary"]["manifest_count"] == 1
    assert payload["summary"]["open_action_count"] == 4
    assert payload["summary"]["file_action_count"] == 2
    assert payload["rows"][1]["drop_path"].endswith("evidence_dropzone/files/core/<HISTORICAL_TARGET_ID>_prediction.pdb")
    assert payload["rows"][2]["drop_path"].endswith(
        "evidence_dropzone/files/ablation/recursive/<HISTORICAL_TARGET_ID>TS.pdb"
    )
    assert (folder / "EVIDENCE_DROPZONE.md").is_file()
    assert (folder / "evidence_dropzone" / "DROPZONE_MANIFEST.csv").is_file()
    assert (folder / "evidence_dropzone" / "files" / "core" / "README.md").is_file()
    assert (folder / "evidence_dropzone" / "files" / "ablation" / "recursive" / "README.md").is_file()
    manifest_rows = _read_csv(folder / "evidence_dropzone" / "DROPZONE_MANIFEST.csv")
    assert manifest_rows[1]["template_column"] == "prediction_pdb"
    assert "row_fill.csv" in manifest_rows[1]["operator_note"]


def test_evidence_dropzone_ready_when_worklist_has_no_actions(tmp_path: Path) -> None:
    worklist = tmp_path / "worklist.json"
    _write_json(
        worklist,
        {"summary": {"worklist_status": "ready", "row_count": 1, "open_action_count": 0}, "rows": []},
    )
    args = mod.parse_args(["--worklist-json", str(worklist)])

    payload = mod.build_payload(args)

    assert payload["summary"]["dropzone_status"] == "ready"
    assert payload["summary"]["dropzone_count"] == 0
    assert payload["summary"]["open_action_count"] == 0
    assert payload["rows"] == []
