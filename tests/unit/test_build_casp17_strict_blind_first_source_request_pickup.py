import csv
import json
from pathlib import Path

from tools import build_casp17_strict_blind_first_source_request_pickup as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _args(tmp_path: Path) -> list[str]:
    return [
        "--source-request-packet-json",
        str(tmp_path / "source_requests.json"),
        "--source-route-json",
        str(tmp_path / "source_route.json"),
        "--repair-feasibility-json",
        str(tmp_path / "repair_feasibility.json"),
        "--evidence-packet-json",
        str(tmp_path / "evidence_packet.json"),
        "--pickup-root",
        str(tmp_path / "pickup"),
        "--out-json",
        str(tmp_path / "pickup.json"),
        "--out-csv",
        str(tmp_path / "pickup.csv"),
        "--out-md",
        str(tmp_path / "PICKUP.md"),
    ]


def _write_inputs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "source_requests.json",
        {
            "summary": {
                "source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement",
                "first_request_id": "source_request_001",
            },
            "rows": [
                {
                    "request_id": "source_request_001",
                    "request_kind": "pre_native_prediction_source_required",
                    "request_status": "awaiting_pre_native_source_or_replacement",
                    "candidate_target_id": "HIST_BBA5",
                    "candidate_scope": "monomer",
                    "first_blocker": "prediction_not_before_native",
                    "current_prediction_pdb": "post_native_prediction.pdb",
                    "prediction_created_at": "2026-02-19",
                    "native_release_date": "2004-05-13",
                    "operator_template_csv": "source_request_001/operator_source_values_template.csv",
                    "next_action": "attach a prediction artifact created before native release",
                }
            ],
        },
    )
    _write_json(
        tmp_path / "source_route.json",
        {
            "summary": {
                "strict_blind_replacement_first_slot_source_route_board_status": (
                    "first_slot_requires_pre_native_monomer_source_or_replacement"
                ),
                "allowed_for_first_slot_count": 0,
                "in_scope_external_required_count": 10,
                "out_of_scope_route_count": 7,
            }
        },
    )
    _write_json(
        tmp_path / "repair_feasibility.json",
        {
            "summary": {
                "strict_blind_replacement_first_slot_repair_feasibility_board_status": (
                    "first_slot_current_local_candidate_source_required"
                ),
                "external_pre_native_artifact_required_target_count": 10,
            }
        },
    )
    _write_json(
        tmp_path / "evidence_packet.json",
        {
            "summary": {
                "first_unlock_evidence_packet_status": "awaiting_first_unlock_evidence_collection",
                "packet_folder": "packet/source_request_001_hist_bba5",
                "prediction_dropzone": "dropzones/replacement_prediction.pdb",
            }
        },
    )


def test_first_source_request_pickup_materializes_operator_packet(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["first_source_request_pickup_status"] == "first_source_request_requires_pre_native_source"
    assert summary["request_id"] == "source_request_001"
    assert summary["candidate_target_id"] == "HIST_BBA5"
    assert summary["current_prediction_before_native"] == "False"
    assert summary["pickup_option_count"] == 3
    assert summary["ready_option_count"] == 0
    assert summary["blocked_option_count"] == 3
    assert summary["first_action_id"] == "first_source_pickup_001"
    assert summary["first_blocker"] == "prediction_not_before_native"
    assert payload["rows"][0]["resolution_path"] == "acquire_pre_native_prediction_source"
    assert payload["rows"][1]["blocker"] == "no_allowed_first_slot_candidate"

    folder = Path(summary["pickup_folder"])
    assert folder.is_dir()
    assert (folder / "OPERATOR_PICKUP.md").is_file()
    decision_rows = list(csv.DictReader((folder / "operator_decision_template.csv").open("r", encoding="utf-8")))
    assert decision_rows[0]["field_key"] == "resolution_path"
    file_rows = list(csv.DictReader((folder / "required_files_manifest.csv").open("r", encoding="utf-8")))
    assert file_rows[1]["required_path_or_ref"] == "dropzones/replacement_prediction.pdb"


def test_first_source_request_pickup_blocks_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["first_source_request_pickup_status"] == "blocked_missing_inputs"
    assert "source_request_packet_json_missing" in payload["summary"]["input_blockers"]
    assert payload["rows"] == []
