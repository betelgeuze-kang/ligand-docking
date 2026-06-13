from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_production_ai_registry_promotion_operator_staging_apply as mod
from tools.product.build_production_ai_registry_promotion_operator_receipt import (
    APPROVAL_TOKEN,
    ARTIFACT_ID,
    REQUIRED_COLUMNS,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in REQUIRED_COLUMNS})


def _receipt_row(*, filled: bool = False) -> dict[str, str]:
    row = {
        "artifact_id": ARTIFACT_ID,
        "operator_decision": "OPERATOR_FILL_DECISION",
        "registry_artifact": "runs/residual_model_registry_current.json",
        "checkpoint_readiness_artifact": "runs/product_production_ai_checkpoint_readiness_current.json",
        "production_promotion_allowed": "OPERATOR_CONFIRM_TRUE",
        "customer_facing_auto_correction_allowed": "OPERATOR_CONFIRM_TRUE",
        "customer_facing_score_mutation_allowed": "OPERATOR_CONFIRM_TRUE",
        "customer_facing_ranking_mutation_allowed": "OPERATOR_CONFIRM_TRUE",
        "default_residual_mode": "OPERATOR_FILL_PRODUCTION_GUARDED_MODE",
        "trained_model_checkpoint_count": "OPERATOR_FILL_POSITIVE_CHECKPOINT_COUNT",
        "registry_validation_command": (
            "python3 tools/build_residual_model_registry.py && "
            "python3 tools/build_product_production_ai_checkpoint_readiness.py"
        ),
        "validation_chain_reviewed": "OPERATOR_CONFIRM_TRUE",
        "claim_boundary_reviewed": "OPERATOR_CONFIRM_TRUE",
        "customer_facing_mutation_policy_reviewed": "OPERATOR_CONFIRM_TRUE",
        "reviewer": "OPERATOR_FILL_REVIEWER",
        "reviewed_at_utc": "OPERATOR_FILL_REVIEWED_AT_UTC",
        "approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
        "external_state_mutated": "false",
        "operator_attestation": "reviewed_for_production_ai_registry_promotion",
        "notes": "pending",
    }
    if filled:
        row.update(
            {
                "operator_decision": "promote_guarded",
                "production_promotion_allowed": "true",
                "customer_facing_auto_correction_allowed": "true",
                "customer_facing_score_mutation_allowed": "true",
                "customer_facing_ranking_mutation_allowed": "true",
                "default_residual_mode": "production_guarded",
                "trained_model_checkpoint_count": "2",
                "validation_chain_reviewed": "true",
                "claim_boundary_reviewed": "true",
                "customer_facing_mutation_policy_reviewed": "true",
                "reviewer": "operator",
                "reviewed_at_utc": "2026-06-13T00:00:00Z",
                "approval_token": APPROVAL_TOKEN,
            }
        )
    return row


def _write_registry_sources(root: Path, *, ready: bool = False) -> None:
    summary = {
        "status": "residual_model_registry_ready",
        "default_residual_mode": "production_guarded" if ready else "shadow",
        "production_promotion_allowed": ready,
        "customer_facing_auto_correction_allowed": ready,
        "customer_facing_score_mutation_allowed": ready,
        "customer_facing_ranking_mutation_allowed": ready,
        "trained_model_checkpoint_count": 2 if ready else 1,
    }
    checkpoint_summary = {
        "status": (
            "product_production_ai_checkpoint_readiness_ready"
            if ready
            else "blocked_product_production_ai_checkpoint_readiness"
        ),
        **summary,
        "registry_promotion_currently_satisfied": ready,
        "registry_promotion_missing_gate_ids": []
        if ready
        else [
            "default_residual_mode_guarded",
            "production_promotion_allowed",
            "customer_facing_mutation_flags",
        ],
    }
    _write_json(root / mod.DEFAULT_REGISTRY_JSON, {"summary": summary})
    _write_json(root / mod.DEFAULT_CHECKPOINT_READINESS_JSON, {"summary": checkpoint_summary})


def _write_field_worksheet(root: Path, *, pending_field_count: int = 13) -> None:
    _write_json(
        root / mod.DEFAULT_FIELD_WORKSHEET_JSON,
        {
            "summary": {
                "status": "production_ai_registry_promotion_operator_field_worksheet_ready",
                "operator_fill_pending_field_count": pending_field_count,
                "diagnostic_required_pending_field_count": 6 if pending_field_count else 0,
                "top_gate_id": "default_residual_mode_guarded",
                "top_priority_bucket": "guarded_residual_mode_selection_required",
            }
        },
    )


def test_registry_promotion_operator_staging_apply_blocks_placeholder_receipt(
    tmp_path: Path,
) -> None:
    _write_csv(tmp_path / mod.DEFAULT_STAGING_RECEIPT_CSV, [_receipt_row(filled=False)])
    _write_registry_sources(tmp_path, ready=False)
    _write_field_worksheet(tmp_path, pending_field_count=13)

    payload = mod.build_production_ai_registry_promotion_operator_staging_apply(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "blocked_production_ai_registry_promotion_operator_staging_apply"
    assert summary["candidate_receipt_ready"] is False
    assert summary["candidate_receipt_status"] == "blocked_production_ai_registry_promotion_operator_receipt"
    assert summary["candidate_pass_row_count"] == 0
    assert summary["candidate_blocked_row_count"] == 1
    assert summary["staging_placeholder_row_count"] == 1
    assert summary["candidate_first_blocked_artifact_id"] == ARTIFACT_ID
    assert summary["candidate_first_blocked_row_blocker"] == "operator_placeholders_unfilled"
    assert summary["field_worksheet_pending_field_count"] == 13
    assert summary["field_worksheet_diagnostic_required_pending_field_count"] == 6
    assert summary["candidate_observed_registry_default_residual_mode"] == "shadow"
    assert summary["candidate_observed_registry_trained_model_checkpoint_count"] == 1
    assert summary["live_copy_allowed"] is False
    assert summary["canonical_receipt_written"] is False
    assert summary["model_promoted"] is False
    assert summary["external_state_mutated"] is False
    assert "candidate_receipt_not_ready" in summary["blockers"]


def test_registry_promotion_operator_staging_apply_writes_candidate_when_receipt_passes(
    tmp_path: Path,
) -> None:
    _write_csv(tmp_path / mod.DEFAULT_STAGING_RECEIPT_CSV, [_receipt_row(filled=True)])
    _write_registry_sources(tmp_path, ready=True)
    _write_field_worksheet(tmp_path, pending_field_count=0)

    payload = mod.build_production_ai_registry_promotion_operator_staging_apply(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "production_ai_registry_promotion_operator_staging_preview_ready"
    assert summary["candidate_receipt_ready"] is True
    assert summary["candidate_pass_row_count"] == 1
    assert summary["candidate_blocked_row_count"] == 0
    assert summary["candidate_receipt_written"] is True
    assert summary["live_copy_allowed"] is False
    assert summary["canonical_receipt_written"] is False
    assert (tmp_path / mod.DEFAULT_CANDIDATE_RECEIPT_CSV).is_file()


def test_registry_promotion_operator_staging_apply_live_copy_requires_approval_token(
    tmp_path: Path,
) -> None:
    staging_csv = tmp_path / "runs/staging_registry_receipt.csv"
    live_csv = tmp_path / mod.DEFAULT_LIVE_RECEIPT_CSV
    _write_csv(staging_csv, [_receipt_row(filled=True)])
    _write_csv(live_csv, [_receipt_row(filled=False)])
    _write_registry_sources(tmp_path, ready=True)
    _write_field_worksheet(tmp_path, pending_field_count=0)

    blocked = mod.build_production_ai_registry_promotion_operator_staging_apply(
        staging_csv=staging_csv,
        live_receipt_csv=live_csv,
        mode="live_apply",
        write_canonical_receipt=True,
        root=tmp_path,
    )["summary"]
    assert blocked["canonical_receipt_written"] is False
    assert blocked["approval_token_accepted"] is False
    assert "write_canonical_receipt_approval_token_missing_or_invalid" in blocked["blockers"]

    applied = mod.build_production_ai_registry_promotion_operator_staging_apply(
        staging_csv=staging_csv,
        live_receipt_csv=live_csv,
        mode="live_apply",
        write_canonical_receipt=True,
        approval_token=APPROVAL_TOKEN,
        root=tmp_path,
    )["summary"]
    assert applied["status"] == "production_ai_registry_promotion_operator_receipt_canonical_written"
    assert applied["canonical_receipt_written"] is True
    assert applied["approval_token_accepted"] is True
    with live_csv.open("r", encoding="utf-8", newline="") as handle:
        live_rows = list(csv.DictReader(handle))
    assert live_rows[0]["operator_decision"] == "promote_guarded"
