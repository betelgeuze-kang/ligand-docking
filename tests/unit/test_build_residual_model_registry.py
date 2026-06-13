from __future__ import annotations

import json
from pathlib import Path

from tools import build_residual_model_registry as mod


def _shadow() -> dict[str, object]:
    return {
        "summary": {
            "status": "residual_shadow_ab_scaffold_ready",
            "residual_mode": "shadow",
            "raw_baseline_preserved": True,
            "no_customer_facing_ranking_change": True,
            "abstention_fields_present": True,
        }
    }


def _assist_gate() -> dict[str, object]:
    return {
        "summary": {
            "status": "residual_assist_promotion_gate_ready",
            "assist_promotion_allowed": True,
            "production_promotion_allowed": False,
        }
    }


def _gpcr_breadth_gate() -> dict[str, object]:
    return {
        "summary": {
            "status": "gpcr_residual_proof_breadth_gate_ready",
            "gpcr_residual_proof_breadth_gate_ready": True,
            "production_promotion_allowed": False,
        }
    }


def _public_assist_gate() -> dict[str, object]:
    return {
        "summary": {
            "status": "public_benchmark_residual_assist_comparison_gate_ready",
            "assist_comparison_gate_ready": True,
            "production_promotion_allowed": False,
        }
    }


def _checkpoint_preflight() -> dict[str, object]:
    return {
        "summary": {
            "status": "residual_production_checkpoint_preflight_ready",
            "checkpoint_preflight_ready": True,
            "candidate_checkpoint_count": 3,
            "ready_checkpoint_count": 2,
        }
    }


def _checkpoint_work_order() -> dict[str, object]:
    return {
        "summary": {
            "status": "residual_production_checkpoint_work_order_ready",
            "checkpoint_preflight_ready": True,
            "candidate_checkpoint_count": 3,
            "ready_checkpoint_count": 2,
        }
    }


def _blocked_checkpoint_preflight() -> dict[str, object]:
    return {
        "summary": {
            "status": "blocked_residual_production_checkpoint_preflight",
            "checkpoint_preflight_ready": False,
            "candidate_checkpoint_count": 3,
            "ready_checkpoint_count": 0,
            "primary_blocker": (
                "missing_output_fields:delta_energy,delta_force;"
                "missing_adapter_output_policy:delta_energy,delta_force;"
                "force_gpu_worker_return_receipt_not_ready"
            ),
        }
    }


def _blocked_checkpoint_sidecar() -> dict[str, object]:
    return {
        "summary": {
            "status": "blocked_residual_production_checkpoint_sidecar",
            "sidecar_ready": False,
            "checkpoint_path": "models/residual_production_score_model_current.pt",
            "blockers": [
                "production_output_heads_complete",
                "production_training_data_contract_ready",
                "force_gpu_return_receipt_ready",
            ],
            "missing_production_output_fields": ["delta_force"],
            "training_contract_missing_label_fields": ["delta_force"],
            "training_contract_missing_output_fields": ["delta_force"],
            "production_training_data_contract_ready": False,
            "force_gpu_return_receipt_ready": False,
            "force_gpu_return_receipt_operator_verified": False,
            "force_gpu_return_receipt_operator_verified_true_count": 0,
            "force_gpu_return_receipt_expected_queue_rows": 768,
        }
    }


def _build(**overrides: dict[str, object]) -> dict[str, object]:
    packets = {
        "residual_shadow_packet": _shadow(),
        "residual_assist_gate_packet": _assist_gate(),
        "gpcr_breadth_gate_packet": _gpcr_breadth_gate(),
        "public_assist_gate_packet": _public_assist_gate(),
    }
    packets.update(overrides)
    return mod.build_residual_model_registry(**packets)  # type: ignore[arg-type]


def _promotion_receipt_row(**overrides: object) -> dict[str, str]:
    row = {
        "artifact_id": mod.PROMOTION_RECEIPT_ARTIFACT_ID,
        "operator_decision": "promote_guarded",
        "registry_artifact": mod.DEFAULT_OUT_JSON,
        "checkpoint_readiness_artifact": "runs/product_production_ai_checkpoint_readiness_current.json",
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
        "approval_token": mod.PROMOTION_APPROVAL_TOKEN,
        "external_state_mutated": "false",
        "operator_attestation": "reviewed_for_production_ai_registry_promotion",
        "notes": "local guarded promotion receipt",
    }
    row.update({key: str(value) for key, value in overrides.items()})
    return row


def test_residual_model_registry_ready_with_shadow_default() -> None:
    payload = _build()

    summary = payload["summary"]
    assert summary["status"] == "residual_model_registry_ready"
    assert summary["product_model_layer_ready"] is True
    assert summary["default_residual_mode"] == "shadow"
    assert summary["production_promotion_allowed"] is False
    assert summary["customer_facing_auto_correction_allowed"] is False
    assert summary["customer_facing_score_mutation_allowed"] is False
    assert summary["customer_facing_ranking_mutation_allowed"] is False
    assert summary["checkpoint_preflight_ready"] is False
    assert summary["production_checkpoint_blocked"] is True
    assert summary["checkpoint_primary_blocker"] == "checkpoint_preflight_not_ready"
    assert summary["checkpoint_missing_output_fields"] == []
    assert summary["trained_model_checkpoint_count"] == 0
    assert summary["component_count"] == 6
    assert summary["required_output_fields_present"] is True
    assert any(row["display_name"] == "Physics Guard" for row in payload["rows"])
    assert any(row["display_name"] == "Uncertainty Abstainer" for row in payload["rows"])


def test_residual_model_registry_blocks_non_shadow_default() -> None:
    shadow = _shadow()
    shadow["summary"]["residual_mode"] = "assist"  # type: ignore[index]
    payload = _build(residual_shadow_packet=shadow)

    summary = payload["summary"]
    assert summary["status"] == "blocked_residual_model_registry"
    assert summary["product_model_layer_ready"] is False
    assert summary["residual_mode_policy_locked"] is False


def test_residual_model_registry_registers_checkpoint_without_auto_promotion() -> None:
    payload = _build(checkpoint_preflight_packet=_checkpoint_preflight())

    summary = payload["summary"]
    assert summary["status"] == "residual_model_registry_ready"
    assert summary["default_residual_mode"] == "shadow"
    assert summary["production_promotion_allowed"] is False
    assert summary["production_mode_allowed"] is False
    assert summary["registry_customer_facing_promotion_allowed"] is False
    assert summary["customer_facing_auto_correction_allowed"] is False
    assert summary["customer_facing_score_mutation_allowed"] is False
    assert summary["customer_facing_ranking_mutation_allowed"] is False
    assert summary["checkpoint_preflight_ready"] is True
    assert summary["production_checkpoint_blocked"] is False
    assert summary["checkpoint_primary_blocker"] == "none"
    assert summary["candidate_checkpoint_count"] == 3
    assert summary["trained_model_checkpoint_count"] == 2
    assert summary["ready_checkpoint_count"] == 2
    assert summary["registry_promotion_operator_approval_ready"] is False
    assert "operator_receipt_csv_missing" in summary["registry_promotion_operator_approval_blockers"]
    assert "Preflight-ready checkpoint is registered" in summary["next_required_step"]


def test_residual_model_registry_reads_work_order_checkpoint_evidence() -> None:
    payload = _build(
        checkpoint_preflight_packet={"summary": {"status": "residual_production_checkpoint_preflight_ready", "preflight_green": True}},
        checkpoint_work_order_packet=_checkpoint_work_order(),
    )

    summary = payload["summary"]
    assert summary["checkpoint_preflight_ready"] is True
    assert summary["candidate_checkpoint_count"] == 3
    assert summary["trained_model_checkpoint_count"] == 2
    assert summary["ready_checkpoint_count"] == 2
    assert summary["checkpoint_work_order_status"] == "residual_production_checkpoint_work_order_ready"
    assert summary["production_promotion_allowed"] is False


def test_residual_model_registry_promotes_only_with_operator_receipt() -> None:
    payload = _build(
        checkpoint_preflight_packet=_checkpoint_preflight(),
        promotion_operator_receipt_rows=[_promotion_receipt_row()],
        promotion_operator_receipt_present=True,
    )

    summary = payload["summary"]
    assert summary["default_residual_mode"] == "production_guarded"
    assert summary["production_promotion_allowed"] is True
    assert summary["production_mode_allowed"] is True
    assert summary["registry_customer_facing_promotion_allowed"] is True
    assert summary["customer_facing_auto_correction_allowed"] is True
    assert summary["customer_facing_score_mutation_allowed"] is True
    assert summary["customer_facing_ranking_mutation_allowed"] is True
    assert summary["trained_model_checkpoint_count"] == 2
    assert summary["registry_promotion_operator_approval_ready"] is True
    assert summary["registry_promotion_operator_approval_blockers"] == []


def test_residual_model_registry_surfaces_checkpoint_output_blockers() -> None:
    payload = _build(
        checkpoint_preflight_packet=_blocked_checkpoint_preflight(),
        checkpoint_sidecar_packet=_blocked_checkpoint_sidecar(),
    )

    summary = payload["summary"]
    assert summary["status"] == "residual_model_registry_ready"
    assert summary["product_model_layer_ready"] is True
    assert summary["default_residual_mode"] == "shadow"
    assert summary["production_promotion_allowed"] is False
    assert summary["customer_facing_auto_correction_allowed"] is False
    assert summary["customer_facing_score_mutation_allowed"] is False
    assert summary["customer_facing_ranking_mutation_allowed"] is False
    assert summary["production_checkpoint_blocked"] is True
    assert summary["checkpoint_primary_blocker"].startswith("missing_output_fields:delta_energy,delta_force")
    assert summary["checkpoint_missing_output_fields"] == ["delta_energy", "delta_force"]
    assert summary["checkpoint_missing_adapter_output_policy_fields"] == ["delta_energy", "delta_force"]
    assert summary["selected_sidecar_status"] == "blocked_residual_production_checkpoint_sidecar"
    assert summary["selected_sidecar_ready"] is False
    assert summary["selected_sidecar_checkpoint_path"] == "models/residual_production_score_model_current.pt"
    assert summary["selected_sidecar_missing_output_fields"] == ["delta_force"]
    assert summary["selected_sidecar_training_contract_ready"] is False
    assert summary["selected_sidecar_training_contract_missing_label_fields"] == ["delta_force"]
    assert summary["selected_sidecar_force_receipt_ready"] is False
    assert summary["selected_sidecar_force_receipt_operator_verified"] is False
    assert summary["selected_sidecar_force_receipt_operator_verified_true_count"] == 0
    assert summary["selected_sidecar_force_receipt_expected_queue_rows"] == 768
    assert "selected_sidecar_missing_output_fields=delta_force" in summary["selected_sidecar_detail"]
    assert "selected_sidecar_force_receipt_expected_queue_rows=768" in summary["production_promotion_blocked_reason"]
    assert "production checkpoint preflight is blocked" in summary["production_promotion_blocked_reason"]
    assert "force_gpu_worker_return_receipt_not_ready" in summary["production_promotion_blocked_reason"]


def test_residual_model_registry_cli_writes_outputs(tmp_path: Path) -> None:
    packet_paths: dict[str, Path] = {}
    for name, packet in {
        "shadow": _shadow(),
        "assist": _assist_gate(),
        "gpcr": _gpcr_breadth_gate(),
        "public": _public_assist_gate(),
    }.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(packet) + "\n", encoding="utf-8")
        packet_paths[name] = path

    out_json = tmp_path / "registry.json"
    out_csv = tmp_path / "registry.csv"
    out_md = tmp_path / "registry.md"
    missing_preflight = tmp_path / "missing_preflight.json"
    mod.main(
        [
            "--residual-shadow-json",
            str(packet_paths["shadow"]),
            "--residual-assist-gate-json",
            str(packet_paths["assist"]),
            "--gpcr-breadth-gate-json",
            str(packet_paths["gpcr"]),
            "--public-assist-gate-json",
            str(packet_paths["public"]),
            "--checkpoint-preflight-json",
            str(missing_preflight),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["product_model_layer_ready"] is True
    assert "component_id" in out_csv.read_text(encoding="utf-8")
    assert "Residual Model Registry" in out_md.read_text(encoding="utf-8")
