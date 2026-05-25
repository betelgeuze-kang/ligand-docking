from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_target_identity_clearance_workorder as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path, queue_json: Path) -> list[str]:
    return [
        "--clearance-queue-json",
        str(queue_json),
        "--out-dir",
        str(tmp_path / "workorders"),
        "--out-json",
        str(tmp_path / "workorder.json"),
        "--out-csv",
        str(tmp_path / "workorder.csv"),
        "--out-md",
        str(tmp_path / "WORKORDER.md"),
    ]


def test_clearance_workorder_materializes_per_target_dropzones_and_templates(tmp_path: Path) -> None:
    queue_json = tmp_path / "queue.json"
    _write_json(
        queue_json,
        {
            "summary": {"clearance_queue_status": "awaiting_target_identity_clearance"},
            "rows": [
                {
                    "target_id": "H1001",
                    "target_name": "Example complex",
                    "scope": "complex",
                    "candidate_use_status": "operator_review_required",
                    "prediction_pdb": "runs/pred/H1001_model_1.pdb",
                    "ts_prediction_pdb": "runs/pred/H1001TS.pdb",
                    "native_status": "missing",
                    "provenance_cleared": "false",
                    "blockers": "native_pdb_missing,no_leak_provenance_not_cleared",
                },
                {
                    "target_id": "H1002",
                    "target_name": "Ready complex",
                    "scope": "complex",
                    "candidate_use_status": "operator_review_required",
                    "prediction_pdb": "runs/pred/H1002_model_1.pdb",
                    "ts_prediction_pdb": "",
                    "native_status": "present",
                    "provenance_cleared": "true",
                    "blockers": "",
                },
                {
                    "target_id": "H1003",
                    "candidate_use_status": "blocked_current_casp17_target",
                },
            ],
        },
    )
    args = mod.parse_args(_args(tmp_path, queue_json))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    by_id = {row["target_id"]: row for row in payload["rows"]}
    assert payload["summary"]["clearance_workorder_status"] == "awaiting_native_or_provenance"
    assert payload["summary"]["workorder_count"] == 2
    assert payload["summary"]["ready_for_manifest_stub_count"] == 1
    assert payload["summary"]["native_and_provenance_required_count"] == 1
    assert payload["summary"]["native_dropzone_count"] == 2
    assert by_id["H1001"]["workorder_status"] == "native_and_provenance_required"
    assert by_id["H1002"]["workorder_status"] == "ready_for_manifest_stub_review"
    assert Path(tmp_path, by_id["H1001"]["provenance_template_csv"]).is_file()
    assert Path(tmp_path, by_id["H1001"]["manifest_stub_csv"]).is_file()
    assert Path(tmp_path, by_id["H1001"]["readme_path"]).is_file()
    assert _read_csv(tmp_path / "workorder.csv")[0]["target_id"] == "H1001"
    manifest_stub = _read_csv(Path(tmp_path, by_id["H1001"]["manifest_stub_csv"]))[0]
    assert manifest_stub["native_pdb"].endswith("H1001_native.pdb")
    assert manifest_stub["operator_clearance"] == "REQUIRED_OPERATOR_CLEARANCE"
    assert "does not fetch native structures" in payload["summary"]["claim_boundary"]


def test_clearance_workorder_reports_missing_queue(tmp_path: Path) -> None:
    queue_json = tmp_path / "queue.json"
    _write_json(queue_json, {"summary": {}, "rows": []})
    args = mod.parse_args(_args(tmp_path, queue_json))

    payload = mod.build_payload(args)

    assert payload["summary"]["clearance_workorder_status"] == "missing_clearance_queue"
    assert payload["summary"]["workorder_count"] == 0
    assert payload["rows"] == []
