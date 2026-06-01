import csv
import json
from pathlib import Path

from tools import build_casp17_strict_blind_first_unlock_evidence_sync_plan as mod


FIELDS = [
    "source_id",
    "prediction_pdb",
    "prediction_pdb_dropzone",
    "prediction_created_at",
    "native_release_date",
    "prediction_created_at/native_release_date",
    "native_authority_ref",
    "creation_evidence_ref",
    "no_leak_evidence_ref",
    "method_summary",
    "operator_clearance",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _operator_rows() -> list[dict]:
    return [
        {
            "field_key": field,
            "fill_kind": "manifest_value",
            "operator_value": "",
            "operator_evidence_ref": "",
            "required_format": "",
            "current_value": "",
            "destination": "manifest.csv",
            "blocked_checks": "",
            "operator_status": "awaiting_operator_value",
            "next_action": f"fill {field}",
        }
        for field in FIELDS
    ]


def _review_rows(*, ready: bool) -> list[dict]:
    return [
        {
            "field_key": field,
            "review_gate_status": "field_ready_for_source_gate_sync" if ready else "awaiting_operator_evidence",
            "template_operator_value": f"value_{field}" if ready else "",
            "template_operator_evidence_ref": f"evidence_{field}.md" if ready else f"stub_{field}.md",
            "template_operator_clearance": "clear" if ready else "",
            "template_operator_id": "operator_a" if ready else "",
            "first_blocker": "" if ready else "template_operator_value_missing",
            "next_action": "sync" if ready else f"fill operator_value for {field}",
        }
        for field in FIELDS
    ]


def _write_inputs(tmp_path: Path, *, ready: bool) -> tuple[Path, Path, Path]:
    operator_csv = tmp_path / "source_gate_operator_values.csv"
    _write_csv(operator_csv, _operator_rows(), list(_operator_rows()[0].keys()))
    review_json = tmp_path / "review.json"
    operator_packet_json = tmp_path / "operator_packet.json"
    _write_json(
        review_json,
        {
            "summary": {
                "first_unlock_evidence_review_gate_status": (
                    "first_unlock_evidence_ready_for_source_gate_sync"
                    if ready
                    else "awaiting_first_unlock_evidence_review"
                ),
                "request_id": "source_request_001",
                "candidate_target_id": "HIST_BBA5",
                "ready_field_count": 11 if ready else 0,
                "blocked_field_count": 0 if ready else 11,
            },
            "rows": _review_rows(ready=ready),
        },
    )
    _write_json(
        operator_packet_json,
        {
            "summary": {
                "source_gate_operator_packet_status": "awaiting_source_gate_operator_values",
                "operator_csv": str(operator_csv),
            },
            "operator_rows": _operator_rows(),
        },
    )
    return review_json, operator_packet_json, operator_csv


def _args(tmp_path: Path, review_json: Path, operator_packet_json: Path, *extra: str) -> list[str]:
    return [
        "--review-gate-json",
        str(review_json),
        "--source-gate-operator-packet-json",
        str(operator_packet_json),
        "--out-json",
        str(tmp_path / "sync.json"),
        "--out-csv",
        str(tmp_path / "sync.csv"),
        "--out-md",
        str(tmp_path / "SYNC.md"),
        *extra,
    ]


def test_first_unlock_evidence_sync_plan_blocks_until_review_gate_ready(tmp_path: Path) -> None:
    review_json, operator_packet_json, _operator_csv = _write_inputs(tmp_path, ready=False)

    args = mod.parse_args(_args(tmp_path, review_json, operator_packet_json))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["first_unlock_evidence_sync_plan_status"] == "awaiting_first_unlock_evidence_review"
    assert summary["action_count"] == 11
    assert summary["ready_action_count"] == 0
    assert summary["blocked_action_count"] == 11
    assert summary["first_action_id"] == "first_unlock_evidence_sync_001"
    assert summary["first_blocked_field"] == "source_id"
    assert summary["first_blocker"] == "template_operator_value_missing"
    assert payload["rows"][0]["action_status"] == "blocked_review_gate_not_ready"
    assert (tmp_path / "SYNC.md").is_file()


def test_first_unlock_evidence_sync_plan_builds_ready_dry_run(tmp_path: Path) -> None:
    review_json, operator_packet_json, _operator_csv = _write_inputs(tmp_path, ready=True)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, review_json, operator_packet_json)))

    summary = payload["summary"]
    assert summary["first_unlock_evidence_sync_plan_status"] == "first_unlock_evidence_sync_ready_dry_run"
    assert summary["action_count"] == 11
    assert summary["ready_action_count"] == 11
    assert summary["blocked_action_count"] == 0
    assert summary["request_id"] == "source_request_001"
    assert summary["candidate_target_id"] == "HIST_BBA5"
    assert payload["rows"][0]["field_key"] == "source_id"
    assert payload["rows"][0]["proposed_operator_value"] == "value_source_id"
    assert payload["rows"][0]["source_operator_evidence_ref"] == "evidence_source_id.md"


def test_first_unlock_evidence_sync_plan_apply_updates_operator_csv(tmp_path: Path) -> None:
    review_json, operator_packet_json, operator_csv = _write_inputs(tmp_path, ready=True)

    args = mod.parse_args(_args(tmp_path, review_json, operator_packet_json, "--mode", "apply"))
    payload = mod.build_payload(args)

    assert payload["summary"]["first_unlock_evidence_sync_plan_status"] == "first_unlock_evidence_sync_applied"
    assert payload["summary"]["applied_action_count"] == 11
    rows = list(csv.DictReader(operator_csv.open("r", encoding="utf-8", newline="")))
    assert rows[0]["operator_value"] == "value_source_id"
    assert rows[0]["operator_evidence_ref"] == "evidence_source_id.md"


def test_first_unlock_evidence_sync_plan_blocks_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(
        mod.parse_args(_args(tmp_path, tmp_path / "missing_review.json", tmp_path / "missing_operator.json"))
    )

    assert payload["summary"]["first_unlock_evidence_sync_plan_status"] == "blocked_missing_inputs"
    assert payload["summary"]["input_blockers"] == (
        "review_gate_json_missing,source_gate_operator_packet_json_missing"
    )
    assert payload["rows"] == []
