import json
from pathlib import Path

from tools.casp17 import build_casp17_current_escrow_external_timestamp_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _escrow_row(tmp_path: Path, target_id: str, queue_rank: int, urgency: str = "today") -> dict:
    escrow_md = tmp_path / "escrow" / target_id.lower() / "ESCROW.md"
    escrow_md.parent.mkdir(parents=True, exist_ok=True)
    escrow_md.write_text(f"# {target_id} escrow\n", encoding="utf-8")
    return {
        "target_id": target_id,
        "official_target_id": target_id,
        "protein_name": f"{target_id} protein",
        "queue_rank": queue_rank,
        "urgency": urgency,
        "upload_queue_status": "upload_ready_expiring_today" if urgency == "today" else "upload_ready_expiring_soon",
        "escrow_status": "prospective_escrow_ready_native_pending",
        "candidate_pdb": f"runs/casp17_predictions_sidechain_repacked_current/{target_id}TS.pdb",
        "candidate_sha256": f"sha_{target_id}",
        "candidate_size_bytes": 1234,
        "sha256_match": "True",
        "escrow_md": str(escrow_md),
        "review_md": f"casp17/current_upload_review_packet/{queue_rank:02d}_{target_id.lower()}/UPLOAD_REVIEW.md",
        "native_status": "official_native_release_pending",
        "external_timestamp_status": "external_timestamp_required",
        "competitive_proof_eligible": "false",
    }


def test_current_escrow_external_timestamp_packet_builds_ready_manifest(tmp_path: Path) -> None:
    escrow_json = tmp_path / "escrow.json"
    _write_json(
        escrow_json,
        {
            "summary": {
                "prospective_escrow_status": (
                    "current_prospective_strict_blind_escrow_ready_native_pending_partial_upload_window"
                ),
                "manifest_signature_sha256": "abc123",
            },
            "rows": [_escrow_row(tmp_path, "H2319", 1), _escrow_row(tmp_path, "T1342", 2, "soon")],
        },
    )
    args = mod.parse_args(
        [
            "--escrow-json",
            str(escrow_json),
            "--out-dir",
            str(tmp_path / "timestamp_packet"),
            "--out-json",
            str(tmp_path / "timestamp.json"),
            "--out-csv",
            str(tmp_path / "timestamp.csv"),
            "--out-md",
            str(tmp_path / "TIMESTAMP.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["current_escrow_external_timestamp_packet_status"] == (
        "current_escrow_external_timestamp_packet_ready_for_external_timestamp"
    )
    assert summary["target_count"] == 2
    assert summary["timestamp_ready_count"] == 2
    assert summary["timestamp_blocked_count"] == 0
    assert summary["upload_ready_count"] == 2
    assert summary["sha256_match_count"] == 2
    assert summary["escrow_md_present_count"] == 2
    assert summary["timestamp_manifest_row_count"] == 2
    assert summary["native_pending_count"] == 2
    assert summary["external_timestamp_required_count"] == 2
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert summary["coordinate_copy_count"] == 0
    assert summary["proof_marker_count"] == 0
    assert summary["portal_submit_marker_count"] == 0
    assert summary["first_ready_target_id"] == "H2319"
    assert summary["first_blocked_target_id"] == ""
    assert payload["rows"][0]["timestamp_action"] == "timestamp_now_expiring_today"
    assert payload["rows"][1]["timestamp_action"] == "timestamp_now_expiring_soon"
    assert (tmp_path / "timestamp_packet" / "TIMESTAMP_MANIFEST.csv").is_file()
    assert (tmp_path / "timestamp_packet" / "RERUN_COMMANDS.md").is_file()
    assert (tmp_path / "TIMESTAMP.md").is_file()


def test_current_escrow_external_timestamp_packet_blocks_broken_escrow_row(tmp_path: Path) -> None:
    row = _escrow_row(tmp_path, "H2319", 1)
    row["sha256_match"] = "False"
    row["escrow_md"] = str(tmp_path / "missing" / "ESCROW.md")
    escrow_json = tmp_path / "escrow.json"
    _write_json(
        escrow_json,
        {
            "summary": {"prospective_escrow_status": "current_prospective_strict_blind_escrow_partial"},
            "rows": [row],
        },
    )
    payload = mod.build_payload(mod.parse_args(["--escrow-json", str(escrow_json)]))

    assert payload["summary"]["current_escrow_external_timestamp_packet_status"] == (
        "blocked_current_escrow_external_timestamp_packet"
    )
    assert payload["summary"]["timestamp_ready_count"] == 0
    assert payload["summary"]["timestamp_blocked_count"] == 1
    assert payload["summary"]["first_blocked_target_id"] == "H2319"
    assert payload["summary"]["first_blocker"] == "sha256_not_verified"
    assert "escrow_md_missing" in payload["rows"][0]["blockers"]


def test_current_escrow_external_timestamp_packet_blocks_missing_escrow_payload(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(["--escrow-json", str(tmp_path / "missing.json")]))

    assert payload["summary"]["current_escrow_external_timestamp_packet_status"] == (
        "blocked_current_prospective_strict_blind_escrow_missing"
    )
    assert payload["summary"]["target_count"] == 0
    assert payload["summary"]["timestamp_ready_count"] == 0
