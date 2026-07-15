from __future__ import annotations

import json
from pathlib import Path

from tools.product.ci_contract_fixture_packets import (
    write_license_decision_packets,
    write_restricted_production_ai_checkpoint_readiness_contract,
    write_restricted_self_hosted_commercial_packets,
)


def test_write_license_decision_packets_does_not_overwrite_commercial_gate(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    commercial_path = runs / "product_commercial_independence_gate_current.json"
    commercial_path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_product_commercial_independence_gate",
                    "dependency_provenance_manifest_present": True,
                    "reproducible_install_manifest_ready": True,
                    "local_self_hosted_api_cli_ready": True,
                    "blocker_count": 1,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    write_license_decision_packets(runs)

    payload = json.loads(commercial_path.read_text(encoding="utf-8"))
    assert payload["summary"]["dependency_provenance_manifest_present"] is True
    assert payload["summary"]["blocker_count"] == 1
    assert (runs / "product_license_decision_gate_current.json").is_file()


def test_write_restricted_self_hosted_commercial_packets_restores_readiness_fields(tmp_path: Path) -> None:
    runs = tmp_path / "runs"

    write_restricted_self_hosted_commercial_packets(runs)

    commercial = json.loads((runs / "product_commercial_independence_gate_current.json").read_text(encoding="utf-8"))
    release_bundle = json.loads((runs / "product_release_bundle_current.json").read_text(encoding="utf-8"))
    pilot = json.loads((runs / "product_pilot_packet_contract_current.json").read_text(encoding="utf-8"))
    image_smoke = json.loads((runs / "product_image_smoke_preflight_current.json").read_text(encoding="utf-8"))
    trajectory_sla = json.loads((runs / "product_trajectory_sla_contract_current.json").read_text(encoding="utf-8"))
    ai_graph = json.loads((runs / "product_ai_decision_graph_contract_current.json").read_text(encoding="utf-8"))
    ai_report = json.loads((runs / "product_ai_report_ux_contract_current.json").read_text(encoding="utf-8"))
    handoff = json.loads((runs / "product_commercial_readiness_handoff_bundle_current.json").read_text(encoding="utf-8"))

    assert commercial["summary"]["local_self_hosted_operation_ready"] is True
    assert commercial["summary"]["restricted_commercial_scope_claim_ready"] is True
    assert commercial["summary"]["commercial_claim_scope_tier"] == "restricted_family_local_product"
    assert commercial["summary"]["general_platform_claim_allowed"] is False
    assert commercial["summary"]["blocker_count"] == 0
    assert release_bundle["summary"]["release_bundle_ready"] is True
    assert release_bundle["summary"]["artifact_count"] == 34
    assert release_bundle["summary"]["check_count"] == 26
    assert release_bundle["summary"]["pass_count"] == 26
    assert release_bundle["summary"]["blocker_count"] == 0
    assert pilot["summary"]["delivery_ready_claim_allowed"] is True
    assert pilot["summary"]["bundle_assembled"] is True
    assert pilot["summary"]["bundle_validation_present"] is True
    assert pilot["summary"]["bundle_dir_exists"] is True
    assert image_smoke["summary"]["status"] == "blocked_product_image_smoke_preflight"
    assert image_smoke["summary"]["clean_container_smoke_ready"] is False
    assert image_smoke["summary"]["receipt_status"] == (
        "blocked_product_image_rocm_runtime_smoke"
    )
    assert image_smoke["summary"]["receipt_mode"] == "rocm-runtime"
    assert image_smoke["summary"]["product_runner_smoke_ready"] is False
    assert image_smoke["summary"]["validated_runner_namespace_runtime_qualified"] is False
    assert image_smoke["summary"]["customer_execution_enabled"] is False
    assert image_smoke["summary"][
        "validated_runner_namespace_runtime_receipt_verification_reason"
    ] == "receipt_path_missing"
    assert image_smoke["summary"]["blockers"] == [
        "validated_runner_namespace_runtime_unqualified"
    ]
    assert image_smoke["summary"]["container_runtime_rust_hip_backend_enabled"] is True
    assert image_smoke["summary"]["receipt_simulate_missing_profile_http"] == 422
    assert trajectory_sla["summary"]["required_families"] == ["gpcr", "ion_channel", "kinase"]
    assert trajectory_sla["summary"]["qualified_ready_families"] == ["gpcr", "ion_channel", "kinase"]
    assert trajectory_sla["summary"]["current_rocm_baseline_production_trajectory_profile_enabled"] is True
    assert trajectory_sla["summary"]["rocm_baseline_profile_gap_acknowledged"] is False
    assert len(trajectory_sla["rows"]) == trajectory_sla["summary"]["candidate_artifact_count"]
    assert ai_graph["summary"]["ordered_graph_path"] == [
        "structure_quality",
        "binding_site_context",
        "pose_generation_contract",
        "scoring_ranking_gate",
        "uncertainty_abstention_guard",
        "report_bundle_contract",
        "customer_report_ux",
    ]
    assert ai_graph["summary"]["node_count"] == len(ai_graph["rows"])
    assert ai_graph["summary"]["edge_count"] == len(ai_graph["edges"])
    assert ai_report["summary"]["customer_report_card"]["primary_abstention_reason"] == (
        "production_residual_checkpoint_not_promoted"
    )
    assert ai_report["summary"]["section_count"] == len(ai_report["rows"])
    assert handoff["summary"]["status"] == "product_commercial_readiness_handoff_bundle_ready"
    assert handoff["summary"]["handoff_bundle_ready"] is True
    assert handoff["summary"]["local_missing_artifact_reference_count"] == 0
    assert handoff["summary"]["production_ai_registry_promotion_operator_receipt_status"] == (
        "blocked_production_ai_registry_promotion_operator_receipt"
    )
    assert handoff["summary"]["production_ai_registry_promotion_priority_packet_ready"] is True


def test_write_capability_prerequisite_packets_restores_cleanup_completion_contract(tmp_path: Path) -> None:
    from tools.product.ci_contract_fixture_packets import write_capability_prerequisite_packets

    runs = tmp_path / "runs"

    write_capability_prerequisite_packets(runs)

    cleanup = json.loads((runs / "cleanup_completion_gate_current.json").read_text(encoding="utf-8"))
    summary = cleanup["summary"]
    assert summary["cleanup_complete"] is True
    assert summary["stage_count"] == 5
    assert summary["postcheck_contract_ready"] is True
    assert summary["postcheck_row_count"] == 5
    assert summary["postcheck_blocked_row_count"] == 0
    assert summary["approval_ready"] is True
    assert summary["transition_cleanup_complete"] is True
    assert summary["ligand_heavy_cleanup_complete"] is True
    assert summary["protected_policy_resolved"] is True

    orchestration = json.loads(
        (runs / "product_job_orchestration_contract_current.json").read_text(encoding="utf-8")
    )
    assert orchestration["summary"]["stale_worker_lease_recovery_ready"] is True
    assert orchestration["summary"]["stale_worker_lease_sweep_ready"] is True
    assert orchestration["summary"]["stale_worker_lease_detected_count"] == 1
    assert orchestration["summary"]["stale_worker_lease_updated_count"] == 1
    assert orchestration["summary"]["ready_check_count"] == orchestration["summary"]["check_count"]
    assert orchestration["summary"]["blocked_check_count"] == 0
    assert len(orchestration["rows"]) == orchestration["summary"]["check_count"]


def test_write_restricted_production_ai_checkpoint_readiness_contract_keeps_registry_only_blocker(
    tmp_path: Path,
) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    checkpoint = runs / "product_production_ai_checkpoint_readiness_current.json"
    checkpoint.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_product_production_ai_checkpoint_readiness",
                    "failed_check_ids": ["production_training_data_ready"],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    write_restricted_production_ai_checkpoint_readiness_contract(runs)

    summary = json.loads(checkpoint.read_text(encoding="utf-8"))["summary"]
    assert summary["fail_check_count"] == 1
    assert summary["failed_check_ids"] == ["registry_customer_facing_promotion_allowed"]
    assert summary["production_training_data_ready"] is True
    assert summary["production_inference_acceptance_blocked_stage_ids"] == [
        "registry_guarded_promotion_acceptance"
    ]
