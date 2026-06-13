from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_production_ai_registry_promotion_operator_field_worksheet as mod
from tools.product.build_production_ai_registry_promotion_operator_receipt import REQUIRED_COLUMNS


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_receipt_csv(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerow({column: row.get(column, "") for column in REQUIRED_COLUMNS})


def _registry_summary(**overrides: object) -> dict:
    summary = {
        "status": "residual_model_registry_ready",
        "default_residual_mode": "shadow",
        "production_promotion_allowed": False,
        "customer_facing_auto_correction_allowed": False,
        "customer_facing_score_mutation_allowed": False,
        "customer_facing_ranking_mutation_allowed": False,
        "trained_model_checkpoint_count": 1,
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
        "trained_model_checkpoint_count": 1,
        "registry_promotion_currently_satisfied": False,
        "registry_promotion_missing_gate_ids": [
            "production_promotion_allowed",
            "customer_facing_mutation_flags",
            "default_residual_mode_guarded",
        ],
        "external_state_mutated": False,
    }
    summary.update(overrides)
    return {"summary": summary}


def _receipt_summary(**overrides: object) -> dict:
    summary = {
        "status": "blocked_production_ai_registry_promotion_operator_receipt",
        "operator_receipt_ready": False,
        "external_state_mutated": False,
    }
    summary.update(overrides)
    return {"summary": summary}


def _priority_summary(**overrides: object) -> dict:
    summary = {
        "status": "blocked_production_ai_registry_promotion_priority_packet",
        "top_gate_id": "default_residual_mode_guarded",
        "top_priority_bucket": "guarded_residual_mode_selection_required",
        "top_required_input": "Set the guarded default residual mode.",
        "top_next_operator_step": "Fill the guarded promotion operator receipt.",
        "external_state_mutated": False,
    }
    summary.update(overrides)
    return {"summary": summary}


def _write_sources(tmp_path: Path, *, receipt_row: dict[str, str]) -> None:
    _write_receipt_csv(tmp_path / mod.DEFAULT_RECEIPT_CSV, receipt_row)
    _write_json(tmp_path / mod.DEFAULT_OPERATOR_RECEIPT_JSON, _receipt_summary())
    _write_json(tmp_path / mod.DEFAULT_REGISTRY_JSON, _registry_summary())
    _write_json(tmp_path / mod.DEFAULT_CHECKPOINT_READINESS_JSON, _checkpoint_summary())
    _write_json(tmp_path / mod.DEFAULT_PRIORITY_PACKET_JSON, _priority_summary())


def test_production_ai_registry_promotion_operator_field_worksheet_flags_pending_current_fields(
    tmp_path: Path,
) -> None:
    _write_sources(
        tmp_path,
        receipt_row={
            "artifact_id": mod.ARTIFACT_ID,
            "operator_decision": "OPERATOR_FILL_DECISION",
            "registry_artifact": mod.DEFAULT_REGISTRY_JSON,
            "checkpoint_readiness_artifact": mod.DEFAULT_CHECKPOINT_READINESS_JSON,
            "production_promotion_allowed": "OPERATOR_CONFIRM_TRUE",
            "customer_facing_auto_correction_allowed": "OPERATOR_CONFIRM_TRUE",
            "customer_facing_score_mutation_allowed": "OPERATOR_CONFIRM_TRUE",
            "customer_facing_ranking_mutation_allowed": "OPERATOR_CONFIRM_TRUE",
            "default_residual_mode": "OPERATOR_FILL_PRODUCTION_GUARDED_MODE",
            "trained_model_checkpoint_count": "OPERATOR_FILL_POSITIVE_CHECKPOINT_COUNT",
            "registry_validation_command": "python3 tools/build_residual_model_registry.py",
            "validation_chain_reviewed": "OPERATOR_CONFIRM_TRUE",
            "claim_boundary_reviewed": "OPERATOR_CONFIRM_TRUE",
            "customer_facing_mutation_policy_reviewed": "OPERATOR_CONFIRM_TRUE",
            "reviewer": "OPERATOR_FILL_REVIEWER",
            "reviewed_at_utc": "OPERATOR_FILL_REVIEWED_AT_UTC",
            "approval_token": "OPERATOR_FILL_APPROVAL_TOKEN",
            "external_state_mutated": "false",
            "operator_attestation": "reviewed_for_production_ai_registry_promotion",
            "notes": "pending",
        },
    )

    payload = mod.build_production_ai_registry_promotion_operator_field_worksheet(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "production_ai_registry_promotion_operator_field_worksheet_ready"
    assert summary["field_worksheet_ready"] is True
    assert summary["operator_fill_complete"] is False
    assert summary["worksheet_field_row_count"] == 20
    assert summary["required_receipt_field_count"] == 19
    assert summary["operator_fill_pending_field_count"] == 13
    assert summary["diagnostic_required_field_count"] == 6
    assert summary["diagnostic_required_pending_field_count"] == 6
    assert summary["top_gate_id"] == "default_residual_mode_guarded"
    assert summary["observed_registry_default_residual_mode"] == "shadow"
    assert summary["observed_registry_trained_model_checkpoint_count"] == 1
    assert summary["approval_token_required"] == mod.APPROVAL_TOKEN
    assert summary["model_promoted"] is False
    assert summary["customer_facing_mutation_enabled"] is False
    assert summary["external_state_mutated"] is False
    pending = [row for row in payload["rows"] if row["field_status"] == "operator_fill_pending"]
    assert {row["field_name"] for row in pending} == set(summary["pending_field_names"])
    assert any(row["field_name"] == "default_residual_mode" for row in pending)


def test_production_ai_registry_promotion_operator_field_worksheet_can_be_fill_complete(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / mod.DEFAULT_REGISTRY_JSON,
        _registry_summary(
            default_residual_mode="production_guarded",
            production_promotion_allowed=True,
            customer_facing_auto_correction_allowed=True,
            customer_facing_score_mutation_allowed=True,
            customer_facing_ranking_mutation_allowed=True,
            trained_model_checkpoint_count=2,
        ),
    )
    _write_json(
        tmp_path / mod.DEFAULT_CHECKPOINT_READINESS_JSON,
        _checkpoint_summary(
            default_residual_mode="production_guarded",
            production_promotion_allowed=True,
            customer_facing_auto_correction_allowed=True,
            customer_facing_score_mutation_allowed=True,
            customer_facing_ranking_mutation_allowed=True,
            trained_model_checkpoint_count=2,
            registry_promotion_currently_satisfied=True,
            registry_promotion_missing_gate_ids=[],
        ),
    )
    _write_json(
        tmp_path / mod.DEFAULT_OPERATOR_RECEIPT_JSON,
        _receipt_summary(
            status="production_ai_registry_promotion_operator_receipt_ready",
            operator_receipt_ready=True,
        ),
    )
    _write_json(
        tmp_path / mod.DEFAULT_PRIORITY_PACKET_JSON,
        _priority_summary(
            status="production_ai_registry_promotion_priority_packet_ready",
            top_gate_id="trained_model_checkpoint_count_positive",
            top_priority_bucket="gate_satisfied",
        ),
    )
    _write_receipt_csv(
        tmp_path / mod.DEFAULT_RECEIPT_CSV,
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
            "reviewer": "operator",
            "reviewed_at_utc": "2026-06-13T00:00:00Z",
            "approval_token": mod.APPROVAL_TOKEN,
            "external_state_mutated": "false",
            "operator_attestation": "reviewed_for_production_ai_registry_promotion",
            "notes": "reviewed",
        },
    )

    payload = mod.build_production_ai_registry_promotion_operator_field_worksheet(root=tmp_path)
    summary = payload["summary"]

    assert summary["operator_fill_complete"] is True
    assert summary["operator_fill_pending_field_count"] == 0
    assert summary["diagnostic_required_pending_field_count"] == 0
    assert summary["invalid_field_count"] == 0
    assert all(row["operator_input_required"] is False for row in payload["rows"])


def test_production_ai_registry_promotion_operator_field_worksheet_cli_writes_outputs(
    tmp_path: Path,
) -> None:
    out_json = tmp_path / "worksheet.json"
    out_csv = tmp_path / "worksheet.csv"
    out_md = tmp_path / "worksheet.md"

    mod.main(["--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "production_ai_registry_promotion_operator_field_worksheet_ready"
    assert "field_status" in out_csv.read_text(encoding="utf-8")
    assert "Production AI Registry Promotion Operator Field Worksheet" in out_md.read_text(
        encoding="utf-8"
    )
