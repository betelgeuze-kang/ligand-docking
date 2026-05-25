from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_target_identity_clearance_queue as mod


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


def _args(
    tmp_path: Path,
    discovery_json: Path,
    checklist_csv: Path,
    provenance_csv: Path,
    native_dir: Path,
    existing_structure_dir: Path,
) -> list[str]:
    return [
        "--discovery-json",
        str(discovery_json),
        "--existing-structure-checklist-csv",
        str(checklist_csv),
        "--existing-structure-provenance-csv",
        str(provenance_csv),
        "--historical-native-dir",
        str(native_dir),
        "--existing-structure-dir",
        str(existing_structure_dir),
        "--out-json",
        str(tmp_path / "queue.json"),
        "--out-csv",
        str(tmp_path / "queue.csv"),
        "--out-md",
        str(tmp_path / "QUEUE.md"),
    ]


def test_clearance_queue_separates_ready_and_blocked_review_targets(tmp_path: Path) -> None:
    discovery_json = tmp_path / "discovery.json"
    checklist_csv = tmp_path / "checklist.csv"
    provenance_csv = tmp_path / "provenance.csv"
    native_dir = tmp_path / "natives"
    existing_structure_dir = tmp_path / "existing"
    ts_path_ready = tmp_path / "runs" / "casp17_predictions_current" / "H1001TS.pdb"
    ts_path_ready.parent.mkdir(parents=True)
    ts_path_ready.write_text("PFRMAT TS\n", encoding="utf-8")
    (native_dir / "H1001_native.pdb").parent.mkdir(parents=True)
    (native_dir / "H1001_native.pdb").write_text("ATOM\n", encoding="utf-8")
    ts_path = tmp_path / "runs" / "casp17_predictions_current" / "H1002TS.pdb"
    ts_path.parent.mkdir(parents=True, exist_ok=True)
    ts_path.write_text("PFRMAT TS\n", encoding="utf-8")
    _write_json(
        discovery_json,
        {
            "summary": {"target_identity_discovery_status": "review_required"},
            "rows": [
                {
                    "target_id": "H1001",
                    "description": "Ready complex",
                    "identity_discovery_status": "closed_casp17_watchlist",
                    "candidate_use_status": "operator_review_required",
                },
                {
                    "target_id": "H1002",
                    "description": "Blocked complex",
                    "identity_discovery_status": "closed_casp17_watchlist",
                    "candidate_use_status": "operator_review_required",
                    "blockers": "no_leak_clearance_required",
                    "next_action": "operator must confirm no-leak clearance",
                },
                {
                    "target_id": "H1003",
                    "identity_discovery_status": "open_current_target",
                    "candidate_use_status": "blocked_current_casp17_target",
                },
            ],
        },
    )
    _write_csv(
        checklist_csv,
        [
            {"target_id": "H1001", "target_name": "Ready complex", "canonical_ts_path": str(ts_path_ready)},
            {"target_id": "H1002", "target_name": "Blocked complex", "canonical_ts_path": str(ts_path)},
        ],
    )
    _write_csv(
        provenance_csv,
        [
            {
                "target_id": "H1001",
                "provenance_status": "cleared",
                "public_or_external_source_used": "false",
                "other_team_structure_used": "false",
                "post_release_structure_used": "false",
                "operator": "operator-a",
            },
            {
                "target_id": "H1002",
                "provenance_status": "needs_operator_clearance",
                "public_or_external_source_used": "",
                "other_team_structure_used": "",
                "post_release_structure_used": "",
                "operator": "",
            },
        ],
    )
    args = mod.parse_args(_args(tmp_path, discovery_json, checklist_csv, provenance_csv, native_dir, existing_structure_dir))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    by_id = {row["target_id"]: row for row in payload["rows"]}
    assert payload["summary"]["review_target_count"] == 2
    assert payload["summary"]["identity_discovery_blocker_count"] == 1
    assert payload["summary"]["ready_for_manifest_scaffold_count"] == 1
    assert payload["summary"]["awaiting_native_or_clearance_count"] == 1
    assert by_id["H1001"]["clearance_status"] == "ready_for_manifest_scaffold_review"
    assert by_id["H1001"]["prediction_status"] == "present"
    assert by_id["H1001"]["native_status"] == "present"
    assert by_id["H1001"]["provenance_cleared"] == "true"
    assert by_id["H1002"]["clearance_status"] == "awaiting_native_or_clearance"
    assert by_id["H1002"]["identity_discovery_blockers"] == "no_leak_clearance_required"
    assert by_id["H1002"]["identity_discovery_next_action"] == "operator must confirm no-leak clearance"
    assert "native_pdb_missing" in by_id["H1002"]["blockers"]
    assert _read_csv(tmp_path / "queue.csv")[0]["target_id"] == "H1001"
    assert (tmp_path / "QUEUE.md").is_file()


def test_clearance_queue_reports_missing_discovery(tmp_path: Path) -> None:
    discovery_json = tmp_path / "discovery.json"
    checklist_csv = tmp_path / "checklist.csv"
    provenance_csv = tmp_path / "provenance.csv"
    native_dir = tmp_path / "natives"
    existing_structure_dir = tmp_path / "existing"
    _write_json(discovery_json, {"summary": {}, "rows": []})
    _write_csv(checklist_csv, [])
    _write_csv(provenance_csv, [])
    args = mod.parse_args(_args(tmp_path, discovery_json, checklist_csv, provenance_csv, native_dir, existing_structure_dir))

    payload = mod.build_payload(args)

    assert payload["summary"]["clearance_queue_status"] == "missing_target_identity_discovery"
    assert payload["summary"]["review_target_count"] == 0
    assert payload["rows"] == []
