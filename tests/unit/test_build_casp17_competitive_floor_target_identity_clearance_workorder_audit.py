from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_target_identity_clearance_workorder_audit as mod


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
    if not fieldnames:
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _ready_provenance(target_id: str) -> dict[str, str]:
    return {
        "benchmark_id": f"hist_{target_id}",
        "target_id": target_id,
        "scope": "complex",
        "split": "historical_candidate",
        "leakage_clearance": "no_leak",
        "prediction_method": "internal_prediction",
        "prediction_created_at": "2026-05-01",
        "native_release_date": "2026-05-20",
        "prediction_generated_before_native_release": "true",
        "public_template_or_native_used_for_prediction": "false",
        "other_team_model_used": "false",
        "post_release_information_used": "false",
        "current_casp17_target": "false",
        "operator_clearance": "no_leak",
        "operator": "operator-a",
        "evidence_ref": "local/no_leak.md",
    }


def _ready_manifest(target_id: str, prediction: Path, native: Path) -> dict[str, str]:
    row = _ready_provenance(target_id)
    return {
        key: row[key]
        for key in [
            "benchmark_id",
            "target_id",
            "scope",
            "split",
            "leakage_clearance",
            "prediction_method",
            "prediction_created_at",
            "native_release_date",
            "prediction_generated_before_native_release",
            "public_template_or_native_used_for_prediction",
            "other_team_model_used",
            "post_release_information_used",
            "current_casp17_target",
            "operator_clearance",
        ]
    } | {"prediction_pdb": str(prediction), "native_pdb": str(native)}


def _placeholder_manifest(target_id: str, prediction: Path, native: Path) -> dict[str, str]:
    return {
        "benchmark_id": f"hist_{target_id}",
        "target_id": target_id,
        "scope": "complex",
        "split": "historical_candidate",
        "prediction_pdb": str(prediction),
        "native_pdb": str(native),
        "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
        "prediction_method": "internal_prediction",
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
        "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
        "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
        "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
        "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
        "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
    }


def _args(tmp_path: Path, workorder_json: Path) -> list[str]:
    return [
        "--workorder-json",
        str(workorder_json),
        "--out-json",
        str(tmp_path / "audit.json"),
        "--out-csv",
        str(tmp_path / "audit.csv"),
        "--out-md",
        str(tmp_path / "AUDIT.md"),
    ]


def test_clearance_workorder_audit_blocks_missing_native_and_placeholders(tmp_path: Path) -> None:
    ready_dir = tmp_path / "ready"
    blocked_dir = tmp_path / "blocked"
    ready_prediction = ready_dir / "H1001_model_1.pdb"
    ready_native = ready_dir / "H1001_native.pdb"
    blocked_prediction = blocked_dir / "H1002_model_1.pdb"
    blocked_native = blocked_dir / "H1002_native.pdb"
    for path in [ready_prediction, ready_native, blocked_prediction]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ATOM      1 CA   ALA A   1       1.000   2.000   3.000  1.00 70.00           C\n", encoding="utf-8")
    ready_provenance = ready_dir / "provenance_template.csv"
    ready_manifest = ready_dir / "manifest_stub.csv"
    blocked_provenance = blocked_dir / "provenance_template.csv"
    blocked_manifest = blocked_dir / "manifest_stub.csv"
    _write_csv(ready_provenance, [_ready_provenance("H1001")])
    _write_csv(ready_manifest, [_ready_manifest("H1001", ready_prediction, ready_native)])
    _write_csv(
        blocked_provenance,
        [
            {
                "target_id": "H1002",
                "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "prediction_created_at": "YYYY-MM-DD",
                "native_release_date": "YYYY-MM-DD",
            }
        ],
    )
    _write_csv(blocked_manifest, [_placeholder_manifest("H1002", blocked_prediction, blocked_native)])
    workorder_json = tmp_path / "workorder.json"
    _write_json(
        workorder_json,
        {
            "summary": {"clearance_workorder_status": "awaiting_native_or_provenance"},
            "rows": [
                {
                    "target_id": "H1001",
                    "workorder_status": "ready_for_manifest_stub_review",
                    "native_dropzone_pdb": str(ready_native),
                    "provenance_template_csv": str(ready_provenance),
                    "manifest_stub_csv": str(ready_manifest),
                    "prediction_pdb": str(ready_prediction),
                },
                {
                    "target_id": "H1002",
                    "workorder_status": "native_and_provenance_required",
                    "native_dropzone_pdb": str(blocked_native),
                    "provenance_template_csv": str(blocked_provenance),
                    "manifest_stub_csv": str(blocked_manifest),
                    "prediction_pdb": str(blocked_prediction),
                },
            ],
        },
    )
    args = mod.parse_args(_args(tmp_path, workorder_json))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    by_id = {row["target_id"]: row for row in payload["rows"]}
    assert payload["summary"]["clearance_workorder_audit_status"] == "blocked"
    assert payload["summary"]["audit_pass_count"] == 1
    assert payload["summary"]["audit_blocked_count"] == 1
    assert payload["summary"]["native_valid_count"] == 1
    assert payload["summary"]["provenance_ready_count"] == 1
    assert payload["summary"]["manifest_stub_ready_count"] == 1
    assert by_id["H1001"]["audit_status"] == "pass"
    assert by_id["H1002"]["audit_status"] == "blocked"
    assert "native_pdb_missing" in by_id["H1002"]["blockers"]
    assert "operator_clearance_required" in by_id["H1002"]["blockers"]
    assert _read_csv(tmp_path / "audit.csv")[0]["target_id"] == "H1001"
    assert (tmp_path / "AUDIT.md").is_file()


def test_clearance_workorder_audit_reports_missing_workorders(tmp_path: Path) -> None:
    workorder_json = tmp_path / "workorder.json"
    _write_json(workorder_json, {"summary": {}, "rows": []})
    args = mod.parse_args(_args(tmp_path, workorder_json))

    payload = mod.build_payload(args)

    assert payload["summary"]["clearance_workorder_audit_status"] == "missing_workorders"
    assert payload["summary"]["audit_target_count"] == 0
    assert payload["rows"] == []
