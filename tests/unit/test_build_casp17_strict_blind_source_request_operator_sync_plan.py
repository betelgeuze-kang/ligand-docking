import csv
import json
from pathlib import Path

from tools import build_casp17_strict_blind_source_request_operator_sync_plan as mod


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
    path.write_text(json.dumps(payload), encoding="utf-8")


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


def _template(path: Path) -> None:
    _write_csv(
        path,
        [
            {
                "field_key": field,
                "operator_value": f"value_{field}",
                "operator_evidence_ref": f"evidence_{field}",
                "required_format": "",
                "source_request_note": "",
            }
            for field in FIELDS
        ],
        [
            "field_key",
            "operator_value",
            "operator_evidence_ref",
            "required_format",
            "source_request_note",
        ],
    )


def test_source_request_operator_sync_plan_builds_dry_run_actions(tmp_path):
    template_csv = tmp_path / "source_request_001" / "operator_source_values_template.csv"
    operator_csv = tmp_path / "source_gate_operator_values.csv"
    _template(template_csv)
    _write_csv(operator_csv, _operator_rows(), list(_operator_rows()[0].keys()))
    fulfillment_json = tmp_path / "fulfillment.json"
    operator_packet_json = tmp_path / "operator_packet.json"
    _write_json(
        fulfillment_json,
        {
            "summary": {
                "source_request_fulfillment_gate_status": "source_request_fulfillment_ready_partial",
                "ready_request_count": 1,
                "blocked_request_count": 1,
            },
            "rows": [
                {
                    "request_id": "source_request_001",
                    "candidate_target_id": "HIST_BBA5",
                    "request_kind": "pre_native_prediction_source_required",
                    "ready_for_operator_packet": "True",
                    "operator_template_csv": str(template_csv),
                }
            ],
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
    args = mod.parse_args(
        [
            "--fulfillment-gate-json",
            str(fulfillment_json),
            "--source-gate-operator-packet-json",
            str(operator_packet_json),
            "--out-json",
            str(tmp_path / "sync.json"),
            "--out-csv",
            str(tmp_path / "sync.csv"),
            "--out-md",
            str(tmp_path / "SYNC.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["source_request_operator_sync_plan_status"] == (
        "source_request_operator_sync_ready_dry_run"
    )
    assert payload["summary"]["sync_action_count"] == 11
    assert payload["summary"]["ready_sync_action_count"] == 11
    assert payload["summary"]["selected_request_id"] == "source_request_001"
    assert payload["rows"][0]["field_key"] == "source_id"
    assert payload["rows"][0]["proposed_operator_value"] == "value_source_id"
    assert (tmp_path / "SYNC.md").is_file()


def test_source_request_operator_sync_plan_blocks_without_ready_request(tmp_path):
    fulfillment_json = tmp_path / "fulfillment.json"
    operator_packet_json = tmp_path / "operator_packet.json"
    _write_json(
        fulfillment_json,
        {
            "summary": {
                "source_request_fulfillment_gate_status": "awaiting_source_request_operator_values",
                "ready_request_count": 0,
                "blocked_request_count": 17,
                "first_blocked_request_id": "source_request_001",
                "first_blocked_target_id": "HIST_BBA5",
                "first_blocker": "source_id_missing",
                "first_next_action": "fill operator_value for source_id",
            },
            "rows": [],
        },
    )
    _write_json(
        operator_packet_json,
        {
            "summary": {
                "source_gate_operator_packet_status": "awaiting_source_gate_operator_values",
                "operator_csv": "operator.csv",
            },
            "operator_rows": _operator_rows(),
        },
    )
    args = mod.parse_args(
        [
            "--fulfillment-gate-json",
            str(fulfillment_json),
            "--source-gate-operator-packet-json",
            str(operator_packet_json),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["source_request_operator_sync_plan_status"] == "awaiting_source_request_fulfillment"
    assert payload["summary"]["sync_action_count"] == 0
    assert payload["summary"]["first_blocker"] == "source_id_missing"
    assert payload["rows"][0]["action_status"] == "blocked_awaiting_source_request_fulfillment"


def test_source_request_operator_sync_plan_apply_updates_operator_csv(tmp_path):
    template_csv = tmp_path / "source_request_001" / "operator_source_values_template.csv"
    operator_csv = tmp_path / "source_gate_operator_values.csv"
    _template(template_csv)
    _write_csv(operator_csv, _operator_rows(), list(_operator_rows()[0].keys()))
    fulfillment_json = tmp_path / "fulfillment.json"
    operator_packet_json = tmp_path / "operator_packet.json"
    _write_json(
        fulfillment_json,
        {
            "summary": {"ready_request_count": 1, "blocked_request_count": 0},
            "rows": [
                {
                    "request_id": "source_request_001",
                    "candidate_target_id": "HIST_BBA5",
                    "request_kind": "pre_native_prediction_source_required",
                    "ready_for_operator_packet": "True",
                    "operator_template_csv": str(template_csv),
                }
            ],
        },
    )
    _write_json(
        operator_packet_json,
        {
            "summary": {"operator_csv": str(operator_csv)},
            "operator_rows": _operator_rows(),
        },
    )
    args = mod.parse_args(
        [
            "--fulfillment-gate-json",
            str(fulfillment_json),
            "--source-gate-operator-packet-json",
            str(operator_packet_json),
            "--mode",
            "apply",
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["source_request_operator_sync_plan_status"] == "source_request_operator_sync_applied"
    assert payload["summary"]["applied_sync_action_count"] == 11
    rows = list(csv.DictReader(operator_csv.open("r", encoding="utf-8")))
    assert rows[0]["operator_value"] == "value_source_id"
    assert rows[0]["operator_evidence_ref"] == "evidence_source_id"
