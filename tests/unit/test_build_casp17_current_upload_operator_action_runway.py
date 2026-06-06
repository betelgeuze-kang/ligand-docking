import json
from pathlib import Path

from tools.casp17 import build_casp17_current_upload_operator_action_runway as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _base_inputs(
    tmp_path: Path,
    *,
    operator_decision: str = "",
    author_serialization_status: str = "",
) -> tuple[Path, Path, Path, Path]:
    gate_json = tmp_path / "decision_rule_gate.json"
    decision_json = tmp_path / "decision_kit.json"
    audit_json = tmp_path / "decision_kit_completion_audit.json"
    lock_json = tmp_path / "active_manifest_lock.json"
    _write_json(
        gate_json,
        {
            "summary": {
                "upload_decision_rule_gate_status": (
                    "current_upload_decision_rule_gate_ready_for_operator_decisions"
                )
            },
            "rows": [
                {
                    "queue_rank": 1,
                    "target_id": "H1001",
                    "official_target_id": "H1001",
                    "urgency": "today",
                    "human_expiration": "2026-06-03",
                    "days_to_deadline": 0,
                    "technical_gate_status": "technical_upload_candidate",
                    "decision_rule_status": (
                        "awaiting_author_serialization"
                        if operator_decision == "approve" and not author_serialization_status
                        else "awaiting_operator_decision"
                    ),
                    "recommendation": "conditional_approve_after_operator_review_and_author_serialization",
                    "operator_decision": operator_decision,
                    "author_serialization_status": author_serialization_status,
                    "blockers": (
                        "author_serialization_missing"
                        if operator_decision == "approve" and not author_serialization_status
                        else "operator_decision_missing"
                    ),
                }
            ],
        },
    )
    _write_json(
        decision_json,
        {
            "summary": {
                "current_upload_operator_decision_kit_status": (
                    "current_upload_operator_decision_kit_awaiting_operator_decisions"
                )
            },
            "rows": [
                {
                    "queue_rank": 1,
                    "target_id": "H1001",
                    "official_target_id": "H1001",
                    "operator_decision": operator_decision,
                    "author_serialization_status": author_serialization_status,
                    "decision_md": "casp17/current_upload_operator_decision_kit/01_h1001/DECISION.md",
                    "review_md": "casp17/current_upload_review_packet/01_h1001/UPLOAD_REVIEW.md",
                    "candidate_pdb": "runs/casp17_predictions_sidechain_repacked_current/H1001TS.pdb",
                    "candidate_sha256": "abc123",
                    "object_count": 3,
                    "chain_ids": "A,B,C",
                }
            ],
        },
    )
    _write_json(
        audit_json,
        {
            "summary": {
                "current_upload_operator_decision_kit_completion_audit_status": (
                    "current_upload_operator_decision_kit_completion_audit_pass"
                )
            }
        },
    )
    _write_json(
        lock_json,
        {
            "summary": {
                "active_manifest_lock_status": "current_upload_active_manifest_lock_pass_stale_readonly"
            }
        },
    )
    return gate_json, decision_json, audit_json, lock_json


def _args(tmp_path: Path, paths: tuple[Path, Path, Path, Path]):
    gate_json, decision_json, audit_json, lock_json = paths
    return mod.parse_args(
        [
            "--decision-rule-gate-json",
            str(gate_json),
            "--operator-decision-kit-json",
            str(decision_json),
            "--operator-decision-kit-completion-audit-json",
            str(audit_json),
            "--active-manifest-lock-json",
            str(lock_json),
            "--out-json",
            str(tmp_path / "runway.json"),
            "--out-csv",
            str(tmp_path / "runway.csv"),
            "--out-md",
            str(tmp_path / "runway.md"),
        ]
    )


def test_operator_action_runway_marks_first_operator_decision_fill(tmp_path: Path) -> None:
    args = _args(tmp_path, _base_inputs(tmp_path))
    payload = mod.build_payload(args)
    mod._write_json(args.out_json, payload)
    mod._write_csv(args.out_csv, payload["rows"])
    mod._write_md(args.out_md, payload)

    assert payload["summary"]["operator_action_runway_status"] == (
        "current_upload_operator_action_runway_ready_for_human_decisions"
    )
    assert payload["summary"]["active_target_count"] == 1
    assert payload["summary"]["technical_upload_candidate_count"] == 1
    assert payload["summary"]["operator_decision_required_count"] == 1
    assert payload["summary"]["first_target_id"] == "H1001"
    assert payload["summary"]["first_action_status"] == "operator_decision_required"
    assert payload["rows"][0]["required_operator_fields"] == (
        "operator_decision,operator_id,operator_decision_ref,operator_notes_optional"
    )
    assert "operator_decision_required" in Path(args.out_md).read_text(encoding="utf-8")


def test_operator_action_runway_marks_approved_row_waiting_author_serialization(tmp_path: Path) -> None:
    payload = mod.build_payload(_args(tmp_path, _base_inputs(tmp_path, operator_decision="approve")))

    assert payload["summary"]["operator_action_runway_status"] == (
        "current_upload_operator_action_runway_awaiting_author_serialization"
    )
    assert payload["summary"]["operator_decision_required_count"] == 0
    assert payload["summary"]["author_serialization_required_count"] == 1
    assert payload["summary"]["approve_count"] == 1
    assert payload["rows"][0]["action_status"] == "author_serialization_required"
    assert payload["rows"][0]["required_operator_fields"] == "author_serialization_status,final_upload_filename"
