from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _run(tmp_path: Path, workorder_json: Path, audit_json: Path) -> dict:
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_competitive_floor_target_identity_clearance_replacement_pickup_packet.py"),
            "--workorder-json",
            str(workorder_json),
            "--audit-json",
            str(audit_json),
            "--out-json",
            str(tmp_path / "pickup.json"),
            "--out-csv",
            str(tmp_path / "pickup.csv"),
            "--out-md",
            str(tmp_path / "pickup.md"),
        ],
        cwd=ROOT,
        check=True,
    )
    return json.loads((tmp_path / "pickup.json").read_text(encoding="utf-8"))


def test_replacement_pickup_packet_expands_selected_dropzone_and_duplicate_blocker(tmp_path: Path) -> None:
    folder = tmp_path / "H1001_to_H2001"
    native = folder / "native" / "H2001_native.pdb"
    provenance = folder / "provenance_template.csv"
    manifest = folder / "manifest_stub.csv"
    _write_csv(
        provenance,
        [
            {
                "target_id": "H2001",
                "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
                "prediction_created_at": "YYYY-MM-DD",
                "operator": "REQUIRED_OPERATOR_ID",
            }
        ],
    )
    _write_csv(manifest, [{"target_id": "H2001", "native_pdb": str(native)}])
    prediction = tmp_path / "H2001_model_1.pdb"
    prediction.write_text("ATOM      1  CA  ALA A   1       0.000   1.000   2.000  1.00 70.00           C  \n", encoding="utf-8")
    workorder_json = tmp_path / "workorder.json"
    audit_json = tmp_path / "audit.json"
    _write_json(
        workorder_json,
        {
            "rows": [
                {
                    "replace_target_id": "H1001",
                    "target_id": "H2001",
                    "target_name": "Replacement A",
                    "scope": "complex",
                    "selection_status": "selected_for_replacement_workorder",
                    "workorder_folder": str(folder),
                    "native_dropzone_pdb": str(native),
                    "provenance_template_csv": str(provenance),
                    "manifest_stub_csv": str(manifest),
                    "prediction_pdb": str(prediction),
                },
                {
                    "replace_target_id": "H1002",
                    "target_id": "H2001",
                    "selection_status": "blocked_duplicate_candidate_assignment",
                    "prediction_pdb": str(prediction),
                    "next_action": "choose a different ready replacement candidate before materializing this workorder",
                    "blockers": "duplicate_candidate_target_id",
                },
            ]
        },
    )
    _write_json(
        audit_json,
        {
            "rows": [
                {
                    "target_id": "H2001",
                    "native_dropzone_pdb": str(native),
                    "audit_status": "blocked",
                    "native_file_status": "missing",
                    "manifest_stub_status": "blocked",
                    "provenance_status": "blocked",
                    "prediction_file_status": "present",
                    "prediction_protein_atom_record_count": 1,
                    "blockers": "native_pdb_missing",
                }
            ]
        },
    )

    payload = _run(tmp_path, workorder_json, audit_json)

    assert payload["summary"]["replacement_pickup_status"] == "open_actions"
    assert payload["summary"]["selected_count"] == 1
    assert payload["summary"]["awaiting_operator_pickup_count"] == 1
    assert payload["summary"]["blocked_selection_count"] == 1
    assert payload["summary"]["native_missing_count"] == 1
    assert payload["summary"]["provenance_required_field_count"] == 3
    assert payload["summary"]["operator_action_count"] == 4
    assert payload["rows"][0]["operator_pickup_md"].endswith("OPERATOR_PICKUP.md")
    assert (folder / "OPERATOR_PICKUP.md").is_file()
    assert payload["rows"][1]["operator_action_count"] == 1


def test_replacement_pickup_packet_marks_ready_after_clean_audit(tmp_path: Path) -> None:
    folder = tmp_path / "H1001_to_H2001"
    native = folder / "native" / "H2001_native.pdb"
    provenance = folder / "provenance_template.csv"
    manifest = folder / "manifest_stub.csv"
    native.parent.mkdir(parents=True, exist_ok=True)
    native.write_text("ATOM      1  CA  ALA A   1       0.000   1.000   2.000  1.00 70.00           C  \n", encoding="utf-8")
    _write_csv(provenance, [{"target_id": "H2001", "leakage_clearance": "clear"}])
    _write_csv(manifest, [{"target_id": "H2001", "native_pdb": str(native)}])
    prediction = tmp_path / "H2001_model_1.pdb"
    prediction.write_text(native.read_text(encoding="utf-8"), encoding="utf-8")
    workorder_json = tmp_path / "workorder.json"
    audit_json = tmp_path / "audit.json"
    _write_json(
        workorder_json,
        {
            "rows": [
                {
                    "replace_target_id": "H1001",
                    "target_id": "H2001",
                    "selection_status": "selected_for_replacement_workorder",
                    "workorder_folder": str(folder),
                    "native_dropzone_pdb": str(native),
                    "provenance_template_csv": str(provenance),
                    "manifest_stub_csv": str(manifest),
                    "prediction_pdb": str(prediction),
                }
            ]
        },
    )
    _write_json(
        audit_json,
        {
            "rows": [
                {
                    "target_id": "H2001",
                    "native_dropzone_pdb": str(native),
                    "audit_status": "pass",
                    "native_file_status": "present",
                    "manifest_stub_status": "ready",
                    "provenance_status": "ready",
                    "prediction_file_status": "present",
                }
            ]
        },
    )

    payload = _run(tmp_path, workorder_json, audit_json)

    assert payload["summary"]["replacement_pickup_status"] == "ready"
    assert payload["summary"]["ready_for_operator_intake_count"] == 1
    assert payload["summary"]["operator_action_count"] == 0
    assert payload["rows"][0]["pickup_status"] == "ready_for_operator_intake"
