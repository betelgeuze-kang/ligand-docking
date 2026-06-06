from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_monomer_pre_native_acquisition_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path) -> list[str]:
    return [
        "--source-request-packet-json",
        str(tmp_path / "source_requests.json"),
        "--internal-like-source-review-json",
        str(tmp_path / "internal_like.json"),
        "--internal-source-audit-json",
        str(tmp_path / "source_audit.json"),
        "--board-dir",
        str(tmp_path / "board"),
        "--out-json",
        str(tmp_path / "board.json"),
        "--out-csv",
        str(tmp_path / "board.csv"),
        "--out-md",
        str(tmp_path / "BOARD.md"),
    ]


def _source_request(
    request_id: str,
    target_id: str,
    *,
    scope: str = "monomer",
    kind: str = "pre_native_prediction_source_required",
) -> dict:
    return {
        "candidate_scope": scope,
        "candidate_target_id": target_id,
        "first_blocker": "prediction_not_before_native",
        "native_release_date": "2004-05-13",
        "operator_field_filled_count": 0,
        "operator_field_missing_count": 11,
        "operator_template_csv": f"requests/{request_id}/operator_source_values_template.csv",
        "prediction_created_at": "2026-02-19",
        "request_folder": f"requests/{request_id}",
        "request_id": request_id,
        "request_kind": kind,
        "request_status": "awaiting_pre_native_source_or_replacement",
        "route_status": "in_scope_current_candidate_disqualified_post_native",
    }


def _write_inputs(tmp_path: Path, *, pre_native_count: int = 0) -> None:
    _write_json(
        tmp_path / "source_requests.json",
        {
            "summary": {
                "source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement"
            },
            "rows": [
                _source_request("source_request_001", "HIST_BBA5"),
                _source_request(
                    "source_request_011",
                    "HIST_COMPLEX",
                    scope="complex",
                    kind="candidate_replacement_required",
                ),
            ],
        },
    )
    _write_json(
        tmp_path / "internal_like.json",
        {
            "summary": {
                "internal_like_source_review_status": "strict_blind_internal_like_source_review_all_post_native",
                "post_native_blocked_count": 16,
                "pre_native_candidate_count": pre_native_count,
                "target_all_post_native_count": 1 if pre_native_count == 0 else 0,
                "target_pre_native_candidate_count": 1 if pre_native_count else 0,
            },
            "target_rows": [
                {
                    "post_native_count": 16,
                    "pre_native_count": pre_native_count,
                    "request_id": "source_request_001",
                }
            ],
        },
    )
    _write_json(
        tmp_path / "source_audit.json",
        {
            "summary": {
                "internal_prediction_source_audit_status": "internal_prediction_source_missing_for_first_slot"
            },
            "rows": [
                {
                    "evidence_ref": "place prediction_pdb evidence at casp17/dropzone/replacement_prediction.pdb",
                    "source_id": "required_prediction_dropzone",
                }
            ],
        },
    )


def test_monomer_pre_native_acquisition_board_writes_operator_acquisition_folders(tmp_path: Path) -> None:
    _write_inputs(tmp_path, pre_native_count=0)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["monomer_pre_native_acquisition_board_status"] == (
        "strict_blind_monomer_pre_native_acquisition_required"
    )
    assert summary["monomer_request_count"] == 1
    assert summary["ready_pre_native_local_candidate_count"] == 0
    assert summary["acquisition_required_count"] == 1
    assert summary["internal_like_pre_native_candidate_count"] == 0
    assert summary["internal_like_post_native_candidate_count"] == 16
    assert summary["operator_field_missing_count"] == 11
    assert summary["first_slot_prediction_dropzone"] == "casp17/dropzone/replacement_prediction.pdb"

    row = payload["rows"][0]
    assert row["acquisition_status"] == "awaiting_pre_native_artifact_operator_acquisition"
    assert row["local_pre_native_candidate_count"] == 0
    assert row["local_post_native_candidate_count"] == 16
    assert Path(row["acquisition_folder"]).name == "01_source_request_001_hist_bba5"

    written_rows = _read_csv(tmp_path / "board.csv")
    assert len(written_rows) == 1
    folder = tmp_path / "board" / "01_source_request_001_hist_bba5"
    assert (folder / "ACQUISITION.md").is_file()
    assert (folder / "operator_acquisition_template.csv").is_file()
    assert (folder / "required_artifacts.csv").is_file()
    assert "Claim Boundary" in (tmp_path / "BOARD.md").read_text(encoding="utf-8")


def test_monomer_pre_native_acquisition_board_marks_local_pre_native_review_available(tmp_path: Path) -> None:
    _write_inputs(tmp_path, pre_native_count=2)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["monomer_pre_native_acquisition_board_status"] == (
        "strict_blind_monomer_pre_native_candidates_available_for_operator_review"
    )
    assert payload["summary"]["ready_pre_native_local_candidate_count"] == 1
    assert payload["summary"]["acquisition_required_count"] == 0
    assert payload["rows"][0]["acquisition_status"] == "operator_review_pre_native_local_candidate_available"


def test_monomer_pre_native_acquisition_board_blocks_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["monomer_pre_native_acquisition_board_status"] == "blocked_missing_input"
    assert "source_request_packet_json_missing" in payload["summary"]["input_blockers"]
    assert payload["rows"] == []
