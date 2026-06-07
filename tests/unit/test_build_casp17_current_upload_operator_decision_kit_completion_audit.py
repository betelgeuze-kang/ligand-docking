import json
from pathlib import Path

from tools.casp17 import build_casp17_current_upload_operator_decision_kit as kit
from tools.casp17 import build_casp17_current_upload_operator_decision_kit_completion_audit as audit


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _review_row(rank: int, target_id: str, urgency: str = "today") -> dict:
    return {
        "queue_rank": rank,
        "target_id": target_id,
        "official_target_id": target_id,
        "review_status": "ready",
        "urgency": urgency,
        "official_human_expiration": "2026-06-02",
        "days_to_official_human_expiration": 0,
        "candidate_pdb": f"runs/casp17_predictions_sidechain_repacked_current/{target_id}TS.pdb",
        "candidate_sha256": f"sha_{target_id}",
        "object_count": 3,
        "chain_ids": "A,B,C",
        "review_md": f"casp17/current_upload_review_packet/{rank:02d}_{target_id.lower()}/UPLOAD_REVIEW.md",
    }


def _build_kit(tmp_path: Path) -> Path:
    review_json = tmp_path / "review.json"
    kit_json = tmp_path / "kit.json"
    _write_json(
        review_json,
        {
            "summary": {"review_packet_status": "current_upload_review_packet_ready"},
            "rows": [_review_row(1, "H2319"), _review_row(2, "T1342", urgency="soon")],
        },
    )
    args = kit.parse_args(
        [
            "--upload-review-packet-json",
            str(review_json),
            "--out-dir",
            str(tmp_path / "decision_kit"),
            "--existing-intake-csv",
            str(tmp_path / "missing_intake.csv"),
            "--out-json",
            str(kit_json),
            "--out-csv",
            str(tmp_path / "kit.csv"),
            "--out-md",
            str(tmp_path / "KIT.md"),
        ]
    )
    kit.write_outputs(args, kit.build_payload(args))
    return kit_json


def test_upload_operator_decision_kit_completion_audit_passes_file_surface(tmp_path: Path) -> None:
    kit_json = _build_kit(tmp_path)
    args = audit.parse_args(
        [
            "--decision-kit-json",
            str(kit_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ]
    )
    payload = audit.build_payload(args)
    audit.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["current_upload_operator_decision_kit_completion_audit_status"] == (
        "casp17_current_upload_operator_decision_kit_completion_audit_pass"
    )
    assert summary["decision_kit_status"] == "current_upload_operator_decision_kit_awaiting_operator_decisions"
    assert summary["review_packet_status"] == "current_upload_review_packet_ready"
    assert summary["review_target_count"] == 2
    assert summary["target_pass_count"] == 2
    assert summary["target_blocked_count"] == 0
    assert summary["root_file_present_count"] == 4
    assert summary["root_file_required_count"] == 4
    assert summary["intake_csv_row_count"] == 2
    assert summary["target_summary_csv_row_count"] == 2
    assert summary["per_target_csv_row_count"] == 2
    assert summary["decision_folder_present_count"] == 2
    assert summary["decision_md_present_count"] == 2
    assert summary["operator_decision_row_csv_present_count"] == 2
    assert summary["target_summary_csv_match_count"] == 2
    assert summary["operator_decision_missing_count"] == 2
    assert summary["invalid_operator_decision_count"] == 0
    assert summary["author_serialization_missing_count"] == 2
    assert summary["coordinate_copy_count"] == 0
    assert summary["proof_marker_count"] == 0
    assert summary["portal_submit_marker_count"] == 0
    assert (tmp_path / "AUDIT.md").is_file()


def test_upload_operator_decision_kit_completion_audit_blocks_row_mismatch(tmp_path: Path) -> None:
    kit_json = _build_kit(tmp_path)
    kit_payload = json.loads(kit_json.read_text(encoding="utf-8"))
    first_folder = Path(kit_payload["rows"][0]["decision_packet_folder"])
    row_csv = tmp_path / first_folder.relative_to(tmp_path) / "operator_decision_row.csv"
    row_csv.write_text("target_id\nWRONG\n", encoding="utf-8")

    payload = audit.build_payload(audit.parse_args(["--decision-kit-json", str(kit_json)]))

    assert payload["summary"]["current_upload_operator_decision_kit_completion_audit_status"] == (
        "blocked_current_upload_operator_decision_kit_completion_audit"
    )
    assert payload["summary"]["target_blocked_count"] == 1
    assert "operator_decision_row_csv_target_mismatch" in payload["rows"][0]["blockers"]


def test_upload_operator_decision_kit_completion_audit_blocks_missing_input(tmp_path: Path) -> None:
    payload = audit.build_payload(
        audit.parse_args(["--decision-kit-json", str(tmp_path / "missing_decision_kit.json")])
    )

    assert payload["summary"]["current_upload_operator_decision_kit_completion_audit_status"] == (
        "blocked_current_upload_operator_decision_kit_missing"
    )
    assert payload["summary"]["review_target_count"] == 0
