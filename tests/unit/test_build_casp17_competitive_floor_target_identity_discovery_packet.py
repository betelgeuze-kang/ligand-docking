from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_target_identity_discovery_packet as mod


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
        fieldnames = ["target_id", "human_open", "qa_open", "server_open"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path, repair_json: Path, watchlist_csv: Path, current_csv: Path, runs_root: Path) -> list[str]:
    return [
        "--source-repair-json",
        str(repair_json),
        "--target-watchlist-csv",
        str(watchlist_csv),
        "--current-target-csv",
        str(current_csv),
        "--runs-root",
        str(runs_root),
        "--out-json",
        str(tmp_path / "discovery.json"),
        "--out-csv",
        str(tmp_path / "discovery.csv"),
        "--out-md",
        str(tmp_path / "DISCOVERY.md"),
    ]


def test_target_identity_discovery_classifies_current_closed_unknown_and_synthetic_targets(tmp_path: Path) -> None:
    repair_json = tmp_path / "repair.json"
    watchlist_csv = tmp_path / "watchlist.csv"
    current_csv = tmp_path / "current.csv"
    runs_root = tmp_path / "runs"
    _write_json(
        repair_json,
        {"summary": {"source_repair_status": "awaiting_target_identity", "target_identity_action_count": 40}},
    )
    _write_csv(
        watchlist_csv,
        [
            {"target_id": "T1000", "human_open": "True", "qa_open": "True", "server_open": "False"},
            {"target_id": "H1001", "human_open": "False", "qa_open": "False", "server_open": "False"},
        ],
    )
    _write_csv(current_csv, [{"target_id": "T1000"}])
    for target_id in ["T1000", "H1001", "H3003", "T8200"]:
        _write_json(
            runs_root / "casp17_validations_current" / f"{target_id}_confidence_calibration.json",
            {
                "summary": {
                    "packet_type": "casp17_confidence_calibration",
                    "target_id": target_id,
                    "confidence_calibration_status": "pass",
                }
            },
        )
    args = mod.parse_args(_args(tmp_path, repair_json, watchlist_csv, current_csv, runs_root))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    by_id = {row["target_id"]: row for row in payload["rows"]}
    assert payload["summary"]["target_identity_discovery_status"] == "review_required"
    assert payload["summary"]["discovered_target_count"] == 4
    assert payload["summary"]["open_current_target_count"] == 1
    assert payload["summary"]["closed_watchlist_target_count"] == 1
    assert payload["summary"]["unknown_local_target_count"] == 1
    assert payload["summary"]["synthetic_test_artifact_count"] == 1
    assert payload["summary"]["operator_review_target_count"] == 2
    assert payload["summary"]["ready_for_identity_intake_count"] == 0
    assert by_id["T1000"]["identity_discovery_status"] == "open_current_target"
    assert by_id["T1000"]["candidate_use_status"] == "blocked_current_casp17_target"
    assert by_id["H1001"]["identity_discovery_status"] == "closed_casp17_watchlist"
    assert by_id["H1001"]["candidate_use_status"] == "operator_review_required"
    assert by_id["H3003"]["identity_discovery_status"] == "unknown_local_target"
    assert by_id["H3003"]["candidate_use_status"] == "operator_review_required"
    assert by_id["T8200"]["identity_discovery_status"] == "synthetic_test_artifact"
    assert by_id["T8200"]["candidate_use_status"] == "blocked_synthetic_test_artifact"
    assert _read_csv(tmp_path / "discovery.csv")[0]["target_id"] == "H1001"
    assert (tmp_path / "DISCOVERY.md").is_file()


def test_target_identity_discovery_reports_empty_scan(tmp_path: Path) -> None:
    repair_json = tmp_path / "repair.json"
    watchlist_csv = tmp_path / "watchlist.csv"
    current_csv = tmp_path / "current.csv"
    runs_root = tmp_path / "runs"
    _write_json(repair_json, {"summary": {"source_repair_status": "awaiting_target_identity"}})
    _write_csv(watchlist_csv, [])
    _write_csv(current_csv, [])
    runs_root.mkdir(parents=True)
    args = mod.parse_args(_args(tmp_path, repair_json, watchlist_csv, current_csv, runs_root))

    payload = mod.build_payload(args)

    assert payload["summary"]["target_identity_discovery_status"] == "missing"
    assert payload["summary"]["discovered_target_count"] == 0
    assert payload["rows"] == []
