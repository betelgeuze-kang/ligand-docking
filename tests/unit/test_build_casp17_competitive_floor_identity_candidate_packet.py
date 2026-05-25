from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_identity_candidate_packet as mod


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = [
            "benchmark_id",
            "target_id",
            "scope",
            "leakage_clearance",
            "operator_clearance",
            "prediction_generated_before_native_release",
            "public_template_or_native_used_for_prediction",
            "other_team_model_used",
            "post_release_information_used",
            "current_casp17_target",
        ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _intake_rows() -> list[dict[str, str]]:
    return [
        {
            "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
            "operator_priority": "1",
            "row_rank": "1",
            "scope": "monomer",
            "current_benchmark_id": "hist_REQUIRED_MONOMER_001",
            "current_target_id": "REQUIRED_MONOMER_001",
            "proposed_benchmark_id": "",
            "proposed_target_id": "",
            "evidence_ref": "",
            "operator_clearance": "",
        },
        {
            "dropzone_id": "priority_011_REQUIRED_COMPLEX_001",
            "operator_priority": "11",
            "row_rank": "26",
            "scope": "complex",
            "current_benchmark_id": "hist_REQUIRED_COMPLEX_001",
            "current_target_id": "REQUIRED_COMPLEX_001",
            "proposed_benchmark_id": "",
            "proposed_target_id": "",
            "evidence_ref": "",
            "operator_clearance": "",
        },
    ]


def _ready_row(target_id: str, scope: str) -> dict[str, str]:
    return {
        "benchmark_id": f"hist_{target_id}",
        "target_id": target_id,
        "scope": scope,
        "split": "historical",
        "leakage_clearance": "no_leak",
        "operator_clearance": "no_leak",
        "prediction_generated_before_native_release": "true",
        "public_template_or_native_used_for_prediction": "false",
        "other_team_model_used": "false",
        "post_release_information_used": "false",
        "current_casp17_target": "false",
    }


def _args(
    tmp_path: Path,
    intake_csv: Path,
    ready_csv: Path,
    candidate_csv: Path,
    operator_csv: Path,
    current_targets_csv: Path,
    *extra: str,
) -> list[str]:
    preflight_json = tmp_path / "preflight.json"
    import_json = tmp_path / "import.json"
    _write_json(preflight_json, {"summary": {"operator_preflight_status": "blocked"}})
    _write_json(import_json, {"summary": {"import_status": "blocked"}})
    return [
        "--intake-csv",
        str(intake_csv),
        "--ready-manifest-csv",
        str(ready_csv),
        "--candidate-manifest-csv",
        str(candidate_csv),
        "--operator-template-csv",
        str(operator_csv),
        "--operator-preflight-json",
        str(preflight_json),
        "--operator-import-json",
        str(import_json),
        "--current-target-csv",
        str(current_targets_csv),
        "--out-json",
        str(tmp_path / "packet.json"),
        "--out-csv",
        str(tmp_path / "packet.csv"),
        "--out-md",
        str(tmp_path / "PACKET.md"),
        *extra,
    ]


def test_identity_candidate_packet_waits_for_cleared_source_candidates(tmp_path: Path) -> None:
    intake_csv = tmp_path / "intake.csv"
    ready_csv = tmp_path / "ready.csv"
    candidate_csv = tmp_path / "candidate.csv"
    operator_csv = tmp_path / "operator.csv"
    current_targets_csv = tmp_path / "current_targets.csv"
    _write_csv(intake_csv, _intake_rows())
    _write_csv(ready_csv, [])
    _write_csv(candidate_csv, [])
    _write_csv(operator_csv, [{"benchmark_id": "hist_REQUIRED_MONOMER_001", "target_id": "REQUIRED_MONOMER_001", "scope": "monomer"}])
    _write_csv(current_targets_csv, [{"target_id": "T1331"}])
    args = mod.parse_args(_args(tmp_path, intake_csv, ready_csv, candidate_csv, operator_csv, current_targets_csv))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["identity_candidate_status"] == "awaiting_candidate_sources"
    assert payload["summary"]["ready_for_intake_count"] == 0
    assert payload["summary"]["awaiting_candidate_source_count"] == 2
    assert payload["summary"]["source_blocked_candidate_count"] == 1
    assert payload["rows"][0]["candidate_status"] == "awaiting_candidate_source"
    assert _read_csv(tmp_path / "packet.csv")[0]["dropzone_id"] == "priority_001_REQUIRED_MONOMER_001"
    assert (tmp_path / "PACKET.md").is_file()


def test_identity_candidate_packet_applies_ready_candidates_to_intake(tmp_path: Path) -> None:
    intake_csv = tmp_path / "intake.csv"
    ready_csv = tmp_path / "ready.csv"
    candidate_csv = tmp_path / "candidate.csv"
    operator_csv = tmp_path / "operator.csv"
    current_targets_csv = tmp_path / "current_targets.csv"
    _write_csv(intake_csv, _intake_rows())
    _write_csv(ready_csv, [_ready_row("T9001", "monomer"), _ready_row("H9002", "complex")])
    _write_csv(candidate_csv, [])
    _write_csv(operator_csv, [])
    _write_csv(current_targets_csv, [{"target_id": "T1331"}])
    args = mod.parse_args(
        _args(tmp_path, intake_csv, ready_csv, candidate_csv, operator_csv, current_targets_csv, "--apply")
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    updated = _read_csv(intake_csv)
    assert payload["summary"]["identity_candidate_status"] == "ready_for_intake_sync"
    assert payload["summary"]["ready_for_intake_count"] == 2
    assert payload["summary"]["applied_intake_count"] == 2
    assert updated[0]["proposed_benchmark_id"] == "hist_T9001"
    assert updated[0]["proposed_target_id"] == "T9001"
    assert updated[0]["operator_clearance"] == "no_leak"
    assert updated[1]["proposed_benchmark_id"] == "hist_H9002"
    assert updated[1]["proposed_target_id"] == "H9002"
