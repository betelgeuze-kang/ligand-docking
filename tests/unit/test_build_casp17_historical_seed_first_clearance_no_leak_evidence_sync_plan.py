from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_first_clearance_no_leak_evidence_sync_plan as mod


INTAKE_COLUMNS = [
    "field_name",
    "current_value",
    "required_value_policy",
    "weak_local_hint",
    "weak_local_hint_source",
    "evidence_ref",
    "operator_value",
    "operator_clearance",
    "notes",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], columns: list[str] = INTAKE_COLUMNS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _intake_rows() -> list[dict[str, str]]:
    return [
        {
            "field_name": "operator",
            "current_value": "REQUIRED_OPERATOR_ID",
            "required_value_policy": "operator_id",
            "weak_local_hint": "",
            "weak_local_hint_source": "",
            "evidence_ref": "casp17/dossier.md",
            "operator_value": "",
            "operator_clearance": "",
            "notes": "manual",
        },
        {
            "field_name": "prediction_created_at",
            "current_value": "YYYY-MM-DD",
            "required_value_policy": "iso_date",
            "weak_local_hint": "2026-02-19",
            "weak_local_hint_source": "prediction_path_date",
            "evidence_ref": "casp17/dossier.md",
            "operator_value": "",
            "operator_clearance": "",
            "notes": "manual",
        },
    ]


def _write_review_packet(tmp_path: Path, *, ready: bool) -> Path:
    intake_csv = tmp_path / "kit" / "no_leak_operator_intake.csv"
    _write_csv(intake_csv, _intake_rows())
    packet_json = tmp_path / "packet.json"
    _write_json(
        packet_json,
        {
            "summary": {
                "no_leak_operator_intake_csv": str(intake_csv),
            }
        },
    )
    status = (
        "first_clearance_no_leak_evidence_ready_for_operator_fill"
        if ready
        else "awaiting_first_clearance_no_leak_evidence_review"
    )
    review_rows = []
    for field_name, value in [("operator", "tester"), ("prediction_created_at", "2025-01-01")]:
        review_rows.append(
            {
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "field_name": field_name,
                "template_operator_value": value if ready else "",
                "template_operator_clearance": "clear" if ready else "",
                "template_operator_evidence_ref": f"evidence/{field_name}.md",
                "review_gate_status": (
                    "ready_for_no_leak_gate_operator_fill" if ready else "awaiting_operator_evidence"
                ),
                "first_blocker": "" if ready else "template_operator_value_missing",
            }
        )
    review_json = tmp_path / "review.json"
    _write_json(
        review_json,
        {
            "summary": {
                "first_clearance_no_leak_evidence_review_gate_status": status,
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "evidence_packet_json": str(packet_json),
            },
            "rows": review_rows,
        },
    )
    return review_json


def _args(tmp_path: Path, review_json: Path, *, mode: str = "dry_run") -> list[str]:
    return [
        "--review-gate-json",
        str(review_json),
        "--mode",
        mode,
        "--out-json",
        str(tmp_path / "sync.json"),
        "--out-csv",
        str(tmp_path / "sync.csv"),
        "--out-md",
        str(tmp_path / "SYNC.md"),
    ]


def test_no_leak_evidence_sync_plan_blocks_until_review_ready(tmp_path: Path) -> None:
    review_json = _write_review_packet(tmp_path, ready=False)

    args = mod.parse_args(_args(tmp_path, review_json))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["first_clearance_no_leak_evidence_sync_plan_status"] == (
        "awaiting_first_clearance_no_leak_evidence_review"
    )
    assert summary["action_count"] == 2
    assert summary["ready_action_count"] == 0
    assert summary["blocked_action_count"] == 2
    assert summary["review_ready_field_count"] == 0
    assert summary["review_blocked_field_count"] == 2
    assert payload["rows"][0]["action_status"] == "blocked_review_gate_not_ready"
    assert payload["rows"][0]["blocker"] == "template_operator_value_missing"
    assert (tmp_path / "SYNC.md").is_file()


def test_no_leak_evidence_sync_plan_ready_dry_run(tmp_path: Path) -> None:
    review_json = _write_review_packet(tmp_path, ready=True)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, review_json)))

    summary = payload["summary"]
    assert summary["first_clearance_no_leak_evidence_sync_plan_status"] == (
        "first_clearance_no_leak_evidence_sync_ready_dry_run"
    )
    assert summary["ready_action_count"] == 2
    assert summary["blocked_action_count"] == 0
    assert payload["rows"][0]["proposed_operator_value"] == "tester"
    assert payload["rows"][0]["evidence_ref_handling"] == (
        "preserve_intake_evidence_ref_review_packet_holds_operator_evidence"
    )


def test_no_leak_evidence_sync_plan_apply_updates_intake_values(tmp_path: Path) -> None:
    review_json = _write_review_packet(tmp_path, ready=True)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, review_json, mode="apply")))

    assert payload["summary"]["first_clearance_no_leak_evidence_sync_plan_status"] == (
        "first_clearance_no_leak_evidence_sync_applied"
    )
    assert payload["summary"]["applied_action_count"] == 2
    intake_csv = Path(payload["summary"]["destination_intake_csv"])
    if not intake_csv.is_absolute():
        intake_csv = Path.cwd() / intake_csv
    rows = list(csv.DictReader(intake_csv.open("r", encoding="utf-8")))
    assert rows[0]["operator_value"] == "tester"
    assert rows[0]["operator_clearance"] == "clear"
    assert rows[0]["evidence_ref"] == "casp17/dossier.md"
    assert rows[1]["operator_value"] == "2025-01-01"


def test_no_leak_evidence_sync_plan_blocks_missing_review_gate(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path, tmp_path / "missing_review.json")))

    assert payload["summary"]["first_clearance_no_leak_evidence_sync_plan_status"] == "blocked_missing_inputs"
    assert payload["summary"]["input_blockers"] == "review_gate_json_missing"
    assert payload["rows"] == []
