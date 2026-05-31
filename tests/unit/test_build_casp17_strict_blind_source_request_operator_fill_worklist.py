import csv
import json
from pathlib import Path

from tools import build_casp17_strict_blind_source_request_operator_fill_worklist as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_template(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "field_key",
                "operator_value",
                "operator_evidence_ref",
                "required_format",
                "source_request_note",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def test_source_request_operator_fill_worklist_expands_templates(tmp_path):
    request_dir = tmp_path / "requests"
    template_1 = request_dir / "source_request_001" / "operator_source_values_template.csv"
    template_2 = request_dir / "source_request_002" / "operator_source_values_template.csv"
    _write_template(
        template_1,
        [
            {
                "field_key": "source_id",
                "operator_value": "internal_source_001",
                "operator_evidence_ref": "ledger:source",
                "required_format": "",
                "source_request_note": "",
            },
            {
                "field_key": "prediction_pdb",
                "operator_value": "",
                "operator_evidence_ref": "",
                "required_format": "",
                "source_request_note": "",
            },
        ],
    )
    _write_template(
        template_2,
        [
            {
                "field_key": "source_id",
                "operator_value": "",
                "operator_evidence_ref": "",
                "required_format": "",
                "source_request_note": "",
            }
        ],
    )
    source_request_json = tmp_path / "source_requests.json"
    fulfillment_json = tmp_path / "fulfillment.json"
    _write_json(
        source_request_json,
        {
            "summary": {"source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement"},
            "rows": [
                {
                    "request_id": "source_request_001",
                    "candidate_target_id": "HIST_BBA5",
                    "candidate_scope": "monomer",
                    "request_kind": "pre_native_prediction_source_required",
                    "required_operator_fields": "source_id,prediction_pdb",
                    "operator_template_csv": str(template_1),
                },
                {
                    "request_id": "source_request_002",
                    "candidate_target_id": "HIST_COMPLEX_01",
                    "candidate_scope": "complex",
                    "request_kind": "candidate_replacement_required",
                    "required_operator_fields": "source_id",
                    "operator_template_csv": str(template_2),
                },
            ],
        },
    )
    _write_json(
        fulfillment_json,
        {"summary": {"source_request_fulfillment_gate_status": "awaiting_source_request_operator_values"}},
    )
    args = mod.parse_args(
        [
            "--source-request-packet-json",
            str(source_request_json),
            "--fulfillment-gate-json",
            str(fulfillment_json),
            "--out-json",
            str(tmp_path / "worklist.json"),
            "--out-csv",
            str(tmp_path / "worklist.csv"),
            "--out-md",
            str(tmp_path / "WORKLIST.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["source_request_operator_fill_worklist_status"] == "awaiting_source_request_operator_values"
    assert summary["field_action_count"] == 3
    assert summary["field_ready_count"] == 1
    assert summary["operator_value_missing_count"] == 2
    assert summary["operator_evidence_missing_count"] == 2
    assert summary["candidate_replacement_field_count"] == 1
    assert summary["first_field_key"] == "prediction_pdb"
    assert payload["rows"][0]["fill_status"] == "field_ready_for_fulfillment_gate"
    assert payload["rows"][1]["fill_status"] == "awaiting_operator_value"
    assert payload["rows"][2]["fill_status"] == "blocked_candidate_replacement_required"
    assert (tmp_path / "WORKLIST.md").is_file()


def test_source_request_operator_fill_worklist_blocks_missing_inputs(tmp_path):
    args = mod.parse_args(
        [
            "--source-request-packet-json",
            str(tmp_path / "missing_source_requests.json"),
            "--fulfillment-gate-json",
            str(tmp_path / "missing_fulfillment.json"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["source_request_operator_fill_worklist_status"] == "blocked_missing_inputs"
    assert "source_request_packet_json_missing" in payload["summary"]["input_blockers"]
    assert "fulfillment_gate_json_missing" in payload["summary"]["input_blockers"]
    assert payload["rows"] == []
