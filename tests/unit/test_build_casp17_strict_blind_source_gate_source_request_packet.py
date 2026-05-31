import json
from pathlib import Path

from tools import build_casp17_strict_blind_source_gate_source_request_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _route_payload() -> dict:
    return {
        "summary": {
            "strict_blind_replacement_first_slot_source_route_board_status": (
                "first_slot_requires_pre_native_monomer_source_or_replacement"
            ),
            "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
            "required_target_id": "REQUIRED_MONOMER_001",
            "required_scope": "monomer",
        },
        "rows": [
            {
                "route_id": "first_slot_source_route_001",
                "target_id": "HIST_BBA5",
                "scope": "monomer",
                "in_first_slot_scope": "True",
                "allowed_for_first_slot": "False",
                "candidate_status": "blocked_chronology_not_strict_blind",
                "route_status": "in_scope_current_candidate_disqualified_post_native",
                "first_blocker": "prediction_not_before_native",
                "prediction_created_at": "2026-02-19",
                "native_release_date": "2004-05-13",
                "external_required_action_count": 2,
            },
            {
                "route_id": "first_slot_source_route_002",
                "target_id": "HIST_COMPLEX_01",
                "scope": "complex",
                "in_first_slot_scope": "False",
                "allowed_for_first_slot": "False",
                "candidate_status": "blocked_scope",
                "route_status": "out_of_scope_for_monomer_slot",
                "first_blocker": "scope_mismatch",
                "external_required_action_count": 0,
            },
        ],
    }


def _candidate_payload() -> dict:
    return {
        "summary": {"strict_blind_replacement_first_slot_local_candidate_board_status": "first_slot_local_candidates_review_only"},
        "rows": [
            {
                "candidate_rank": 1,
                "target_id": "HIST_BBA5",
                "prediction_pdb": "runs/internal/bba5_model.pdb",
                "native_pdb": "casp17/native/bba5_native.pdb",
                "native_authority_ref": "rcsb:1T8J",
            },
            {
                "candidate_rank": 2,
                "target_id": "HIST_COMPLEX_01",
                "prediction_pdb": "runs/internal/complex_model.pdb",
                "native_pdb": "",
                "native_authority_ref": "",
            },
        ],
    }


def _operator_payload() -> dict:
    return {
        "summary": {
            "source_gate_operator_packet_status": "awaiting_source_gate_operator_values",
            "operator_csv": "casp17/source_gate_operator_values.csv",
        },
        "operator_rows": [
            {"field_key": "source_id"},
            {"field_key": "prediction_pdb"},
            {"field_key": "prediction_created_at"},
            {"field_key": "native_release_date"},
            {"field_key": "no_leak_evidence_ref"},
        ],
    }


def test_source_request_packet_turns_routes_into_operator_request_folders(tmp_path):
    route_json = tmp_path / "route.json"
    candidate_json = tmp_path / "candidate.json"
    operator_json = tmp_path / "operator.json"
    request_dir = tmp_path / "requests"
    _write_json(route_json, _route_payload())
    _write_json(candidate_json, _candidate_payload())
    _write_json(operator_json, _operator_payload())
    preserved_template = request_dir / "source_request_001" / "operator_source_values_template.csv"
    preserved_template.parent.mkdir(parents=True, exist_ok=True)
    preserved_template.write_text(
        "\n".join(
            [
                "field_key,operator_value,operator_evidence_ref,required_format,source_request_note",
                "source_id,internal_pre_native_bba5,ledger:001,,existing source",
                "prediction_pdb,,,,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    args = mod.parse_args(
        [
            "--source-route-json",
            str(route_json),
            "--operator-packet-json",
            str(operator_json),
            "--local-candidate-json",
            str(candidate_json),
            "--request-dir",
            str(request_dir),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "PACKET.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["source_request_packet_status"] == "awaiting_pre_native_source_or_candidate_replacement"
    assert summary["request_count"] == 2
    assert summary["pre_native_source_required_count"] == 1
    assert summary["candidate_replacement_required_count"] == 1
    assert summary["operator_template_ready_count"] == 0
    assert summary["operator_template_awaiting_count"] == 2
    assert summary["operator_field_filled_count"] == 1
    assert summary["operator_field_missing_count"] == 9
    assert summary["first_request_target_id"] == "HIST_BBA5"
    assert summary["first_missing_operator_field"] == "prediction_pdb"
    assert payload["rows"][0]["request_kind"] == "pre_native_prediction_source_required"
    assert payload["rows"][0]["operator_field_filled_count"] == 1
    assert payload["rows"][0]["operator_field_missing_count"] == 4
    assert payload["rows"][0]["required_operator_fields"] == (
        "source_id,prediction_pdb,prediction_created_at,native_release_date,no_leak_evidence_ref"
    )
    assert (tmp_path / "requests" / "source_request_001" / "SOURCE_REQUEST.md").is_file()
    assert (tmp_path / "requests" / "source_request_001" / "operator_source_values_template.csv").is_file()
    assert "internal_pre_native_bba5" in preserved_template.read_text(encoding="utf-8")


def test_source_request_packet_blocks_missing_inputs(tmp_path):
    args = mod.parse_args(
        [
            "--source-route-json",
            str(tmp_path / "missing_route.json"),
            "--operator-packet-json",
            str(tmp_path / "missing_operator.json"),
            "--local-candidate-json",
            str(tmp_path / "missing_candidate.json"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["source_request_packet_status"] == "blocked_missing_inputs"
    assert "source_route_json_missing" in payload["summary"]["input_blockers"]
    assert "operator_packet_json_missing" in payload["summary"]["input_blockers"]
    assert payload["rows"] == []
