from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_production_ai_registry_promotion_priority_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


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


def _workbench_summary(**overrides: object) -> dict:
    summary = {
        "status": "blocked_product_production_ai_promotion_workbench",
        "production_ai_promotion_ready": False,
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


def _operator_receipt_summary(**overrides: object) -> dict:
    summary = {
        "status": "blocked_production_ai_registry_promotion_operator_receipt",
        "operator_receipt_ready": False,
        "first_blocked_row_blocker": "operator_placeholders_unfilled",
        "approval_token_required": mod.APPROVAL_TOKEN,
        "external_state_mutated": False,
    }
    summary.update(overrides)
    return {"summary": summary}


def test_production_ai_registry_promotion_priority_packet_blocks_current_registry_promotion() -> None:
    payload = mod.build_production_ai_registry_promotion_priority_packet()
    summary = payload["summary"]

    assert summary["status"] == "blocked_production_ai_registry_promotion_priority_packet"
    assert summary["priority_packet_ready"] is True
    assert summary["registry_promotion_ready"] is False
    assert summary["operator_receipt_ready"] is False
    assert summary["operator_receipt_status"] == "blocked_production_ai_registry_promotion_operator_receipt"
    assert summary["priority_item_count"] == 4
    assert summary["operator_input_required_count"] == 3
    assert summary["blocked_priority_item_count"] == 3
    assert summary["required_gate_count"] == 4
    assert summary["registry_promotion_missing_gate_ids"] == [
        "default_residual_mode_guarded",
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
    ]
    assert summary["top_gate_id"] == "default_residual_mode_guarded"
    assert summary["top_priority_bucket"] == "guarded_residual_mode_selection_required"
    assert summary["top_acceptance_artifact"] == mod.DEFAULT_REGISTRY_JSON
    assert summary["top_verification_command"] == mod.REGISTRY_PROMOTION_RECHECK_COMMAND
    assert "build_product_production_ai_promotion_workbench.py" in summary[
        "top_verification_command"
    ]
    assert "build_production_ai_registry_promotion_operator_receipt.py" in summary[
        "top_verification_command"
    ]
    assert "build_production_ai_registry_promotion_priority_packet.py" in summary[
        "top_verification_command"
    ]
    assert summary["observed_registry_default_residual_mode"] == "shadow"
    assert summary["observed_registry_trained_model_checkpoint_count"] == 1
    assert summary["observed_registry_production_promotion_allowed"] is False
    assert summary["observed_registry_customer_facing_mutation_flags_ready"] is False
    assert summary["observed_checkpoint_registry_promotion_currently_satisfied"] is False
    assert summary["approval_token_required"] == mod.APPROVAL_TOKEN
    assert "registry_promotion_operator_priority_items_pending" in summary["blockers"]
    assert summary["model_promoted"] is False
    assert summary["customer_facing_mutation_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert payload["rows"][0]["gate_id"] == "trained_model_checkpoint_count_positive"
    assert payload["rows"][0]["operator_input_required"] is False
    assert "No new checkpoint registration is required" in payload["rows"][0]["required_input"]
    assert "already satisfied" in payload["rows"][0]["next_operator_step"]
    assert payload["rows"][1]["priority_bucket"] == "guarded_residual_mode_selection_required"
    assert payload["rows"][1]["verification_command"] == mod.REGISTRY_PROMOTION_RECHECK_COMMAND
    assert "operator receipt" in payload["rows"][1]["next_operator_step"]
    assert payload["rows"][2]["priority_bucket"] == "blocked_until_guarded_registry_ready"
    assert payload["rows"][3]["priority_bucket"] == "blocked_until_production_promotion_allowed"
    assert all(row["external_state_mutated"] is False for row in payload["rows"])
    assert all(row["model_promoted"] is False for row in payload["rows"])


def test_production_ai_registry_promotion_priority_packet_keeps_checkpoint_repair_when_missing(
    tmp_path: Path,
) -> None:
    (tmp_path / mod.DEFAULT_OPERATOR_RECEIPT_CSV).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / mod.DEFAULT_OPERATOR_RECEIPT_CSV).write_text("artifact_id\n", encoding="utf-8")
    _write_json(tmp_path / mod.DEFAULT_OPERATOR_RECEIPT_JSON, _operator_receipt_summary())
    _write_json(tmp_path / mod.DEFAULT_REGISTRY_JSON, _registry_summary())
    _write_json(tmp_path / mod.DEFAULT_CHECKPOINT_READINESS_JSON, _checkpoint_summary())
    _write_json(tmp_path / mod.DEFAULT_PROMOTION_WORKBENCH_JSON, _workbench_summary())

    payload = mod.build_production_ai_registry_promotion_priority_packet(root=tmp_path)
    summary = payload["summary"]
    checkpoint_row = payload["rows"][0]

    assert summary["top_gate_id"] == "trained_model_checkpoint_count_positive"
    assert summary["top_priority_bucket"] == "trained_checkpoint_registration_required"
    assert checkpoint_row["gate_satisfied"] is False
    assert checkpoint_row["operator_input_required"] is True
    assert "Register a trained production residual checkpoint" in checkpoint_row["required_input"]
    assert "Return or register a trained checkpoint" in checkpoint_row["next_operator_step"]


def test_production_ai_registry_promotion_priority_packet_ready_when_all_gates_match(
    tmp_path: Path,
) -> None:
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
    (tmp_path / mod.DEFAULT_OPERATOR_RECEIPT_CSV).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / mod.DEFAULT_OPERATOR_RECEIPT_CSV).write_text("artifact_id\n", encoding="utf-8")
    _write_json(
        tmp_path / mod.DEFAULT_OPERATOR_RECEIPT_JSON,
        _operator_receipt_summary(
            status="production_ai_registry_promotion_operator_receipt_ready",
            operator_receipt_ready=True,
            first_blocked_row_blocker="",
        ),
    )
    _write_json(tmp_path / mod.DEFAULT_REGISTRY_JSON, _registry_summary(**ready_fields))
    _write_json(tmp_path / mod.DEFAULT_CHECKPOINT_READINESS_JSON, _checkpoint_summary(**ready_fields))
    _write_json(tmp_path / mod.DEFAULT_PROMOTION_WORKBENCH_JSON, _workbench_summary(**ready_fields))

    payload = mod.build_production_ai_registry_promotion_priority_packet(root=tmp_path)
    summary = payload["summary"]

    assert summary["status"] == "production_ai_registry_promotion_priority_packet_ready"
    assert summary["priority_packet_ready"] is True
    assert summary["registry_promotion_ready"] is True
    assert summary["operator_receipt_ready"] is True
    assert summary["operator_input_required_count"] == 0
    assert summary["blocked_priority_item_count"] == 0
    assert summary["registry_promotion_missing_gate_ids"] == []
    assert summary["blockers"] == []
    assert summary["observed_registry_default_residual_mode"] == "production_guarded"
    assert summary["observed_registry_trained_model_checkpoint_count"] == 2
    assert summary["observed_checkpoint_registry_promotion_currently_satisfied"] is True
    assert all(row["priority_bucket"] == "gate_satisfied" for row in payload["rows"])
    assert all(row["operator_input_required"] is False for row in payload["rows"])


def test_production_ai_registry_promotion_priority_packet_cli_writes_outputs(tmp_path: Path) -> None:
    out_json = tmp_path / "priority.json"
    out_csv = tmp_path / "priority.csv"
    out_md = tmp_path / "priority.md"

    mod.main(["--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "blocked_production_ai_registry_promotion_priority_packet"
    assert "priority_bucket" in out_csv.read_text(encoding="utf-8")
    assert "Production AI Registry Promotion Priority Packet" in out_md.read_text(encoding="utf-8")
