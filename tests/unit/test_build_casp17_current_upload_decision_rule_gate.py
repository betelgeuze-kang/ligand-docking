import json
from pathlib import Path

from tools import build_casp17_current_upload_decision_rule_gate as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _base_inputs(tmp_path: Path, *, preflight_status: str = "ready") -> tuple[Path, Path, Path, Path, Path]:
    queue_json = tmp_path / "queue.json"
    review_json = tmp_path / "review.json"
    decision_json = tmp_path / "decision.json"
    lock_json = tmp_path / "lock.json"
    preflight_json = tmp_path / "preflight.json"
    sha = "abc123"
    _write_json(
        queue_json,
        {
            "summary": {"upload_queue_status": "official_verified_current_upload_queue_partial"},
            "rows": [
                {
                    "queue_rank": 1,
                    "target_id": "H1001",
                    "official_target_id": "H1001",
                    "official_human_expiration": "2026-06-03",
                    "candidate_sha256": sha,
                }
            ],
        },
    )
    _write_json(
        review_json,
        {
            "summary": {"review_packet_status": "current_upload_review_packet_ready"},
            "rows": [
                {
                    "queue_rank": 1,
                    "target_id": "H1001",
                    "review_status": "ready",
                    "urgency": "today",
                }
            ],
        },
    )
    _write_json(
        decision_json,
        {
            "summary": {"decision_kit_status": "current_upload_operator_decision_kit_awaiting_operator_decisions"},
            "rows": [
                {
                    "queue_rank": 1,
                    "target_id": "H1001",
                    "days_to_official_human_expiration": 0,
                    "candidate_sha256": sha,
                    "operator_decision": "",
                    "author_serialization_status": "",
                }
            ],
        },
    )
    _write_json(
        lock_json,
        {
            "summary": {"active_manifest_lock_status": "current_upload_active_manifest_lock_pass_stale_readonly"},
            "rows": [
                {
                    "queue_rank": 1,
                    "target_id": "H1001",
                    "row_kind": "active_upload_target",
                    "lock_status": "active_manifest_locked_awaiting_operator_decision",
                }
            ],
        },
    )
    _write_json(
        preflight_json,
        {
            "summary": {"current_package_preflight_status": "current_casp17_package_preflight_ready"},
            "rows": [
                {
                    "target_id": "H1001",
                    "candidate_sha256": sha,
                    "package_preflight_status": preflight_status,
                    "sidechain_repack_status": "pass",
                    "format_check_status": "pass",
                    "author_record_status": "author_present_redacted",
                }
            ],
        },
    )
    return queue_json, review_json, decision_json, lock_json, preflight_json


def _args(tmp_path: Path, paths: tuple[Path, Path, Path, Path, Path]):
    queue_json, review_json, decision_json, lock_json, preflight_json = paths
    return mod.parse_args(
        [
            "--upload-queue-json",
            str(queue_json),
            "--upload-review-packet-json",
            str(review_json),
            "--upload-operator-decision-kit-json",
            str(decision_json),
            "--upload-active-manifest-lock-json",
            str(lock_json),
            "--submission-package-preflight-json",
            str(preflight_json),
            "--out-json",
            str(tmp_path / "gate.json"),
            "--out-csv",
            str(tmp_path / "gate.csv"),
            "--out-md",
            str(tmp_path / "gate.md"),
        ]
    )


def test_upload_decision_rule_gate_marks_technical_candidate_awaiting_operator(tmp_path: Path) -> None:
    args = _args(tmp_path, _base_inputs(tmp_path))
    payload = mod.build_payload(args)
    mod._write_json(args.out_json, payload)
    mod._write_csv(args.out_csv, payload["rows"])
    mod._write_md(args.out_md, payload)

    assert payload["summary"]["upload_decision_rule_gate_status"] == (
        "current_upload_decision_rule_gate_ready_for_operator_decisions"
    )
    assert payload["summary"]["active_target_count"] == 1
    assert payload["summary"]["technical_upload_candidate_count"] == 1
    assert payload["summary"]["conditional_approve_after_operator_count"] == 1
    assert payload["summary"]["operator_decision_missing_count"] == 1
    assert payload["rows"][0]["technical_gate_status"] == "technical_upload_candidate"
    assert payload["rows"][0]["decision_rule_status"] == "awaiting_operator_decision"
    assert payload["rows"][0]["recommendation"] == (
        "conditional_approve_after_operator_review_and_author_serialization"
    )
    assert "operator_decision_missing" in Path(args.out_md).read_text(encoding="utf-8")


def test_upload_decision_rule_gate_blocks_failed_preflight(tmp_path: Path) -> None:
    payload = mod.build_payload(_args(tmp_path, _base_inputs(tmp_path, preflight_status="blocked")))

    assert payload["summary"]["upload_decision_rule_gate_status"] == (
        "current_upload_decision_rule_gate_technical_blocked"
    )
    assert payload["summary"]["technical_upload_candidate_count"] == 0
    assert payload["summary"]["technical_blocked_count"] == 1
    assert payload["rows"][0]["technical_gate_status"] == "technical_gate_blocked"
    assert "package_preflight_not_ready" in payload["rows"][0]["blockers"]
