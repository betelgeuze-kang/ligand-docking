import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_source_request_fulfillment_gate as mod


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


def _write_template(path: Path, values: dict[str, str], evidence: dict[str, str]) -> None:
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
        for field in FIELDS:
            writer.writerow(
                {
                    "field_key": field,
                    "operator_value": values.get(field, ""),
                    "operator_evidence_ref": evidence.get(field, ""),
                    "required_format": "",
                    "source_request_note": "",
                }
            )


def test_source_request_fulfillment_gate_validates_ready_and_blocked_requests(tmp_path):
    pdb = tmp_path / "predictions" / "bba5_pre_native.pdb"
    pdb.parent.mkdir(parents=True, exist_ok=True)
    pdb.write_text(
        "ATOM      1  CA  GLY A   1       1.000   2.000   3.000  1.00 20.00           C\nEND\n",
        encoding="utf-8",
    )
    request_dir = tmp_path / "requests"
    ready_template = request_dir / "source_request_001" / "operator_source_values_template.csv"
    _write_template(
        ready_template,
        {
            "source_id": "internal_pre_native_bba5_2000",
            "prediction_pdb": str(pdb),
            "prediction_pdb_dropzone": "dropzone/replacement_prediction.pdb",
            "prediction_created_at": "2000-01-01",
            "native_release_date": "2004-05-13",
            "prediction_created_at/native_release_date": "true",
            "native_authority_ref": "rcsb:1T8J",
            "creation_evidence_ref": "ledger:created-before-native",
            "no_leak_evidence_ref": "ledger:no-leak",
            "method_summary": "internal physics pre-native archive",
            "operator_clearance": "approved",
        },
        {
            "source_id": "ledger:source",
            "prediction_pdb": "ledger:pdb",
            "prediction_created_at": "ledger:created",
            "native_release_date": "ledger:native",
            "native_authority_ref": "ledger:native-authority",
            "creation_evidence_ref": "ledger:created",
            "no_leak_evidence_ref": "ledger:no-leak",
            "method_summary": "ledger:method",
            "operator_clearance": "ledger:clearance",
        },
    )
    blocked_template = request_dir / "source_request_002" / "operator_source_values_template.csv"
    _write_template(blocked_template, {"source_id": "internal_bad"}, {"source_id": "ledger:source"})
    source_request_json = tmp_path / "source_request_packet.json"
    operator_packet_json = tmp_path / "operator_packet.json"
    _write_json(
        source_request_json,
        {
            "summary": {
                "source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement",
            },
            "rows": [
                {
                    "request_id": "source_request_001",
                    "candidate_target_id": "HIST_BBA5",
                    "candidate_scope": "monomer",
                    "request_kind": "pre_native_prediction_source_required",
                    "required_operator_fields": ",".join(FIELDS),
                    "request_folder": str(request_dir / "source_request_001"),
                    "operator_template_csv": str(ready_template),
                },
                {
                    "request_id": "source_request_002",
                    "candidate_target_id": "HIST_COMPLEX_01",
                    "candidate_scope": "complex",
                    "request_kind": "candidate_replacement_required",
                    "required_operator_fields": ",".join(FIELDS),
                    "request_folder": str(request_dir / "source_request_002"),
                    "operator_template_csv": str(blocked_template),
                },
            ],
        },
    )
    _write_json(
        operator_packet_json,
        {
            "summary": {
                "source_gate_operator_packet_status": "awaiting_source_gate_operator_values",
                "operator_csv": "operator/source_gate_operator_values.csv",
            }
        },
    )
    args = mod.parse_args(
        [
            "--source-request-packet-json",
            str(source_request_json),
            "--source-gate-operator-packet-json",
            str(operator_packet_json),
            "--out-json",
            str(tmp_path / "gate.json"),
            "--out-csv",
            str(tmp_path / "gate.csv"),
            "--out-md",
            str(tmp_path / "GATE.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["source_request_fulfillment_gate_status"] == "source_request_fulfillment_ready_partial"
    assert summary["ready_request_count"] == 1
    assert summary["blocked_request_count"] == 1
    assert summary["operator_field_filled_count"] == 12
    assert summary["operator_field_missing_count"] == 10
    assert summary["operator_evidence_ref_count"] == 10
    assert summary["operator_evidence_ref_missing_count"] == 8
    assert summary["prediction_pdb_valid_count"] == 1
    assert summary["chronology_pass_count"] == 1
    assert payload["rows"][0]["fulfillment_status"] == "ready_for_source_gate_operator_packet"
    assert payload["rows"][0]["prediction_pdb_atom_count"] == 1
    assert payload["rows"][1]["first_blocker"] == "candidate_replacement_required"
    assert (tmp_path / "GATE.md").is_file()


def test_source_request_fulfillment_gate_blocks_missing_inputs(tmp_path):
    args = mod.parse_args(
        [
            "--source-request-packet-json",
            str(tmp_path / "missing_source_requests.json"),
            "--source-gate-operator-packet-json",
            str(tmp_path / "missing_operator_packet.json"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["source_request_fulfillment_gate_status"] == "blocked_missing_inputs"
    assert "source_request_packet_json_missing" in payload["summary"]["input_blockers"]
    assert "source_gate_operator_packet_json_missing" in payload["summary"]["input_blockers"]
    assert payload["rows"] == []
