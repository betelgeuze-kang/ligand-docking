import csv
import json
from pathlib import Path

from tools import build_casp17_current_upload_operator_decision_kit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mod.ROW_COLUMNS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _review_row(rank: int, target_id: str, urgency: str = "today", ready: bool = True) -> dict:
    return {
        "queue_rank": rank,
        "target_id": target_id,
        "official_target_id": target_id,
        "review_status": "ready" if ready else "blocked",
        "urgency": urgency,
        "official_human_expiration": "2026-06-02",
        "days_to_official_human_expiration": 0,
        "candidate_pdb": f"runs/casp17_predictions_sidechain_repacked_current/{target_id}TS.pdb",
        "candidate_sha256": f"sha_{target_id}",
        "object_count": 3,
        "chain_ids": "A,B,C",
        "review_md": f"casp17/current_upload_review_packet/{rank:02d}_{target_id.lower()}/UPLOAD_REVIEW.md",
    }


def test_upload_operator_decision_kit_collects_ready_reviews(tmp_path: Path) -> None:
    review_json = tmp_path / "review.json"
    _write_json(
        review_json,
        {
            "summary": {"review_packet_status": "current_upload_review_packet_ready"},
            "rows": [_review_row(1, "H2319"), _review_row(2, "T1342", urgency="soon")],
        },
    )
    args = mod.parse_args(
        [
            "--upload-review-packet-json",
            str(review_json),
            "--out-dir",
            str(tmp_path / "kit"),
            "--existing-intake-csv",
            str(tmp_path / "missing_intake.csv"),
            "--out-json",
            str(tmp_path / "kit.json"),
            "--out-csv",
            str(tmp_path / "kit.csv"),
            "--out-md",
            str(tmp_path / "KIT.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["current_upload_operator_decision_kit_status"] == (
        "current_upload_operator_decision_kit_awaiting_operator_decisions"
    )
    assert summary["review_target_count"] == 2
    assert summary["ready_review_count"] == 2
    assert summary["blocked_review_count"] == 0
    assert summary["operator_decision_missing_count"] == 2
    assert summary["author_serialization_missing_count"] == 2
    assert summary["urgency_today_count"] == 1
    assert summary["urgency_soon_count"] == 1
    assert summary["first_target_id"] == "H2319"
    assert summary["first_blocker"] == "operator_decision_missing"
    assert (tmp_path / "kit" / "operator_decision_intake.csv").is_file()
    assert (tmp_path / "kit" / "01_h2319" / "DECISION.md").is_file()
    assert (tmp_path / "KIT.md").is_file()


def test_upload_operator_decision_kit_preserves_existing_operator_decisions(tmp_path: Path) -> None:
    review_json = tmp_path / "review.json"
    existing_csv = tmp_path / "existing.csv"
    _write_json(
        review_json,
        {
            "summary": {"review_packet_status": "current_upload_review_packet_ready"},
            "rows": [_review_row(1, "H2319"), _review_row(2, "T1342")],
        },
    )
    _write_csv(
        existing_csv,
        [
            {
                "target_id": "H2319",
                "operator_decision": "approve",
                "operator_id": "operator_a",
                "operator_decision_ref": "review/H2319.md",
                "author_serialization_status": "author_serialized",
                "final_upload_filename": "H2319TS001_1",
            },
            {
                "target_id": "T1342",
                "operator_decision": "hold",
                "operator_id": "operator_a",
                "operator_decision_ref": "review/T1342.md",
                "author_serialization_status": "",
            },
        ],
    )
    payload = mod.build_payload(
        mod.parse_args(
            [
                "--upload-review-packet-json",
                str(review_json),
                "--existing-intake-csv",
                str(existing_csv),
            ]
        )
    )

    assert payload["summary"]["current_upload_operator_decision_kit_status"] == (
        "current_upload_operator_decision_kit_decision_ready"
    )
    assert payload["summary"]["approve_count"] == 1
    assert payload["summary"]["hold_count"] == 1
    assert payload["summary"]["operator_decision_missing_count"] == 0
    assert payload["summary"]["author_serialization_missing_count"] == 1
    assert payload["rows"][0]["operator_decision"] == "approve"
    assert payload["rows"][1]["operator_decision"] == "hold"


def test_upload_operator_decision_kit_blocks_missing_review_packet(tmp_path: Path) -> None:
    payload = mod.build_payload(
        mod.parse_args(["--upload-review-packet-json", str(tmp_path / "missing_review.json")])
    )

    assert payload["summary"]["current_upload_operator_decision_kit_status"] == (
        "blocked_current_upload_review_packet_missing"
    )
    assert payload["summary"]["review_target_count"] == 0
