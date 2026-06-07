from __future__ import annotations

import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_target_identity_clearance_adjudication_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--workorder-json",
        str(tmp_path / "workorder.json"),
        "--operator-intake-json",
        str(tmp_path / "operator_intake.json"),
        "--native-candidate-json",
        str(tmp_path / "native_candidates.json"),
        "--out-dir",
        str(tmp_path / "adjudication"),
        "--out-json",
        str(tmp_path / "adjudication.json"),
        "--out-csv",
        str(tmp_path / "adjudication.csv"),
        "--out-md",
        str(tmp_path / "ADJUDICATION.md"),
    ]


def test_adjudication_packet_splits_collision_manual_and_ready_targets(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "workorder.json",
        {
            "rows": [
                {"target_id": "H1001", "target_name": "Collision target"},
                {"target_id": "H1002", "target_name": "Manual target"},
                {"target_id": "H1003", "target_name": "Ready target"},
            ]
        },
    )
    _write_json(
        tmp_path / "operator_intake.json",
        {
            "rows": [
                {"target_id": "H1001", "intake_status": "awaiting_input"},
                {"target_id": "H1002", "intake_status": "awaiting_input"},
                {"target_id": "H1003", "intake_status": "ready_to_apply"},
            ]
        },
    )
    _write_json(
        tmp_path / "native_candidates.json",
        {
            "summary": {"native_candidate_packet_status": "review_required"},
            "rows": [
                {
                    "target_id": "H1001",
                    "candidate_status": "blocked_current_target_collision",
                    "query_label": "relaxed",
                    "query_text": "Collision",
                    "pdb_id": "1ABC",
                    "initial_release_date": "2024-01-01",
                    "current_target_collision_ids": "H2001",
                    "blockers": "current_target_name_collision,candidate_public_before_target_entry",
                },
                {
                    "target_id": "H1002",
                    "candidate_status": "no_rcsb_candidate_found",
                    "query_label": "prepared",
                    "query_text": "Manual",
                    "blockers": "rcsb_candidate_missing",
                },
                {
                    "target_id": "H1003",
                    "candidate_status": "operator_review_required",
                    "query_label": "exact",
                    "query_text": "Ready",
                    "pdb_id": "2XYZ",
                    "blockers": "",
                },
            ],
        },
    )
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    by_id = {row["target_id"]: row for row in payload["rows"]}
    assert payload["summary"]["adjudication_packet_status"] == "operator_intake_ready_to_apply"
    assert payload["summary"]["replacement_required_count"] == 1
    assert payload["summary"]["manual_native_search_required_count"] == 1
    assert payload["summary"]["safe_to_apply_operator_intake_count"] == 1
    assert by_id["H1001"]["adjudication_status"] == "blocked_current_target_collision"
    assert by_id["H1001"]["replacement_required"] == "true"
    assert by_id["H1002"]["adjudication_status"] == "manual_native_search_required"
    assert by_id["H1002"]["manual_native_search_required"] == "true"
    assert by_id["H1003"]["adjudication_status"] == "operator_intake_ready_to_apply"
    assert by_id["H1003"]["safe_to_apply_operator_intake"] == "true"
    assert Path(by_id["H1001"]["adjudication_md"]).is_file()
    assert (tmp_path / "ADJUDICATION.md").is_file()


def test_adjudication_packet_reports_missing_workorders(tmp_path: Path) -> None:
    _write_json(tmp_path / "workorder.json", {"rows": []})
    _write_json(tmp_path / "operator_intake.json", {"rows": []})
    _write_json(tmp_path / "native_candidates.json", {"rows": []})
    args = mod.parse_args(_args(tmp_path))

    payload = mod.build_payload(args)

    assert payload["summary"]["adjudication_packet_status"] == "missing_workorders"
    assert payload["summary"]["target_count"] == 0
    assert payload["rows"] == []
