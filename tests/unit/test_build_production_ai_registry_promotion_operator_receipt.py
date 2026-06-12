from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_production_ai_registry_promotion_operator_receipt as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_receipt(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = [str(row.get(column, "")) for column in mod.REQUIRED_COLUMNS]
    path.write_text(",".join(mod.REQUIRED_COLUMNS) + "\n" + ",".join(values) + "\n", encoding="utf-8")


def _registry_summary(**overrides: object) -> dict:
    summary = {
        "status": "residual_model_registry_ready",
        "default_residual_mode": "shadow",
        "production_promotion_allowed": False,
        "customer_facing_auto_correction_allowed": False,
        "customer_facing_score_mutation_allowed": False,
        "customer_facing_ranking_mutation_allowed": False,
        "trained_model_checkpoint_count": 0,
        "external_state_mutated": False,
    }
    summary.update(overrides)
    return {"summary": summary}


def _checkpoint_summary(**overrides: object) -> dict:
    summary = {
        "status": "blocked_product_production_ai_checkpoint_readiness",
        "default_residual_mode": "shadow",
        "production_promotion_allowed": False,
        "customer_facing_auto_correction_allowed": False,
        "customer_facing_score_mutation_allowed": False,
        "customer_facing_ranking_mutation_allowed": False,
        "trained_model_checkpoint_count": 0,
        "registry_promotion_currently_satisfied": False,
        "registry_promotion_missing_gate_ids": [
            "production_promotion_allowed",
            "customer_facing_mutation_flags",
            "default_residual_mode_guarded",
            "trained_model_checkpoint_count_positive",
        ],
        "external_state_mutated": False,
    }
    summary.update(overrides)
    return {"summary": summary}


def test_registry_promotion_operator_receipt_blocks_placeholder_row(tmp_path: Path) -> None:
    receipt_csv = tmp_path / mod.DEFAULT_RECEIPT_CSV
    receipt_csv.parent.mkdir(parents=True, exist_ok=True)
    receipt_csv.write_text(
        (Path.cwd() / mod.DEFAULT_RECEIPT_CSV).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_json(tmp_path / mod.DEFAULT_REGISTRY_JSON, _registry_summary())
    _write_json(tmp_path / mod.DEFAULT_CHECKPOINT_READINESS_JSON, _checkpoint_summary())

    payload = mod.build_production_ai_registry_promotion_operator_receipt(root=tmp_path)

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "blocked_production_ai_registry_promotion_operator_receipt"
    assert summary["operator_receipt_ready"] is False
    assert summary["receipt_row_count"] == 1
    assert summary["blocked_row_count"] == 1
    assert summary["blocker_count"] == 1
    assert summary["approval_token_required"] == mod.APPROVAL_TOKEN
    assert summary["first_blocked_artifact_id"] == mod.ARTIFACT_ID
    assert summary["first_blocked_row_blocker"] == "operator_placeholders_unfilled"
    assert summary["most_common_row_blocker"] == "operator_placeholders_unfilled"
    assert summary["observed_registry_default_residual_mode"] == "shadow"
    assert summary["observed_registry_trained_model_checkpoint_count"] == 0
    assert summary["external_state_mutated"] is False
    assert row["row_status"] == "blocked"
    assert row["registry_edited_by_this_tool"] is False
    assert row["checkpoint_created_by_this_tool"] is False


def test_registry_promotion_operator_receipt_ready_when_registry_and_readiness_match(tmp_path: Path) -> None:
    receipt_csv = tmp_path / mod.DEFAULT_RECEIPT_CSV
    _write_receipt(
        receipt_csv,
        {
            "artifact_id": mod.ARTIFACT_ID,
            "operator_decision": "promote_guarded",
            "registry_artifact": mod.DEFAULT_REGISTRY_JSON,
            "checkpoint_readiness_artifact": mod.DEFAULT_CHECKPOINT_READINESS_JSON,
            "production_promotion_allowed": "true",
            "customer_facing_auto_correction_allowed": "true",
            "customer_facing_score_mutation_allowed": "true",
            "customer_facing_ranking_mutation_allowed": "true",
            "default_residual_mode": "production_guarded",
            "trained_model_checkpoint_count": "2",
            "registry_validation_command": "python3 tools/build_residual_model_registry.py",
            "validation_chain_reviewed": "true",
            "claim_boundary_reviewed": "true",
            "customer_facing_mutation_policy_reviewed": "true",
            "reviewer": "release-operator",
            "reviewed_at_utc": "2026-06-13T00:00:00Z",
            "approval_token": mod.APPROVAL_TOKEN,
            "external_state_mutated": "false",
            "operator_attestation": "reviewed_for_production_ai_registry_promotion",
            "notes": "local guarded promotion receipt",
        },
    )
    ready_fields = {
        "default_residual_mode": "production_guarded",
        "production_promotion_allowed": True,
        "customer_facing_auto_correction_allowed": True,
        "customer_facing_score_mutation_allowed": True,
        "customer_facing_ranking_mutation_allowed": True,
        "trained_model_checkpoint_count": 2,
        "registry_promotion_currently_satisfied": True,
        "registry_promotion_missing_gate_ids": [],
    }
    _write_json(tmp_path / mod.DEFAULT_REGISTRY_JSON, _registry_summary(**ready_fields))
    _write_json(tmp_path / mod.DEFAULT_CHECKPOINT_READINESS_JSON, _checkpoint_summary(**ready_fields))

    payload = mod.build_production_ai_registry_promotion_operator_receipt(root=tmp_path)

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "production_ai_registry_promotion_operator_receipt_ready"
    assert summary["operator_receipt_ready"] is True
    assert summary["pass_row_count"] == 1
    assert summary["blocked_row_count"] == 0
    assert summary["blocker_count"] == 0
    assert summary["observed_registry_default_residual_mode"] == "production_guarded"
    assert summary["observed_registry_trained_model_checkpoint_count"] == 2
    assert summary["observed_checkpoint_registry_promotion_currently_satisfied"] is True
    assert row["row_status"] == "pass"
    assert row["blockers"] == ""
    assert row["external_state_mutated"] is False
