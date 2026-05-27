from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_unblock_map as mod


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


def test_competitive_floor_unblock_map_prioritizes_manifest_seed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    candidate_json = tmp_path / "candidate.json"
    repair_csv = tmp_path / "repair.csv"
    unlock_json = tmp_path / "unlock.json"
    clearance_cycle_json = tmp_path / "clearance_cycle.json"
    decision_json = tmp_path / "decision.json"

    _write_json(
        candidate_json,
        {
            "summary": {
                "identity_candidate_status": "awaiting_candidate_sources",
                "source_candidate_count": 0,
                "source_ready_candidate_count": 0,
                "source_blocked_candidate_count": 0,
            },
            "rows": [
                {
                    "operator_priority": 1,
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "current_benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "current_target_id": "REQUIRED_MONOMER_001",
                    "candidate_status": "awaiting_candidate_source",
                },
                {
                    "operator_priority": 11,
                    "dropzone_id": "priority_011_REQUIRED_COMPLEX_001",
                    "scope": "complex",
                    "current_benchmark_id": "hist_REQUIRED_COMPLEX_001",
                    "current_target_id": "REQUIRED_COMPLEX_001",
                    "candidate_status": "awaiting_candidate_source",
                },
            ],
        },
    )
    _write_csv(
        repair_csv,
        [
            {
                "source_rank": "1",
                "repair_phase": "target_identity",
                "repair_status": "awaiting_target_identity",
                "blocking_field_count": "1",
                "blockers": "placeholder_target_id",
                "next_action": "replace REQUIRED target/benchmark placeholders",
            },
            {
                "source_rank": "1",
                "repair_phase": "core_files",
                "repair_status": "awaiting_core_files",
                "blocking_field_count": "2",
                "blockers": "native_pdb_not_found,prediction_pdb_not_found",
                "next_action": "provide local historical prediction/native files",
            },
            {
                "source_rank": "2",
                "repair_phase": "target_identity",
                "repair_status": "awaiting_target_identity",
                "blocking_field_count": "1",
                "blockers": "placeholder_target_id",
                "next_action": "replace REQUIRED target/benchmark placeholders",
            },
        ],
    )
    _write_json(unlock_json, {"summary": {"identity_unlock_status": "awaiting_identity"}})
    _write_json(clearance_cycle_json, {"summary": {"cycle_status": "awaiting_operator_intake"}})
    _write_json(decision_json, {"summary": {"decision_preflight_status": "awaiting_operator_decision"}})
    args = mod.parse_args(
        [
            "--identity-candidate-json",
            str(candidate_json),
            "--identity-source-repair-csv",
            str(repair_csv),
            "--identity-unlock-kit-json",
            str(unlock_json),
            "--target-clearance-cycle-json",
            str(clearance_cycle_json),
            "--replacement-decision-preflight-json",
            str(decision_json),
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            str(tmp_path / "out.csv"),
            "--out-md",
            str(tmp_path / "out.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["unblock_map_status"] == "awaiting_historical_manifest_seed"
    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["monomer_count"] == 1
    assert payload["summary"]["complex_count"] == 1
    assert payload["summary"]["phase_open_counts"]["target_identity"] == 2
    assert payload["summary"]["phase_open_counts"]["core_files"] == 2
    assert payload["summary"]["blocking_field_count"] == 4
    assert payload["rows"][0]["first_blocking_phase"] == "target_identity"
    assert payload["rows"][0]["first_blockers"] == "placeholder_target_id"
    assert (tmp_path / "out.md").is_file()


def test_competitive_floor_unblock_map_detects_ready_identity_sync(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    candidate_json = tmp_path / "candidate.json"
    repair_csv = tmp_path / "repair.csv"
    _write_json(
        candidate_json,
        {
            "summary": {
                "identity_candidate_status": "ready_for_intake_sync",
                "source_candidate_count": 1,
                "source_ready_candidate_count": 1,
                "source_blocked_candidate_count": 0,
            },
            "rows": [
                {
                    "operator_priority": 1,
                    "dropzone_id": "priority_001",
                    "scope": "monomer",
                    "current_benchmark_id": "hist_T1000",
                    "current_target_id": "T1000",
                    "candidate_status": "ready_for_intake",
                }
            ],
        },
    )
    _write_csv(
        repair_csv,
        [
            {
                "source_rank": "1",
                "repair_phase": phase,
                "repair_status": "ready",
                "blocking_field_count": "0",
                "blockers": "",
                "next_action": "",
            }
            for phase in mod.PHASE_ORDER
        ],
    )
    args = mod.parse_args(
        [
            "--identity-candidate-json",
            str(candidate_json),
            "--identity-source-repair-csv",
            str(repair_csv),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["unblock_map_status"] == "identity_ready_for_sync"
    assert payload["summary"]["ready_for_intake_count"] == 1
    assert payload["summary"]["blocking_phase_count"] == 0
    assert payload["rows"][0]["next_unblock_action"] == "sync this cleared identity candidate into the identity unlock kit"
