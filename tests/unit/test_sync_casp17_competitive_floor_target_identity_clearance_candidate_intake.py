import csv
import json
from pathlib import Path

from tools import sync_casp17_competitive_floor_target_identity_clearance_candidate_intake as mod


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _live_row() -> dict[str, str]:
    return {
        "dropzone_id": "priority_011_REQUIRED_COMPLEX_001",
        "operator_priority": "11",
        "row_rank": "11",
        "scope": "complex",
        "current_benchmark_id": "hist_REQUIRED_COMPLEX_001",
        "current_target_id": "REQUIRED_COMPLEX_001",
        "proposed_benchmark_id": "",
        "proposed_target_id": "",
        "evidence_ref": "",
        "operator_clearance": "",
        "identity_status": "awaiting_identity",
        "missing_field_count": "4",
        "blockers": "proposed_benchmark_id_required,proposed_target_id_required",
        "file_actions_unlocked": "0",
        "readiness_gate_status": "awaiting_identity",
        "apply_identity_command": "python3 tools/run_casp17_competitive_floor_identity_unlock_round.py --apply-identity",
        "verify_command": "python3 tools/build_casp17_competitive_floor_execution_board.py",
        "next_action": "fill proposed_benchmark_id",
    }


def _candidate_row(*, staged: bool = True, target_id: str = "H1001") -> dict[str, str]:
    row = _live_row()
    if staged:
        row.update(
            {
                "proposed_benchmark_id": f"hist_{target_id}_clearance_candidate",
                "proposed_target_id": target_id,
                "evidence_ref": f"casp17/promotion.json#{target_id}",
                "operator_clearance": "cleared",
                "identity_status": "staged_for_operator_review",
                "missing_field_count": "0",
                "blockers": "",
                "next_action": "review this candidate row",
            }
        )
    return row


def _args(tmp_path: Path, candidate_csv: Path, live_csv: Path, current_csv: Path, *extra: str) -> list[str]:
    return [
        "--candidate-intake-csv",
        str(candidate_csv),
        "--live-intake-csv",
        str(live_csv),
        "--current-target-csv",
        str(current_csv),
        "--out-json",
        str(tmp_path / "sync.json"),
        "--out-csv",
        str(tmp_path / "sync.csv"),
        "--out-md",
        str(tmp_path / "SYNC.md"),
        *extra,
    ]


def test_candidate_intake_sync_waits_when_no_staged_rows(tmp_path):
    candidate_csv = tmp_path / "candidate.csv"
    live_csv = tmp_path / "live.csv"
    current_csv = tmp_path / "current.csv"
    _write_csv(candidate_csv, [_candidate_row(staged=False)])
    _write_csv(live_csv, [_live_row()])
    _write_csv(current_csv, [{"target_id": "T1331"}])
    args = mod.parse_args(_args(tmp_path, candidate_csv, live_csv, current_csv))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["candidate_intake_sync_status"] == "waiting_on_staged_identity"
    assert payload["summary"]["waiting_on_staged_identity_count"] == 1
    assert payload["summary"]["applied_field_count"] == 0
    assert _read_csv(live_csv)[0]["proposed_target_id"] == ""
    assert _read_json(tmp_path / "sync.json")["summary"]["sync_row_count"] == 1


def test_candidate_intake_sync_apply_updates_live_intake(tmp_path):
    candidate_csv = tmp_path / "candidate.csv"
    live_csv = tmp_path / "live.csv"
    current_csv = tmp_path / "current.csv"
    _write_csv(candidate_csv, [_candidate_row()])
    _write_csv(live_csv, [_live_row()])
    _write_csv(current_csv, [{"target_id": "T1331"}])
    args = mod.parse_args(_args(tmp_path, candidate_csv, live_csv, current_csv, "--apply"))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["candidate_intake_sync_status"] == "applied"
    assert payload["summary"]["applied_row_count"] == 1
    assert payload["summary"]["applied_field_count"] > 0
    live = _read_csv(live_csv)[0]
    assert live["proposed_target_id"] == "H1001"
    assert live["proposed_benchmark_id"] == "hist_H1001_clearance_candidate"
    assert live["identity_status"] == "staged_for_operator_review"
    assert live["missing_field_count"] == "0"


def test_candidate_intake_sync_blocks_current_target_and_nonempty_live_slot(tmp_path):
    candidate_csv = tmp_path / "candidate.csv"
    live_csv = tmp_path / "live.csv"
    current_csv = tmp_path / "current.csv"
    live = _live_row()
    live["proposed_target_id"] = "H9999"
    live["proposed_benchmark_id"] = "hist_H9999"
    _write_csv(candidate_csv, [_candidate_row(target_id="H1001")])
    _write_csv(live_csv, [live])
    _write_csv(current_csv, [{"target_id": "H1001"}])
    args = mod.parse_args(_args(tmp_path, candidate_csv, live_csv, current_csv, "--apply"))

    payload = mod.build_payload(args)

    assert payload["summary"]["candidate_intake_sync_status"] == "blocked"
    assert payload["summary"]["blocked_count"] == 1
    assert payload["summary"]["applied_field_count"] == 0
    assert "proposed_target_id_is_current_casp17_target" in payload["rows"][0]["blockers"]
    assert "live_intake_slot_not_empty" in payload["rows"][0]["blockers"]
