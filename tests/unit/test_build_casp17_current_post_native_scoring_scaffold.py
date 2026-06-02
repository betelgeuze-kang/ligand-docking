import json
from pathlib import Path

from tools import build_casp17_current_post_native_scoring_scaffold as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _escrow_row(target_id: str, rank: int, urgency: str = "today") -> dict:
    return {
        "target_id": target_id,
        "official_target_id": target_id,
        "protein_name": f"{target_id} protein",
        "queue_rank": rank,
        "urgency": urgency,
        "upload_queue_status": "upload_ready_expiring_today" if urgency == "today" else "upload_ready_expiring_soon",
        "escrow_status": "prospective_escrow_ready_native_pending",
        "candidate_pdb": f"runs/casp17_predictions_sidechain_repacked_current/{target_id}TS.pdb",
        "candidate_sha256": f"sha_{target_id}",
        "candidate_size_bytes": 1234,
        "sha256_match": "True",
        "escrow_md": f"casp17/current_prospective_strict_blind_escrow/{target_id.lower()}/ESCROW.md",
        "native_status": "official_native_release_pending",
        "competitive_proof_eligible": "false",
    }


def _timestamp_row(target_id: str) -> dict:
    return {
        "target_id": target_id,
        "timestamp_packet_status": "ready_for_external_timestamp",
        "timestamp_manifest_csv": "casp17/current_escrow_external_timestamp_packet/TIMESTAMP_MANIFEST.csv",
    }


def test_current_post_native_scoring_scaffold_builds_metric_surface(tmp_path: Path) -> None:
    escrow_json = tmp_path / "escrow.json"
    timestamp_json = tmp_path / "timestamp.json"
    _write_json(
        escrow_json,
        {
            "summary": {
                "prospective_escrow_status": "current_prospective_strict_blind_escrow_ready_native_pending",
                "manifest_signature_sha256": "abc123",
            },
            "rows": [_escrow_row("H2319", 1), _escrow_row("T1342", 2, "soon")],
        },
    )
    _write_json(
        timestamp_json,
        {
            "summary": {
                "current_escrow_external_timestamp_packet_status": (
                    "current_escrow_external_timestamp_packet_ready_for_external_timestamp"
                )
            },
            "rows": [_timestamp_row("H2319"), _timestamp_row("T1342")],
        },
    )
    args = mod.parse_args(
        [
            "--escrow-json",
            str(escrow_json),
            "--timestamp-packet-json",
            str(timestamp_json),
            "--out-dir",
            str(tmp_path / "scaffold"),
            "--out-json",
            str(tmp_path / "scaffold.json"),
            "--out-csv",
            str(tmp_path / "scaffold.csv"),
            "--metric-csv",
            str(tmp_path / "metrics.csv"),
            "--out-md",
            str(tmp_path / "SCAFFOLD.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["current_post_native_scoring_scaffold_status"] == (
        "current_post_native_scoring_scaffold_ready_native_pending"
    )
    assert summary["target_count"] == 2
    assert summary["target_ready_count"] == 2
    assert summary["target_blocked_count"] == 0
    assert summary["complex_target_count"] == 1
    assert summary["monomer_target_count"] == 1
    assert summary["upload_ready_count"] == 2
    assert summary["timestamp_ready_count"] == 2
    assert summary["native_pending_count"] == 2
    assert summary["native_file_present_count"] == 0
    assert summary["native_file_missing_count"] == 2
    assert summary["metric_row_count"] == 15
    assert summary["metric_ready_count"] == 0
    assert summary["metric_blocked_count"] == 15
    assert summary["complex_metric_row_count"] == 9
    assert summary["monomer_metric_row_count"] == 6
    assert summary["dropzone_count"] == 2
    assert summary["native_input_manifest_count"] == 2
    assert summary["chain_mapping_template_count"] == 2
    assert summary["metric_requirements_csv_count"] == 2
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["coordinate_copy_count"] == 0
    assert summary["proof_marker_count"] == 0
    assert summary["portal_submit_marker_count"] == 0
    assert summary["first_ready_target_id"] == "H2319"
    assert summary["first_blocked_target_id"] == ""
    assert payload["target_rows"][0]["metric_row_count"] == 9
    assert payload["target_rows"][1]["metric_row_count"] == 6
    assert {row["metric_name"] for row in payload["metric_rows"] if row["target_id"] == "H2319"} >= {
        "DockQ",
        "ICS",
        "IPS",
    }
    assert not any(row["metric_name"] == "DockQ" for row in payload["metric_rows"] if row["target_id"] == "T1342")
    assert (tmp_path / "scaffold" / "01_h2319" / "native_input_manifest.csv").is_file()
    assert (tmp_path / "scaffold" / "01_h2319" / "chain_mapping_template.csv").is_file()
    assert (tmp_path / "scaffold" / "01_h2319" / "metric_requirements.csv").is_file()
    assert (tmp_path / "scaffold" / "01_h2319" / "POST_NATIVE_SCORING.md").is_file()
    assert (tmp_path / "SCAFFOLD.md").is_file()


def test_current_post_native_scoring_scaffold_blocks_missing_timestamp(tmp_path: Path) -> None:
    escrow_json = tmp_path / "escrow.json"
    timestamp_json = tmp_path / "timestamp.json"
    row = _escrow_row("H2319", 1)
    row["sha256_match"] = "False"
    _write_json(
        escrow_json,
        {"summary": {"prospective_escrow_status": "current_prospective_strict_blind_escrow_partial"}, "rows": [row]},
    )
    _write_json(timestamp_json, {"summary": {}, "rows": []})
    payload = mod.build_payload(
        mod.parse_args(["--escrow-json", str(escrow_json), "--timestamp-packet-json", str(timestamp_json)])
    )

    assert payload["summary"]["current_post_native_scoring_scaffold_status"] == (
        "blocked_current_post_native_scoring_scaffold"
    )
    assert payload["summary"]["target_ready_count"] == 0
    assert payload["summary"]["target_blocked_count"] == 1
    assert payload["summary"]["first_blocked_target_id"] == "H2319"
    assert payload["summary"]["first_blocker"] == "sha256_not_verified"
    assert "external_timestamp_packet_not_ready" in payload["target_rows"][0]["blockers"]


def test_current_post_native_scoring_scaffold_blocks_missing_escrow(tmp_path: Path) -> None:
    payload = mod.build_payload(
        mod.parse_args(
            [
                "--escrow-json",
                str(tmp_path / "missing_escrow.json"),
                "--timestamp-packet-json",
                str(tmp_path / "missing_timestamp.json"),
            ]
        )
    )

    assert payload["summary"]["current_post_native_scoring_scaffold_status"] == (
        "blocked_current_prospective_strict_blind_escrow_missing"
    )
    assert payload["summary"]["target_count"] == 0
    assert payload["summary"]["metric_row_count"] == 0
