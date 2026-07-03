from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _artifact_summary(name: str) -> dict:
    path = ROOT / "runs" / name
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _artifact_payload(name: str) -> dict:
    path = ROOT / "runs" / name
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def test_api_product_router_is_registered_when_fastapi_is_available() -> None:
    pytest.importorskip("fastapi")
    main = importlib.import_module("api.main")
    product = importlib.import_module("api.product")
    product_architecture = importlib.import_module("api.product_architecture")
    product_benchmark = importlib.import_module("api.product_benchmark")
    product_capabilities = importlib.import_module("api.product_capabilities")
    product_docking = importlib.import_module("api.product_docking")
    product_service_contracts = importlib.import_module("api.product_service_contracts")
    product_operational = importlib.import_module("api.product_operational")
    product_release_ops = importlib.import_module("api.product_release_ops")
    product_ai_surface = importlib.import_module("api.product_ai_surface")
    product_cameo_runner = importlib.import_module("api.product_cameo_runner")
    product_license = importlib.import_module("api.product_license")
    product_production_ai = importlib.import_module("api.product_production_ai")
    product_scope = importlib.import_module("api.product_scope")
    product_commercial_readiness = importlib.import_module("api.product_commercial_readiness")
    product_evidence_goal = importlib.import_module("api.product_evidence_goal")
    product_hbond_backmap = importlib.import_module("api.product_hbond_backmap")
    product_gpcr_hard_decoy = importlib.import_module("api.product_gpcr_hard_decoy")
    product_pocketmd_lite = importlib.import_module("api.product_pocketmd_lite")

    paths = {route.path for route in main.app.routes}
    architecture_router_paths = {route.path for route in product_architecture.router.routes}
    benchmark_router_paths = {route.path for route in product_benchmark.router.routes}
    capability_router_paths = {route.path for route in product_capabilities.router.routes}
    docking_router_paths = {route.path for route in product_docking.router.routes}
    service_contract_router_paths = {route.path for route in product_service_contracts.router.routes}
    operational_router_paths = {route.path for route in product_operational.router.routes}
    release_ops_router_paths = {route.path for route in product_release_ops.router.routes}
    ai_surface_router_paths = {route.path for route in product_ai_surface.router.routes}
    cameo_runner_router_paths = {route.path for route in product_cameo_runner.router.routes}
    license_router_paths = {route.path for route in product_license.router.routes}
    production_ai_router_paths = {route.path for route in product_production_ai.router.routes}
    scope_router_paths = {route.path for route in product_scope.router.routes}
    commercial_readiness_router_paths = {route.path for route in product_commercial_readiness.router.routes}
    evidence_goal_router_paths = {route.path for route in product_evidence_goal.router.routes}
    hbond_backmap_router_paths = {route.path for route in product_hbond_backmap.router.routes}
    pocketmd_lite_router_paths = {route.path for route in product_pocketmd_lite.router.routes}
    assert "/product/capabilities" in paths
    assert "/product/hbond-backmap-report" in paths
    assert "/product/hbond-backmap-report" in hbond_backmap_router_paths
    assert "/product/gpcr-hard-decoy-suite-report" in paths
    assert "/product/gpcr-hard-decoy-suite-report" in {
        route.path for route in product_gpcr_hard_decoy.router.routes
    }
    assert "/product/pocketmd-lite-report" in paths
    assert "/product/pocketmd-lite-report" in pocketmd_lite_router_paths
    assert "/product/pocketmd-lite-remaining-evidence-queue" in paths
    assert "/product/pocketmd-lite-remaining-evidence-queue" in pocketmd_lite_router_paths
    assert "/product/pocketmd-lite-candidate-metric-fill-preview-report" in paths
    assert "/product/pocketmd-lite-candidate-metric-fill-preview-report" in pocketmd_lite_router_paths
    assert "/product/pocketmd-lite-topk-refinement-audit" in paths
    assert "/product/pocketmd-lite-topk-refinement-audit" in pocketmd_lite_router_paths
    assert "/product/architecture" in paths
    assert "/product/architecture-validation" in paths
    assert "/product/service-boundary" in paths
    assert "/product/api-contract" in paths
    assert "/product/operational-quality" in paths
    assert "/product/security-deployment-contract" in paths
    assert "/product/rollout-execution-smoke-receipt" in paths
    assert "/product/public-benchmark" in paths
    assert "/product/public-benchmark-external-receipts-audit" in paths
    assert "/product/public-benchmark-external-receipts-audit" in benchmark_router_paths
    assert "/product/job-orchestration-contract" in paths
    assert "/product/trajectory-sla-contract" in paths
    assert "/product/api-runner-profile-promotion-operator-receipt" in paths
    assert "/product/api-runner-profile-promotion-operator-staging-apply" in paths
    assert "/product/ai-decision-graph" in paths
    assert "/product/ai-report-ux" in paths
    assert "/product/cameo-live-validation" in paths
    assert "/product/cameo-official-result-fetch-preflight" in paths
    assert "/product/operations" in paths
    assert "/product/license-decision" in paths
    assert "/product/license-options" in paths
    assert "/product/license-file-work-order" in paths
    assert "/product/self-hosted-license-distribution-audit" in paths
    assert "/product/commercial-independence" in paths
    assert "/product/release-readiness" in paths
    assert "/product/residual-model-registry" in paths
    assert "/product/production-ai-checkpoint-readiness" in paths
    assert "/product/production-ai-gpu-worker-dispatch-manifest" in paths
    assert "/product/production-ai-gpu-worker-dispatch-bundle" in paths
    assert "/product/production-ai-gpu-worker-execution-runbook" in paths
    assert "/product/production-ai-gpu-return-intake" in paths
    assert "/product/production-ai-promotion-workbench" in paths
    assert "/product/production-ai-registry-promotion-operator-receipt" in paths
    assert "/product/production-ai-registry-promotion-priority" in paths
    assert "/product/scope-breadth-contract" in paths
    assert "/product/scope-claim-guard" in paths
    assert "/product/scope-evidence-priority" in paths
    assert "/product/scope-evidence-intake-readiness" in paths
    assert "/product/transporter-manual-review-intake" in paths
    assert "/product/pxr-exact-review-intake" in paths
    assert "/product/aqp1-operator-validation-candidate" in paths
    assert "/product/aqp1-direct-binding-procurement-packet" in paths
    assert "/product/commercial-readiness-operator-packet" in paths
    assert "/product/commercial-readiness-operator-packet-freshness" in paths
    assert "/product/commercial-readiness-execution-ladder" in paths
    assert "/product/commercial-readiness-handoff-bundle" in paths
    assert "/product/scope-breadth-evidence-receipt" in paths
    assert "/product/engine-refinement-claim-evidence-receipt" in paths
    assert "/product/engine-refinement-claim-evidence-priority" in paths
    assert "/product/full-commercial-blocker-evidence-matrix" in paths
    assert "/product/goal-completion-audit" in paths
    assert "/product/pose-sampling-readiness" in paths
    assert "/product/structure/analyze" in paths
    assert "/product/docking/jobs" in paths
    assert "/product/docking/jobs/{job_id}" in paths
    assert "/product/docking/jobs/{job_id}/history" in paths
    assert "/product/docking/jobs/{job_id}/cancel" in paths
    assert "/product/docking/jobs/{job_id}/retry" in paths
    assert "/product/tier-beta/docking/jobs" in paths
    assert "/product/architecture" in architecture_router_paths
    assert "/product/architecture-validation" in architecture_router_paths
    assert "/product/capabilities" in capability_router_paths
    assert "/product/docking/jobs" in docking_router_paths
    assert "/product/structure/analyze" in docking_router_paths
    assert "/product/service-boundary" in service_contract_router_paths
    assert "/product/api-contract" in service_contract_router_paths
    assert "/product/operational-quality" in operational_router_paths
    assert "/product/security-deployment-contract" in operational_router_paths
    assert "/product/operations" in release_ops_router_paths
    assert "/product/commercial-independence" in release_ops_router_paths
    assert "/product/release-readiness" in release_ops_router_paths
    assert "/product/job-orchestration-contract" in release_ops_router_paths
    assert "/product/external-metrics" in benchmark_router_paths
    assert "/product/public-benchmark" in benchmark_router_paths
    assert "/product/trajectory-sla-contract" in benchmark_router_paths
    assert "/product/rollout-execution-smoke-receipt" in benchmark_router_paths
    assert "/product/ai-decision-graph" in ai_surface_router_paths
    assert "/product/pose-sampling-readiness" in ai_surface_router_paths
    assert "/product/ai-report-ux" in ai_surface_router_paths
    assert "/product/residual-model-registry" in ai_surface_router_paths
    assert "/product/cameo-live-validation" in cameo_runner_router_paths
    assert "/product/cameo-official-result-fetch-preflight" in cameo_runner_router_paths
    assert "/product/api-runner-profile-promotion-operator-receipt" in cameo_runner_router_paths
    assert "/product/api-runner-profile-promotion-operator-staging-apply" in cameo_runner_router_paths
    assert "/product/license-decision" in license_router_paths
    assert "/product/license-options" in license_router_paths
    assert "/product/license-file-work-order" in license_router_paths
    assert "/product/self-hosted-license-distribution-audit" in license_router_paths
    assert "/product/production-ai-checkpoint-readiness" in production_ai_router_paths
    assert "/product/production-ai-gpu-worker-dispatch-manifest" in production_ai_router_paths
    assert "/product/production-ai-gpu-worker-dispatch-bundle" in production_ai_router_paths
    assert "/product/production-ai-gpu-worker-execution-runbook" in production_ai_router_paths
    assert "/product/production-ai-gpu-return-intake" in production_ai_router_paths
    assert "/product/production-ai-promotion-workbench" in production_ai_router_paths
    assert "/product/production-ai-registry-promotion-operator-receipt" in production_ai_router_paths
    assert "/product/production-ai-registry-promotion-priority" in production_ai_router_paths
    assert "/product/scope-breadth-contract" in scope_router_paths
    assert "/product/scope-claim-guard" in scope_router_paths
    assert "/product/scope-evidence-priority" in scope_router_paths
    assert "/product/scope-evidence-intake-readiness" in scope_router_paths
    assert "/product/transporter-manual-review-intake" in scope_router_paths
    assert "/product/pxr-exact-review-intake" in scope_router_paths
    assert "/product/aqp1-operator-validation-candidate" in scope_router_paths
    assert "/product/aqp1-direct-binding-procurement-packet" in scope_router_paths
    assert "/product/commercial-readiness-operator-packet" in commercial_readiness_router_paths
    assert "/product/commercial-readiness-operator-packet-freshness" in commercial_readiness_router_paths
    assert "/product/commercial-readiness-execution-ladder" in commercial_readiness_router_paths
    assert "/product/commercial-readiness-handoff-bundle" in commercial_readiness_router_paths
    assert "/product/scope-breadth-evidence-receipt" in evidence_goal_router_paths
    assert "/product/engine-refinement-claim-evidence-receipt" in evidence_goal_router_paths
    assert "/product/engine-refinement-claim-evidence-priority" in evidence_goal_router_paths
    assert "/product/full-commercial-blocker-evidence-matrix" in evidence_goal_router_paths
    assert "/product/goal-completion-audit" in evidence_goal_router_paths
    assert sum(1 for route in main.app.routes if route.path == "/product/architecture") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/architecture-validation") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/capabilities") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/hbond-backmap-report") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/gpcr-hard-decoy-suite-report") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/pocketmd-lite-report") == 1
    assert (
        sum(1 for route in main.app.routes if route.path == "/product/pocketmd-lite-remaining-evidence-queue")
        == 1
    )
    assert (
        sum(
            1
            for route in main.app.routes
            if route.path == "/product/pocketmd-lite-candidate-metric-fill-preview-report"
        )
        == 1
    )
    assert sum(1 for route in main.app.routes if route.path == "/product/service-boundary") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/api-contract") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/operational-quality") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/security-deployment-contract") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/operations") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/commercial-independence") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/release-readiness") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/job-orchestration-contract") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/external-metrics") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/public-benchmark") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/trajectory-sla-contract") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/rollout-execution-smoke-receipt") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/ai-decision-graph") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/pose-sampling-readiness") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/ai-report-ux") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/residual-model-registry") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/cameo-live-validation") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/cameo-official-result-fetch-preflight") == 1
    assert (
        sum(
            1
            for route in main.app.routes
            if route.path == "/product/api-runner-profile-promotion-operator-receipt"
        )
        == 1
    )
    assert (
        sum(
            1
            for route in main.app.routes
            if route.path == "/product/api-runner-profile-promotion-operator-staging-apply"
        )
        == 1
    )
    assert sum(1 for route in main.app.routes if route.path == "/product/license-decision") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/license-options") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/license-file-work-order") == 1
    assert (
        sum(1 for route in main.app.routes if route.path == "/product/self-hosted-license-distribution-audit")
        == 1
    )
    assert sum(1 for route in main.app.routes if route.path == "/product/production-ai-checkpoint-readiness") == 1
    assert (
        sum(1 for route in main.app.routes if route.path == "/product/production-ai-gpu-worker-dispatch-manifest")
        == 1
    )
    assert (
        sum(1 for route in main.app.routes if route.path == "/product/production-ai-gpu-worker-dispatch-bundle")
        == 1
    )
    assert (
        sum(1 for route in main.app.routes if route.path == "/product/production-ai-gpu-worker-execution-runbook")
        == 1
    )
    assert sum(1 for route in main.app.routes if route.path == "/product/production-ai-gpu-return-intake") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/production-ai-promotion-workbench") == 1
    assert (
        sum(
            1
            for route in main.app.routes
            if route.path == "/product/production-ai-registry-promotion-operator-receipt"
        )
        == 1
    )
    assert (
        sum(1 for route in main.app.routes if route.path == "/product/production-ai-registry-promotion-priority")
        == 1
    )
    assert sum(1 for route in main.app.routes if route.path == "/product/scope-breadth-contract") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/scope-claim-guard") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/scope-evidence-priority") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/scope-evidence-intake-readiness") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/transporter-manual-review-intake") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/pxr-exact-review-intake") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/aqp1-operator-validation-candidate") == 1
    assert (
        sum(1 for route in main.app.routes if route.path == "/product/aqp1-direct-binding-procurement-packet")
        == 1
    )
    assert sum(1 for route in main.app.routes if route.path == "/product/commercial-readiness-operator-packet") == 1
    assert (
        sum(1 for route in main.app.routes if route.path == "/product/commercial-readiness-operator-packet-freshness")
        == 1
    )
    assert sum(1 for route in main.app.routes if route.path == "/product/commercial-readiness-execution-ladder") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/commercial-readiness-handoff-bundle") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/scope-breadth-evidence-receipt") == 1
    assert sum(1 for route in main.app.routes if route.path == "/product/engine-refinement-claim-evidence-receipt") == 1
    assert (
        sum(1 for route in main.app.routes if route.path == "/product/engine-refinement-claim-evidence-priority")
        == 1
    )
    assert (
        sum(1 for route in main.app.routes if route.path == "/product/full-commercial-blocker-evidence-matrix")
        == 1
    )
    assert sum(1 for route in main.app.routes if route.path == "/product/goal-completion-audit") == 1

    capabilities = asyncio.run(product.get_product_capabilities())
    capability_source = _artifact_summary("product_capability_surface_contract_current.json")
    assert capabilities["status"] == capability_source.get("status")
    assert capabilities["structure_analysis_capability_ready"] is True
    assert capabilities["ligand_docking_capability_ready"] is True
    assert capabilities["restricted_scope_claim_guard_ready"] is True
    assert capabilities["allowed_scope_families"] == ["gpcr", "ion_channel", "kinase"]
    assert capabilities["blocked_claim_scopes"] == [
        "transporter_domain_promotion",
        "general_protein_ligand_platform",
    ]
    assert capabilities["general_platform_claim_allowed"] is False
    assert "general_platform_claim_allowed=False" in capabilities["scope_claim_boundary_detail"]

    structure = asyncio.run(
        product.analyze_product_structure(
            product.StructureAnalysisRequest(
                pdb_content="ATOM      1  CA  GLY A   1      12.104  13.207  14.321  1.00 10.00           C\n"
            )
        )
    )
    assert structure["status"] == "structure_analysis_ready"
    assert structure["atom_count"] == 1
    assert structure["chain_count"] == 1

    architecture = asyncio.run(product.get_product_architecture())
    assert architecture["status"] == "product_architecture_contract_ready"
    assert architecture["architecture_release_ready"] is True
    assert architecture["commercial_independence_ready"] is True
    assert architecture["cleanup_control_surface_ready"] is True

    service_boundary = asyncio.run(product.get_product_service_boundary())
    assert service_boundary["status"] == "product_service_boundary_contract_ready"
    assert service_boundary["service_boundary_ready"] is True
    assert service_boundary["blocker_count"] == 0

    api_contract = asyncio.run(product.get_product_api_contract())
    assert api_contract["status"] == "product_api_contract_ready"
    assert api_contract["api_contract_ready"] is True
    assert api_contract["blocker_count"] == 0

    pose_sampling = asyncio.run(product.get_product_pose_sampling_readiness())
    assert pose_sampling["status"] == "product_pose_sampling_readiness_ready"
    assert pose_sampling["pose_sampling_readiness_ready"] is True
    assert pose_sampling["pose_generation_contract_ready"] is True
    assert pose_sampling["pose_count"] == 6
    assert pose_sampling["cluster_count"] >= 2
    assert pose_sampling["claim_grade_pose_accuracy_ready"] is False
    assert pose_sampling["execution_enabled"] is False
    assert pose_sampling["docking_results_emitted"] is False
    assert pose_sampling["external_state_mutated"] is False

    pocketmd_report = asyncio.run(product_pocketmd_lite.get_product_pocketmd_lite_report())
    pocketmd_report_source = _artifact_summary("pocketmd_lite_report_current.json")
    assert pocketmd_report["status"] == pocketmd_report_source.get("status")
    assert pocketmd_report["pocketmd_lite_claim_safe"] is (
        pocketmd_report_source.get("pocketmd_lite_claim_safe") is True
    )
    assert pocketmd_report["top_k_refinement_evidence_ready"] is (
        pocketmd_report_source.get("top_k_refinement_evidence_ready") is True
    )
    for key in (
        "claim_grade_metric_ready_row_count",
        "green_row_count",
        "yellow_row_count",
        "red_row_count",
        "abstain_row_count",
    ):
        assert pocketmd_report[key] == int(pocketmd_report_source.get(key) or 0)
    assert pocketmd_report["missing_refinement_metric_names"] == (
        pocketmd_report_source.get("missing_refinement_metric_names") or []
    )
    assert pocketmd_report["missing_refinement_metric_counts"] == (
        pocketmd_report_source.get("missing_refinement_metric_counts") or {}
    )
    assert pocketmd_report["execution_enabled"] is False
    assert pocketmd_report["docking_results_emitted"] is False
    assert pocketmd_report["external_state_mutated"] is False

    pocketmd_queue = asyncio.run(product_pocketmd_lite.get_product_pocketmd_lite_remaining_evidence_queue())
    assert pocketmd_queue["execution_enabled"] is False
    assert pocketmd_queue["docking_results_emitted"] is False
    assert pocketmd_queue["external_state_mutated"] is False

    pocketmd_preview_report = asyncio.run(
        product_pocketmd_lite.get_product_pocketmd_lite_candidate_metric_fill_preview_report()
    )
    pocketmd_preview_source = _artifact_summary("pocketmd_lite_candidate_metric_fill_preview_report_current.json")
    pocketmd_audit_source = _artifact_summary("pocketmd_lite_topk_refinement_audit_current.json")
    preview_ready = (
        pocketmd_preview_source.get("status") == "pocketmd_lite_report_ready"
        and pocketmd_preview_source.get("top_k_refinement_evidence_ready") is True
    )
    canonical_ready = (
        pocketmd_report_source.get("status") == "pocketmd_lite_report_ready"
        and pocketmd_report_source.get("top_k_refinement_evidence_ready") is True
        and pocketmd_report_source.get("pocketmd_lite_claim_safe") is True
    )
    assert pocketmd_preview_report["canonical_report_status"] == pocketmd_report_source.get("status")
    assert pocketmd_preview_report["canonical_report_ready"] is canonical_ready
    assert pocketmd_preview_report["canonical_pocketmd_lite_claim_safe"] is (
        pocketmd_report_source.get("pocketmd_lite_claim_safe") is True
    )
    assert pocketmd_preview_report["canonical_abstain_row_count"] == int(
        pocketmd_report_source.get("abstain_row_count") or 0
    )
    assert pocketmd_preview_report["canonical_missing_refinement_metric_names"] == (
        pocketmd_report_source.get("missing_refinement_metric_names") or []
    )
    assert pocketmd_preview_report["canonical_missing_refinement_metric_counts"] == (
        pocketmd_report_source.get("missing_refinement_metric_counts") or {}
    )
    assert pocketmd_preview_report["canonical_review_required"] is (preview_ready and not canonical_ready)
    assert pocketmd_preview_report["canonical_candidate_csv_mutated"] is (
        pocketmd_audit_source.get("candidate_metric_fill_preview_canonical_candidate_csv_mutated") is True
    )
    assert pocketmd_preview_report["preview_report_ready"] is preview_ready
    assert pocketmd_preview_report["preview_requires_canonical_review"] is True
    assert pocketmd_preview_report["preview_pocketmd_lite_claim_safe"] is (
        pocketmd_preview_source.get("pocketmd_lite_claim_safe") is True
    )
    assert pocketmd_preview_report["pocketmd_lite_claim_safe"] is False
    assert pocketmd_preview_report["execution_enabled"] is False
    assert pocketmd_preview_report["docking_results_emitted"] is False
    assert pocketmd_preview_report["external_state_mutated"] is False

    pocketmd_audit = asyncio.run(product_pocketmd_lite.get_product_pocketmd_lite_topk_refinement_audit())
    assert "claim_grade_refinement_evidence_ready" in pocketmd_audit
    assert pocketmd_audit["claim_promotion_allowed"] is False
    assert pocketmd_audit["execution_enabled"] is False
    assert pocketmd_audit["docking_results_emitted"] is False
    assert pocketmd_audit["external_state_mutated"] is False

    operational_quality = asyncio.run(product.get_product_operational_quality())
    assert operational_quality["status"] == "product_operational_quality_contract_ready"
    assert operational_quality["operational_quality_ready"] is True
    assert operational_quality["production_ai_correction_fail_closed_ready"] is True
    assert operational_quality["sample_production_ai_correction_applied"] is False
    assert operational_quality["production_ai_shadow_abstention_ready"] is True
    assert operational_quality["sample_production_ai_abstention_enforced"] is True
    assert operational_quality["sample_production_ai_default_residual_mode"] == "shadow"
    assert operational_quality["sample_production_ai_customer_facing_auto_correction_allowed"] is False
    assert operational_quality["sample_production_ai_customer_facing_score_mutation_allowed"] is False
    assert operational_quality["sample_production_ai_customer_facing_ranking_mutation_allowed"] is False
    assert operational_quality["sample_production_ai_selected_sidecar_missing_output_fields"] == ["delta_force"]

    job_list = asyncio.run(product.list_docking_jobs(limit=5))
    assert job_list["status"] == "product_job_history_ready"
    assert "source_host_filter" in job_list
    assert "root_job_id_filter" in job_list
    assert "customer_id_filter" in job_list
    assert "user_id_filter" in job_list
    assert job_list["execution_enabled"] is False
    assert job_list["docking_results_emitted"] is False
    assert job_list["external_state_mutated"] is False

    job_orchestration = asyncio.run(product.get_product_job_orchestration_contract())
    assert job_orchestration["status"] == "product_job_orchestration_contract_ready"
    assert job_orchestration["product_job_orchestration_contract_ready"] is True
    assert job_orchestration["ready_check_count"] == job_orchestration["check_count"]
    assert job_orchestration["blocked_check_count"] == 0
    assert job_orchestration["retry_child_attempt_created"] is True
    assert job_orchestration["idempotency_preserved"] is True
    assert job_orchestration["progress_fields_present"] is True
    assert job_orchestration["listed_status_progress_contract_ready"] is True
    assert job_orchestration["queue_lifecycle_progress_ready"] is True
    assert job_orchestration["customer_run_history_lineage_ready"] is True
    assert job_orchestration["status_snapshot_persistence_ready"] is True
    assert job_orchestration["retention_policy_ready"] is True
    assert job_orchestration["rerun_manifest_ready"] is True
    assert job_orchestration["long_running_status_persistence_ready"] is True
    assert job_orchestration["worker_backend_contract_ready"] is True
    assert job_orchestration["worker_lease_heartbeat_ready"] is True
    assert job_orchestration["retryable_failure_resume_ready"] is True
    assert job_orchestration["running_cancel_ack_ready"] is True
    assert job_orchestration["stale_worker_lease_recovery_ready"] is True
    assert job_orchestration["stale_worker_lease_sweep_ready"] is True
    assert job_orchestration["stale_worker_lease_detected_count"] == 1
    assert job_orchestration["stale_worker_lease_updated_count"] == 1
    assert job_orchestration["retryable_after_stale_count"] == 1
    assert job_orchestration["stale_worker_lease_timeout_seconds"] == 1800
    assert job_orchestration["job_retention_days"] == 90
    assert job_orchestration["source_host_filter_job_count"] == 4
    assert job_orchestration["root_job_id_filter_job_count"] == 3
    assert job_orchestration["customer_id_filter_job_count"] == 4
    assert job_orchestration["user_id_filter_job_count"] == 4
    assert job_orchestration["root_attempt_count_after_retry"] == 3
    assert job_orchestration["history_event_count"] == 3
    assert job_orchestration["job_count_after_retry"] == 3
    assert job_orchestration["job_count_after_stale_probe"] == 4
    assert len(job_orchestration["checks"]) == job_orchestration["check_count"]
    assert job_orchestration["execution_enabled"] is False
    assert job_orchestration["docking_results_emitted"] is False
    assert job_orchestration["external_state_mutated"] is False

    security_deployment = asyncio.run(product.get_product_security_deployment_contract())
    security_source = _artifact_summary("product_security_deployment_contract_current.json")
    assert security_deployment["status"] == security_source.get("status")
    for key in (
        "security_deployment_ready",
        "auth_ready",
        "tenant_isolation_ready",
        "rate_limit_ready",
        "tenant_quota_ready",
        "payload_limit_ready",
        "path_allowlist_ready",
        "audit_log_ready",
        "audit_retention_ready",
        "blocked_request_audit_ready",
        "security_headers_ready",
        "fail_closed_block_response_ready",
        "audit_redaction_ready",
        "sbom_ready",
        "secret_rotation_contract_ready",
        "backup_dr_contract_ready",
        "pager_alert_contract_ready",
        "container_image_ready",
        "metrics_endpoint_ready",
        "rollback_ready",
        "hosted_deployment_contract_ready",
        "hosted_deployment_currently_satisfied",
        "hosted_external_exposure_allowed",
        "hosted_secret_injection_ready",
        "tls_termination_operator_verified",
    ):
        assert security_deployment[key] is (security_source.get(key) is True)
    assert security_deployment["blocker_count"] == int(security_source.get("blocker_count") or 0)
    if security_deployment["blocker_count"]:
        assert security_deployment["blockers"][0]["check"] == "security_deployment_contract_rows_present"
    else:
        assert security_deployment["blockers"] == []
    assert security_deployment["hosted_deployment_blocked_stage_count"] == int(
        security_source.get("hosted_deployment_blocked_stage_count") or 0
    )
    assert security_deployment["hosted_deployment_next_stage_id"] == security_source.get(
        "hosted_deployment_next_stage_id", ""
    )
    assert security_deployment["hosted_exposure_approval_token_required"] == security_source.get(
        "hosted_exposure_approval_token_required", ""
    )
    assert len(security_deployment["checks"]) == security_deployment["check_count"]

    public_benchmark = asyncio.run(product.get_product_public_benchmark())
    assert public_benchmark["status"] == "product_public_benchmark_work_order_clear"
    assert public_benchmark["public_benchmark_validation_ready"] is True
    assert public_benchmark["suite_result_provenance_command_count"] == 5
    assert public_benchmark["suite_result_provenance_present_count"] == 5
    assert public_benchmark["local_artifact_preflight_ready_suite_count"] == 5
    assert public_benchmark["scorecard_panel_ready"] is True
    assert public_benchmark["suite_row_count"] == public_benchmark["suite_count"]
    assert public_benchmark["suite_green_row_count"] == public_benchmark["suite_count"]
    assert public_benchmark["suite_blocked_row_count"] == 0
    assert public_benchmark["scorecard_blocker_row_count"] == 0
    assert public_benchmark["scorecard_blocker_rows"] == []
    assert len(public_benchmark["suite_rows"]) == public_benchmark["suite_count"]
    assert all(row["scorecard_ready"] is True for row in public_benchmark["suite_rows"])
    assert all(row["claim_promotion_allowed"] is False for row in public_benchmark["suite_rows"])
    assert public_benchmark["requires_24h_server"] is False
    assert public_benchmark["requires_competition_season"] is False
    assert public_benchmark["requires_paid_vps"] is False

    public_benchmark_receipts = asyncio.run(product.get_product_public_benchmark_external_receipts_audit())
    public_benchmark_receipts_source = _artifact_summary("public_benchmark_external_receipts_audit_current.json")
    assert public_benchmark["external_receipts_status"] == public_benchmark_receipts_source.get(
        "status", ""
    )
    assert public_benchmark["external_receipts_ready"] is (
        public_benchmark_receipts_source.get("external_benchmark_receipts_ready") is True
    )
    assert public_benchmark["external_receipts_blocker_count"] == int(
        public_benchmark_receipts_source.get("blocker_count") or 0
    )
    assert public_benchmark["external_receipt_blocker_row_count"] == int(
        public_benchmark_receipts_source.get("blocker_count") or 0
    )
    assert public_benchmark["external_beta_claim_allowed"] is False
    assert public_benchmark["claim_promotion_allowed"] is False
    assert public_benchmark_receipts["status"] == public_benchmark_receipts_source.get("status")
    assert public_benchmark_receipts["external_benchmark_receipts_ready"] is (
        public_benchmark_receipts_source.get("external_benchmark_receipts_ready") is True
    )
    assert public_benchmark_receipts["claim_promotion_allowed"] is False
    assert public_benchmark_receipts["ready_step_count"] == int(
        public_benchmark_receipts_source.get("ready_step_count") or 0
    )
    assert public_benchmark_receipts["blocked_step_count"] == int(
        public_benchmark_receipts_source.get("blocked_step_count") or 0
    )
    assert public_benchmark_receipts["receipt_blocked_row_count"] == int(
        public_benchmark_receipts_source.get("receipt_blocked_row_count") or 0
    )
    assert public_benchmark_receipts["vina_gnina_comparison_adapter_score_evidence_ready"] is (
        public_benchmark_receipts_source.get("vina_gnina_comparison_adapter_score_evidence_ready") is True
    )
    for key in (
        "phase2_harness_ready",
        "materialization_manifest_ready",
        "subset_dry_run_ready",
        "pose_rmsd_2a_5a_ready",
        "posebusters_validity_ready",
        "vina_gnina_same_input_comparison_ready",
        "benchmark_receipt_attach_ready",
        "benchmark_ledger_review_ready",
        "vina_gnina_score_template_receipt_ready",
        "vina_gnina_score_template_validation_ready",
    ):
        assert public_benchmark_receipts[key] is (public_benchmark_receipts_source.get(key) is True)
    for key in (
        "vina_gnina_score_template_filled_score_row_count",
        "vina_gnina_score_value_pending_count",
        "vina_gnina_license_ok_pending_count",
        "vina_gnina_operator_metadata_pending_count",
        "vina_gnina_approval_token_pending_count",
        "vina_gnina_pending_field_count",
        "benchmark_ledger_entry_count",
        "benchmark_ledger_external_safe_count",
    ):
        assert public_benchmark_receipts[key] == int(public_benchmark_receipts_source.get(key) or 0)
    assert public_benchmark_receipts["next_required_step"] == public_benchmark_receipts_source.get(
        "next_required_step", ""
    )
    assert public_benchmark_receipts["scorecard_status"] == public_benchmark_receipts_source.get(
        "scorecard_status", ""
    )
    assert public_benchmark_receipts["vina_gnina_score_template_receipt_status"] == (
        public_benchmark_receipts_source.get("vina_gnina_score_template_receipt_status", "")
    )
    assert public_benchmark_receipts["vina_gnina_pending_field_counts"] == (
        public_benchmark_receipts_source.get("vina_gnina_pending_field_counts") or {}
    )
    public_benchmark_receipts_payload = _artifact_payload("public_benchmark_external_receipts_audit_current.json")
    source_blocked_steps = [
        row
        for row in public_benchmark_receipts_payload.get("rows", [])
        if not (row.get("ready") is True and row.get("status") == "ready")
    ]
    assert len(public_benchmark_receipts["blocked_steps"]) == len(source_blocked_steps)
    assert public_benchmark_receipts["blocked_steps"][0]["step_id"] == source_blocked_steps[0].get("step_id")
    assert public_benchmark_receipts["blocked_steps"][0]["blocker"] == source_blocked_steps[0].get("blocker")
    assert len(public_benchmark_receipts["steps"]) == public_benchmark_receipts["step_count"]

    trajectory_sla = asyncio.run(product.get_product_trajectory_sla_contract())
    trajectory_source = _artifact_summary("product_trajectory_sla_contract_current.json")
    assert trajectory_sla["status"] == trajectory_source.get("status")
    for key in (
        "production_trajectory_sla_ready",
        "restricted_family_sla_allowed",
        "broad_platform_sla_allowed",
        "current_rocm_baseline_production_trajectory_profile_enabled",
        "current_rocm_baseline_supports_restricted_family_sla",
        "current_rocm_baseline_supports_broad_platform_sla",
        "customer_sla_disclosure_ready",
        "general_platform_sla_allowed",
        "restricted_sla_backed_by_historical_profile_artifacts",
        "rocm_baseline_profile_gap_acknowledged",
    ):
        assert trajectory_sla[key] is (trajectory_source.get(key) is True)
    for key in (
        "sla_claim_tier",
        "required_families",
        "qualified_ready_families",
        "missing_qualified_families",
        "minimum_ready_rows_per_family",
        "current_rocm_baseline_claim_scope",
        "allowed_sla_claims",
        "blocked_sla_claims",
        "customer_sla_disclosure_card",
    ):
        assert trajectory_sla[key] == trajectory_source.get(key)
    assert "restricted_family_trajectory_profile_sla" in trajectory_sla["allowed_sla_claims"]
    assert "single_target_gpcr_rocm_baseline" in trajectory_sla["allowed_sla_claims"]
    assert "broad_platform_sla" in trajectory_sla["blocked_sla_claims"]
    assert "general_protein_ligand_platform_sla" in trajectory_sla["blocked_sla_claims"]
    assert trajectory_sla["general_platform_sla_allowed"] is False
    assert trajectory_sla["customer_sla_disclosure_card"]["current_rocm_baseline_scope"] == (
        "single_target_gpcr_baseline"
    )
    assert all(row["qualified_for_restricted_family_sla"] for row in trajectory_sla["family_sla_matrix"])
    assert len(trajectory_sla["trajectory_sla_rows"]) == trajectory_sla["candidate_artifact_count"]

    ai_decision_graph = asyncio.run(product.get_product_ai_decision_graph())
    assert ai_decision_graph["status"] == "product_ai_decision_graph_contract_ready"
    assert ai_decision_graph["closed_loop_decision_graph_ready"] is True
    assert ai_decision_graph["production_ai_inference_enabled"] is False
    assert ai_decision_graph["ordered_graph_path"] == [
        "structure_quality",
        "binding_site_context",
        "pose_generation_contract",
        "scoring_ranking_gate",
        "uncertainty_abstention_guard",
        "report_bundle_contract",
        "customer_report_ux",
    ]
    assert ai_decision_graph["node_count"] == len(ai_decision_graph["nodes"])
    assert ai_decision_graph["edge_count"] == len(ai_decision_graph["edges"])
    assert ai_decision_graph["customer_report_ux_node_ready"] is True
    assert ai_decision_graph["viewer_interaction_surface_ready"] is True

    ai_report_ux = asyncio.run(product.get_product_ai_report_ux())
    assert ai_report_ux["status"] == "product_ai_report_ux_contract_ready"
    assert ai_report_ux["ai_report_ux_ready"] is True
    assert ai_report_ux["structured_customer_report_ready"] is True
    assert ai_report_ux["customer_report_delivery_contract_ready"] is True
    assert ai_report_ux["customer_report_evidence_binding_ready"] is True
    assert ai_report_ux["customer_report_viewer_binding_ready"] is True
    assert ai_report_ux["viewer_customer_report_binding_ready"] is True
    assert ai_report_ux["canonical_customer_report_required_blocks"] == ai_report_ux["customer_report_required_blocks"]
    assert ai_report_ux["customer_report_ready_block_count"] == ai_report_ux["customer_report_required_block_count"]
    assert ai_report_ux["customer_report_blocked_block_count"] == 0
    assert ai_report_ux["customer_report_card_ready"] is True
    assert ai_report_ux["customer_report_card"]["primary_abstention_reason"] == (
        "production_residual_checkpoint_not_promoted"
    )
    assert ai_report_ux["pose_comparison_ready"] is True
    assert ai_report_ux["interaction_rationale_ready"] is True
    assert ai_report_ux["ligand_selection_rationale_ready"] is True
    assert "ranking source" in ai_report_ux["selection_rationale"]
    assert ai_report_ux["uncertainty_narrative_ready"] is True
    assert ai_report_ux["counterfactual_rescue_suggestion_ready"] is True
    assert ai_report_ux["viewer_ready"] is True
    assert ai_report_ux["viewer_interaction_surface_ready"] is True
    assert ai_report_ux["general_platform_claim_allowed"] is False
    assert "general_protein_ligand_platform" in ai_report_ux["blocked_claim_scopes"]
    assert ai_report_ux["section_count"] == len(ai_report_ux["report_sections"])

    cameo_live_validation = asyncio.run(product.get_product_cameo_live_validation())
    assert cameo_live_validation["status"] == "blocked_cameo_validation_operations_dossier"
    assert cameo_live_validation["official_results_pending_honest"] is True
    assert cameo_live_validation["receiver_smoke_status"] == "cameo_receiver_smoke_ready"
    assert cameo_live_validation["api_dependency_status"] == "cameo_api_dependency_ready"
    assert cameo_live_validation["public_registration_allowed"] is True
    assert cameo_live_validation["registration_gate_status"] == "cameo_public_registration_approval_gate_ready"
    assert cameo_live_validation["registration_authorized_for_review"] is True
    assert cameo_live_validation["registration_blocker_count"] == 0
    assert cameo_live_validation["server_registration_mutated"] is False

    cameo_fetch = asyncio.run(product.get_product_cameo_official_result_fetch_preflight())
    assert cameo_fetch["status"] == "blocked_cameo_official_result_fetch_preflight"
    assert cameo_fetch["official_result_fetch_preflight_ready"] is False
    assert cameo_fetch["operations_surface_ready"] is True
    assert cameo_fetch["receiver_smoke_ready"] is True
    assert cameo_fetch["source_operations_dossier_status"] == (
        "blocked_cameo_validation_operations_dossier"
    )
    assert cameo_fetch["operator_fetch_csv_present"] is False
    assert cameo_fetch["operator_fetch_csv"].endswith(
        "runs/cameo_official_result_fetch_operator_approval_intake.csv"
    )
    assert cameo_fetch["fetch_approval_token_required"] == (
        "APPROVE_CAMEO_OFFICIAL_RESULT_FETCH"
    )
    assert cameo_fetch["authorized_for_separate_operator_fetch"] is False
    assert cameo_fetch["blocked_row_count"] == 1
    assert cameo_fetch["blocker_count"] == 2
    assert cameo_fetch["blockers"] == [
        "operator_decision_missing",
        "operator_fetch_csv_missing",
    ]
    assert len(cameo_fetch["fetch_rows"]) == 1
    assert cameo_fetch["network_request_opened"] is False
    assert cameo_fetch["official_results_fetched"] is False
    assert cameo_fetch["native_local_accuracy_used"] is False
    assert cameo_fetch["outbound_email_enabled"] is False
    assert cameo_fetch["execution_enabled"] is False
    assert cameo_fetch["docking_results_emitted"] is False
    assert cameo_fetch["external_state_mutated"] is False

    api_runner_receipt = asyncio.run(
        product.get_product_api_runner_profile_promotion_operator_receipt()
    )
    api_runner_receipt_source = _artifact_summary("api_runner_profile_promotion_operator_receipt_current.json")
    for key in (
        "status",
        "readiness_status",
        "operator_template_csv",
        "first_blocked_profile_id",
        "first_blocked_row_blocker",
        "most_common_row_blocker",
        "approval_token_required",
        "blockers",
    ):
        assert api_runner_receipt[key] == api_runner_receipt_source.get(key)
    for key in (
        "operator_receipt_ready",
        "profile_enabled_by_this_tool",
        "runner_executed",
        "external_state_mutated",
    ):
        assert api_runner_receipt[key] is (api_runner_receipt_source.get(key) is True)
    for key in (
        "profile_count",
        "receipt_row_count",
        "pass_row_count",
        "blocked_row_count",
    ):
        assert api_runner_receipt[key] == int(api_runner_receipt_source.get(key) or 0)
    assert len(api_runner_receipt["receipt_rows"]) == api_runner_receipt["receipt_row_count"]
    assert api_runner_receipt["profile_promoted"] is False
    assert api_runner_receipt["execution_enabled"] is False
    assert api_runner_receipt["docking_results_emitted"] is False
    assert api_runner_receipt["external_state_mutated"] is False

    rollout_receipt = asyncio.run(product.get_product_rollout_execution_smoke_receipt())
    assert rollout_receipt["status"] == "product_rollout_execution_smoke_receipt_ready"
    assert rollout_receipt["rollout_execution_smoke_receipt_ready"] is True
    assert rollout_receipt["source_rollout_execution_readiness_status"] == (
        "product_rollout_execution_readiness_ready"
    )
    assert rollout_receipt["source_authorized_for_separate_operator_execution"] is True
    assert rollout_receipt["source_rollout_executed"] is False
    assert rollout_receipt["receipt_csv_present"] is True
    assert rollout_receipt["receipt_row_count"] == 1
    assert rollout_receipt["ready_receipt_row_count"] == 1
    assert rollout_receipt["blocker_count"] == 0
    assert rollout_receipt["target_environment"] == "k8s"
    assert rollout_receipt["rollout_executed"] is True
    assert rollout_receipt["image_pushed"] is True
    assert rollout_receipt["service_restarted"] is True
    assert rollout_receipt["pager_provider_contacted"] is True
    assert rollout_receipt["ingress_certificate_verified_live"] is True
    assert rollout_receipt["receipt_external_state_mutated"] is True
    assert len(rollout_receipt["rollout_receipt_rows"]) == rollout_receipt["receipt_row_count"]
    assert rollout_receipt["execution_enabled"] is False
    assert rollout_receipt["docking_results_emitted"] is False
    assert rollout_receipt["external_state_mutated"] is False

    operations = asyncio.run(product.get_product_operations())
    license_work_order = asyncio.run(product.get_product_license_file_work_order())
    operations_source = _artifact_summary("product_release_operations_dossier_current.json")
    assert operations["status"] == operations_source.get("status")
    for key in (
        "architecture_contract_ready",
        "architecture_release_ready",
        "commercial_independent_product_claim_allowed",
        "authorized_for_execution",
    ):
        assert operations[key] is (operations_source.get(key) is True)
    assert operations["commercial_independence_status"] == operations_source.get(
        "source_commercial_independence_status"
    )
    assert operations["blocked_stage_count"] == int(operations_source.get("blocked_stage_count") or 0)
    assert operations["approval_required_stage_count"] == int(
        operations_source.get("approval_required_stage_count") or 0
    )
    assert operations["approval_tokens_required"] == list(operations_source.get("approval_tokens_required") or [])
    assert operations["source_license_file_creation_work_order_status"] == license_work_order["status"]
    assert operations["license_file_creation_review_ready"] is license_work_order["license_file_creation_review_ready"]
    assert operations["license_file_creation_work_order_blocker_count"] == license_work_order["blocker_count"]

    license_decision = asyncio.run(product.get_product_license_decision())
    assert license_decision["status"] == "product_license_decision_gate_ready"
    assert license_decision["authorized_for_license_file_creation_review"] is True
    assert license_decision["approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"

    license_options = asyncio.run(product.get_product_license_options())
    assert license_options["status"] == "product_license_decision_packet_ready"
    assert license_options["required_decision"] == "create_license_file"
    assert license_options["approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"

    assert license_work_order["status"] in {
        "blocked_product_license_file_creation_work_order",
        "product_license_file_creation_work_order_ready",
    }
    assert isinstance(license_work_order["license_file_creation_review_ready"], bool)
    assert license_work_order["target_license_path"] == "LICENSE"
    assert license_work_order["license_decision_gate_status"] == "product_license_decision_gate_ready"
    assert license_work_order["authorized_for_license_file_creation_review"] is True
    assert license_work_order["license_present"] is True
    assert license_work_order["blocker_count"] >= 0
    assert len(license_work_order["license_review_manifest_fingerprint_sha256"]) == 64

    license_audit = asyncio.run(product.get_product_self_hosted_license_distribution_audit())
    assert license_audit["status"] == "self_hosted_license_distribution_audit_recorded"
    assert license_audit["hard_blocker_count"] == 0
    assert license_audit["operator_review_item_count"] == 1
    assert license_audit["product_license_path"] == "LICENSE"
    assert len(license_audit["product_license_sha256"]) == 64
    assert license_audit["product_license_sha256"] == license_audit[
        "approved_license_text_source_sha256"
    ]
    assert license_audit["spdx_license_id"] == "ProprietaryRef-Betelgeuze"
    assert license_audit["viewer_third_party_notice_path"] == (
        "viewer/vendor/THIRD_PARTY_NOTICES.md"
    )
    assert license_audit["third_party_dual_license_assets"] == ["jszip"]
    assert license_audit["third_party_license_review_gate_status"] == (
        "third_party_license_review_gate_ready"
    )
    assert license_audit["third_party_license_review_gate_ready"] is True
    assert license_audit["third_party_license_review_gate_blocker_count"] == 0
    assert license_audit["legal_advice_provided"] is False
    assert len(license_audit["audit_rows"]) >= 1
    assert len(license_audit["operator_review_items"]) == 1
    assert license_audit["license_file_written"] is False
    assert license_audit["execution_enabled"] is False
    assert license_audit["docking_results_emitted"] is False
    assert license_audit["external_state_mutated"] is False

    commercial = asyncio.run(product.get_product_commercial_independence())
    commercial_source = _artifact_summary("product_commercial_independence_gate_current.json")
    assert commercial["status"] == commercial_source.get("status")
    for key in (
        "commercial_independent_product_claim_allowed",
        "restricted_commercial_scope_claim_ready",
        "general_platform_claim_allowed",
        "license_present",
        "public_benchmark_evidence_ready",
    ):
        assert commercial[key] is (commercial_source.get(key) is True)
    assert commercial["commercial_claim_scope_tier"] == commercial_source.get("commercial_claim_scope_tier")
    assert commercial["allowed_scope_families"] == commercial_source.get("allowed_scope_families")
    assert commercial["blocked_claim_scopes"] == commercial_source.get("blocked_claim_scopes")
    assert commercial["general_platform_claim_allowed"] is False
    assert commercial["blocker_count"] == int(commercial_source.get("blocker_count") or 0)

    release = asyncio.run(product.get_product_release_readiness())
    goal_release = _artifact_summary("goal_release_decision_gate_current.json")
    assert release["status"] == operations_source.get("status")
    assert release["release_allowed"] is (goal_release.get("release_allowed") is True)
    assert release["goal_release_status"] == goal_release.get("status")
    assert release["goal_release_blocker_count"] == int(goal_release.get("blocker_count") or 0)
    assert release["commercial_independent_product_ready"] is (
        commercial["commercial_independent_product_claim_allowed"] is True
    )
    assert release["restricted_commercial_scope_claim_ready"] is True
    assert release["commercial_claim_scope_tier"] == "restricted_family_local_product"
    assert release["commercial_allowed_scope_families"] == ["gpcr", "ion_channel", "kinase"]
    assert release["commercial_blocked_claim_scopes"] == [
        "transporter_domain_promotion",
        "general_protein_ligand_platform",
    ]
    assert release["commercial_general_platform_claim_allowed"] is False
    assert release["product_architecture_release_ready"] is (architecture["architecture_release_ready"] is True)
    assert release["license_present"] is True
    assert release["license_file_creation_work_order_status"] == license_work_order["status"]
    assert release["license_file_creation_review_ready"] is license_work_order["license_file_creation_review_ready"]
    assert release["license_file_creation_work_order_blocker_count"] == license_work_order["blocker_count"]

    registry = asyncio.run(product.get_product_residual_model_registry())
    assert registry["status"] == "residual_model_registry_ready"
    assert registry["registry_ready"] is True
    assert registry["product_model_layer_ready"] is True
    assert registry["production_ai_inference_subject_active"] is False
    assert registry["default_residual_mode"] == "shadow"
    assert registry["production_promotion_allowed"] is False
    assert registry["production_mode_allowed"] is False
    assert registry["customer_facing_auto_correction_allowed"] is False
    assert registry["customer_facing_score_mutation_allowed"] is False
    assert registry["customer_facing_ranking_mutation_allowed"] is False
    assert registry["trained_model_checkpoint_count"] == 1
    assert registry["candidate_checkpoint_count"] == 1
    assert registry["checkpoint_preflight_ready"] is True
    assert registry["production_checkpoint_blocked"] is False
    assert registry["selected_sidecar_ready"] is True
    assert registry["selected_sidecar_status"] == "residual_production_checkpoint_sidecar_ready"
    assert registry["selected_sidecar_missing_output_fields"] == []
    assert registry["selected_sidecar_training_contract_missing_label_fields"] == ["delta_force"]
    assert registry["checkpoint_missing_output_fields"] == []
    assert registry["checkpoint_missing_adapter_output_policy_fields"] == []
    assert registry["component_count"] == 6
    assert registry["required_components_present"] is True
    assert len(registry["components"]) == registry["component_count"]

    checkpoint = asyncio.run(product.get_product_production_ai_checkpoint_readiness())
    checkpoint_source = _artifact_summary("product_production_ai_checkpoint_readiness_current.json")
    assert checkpoint["status"] == "blocked_product_production_ai_checkpoint_readiness"
    assert checkpoint["check_count"] == 8
    assert checkpoint["fail_check_count"] == int(checkpoint_source.get("fail_check_count") or 0)
    assert checkpoint["failed_check_ids"] == checkpoint_source.get("failed_check_ids")
    assert checkpoint["first_failed_check_id"] == checkpoint_source.get("first_failed_check_id")
    assert checkpoint["production_ai_checkpoint_ready"] is False
    assert checkpoint["production_ai_inference_subject_active"] is False
    assert checkpoint["product_model_layer_ready"] is True
    assert checkpoint["default_residual_mode"] == "shadow"
    assert checkpoint["production_promotion_allowed"] is False
    assert checkpoint["registry_promotion_required_gate_ids"] == [
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
        "default_residual_mode_guarded",
        "trained_model_checkpoint_count_positive",
    ]
    assert checkpoint["registry_promotion_missing_gate_ids"] == [
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
        "default_residual_mode_guarded",
    ]
    assert checkpoint["registry_promotion_missing_gate_count"] == 3
    assert checkpoint["registry_promotion_upstream_acceptance_ready"] is (
        checkpoint_source.get("registry_promotion_upstream_acceptance_ready") is True
    )
    assert checkpoint["registry_promotion_currently_satisfied"] is False
    assert checkpoint["customer_facing_auto_correction_allowed"] is False
    assert checkpoint["customer_facing_score_mutation_allowed"] is False
    assert checkpoint["customer_facing_ranking_mutation_allowed"] is False
    assert checkpoint["trained_model_checkpoint_count"] == 1
    assert checkpoint["candidate_checkpoint_count"] == 1
    assert checkpoint["ready_checkpoint_count"] == 1
    assert checkpoint["checkpoint_preflight_ready"] is True
    assert checkpoint["production_training_data_ready"] is True
    assert checkpoint["production_output_head_gap_contract_ready"] is True
    assert checkpoint["production_output_heads_complete"] is True
    assert checkpoint["production_output_head_ready_field_count"] == 7
    assert checkpoint["production_output_head_blocked_field_count"] == 0
    assert checkpoint["production_output_head_blocked_fields"] == []
    assert checkpoint["production_output_head_first_blocked_field"] == ""
    assert checkpoint["force_gpu_worker_return_receipt_ready"] is True
    assert checkpoint["force_gpu_worker_handoff_ready"] is True
    assert checkpoint["production_gpu_execution_environment_ready"] is True
    assert checkpoint["production_gpu_execution_environment_artifact_path"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert checkpoint["production_gpu_execution_environment_status"] == "rocm_environment_manifest_ready"
    assert checkpoint["production_gpu_rocm_manifest_ready"] is True
    assert checkpoint["production_gpu_rocm_stack_detected"] is True
    assert checkpoint["production_gpu_rocm_torch_ready"] is True
    assert checkpoint["production_gpu_rocm_amd_gpu_detected"] is True
    assert checkpoint["production_gpu_rocm_visible_device_count"] == 1
    assert checkpoint["production_gpu_rocm_device_names"] == ["AMD Radeon RX 6900 XT"]
    assert checkpoint["production_gpu_rocm_torch_version"].endswith("+rocm6.1")
    assert checkpoint["production_gpu_rocm_torch_hip_version"]
    assert checkpoint["production_gpu_rocm_visibility_diagnostic_packet_ready"] is True
    assert checkpoint["production_gpu_rocm_visibility_diagnostic_command_count"] == 5
    assert "rocminfo" in checkpoint["production_gpu_rocm_visibility_diagnostic_commands"]
    assert "visible_device_count" in checkpoint[
        "production_gpu_rocm_visibility_diagnostic_required_fields"
    ]
    assert "visible_device_count>0" in checkpoint[
        "production_gpu_rocm_visibility_diagnostic_completion_rule"
    ]
    assert "runs/rocm_environment_manifest_current.json" in checkpoint[
        "production_gpu_rocm_visibility_diagnostic_return_artifacts"
    ]
    assert checkpoint["production_gpu_rocm_visibility_torch_probe_command"].startswith("python3 -c")
    assert checkpoint["force_gpu_worker_handoff_required"] is True
    assert checkpoint["force_gpu_worker_operator_action_required"] is True
    assert checkpoint["force_gpu_worker_operator_transfer_manifest_ready"] is True
    assert checkpoint["force_gpu_worker_operator_transfer_outbound_artifact_count"] == 10
    assert "tools/generate_ligand_trajectory_engine.py" in checkpoint[
        "force_gpu_worker_operator_transfer_outbound_artifacts"
    ]
    assert "tools/build_rocm_environment_manifest.py" in checkpoint[
        "force_gpu_worker_operator_transfer_outbound_artifacts"
    ]
    assert checkpoint["force_gpu_worker_operator_transfer_inbound_artifact_count"] == 5
    assert checkpoint["force_gpu_worker_operator_transfer_first_return_artifact"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert checkpoint["force_gpu_worker_operator_transfer_return_manifest_artifact"] == (
        "runs/residual_force_trajectory_regeneration_current_manifest.csv"
    )
    assert checkpoint["force_gpu_worker_operator_transfer_acceptance_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert checkpoint["force_gpu_worker_operator_transfer_acceptance_ready_key"] == (
        "gpu_worker_return_receipt_ready"
    )
    assert checkpoint["force_gpu_worker_return_summary_template_payload_json"] == (
        "runs/residual_force_trajectory_regeneration_current_summary_template.json"
    )
    assert "generate_ligand_trajectory_engine.py" in checkpoint["force_gpu_worker_full_regeneration_command"]
    assert "build_residual_force_gpu_worker_return_receipt.py" in checkpoint[
        "force_gpu_worker_post_return_validation_command"
    ]
    assert checkpoint["force_gpu_worker_post_return_output_contract_ready"] is True
    assert checkpoint["force_gpu_worker_post_return_required_production_output_fields"] == [
        "delta_score",
        "corrected_score",
        "delta_energy",
        "delta_force",
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    ]
    assert checkpoint["force_gpu_worker_post_return_unlock_output_fields"] == [
        "delta_force",
        "uncertainty",
        "abstention_reason",
        "stage2_route_decision",
    ]
    assert "runs/residual_force_gpu_worker_return_receipt_current.json" in checkpoint[
        "force_gpu_worker_post_return_gpu_unlock_artifacts"
    ]
    assert checkpoint["force_gpu_worker_post_return_min_expected_label_rows"] == 768
    assert checkpoint["force_gpu_worker_post_return_promotion_ladder_ready"] is True
    assert checkpoint["force_gpu_worker_post_return_promotion_ladder_contract_ready"] is True
    assert checkpoint["force_gpu_worker_post_return_promotion_ladder_currently_satisfied"] is False
    assert checkpoint["force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count"] == int(
        checkpoint_source.get("force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_count") or 0
    )
    assert checkpoint["force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids"] == (
        checkpoint_source.get("force_gpu_worker_post_return_promotion_ladder_current_blocked_stage_ids")
    )
    assert checkpoint["force_gpu_worker_post_return_promotion_ladder_current_next_stage_id"] == checkpoint_source.get(
        "force_gpu_worker_post_return_promotion_ladder_current_next_stage_id"
    )
    assert checkpoint["force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact"] == (
        checkpoint_source.get("force_gpu_worker_post_return_promotion_ladder_current_next_stage_artifact")
    )
    assert checkpoint["force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command"] == (
        checkpoint_source.get("force_gpu_worker_post_return_promotion_ladder_current_next_stage_validation_command")
    )
    assert checkpoint["force_gpu_worker_post_return_promotion_ladder_stage_count"] == 10
    assert checkpoint["force_gpu_worker_post_return_promotion_ladder_stage_ids"][:2] == [
        "gpu_return_receipt",
        "force_derivation_validation",
    ]
    assert checkpoint["force_gpu_worker_post_return_promotion_ladder"][-1]["stage_id"] == (
        "product_goal_completion_audit"
    )
    assert checkpoint["force_gpu_worker_post_return_promotion_ladder_missing_ready_keys"] == []
    assert checkpoint["production_inference_acceptance_matrix_ready"] is (
        checkpoint_source.get("production_inference_acceptance_matrix_ready") is True
    )
    assert checkpoint["production_inference_acceptance_stage_count"] == int(
        checkpoint_source.get("production_inference_acceptance_stage_count") or 0
    )
    assert checkpoint["production_inference_acceptance_ready_stage_count"] == int(
        checkpoint_source.get("production_inference_acceptance_ready_stage_count") or 0
    )
    assert checkpoint["production_inference_acceptance_blocked_stage_count"] == int(
        checkpoint_source.get("production_inference_acceptance_blocked_stage_count") or 0
    )
    assert checkpoint["production_inference_acceptance_blocked_stage_ids"] == checkpoint_source.get(
        "production_inference_acceptance_blocked_stage_ids"
    )
    assert checkpoint["production_inference_acceptance_next_stage_id"] == checkpoint_source.get(
        "production_inference_acceptance_next_stage_id"
    )
    assert checkpoint["production_inference_acceptance_next_stage_artifact"] == checkpoint_source.get(
        "production_inference_acceptance_next_stage_artifact"
    )
    assert checkpoint["production_inference_acceptance_next_stage_validation_command"] == checkpoint_source.get(
        "production_inference_acceptance_next_stage_validation_command"
    )
    assert checkpoint["production_inference_acceptance_next_stage_unlock_fields"] == checkpoint_source.get(
        "production_inference_acceptance_next_stage_unlock_fields"
    )
    assert checkpoint["production_inference_acceptance_next_stage_required_checks"] == checkpoint_source.get(
        "production_inference_acceptance_next_stage_required_checks"
    )
    assert checkpoint["production_inference_actionable_blocker_stage_id"] == checkpoint_source.get(
        "production_inference_actionable_blocker_stage_id"
    )
    assert checkpoint["production_inference_actionable_blocker_check_id"] == checkpoint_source.get(
        "production_inference_actionable_blocker_check_id"
    )
    assert checkpoint["production_inference_actionable_blocker_artifact"] == checkpoint_source.get(
        "production_inference_actionable_blocker_artifact"
    )
    assert checkpoint["production_inference_actionable_blocker_observed"] == checkpoint_source.get(
        "production_inference_actionable_blocker_observed"
    )
    assert checkpoint["production_inference_actionable_blocker_required"] == checkpoint_source.get(
        "production_inference_actionable_blocker_required"
    )
    assert checkpoint["production_inference_actionable_blocker_next_action"] == checkpoint_source.get(
        "production_inference_actionable_blocker_next_action"
    )
    assert checkpoint["production_inference_actionable_blocker_validation_command"] == checkpoint_source.get(
        "production_inference_actionable_blocker_validation_command"
    )
    assert checkpoint["production_inference_actionable_blocker_unlock_fields"] == checkpoint_source.get(
        "production_inference_actionable_blocker_unlock_fields"
    )
    assert checkpoint["production_inference_actionable_blocker_downstream_blocked_stage_count"] == int(
        checkpoint_source.get("production_inference_actionable_blocker_downstream_blocked_stage_count") or 0
    )
    assert checkpoint["production_inference_next_after_actionable_blocker_stage_id"] == checkpoint_source.get(
        "production_inference_next_after_actionable_blocker_stage_id"
    )
    assert checkpoint["production_inference_next_after_actionable_blocker_artifact"] == checkpoint_source.get(
        "production_inference_next_after_actionable_blocker_artifact"
    )
    assert checkpoint["production_inference_next_after_actionable_blocker_validation_command"] == (
        checkpoint_source.get("production_inference_next_after_actionable_blocker_validation_command")
    )
    assert checkpoint["production_inference_next_after_actionable_blocker_required_checks"] == checkpoint_source.get(
        "production_inference_next_after_actionable_blocker_required_checks"
    )
    assert checkpoint["production_inference_next_after_actionable_blocker_unlock_fields"] == checkpoint_source.get(
        "production_inference_next_after_actionable_blocker_unlock_fields"
    )
    assert checkpoint["production_inference_next_after_actionable_blocker_next_action"] == checkpoint_source.get(
        "production_inference_next_after_actionable_blocker_next_action"
    )
    assert checkpoint["production_inference_actionable_blocker_blocks_registry_promotion"] is (
        checkpoint_source.get("production_inference_actionable_blocker_blocks_registry_promotion") is True
    )
    assert checkpoint["production_inference_actionable_operator_completion_packet_ready"] is (
        checkpoint_source.get("production_inference_actionable_operator_completion_packet_ready") is True
    )
    assert checkpoint["production_inference_actionable_operator_completion_packet"] == checkpoint_source.get(
        "production_inference_actionable_operator_completion_packet"
    )
    assert checkpoint["production_inference_actionable_operator_completion_diagnostic_command_count"] == int(
        checkpoint_source.get("production_inference_actionable_operator_completion_diagnostic_command_count")
        or 0
    )
    assert checkpoint["production_inference_actionable_operator_completion_diagnostic_commands"] == (
        checkpoint_source.get("production_inference_actionable_operator_completion_diagnostic_commands")
    )
    assert checkpoint["production_inference_actionable_operator_completion_diagnostic_required_fields"] == (
        checkpoint_source.get("production_inference_actionable_operator_completion_diagnostic_required_fields")
    )
    assert checkpoint["production_inference_actionable_operator_completion_diagnostic_completion_rule"] == (
        checkpoint_source.get("production_inference_actionable_operator_completion_diagnostic_completion_rule")
    )
    assert checkpoint["production_inference_actionable_operator_completion_torch_visibility_probe_command"] == (
        checkpoint_source.get("production_inference_actionable_operator_completion_torch_visibility_probe_command")
    )
    assert checkpoint["production_inference_worker_runtime_receipt_contract_ready"] is (
        checkpoint_source.get("production_inference_worker_runtime_receipt_contract_ready") is True
    )
    assert checkpoint["production_inference_worker_runtime_receipt_required_fields_or_columns"] == (
        checkpoint_source.get("production_inference_worker_runtime_receipt_required_fields_or_columns")
    )
    assert checkpoint["production_inference_worker_runtime_receipt_required_field_count"] == int(
        checkpoint_source.get("production_inference_worker_runtime_receipt_required_field_count") or 0
    )
    assert checkpoint["production_inference_worker_runtime_receipt_completion_rule"] == checkpoint_source.get(
        "production_inference_worker_runtime_receipt_completion_rule"
    )
    assert checkpoint["production_inference_worker_runtime_receipt_post_environment_next_stage_id"] == (
        checkpoint_source.get("production_inference_worker_runtime_receipt_post_environment_next_stage_id")
    )
    assert checkpoint["production_inference_worker_runtime_receipt_post_environment_next_artifact"] == (
        checkpoint_source.get("production_inference_worker_runtime_receipt_post_environment_next_artifact")
    )
    assert checkpoint["production_inference_worker_runtime_receipt_post_environment_validation_command"] == (
        checkpoint_source.get("production_inference_worker_runtime_receipt_post_environment_validation_command")
    )
    assert checkpoint["production_inference_worker_runtime_receipt_full_regeneration_command"] == (
        checkpoint_source.get("production_inference_worker_runtime_receipt_full_regeneration_command")
    )
    assert "generate_ligand_trajectory_engine.py" in checkpoint[
        "production_inference_worker_runtime_receipt_full_regeneration_command"
    ]
    assert checkpoint["production_inference_worker_runtime_receipt_guardrails"] == checkpoint_source.get(
        "production_inference_worker_runtime_receipt_guardrails"
    )
    assert len(checkpoint["production_inference_acceptance_matrix"]) == 8
    assert checkpoint["force_gpu_worker_post_run_validation_chain_current"] is (
        checkpoint_source.get("force_gpu_worker_post_run_validation_chain_current") is True
    )
    assert checkpoint["force_gpu_worker_post_run_validation_command_count"] == int(
        checkpoint_source.get("force_gpu_worker_post_run_validation_command_count") or 0
    )
    assert checkpoint["force_gpu_worker_post_run_validation_commands"] == checkpoint_source.get(
        "force_gpu_worker_post_run_validation_commands"
    )
    assert checkpoint["force_gpu_worker_post_run_validation_commands"][0] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert checkpoint["checkpoint_closure_blockers"] == checkpoint_source.get("checkpoint_closure_blockers")
    assert checkpoint["checkpoint_missing_output_fields"] == checkpoint_source.get("checkpoint_missing_output_fields")
    assert checkpoint["selected_sidecar_ready"] is (checkpoint_source.get("selected_sidecar_ready") is True)
    assert checkpoint["selected_sidecar_missing_output_fields"] == checkpoint_source.get(
        "selected_sidecar_missing_output_fields"
    )
    assert checkpoint["selected_sidecar_training_contract_ready"] is (
        checkpoint_source.get("selected_sidecar_training_contract_ready") is True
    )
    assert checkpoint["selected_sidecar_force_receipt_ready"] is (
        checkpoint_source.get("selected_sidecar_force_receipt_ready") is True
    )
    assert checkpoint["selected_sidecar_force_receipt_operator_verified"] is (
        checkpoint_source.get("selected_sidecar_force_receipt_operator_verified") is True
    )
    assert checkpoint["selected_sidecar_force_receipt_operator_verified_true_count"] == int(
        checkpoint_source.get("selected_sidecar_force_receipt_operator_verified_true_count") or 0
    )
    assert checkpoint["selected_sidecar_force_receipt_expected_queue_rows"] == int(
        checkpoint_source.get("selected_sidecar_force_receipt_expected_queue_rows") or 0
    )
    assert checkpoint["gpu_receipt_blockers"] == checkpoint_source.get("gpu_receipt_blockers")
    assert checkpoint["gpu_receipt_summary_manifest_bound"] is (
        checkpoint_source.get("gpu_receipt_summary_manifest_bound") is True
    )
    assert checkpoint["gpu_receipt_summary_out_manifest_csv_bound"] is (
        checkpoint_source.get("gpu_receipt_summary_out_manifest_csv_bound") is True
    )
    assert checkpoint["gpu_receipt_summary_out_summary_json_bound"] is (
        checkpoint_source.get("gpu_receipt_summary_out_summary_json_bound") is True
    )
    assert checkpoint["gpu_receipt_summary_manifest_row_counts_consistent"] is (
        checkpoint_source.get("gpu_receipt_summary_manifest_row_counts_consistent") is True
    )
    assert checkpoint["gpu_receipt_summary_manifest_csv"] == checkpoint_source.get(
        "gpu_receipt_summary_manifest_csv"
    )
    assert checkpoint["gpu_receipt_summary_out_manifest_csv"] == checkpoint_source.get(
        "gpu_receipt_summary_out_manifest_csv"
    )
    assert checkpoint["gpu_receipt_summary_out_summary_json"] == checkpoint_source.get(
        "gpu_receipt_summary_out_summary_json"
    )
    assert checkpoint["gpu_receipt_production_gpu_backend_provenance_ready"] is (
        checkpoint_source.get("gpu_receipt_production_gpu_backend_provenance_ready") is True
    )
    assert checkpoint["gpu_receipt_production_gpu_backend_rows"] == int(
        checkpoint_source.get("gpu_receipt_production_gpu_backend_rows") or 0
    )
    assert checkpoint["gpu_receipt_production_gpu_backend_non_production_rows"] == int(
        checkpoint_source.get("gpu_receipt_production_gpu_backend_non_production_rows") or 0
    )
    assert checkpoint["gpu_receipt_production_gpu_backend_prod_mode"] is (
        checkpoint_source.get("gpu_receipt_production_gpu_backend_prod_mode") is True
    )
    assert checkpoint["gpu_receipt_production_gpu_backend_require_rust_hip"] is (
        checkpoint_source.get("gpu_receipt_production_gpu_backend_require_rust_hip") is True
    )
    assert checkpoint["gpu_receipt_expected_queue_rows"] == int(
        checkpoint_source.get("gpu_receipt_expected_queue_rows") or 0
    )
    assert checkpoint["gpu_receipt_expected_npz_count"] == int(
        checkpoint_source.get("gpu_receipt_expected_npz_count") or 0
    )
    assert checkpoint["gpu_receipt_queue_id_count"] == int(
        checkpoint_source.get("gpu_receipt_queue_id_count") or 0
    )
    assert checkpoint["gpu_receipt_queue_fingerprint_count"] == int(
        checkpoint_source.get("gpu_receipt_queue_fingerprint_count") or 0
    )
    assert checkpoint["gpu_receipt_manifest_row_count"] == int(
        checkpoint_source.get("gpu_receipt_manifest_row_count") or 0
    )
    assert checkpoint["gpu_receipt_manifest_ok_row_count"] == int(
        checkpoint_source.get("gpu_receipt_manifest_ok_row_count") or 0
    )
    assert checkpoint["gpu_receipt_manifest_identity_row_count"] == int(
        checkpoint_source.get("gpu_receipt_manifest_identity_row_count") or 0
    )
    assert checkpoint["gpu_receipt_manifest_matched_queue_id_count"] == int(
        checkpoint_source.get("gpu_receipt_manifest_matched_queue_id_count") or 0
    )
    assert checkpoint["gpu_receipt_manifest_matched_expected_npz_count"] == int(
        checkpoint_source.get("gpu_receipt_manifest_matched_expected_npz_count") or 0
    )
    assert checkpoint["gpu_receipt_manifest_matched_queue_fingerprint_count"] == int(
        checkpoint_source.get("gpu_receipt_manifest_matched_queue_fingerprint_count") or 0
    )
    assert checkpoint["gpu_receipt_manifest_operator_verified"] is (
        checkpoint_source.get("gpu_receipt_manifest_operator_verified") is True
    )
    assert checkpoint["gpu_receipt_operator_verified_true_count"] == int(
        checkpoint_source.get("gpu_receipt_operator_verified_true_count") or 0
    )
    assert checkpoint["gpu_receipt_identity_coverage_ready"] is (
        checkpoint_source.get("gpu_receipt_identity_coverage_ready") is True
    )
    assert checkpoint["training_data_failed_check_ids"] == checkpoint_source.get(
        "training_data_failed_check_ids"
    )
    assert checkpoint["training_data_missing_output_labels"] == checkpoint_source.get(
        "training_data_missing_output_labels"
    )

    gpu_dispatch = asyncio.run(product.get_product_production_ai_gpu_worker_dispatch_manifest())
    assert gpu_dispatch["status"] == "residual_force_gpu_worker_dispatch_manifest_ready"
    assert gpu_dispatch["dispatch_manifest_ready"] is True
    assert gpu_dispatch["handoff_package_ready"] is True
    assert gpu_dispatch["queue_rows"] == 768
    assert gpu_dispatch["outbound_artifact_count"] == 10
    assert gpu_dispatch["inbound_artifact_count"] == 5
    assert gpu_dispatch["local_artifact_missing_count"] == 0
    assert gpu_dispatch["native_pdb_dependency_count"] >= 1
    assert gpu_dispatch["native_pdb_missing_count"] == 0
    assert len(gpu_dispatch["queue_csv_sha256"]) == 64
    assert "generate_ligand_trajectory_engine.py" in gpu_dispatch["tiny_pilot_command"]
    assert "generate_ligand_trajectory_engine.py" in gpu_dispatch["full_regeneration_command"]
    assert gpu_dispatch["acceptance_contract"]["return_receipt_ready_key"] == (
        "gpu_worker_return_receipt_ready"
    )
    assert "queue_row_fingerprint" in gpu_dispatch["return_manifest_required_identity_rule"]
    assert "visible_device_count>0" in gpu_dispatch["worker_rocm_manifest_completion_rule"]
    assert sum(1 for row in gpu_dispatch["rows"] if row["local_file_reference"] is True) == (
        gpu_dispatch["local_artifact_reference_count"]
    )
    assert gpu_dispatch["execution_enabled"] is False
    assert gpu_dispatch["full_regeneration_executed"] is False
    assert gpu_dispatch["model_promoted"] is False

    gpu_bundle = asyncio.run(product.get_product_production_ai_gpu_worker_dispatch_bundle())
    assert gpu_bundle["status"] == "residual_force_gpu_worker_dispatch_bundle_ready"
    assert gpu_bundle["dispatch_bundle_ready"] is True
    assert gpu_bundle["dispatch_manifest_ready"] is True
    assert gpu_bundle["bundle_tar_exists"] is True
    assert gpu_bundle["bundle_tar_path"] == "runs/residual_force_gpu_worker_dispatch_bundle_current.tar.gz"
    assert len(gpu_bundle["bundle_tar_sha256"]) == 64
    assert gpu_bundle["bundle_member_count"] == gpu_bundle["source_artifact_count"]
    assert gpu_bundle["source_artifact_count"] == gpu_dispatch["local_artifact_reference_count"]
    assert gpu_bundle["local_artifact_missing_count"] == 0
    assert gpu_bundle["native_pdb_dependency_count"] == 3
    assert gpu_bundle["native_pdb_missing_count"] == 0
    assert gpu_bundle["queue_rows"] == 768
    assert gpu_bundle["acceptance_contract"]["return_receipt_ready_key"] == (
        "gpu_worker_return_receipt_ready"
    )
    assert gpu_bundle["execution_enabled"] is False
    assert gpu_bundle["full_regeneration_executed"] is False
    assert gpu_bundle["model_promoted"] is False

    gpu_runbook = asyncio.run(product.get_product_production_ai_gpu_worker_execution_runbook())
    assert gpu_runbook["status"] == "residual_force_gpu_worker_execution_runbook_ready"
    assert gpu_runbook["execution_runbook_ready"] is True
    assert gpu_runbook["dispatch_bundle_ready"] is True
    assert gpu_runbook["bundle_tar_path"] == "runs/residual_force_gpu_worker_dispatch_bundle_current.tar.gz"
    assert len(gpu_runbook["bundle_tar_sha256"]) == 64
    assert gpu_runbook["queue_rows"] == 768
    assert gpu_runbook["worker_script_path"] == "runs/residual_force_gpu_worker_execution_runbook_current.sh"
    assert gpu_runbook["worker_script_exists"] is True
    assert gpu_runbook["worker_script_executable"] is True
    assert gpu_runbook["return_packager_script_path"] == (
        "runs/residual_force_gpu_worker_return_bundle_packager_current.sh"
    )
    assert gpu_runbook["return_packager_script_exists"] is True
    assert gpu_runbook["return_packager_script_executable"] is True
    assert gpu_runbook["return_bundle_tar_path"] == (
        "runs/residual_force_gpu_worker_return_bundle_current.tar.gz"
    )
    assert gpu_runbook["return_bundle_sha256_path"].endswith(".tar.gz.sha256")
    assert "expected_regenerated_trajectory_npz" in gpu_runbook["manifest_npz_path_columns"]
    assert "runs/residual_force_trajectory_regeneration_current_summary.json" in gpu_runbook[
        "required_return_core_files"
    ]
    assert gpu_runbook["return_packager_command"] == (
        "bash runs/residual_force_gpu_worker_return_bundle_packager_current.sh"
    )
    assert gpu_runbook["step_count"] == 8
    assert gpu_runbook["worker_executable_step_count"] == 6
    assert gpu_runbook["required_return_artifact_count"] == 5
    assert "runs/rocm_environment_manifest_current.json" in gpu_runbook["required_return_artifacts"]
    assert "generate_ligand_trajectory_engine.py" in gpu_runbook["tiny_pilot_command"]
    assert "generate_ligand_trajectory_engine.py" in gpu_runbook["full_regeneration_command"]
    assert "build_residual_force_gpu_worker_return_receipt.py" in gpu_runbook[
        "post_return_validation_command"
    ]
    assert gpu_runbook["execution_enabled"] is False
    assert gpu_runbook["full_regeneration_executed"] is False
    assert gpu_runbook["model_promoted"] is False

    gpu_return = asyncio.run(product.get_product_production_ai_gpu_return_intake())
    assert gpu_return["status"] == "blocked_product_production_ai_gpu_return_intake"
    assert gpu_return["gpu_return_intake_ready"] is True
    assert gpu_return["gpu_return_artifacts_ready"] is False
    assert gpu_return["pass_check_count"] == 15
    assert gpu_return["check_count"] == 20
    assert gpu_return["fail_check_count"] == 5
    assert gpu_return["failed_check_ids"] == [
        "actual_manifest_npz_files_exist",
        "actual_manifest_npz_files_valid",
        "actual_manifest_npz_schema_valid",
        "actual_manifest_npz_identity_valid",
        "post_run_force_derivation_validation",
    ]
    assert gpu_return["expected_queue_rows"] == 768
    assert gpu_return["operator_return_blocker_count"] == 5
    assert gpu_return["operator_return_bundle_contract_ready"] is True
    assert gpu_return["operator_return_required_artifact_count"] == 5
    assert gpu_return["operator_return_required_artifacts"] == [
        "runs/residual_force_trajectory_regeneration_current_summary.json",
        "runs/residual_force_trajectory_regeneration_current_manifest.csv",
        "regenerated NPZ bundles referenced by the returned manifest",
        "runs/residual_force_derivation_validation_current.json",
        "runs/rocm_environment_manifest_current.json",
    ]
    assert gpu_return["operator_return_manifest_required_columns"] == [
        "queue_id",
        "expected_regenerated_trajectory_npz",
        "status",
        "operator_verified_npz_exists",
    ]
    assert gpu_return["operator_return_validation_ladder_ready"] is True
    assert gpu_return["operator_return_handoff_binding_ready"] is True
    assert gpu_return["operator_return_handoff_queue_csv"] == (
        "runs/residual_force_trajectory_regeneration_queue_current.csv"
    )
    assert len(gpu_return["operator_return_handoff_queue_csv_sha256"]) == 64
    assert "generate_ligand_trajectory_engine.py" in gpu_return[
        "operator_return_handoff_full_regeneration_command"
    ]
    assert gpu_return["operator_return_handoff_return_manifest_schema_contract_ready"] is True
    assert "queue_row_fingerprint" in gpu_return[
        "operator_return_handoff_return_manifest_required_identity_rule"
    ]
    assert "queue_row_fingerprint" in gpu_return[
        "operator_return_handoff_return_manifest_fingerprint_columns"
    ]
    assert "queue_id" in gpu_return["operator_return_handoff_return_manifest_queue_id_columns"]
    assert "expected_regenerated_trajectory_npz" in gpu_return[
        "operator_return_handoff_return_manifest_npz_columns"
    ]
    assert gpu_return["operator_acceptance_matrix_ready"] is True
    assert gpu_return["operator_acceptance_stage_count"] == 5
    assert gpu_return["operator_acceptance_ready_stage_count"] == 2
    assert gpu_return["operator_acceptance_blocked_stage_count"] == 3
    assert gpu_return["operator_acceptance_blocked_stage_ids"] == [
        "returned_manifest_npz_acceptance",
        "force_derivation_acceptance",
        "post_return_promotion_chain",
    ]
    assert gpu_return["operator_acceptance_next_stage_id"] == "returned_manifest_npz_acceptance"
    assert gpu_return["operator_acceptance_next_stage_artifact"] == (
        "runs/residual_force_trajectory_regeneration_current_manifest.csv;regenerated NPZ "
        "bundles referenced by manifest"
    )
    assert gpu_return["operator_acceptance_next_stage_validation_command"] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert gpu_return["operator_acceptance_next_stage_release_effect"] == (
        "returned manifest, NPZ bundle existence, schema, identity, and operator "
        "verification are accepted"
    )
    assert gpu_return["operator_acceptance_next_stage_required_checks"] == [
        "actual_manifest_returned_complete",
        "actual_manifest_npz_paths_complete",
        "actual_manifest_npz_files_exist",
        "actual_manifest_npz_files_valid",
        "actual_manifest_npz_schema_valid",
        "actual_manifest_npz_identity_valid",
        "actual_manifest_operator_verified",
        "queue_manifest_identity_coverage",
    ]
    assert len(gpu_return["operator_acceptance_matrix"]) == 5
    assert gpu_return["operator_acceptance_stage_check_matrix_count"] == 5
    assert gpu_return["operator_acceptance_current_blocked_stage_check_matrix_count"] == 3
    assert gpu_return["operator_acceptance_stage_check_matrix"][1]["stage_id"] == (
        "returned_summary_acceptance"
    )
    assert gpu_return["operator_acceptance_stage_check_matrix"][1]["failed_check_ids"] == []
    assert gpu_return["operator_acceptance_current_blocked_stage_check_matrix"][0][
        "stage_id"
    ] == "returned_manifest_npz_acceptance"
    assert gpu_return["operator_return_artifact_completion_matrix_count"] == 5
    assert gpu_return["operator_return_artifact_completion_blocker_count"] == 2
    assert gpu_return["operator_return_next_artifact_id"] == "regenerated_npz_bundles"
    assert gpu_return["operator_return_next_artifact_path"] == (
        "regenerated NPZ bundles referenced by the returned manifest"
    )
    assert gpu_return["operator_return_next_artifact_failed_check_ids"] == [
        "actual_manifest_npz_files_exist",
        "actual_manifest_npz_files_valid",
        "actual_manifest_npz_schema_valid",
        "actual_manifest_npz_identity_valid",
    ]
    assert gpu_return["operator_return_next_artifact_completion_packet_ready"] is True
    assert gpu_return["operator_return_next_artifact_completion_packet"]["artifact_id"] == (
        "regenerated_npz_bundles"
    )
    assert gpu_return["operator_return_next_artifact_completion_packet"]["template_payload"][
        "queue_rows"
    ] == 768
    assert gpu_return["operator_return_next_artifact_completion_packet"]["template_payload"][
        "prod_mode"
    ] is True
    assert gpu_return["operator_return_artifact_completion_matrix"][0]["artifact_id"] == "returned_summary_json"
    assert gpu_return["operator_return_artifact_completion_blocker_matrix"][0]["artifact_id"] == (
        "regenerated_npz_bundles"
    )
    assert gpu_return["first_failed_check_id"] == "actual_manifest_npz_files_exist"
    assert gpu_return["first_failed_source_artifact"] == (
        "runs/residual_force_gpu_worker_return_receipt_current.json"
    )
    assert gpu_return["first_failed_required"] == (
        "actual returned manifest NPZ paths resolve to local files for every ok and "
        "operator-verified row"
    )
    assert gpu_return["first_failed_next_action"] == (
        "Restore or return the regenerated NPZ files at the manifest paths before accepting "
        "the GPU return."
    )
    assert gpu_return["handoff_ready"] is True
    assert gpu_return["operator_action_required"] is True
    assert gpu_return["manifest_template_ready"] is True
    assert gpu_return["manifest_template_row_count"] == 768
    assert gpu_return["manifest_status_placeholder_count"] == 768
    assert gpu_return["manifest_operator_verification_placeholder_count"] == 768
    assert gpu_return["summary_template_ready"] is True
    assert gpu_return["summary_template_csv"] == "runs/residual_force_gpu_worker_return_summary_template_current.csv"
    assert gpu_return["summary_template_payload_json"] == (
        "runs/residual_force_trajectory_regeneration_current_summary_template.json"
    )
    assert gpu_return["summary_template_payload"]["queue_rows"] == 768
    assert gpu_return["summary_template_payload"]["prod_mode"] is True
    assert gpu_return["summary_template_payload"]["require_rust_hip"] is True
    assert gpu_return["summary_template_payload"]["out_manifest_csv"] == (
        "runs/residual_force_trajectory_regeneration_current_manifest.csv"
    )
    assert gpu_return["summary_template_field_count"] == 10
    assert gpu_return["summary_template_required_fields"] == [
        "queue_rows",
        "processed_rows",
        "ok_rows",
        "failed_rows",
        "aborted_early",
        "out_manifest_csv",
        "out_summary_json",
        "prod_mode",
        "require_rust_hip",
        "backend_counts",
    ]
    assert "processed_rows>=expected_queue_rows" in gpu_return["summary_template_completion_rule"]
    assert gpu_return["summary_template_backend_provenance_contract_ready"] is True
    assert gpu_return["summary_template_required_backend_provenance_fields"] == [
        "prod_mode",
        "require_rust_hip",
        "backend_counts",
    ]
    assert "backend_counts has rust_hip*" in gpu_return[
        "summary_template_backend_provenance_completion_rule"
    ]
    assert gpu_return["summary_returned"] is True
    assert gpu_return["manifest_returned"] is True
    assert gpu_return["manifest_npz_paths_complete"] is True
    assert gpu_return["manifest_npz_files_exist"] is False
    assert gpu_return["manifest_npz_files_valid"] is False
    assert gpu_return["manifest_npz_schema_valid"] is False
    assert gpu_return["manifest_npz_identity_valid"] is False
    assert gpu_return["manifest_npz_path_column_present"] is True
    assert gpu_return["manifest_npz_path_present_count"] == 768
    assert gpu_return["manifest_ok_row_missing_npz_path_count"] == 0
    assert gpu_return["manifest_operator_verified_missing_npz_path_count"] == 0
    assert gpu_return["manifest_npz_file_existing_count"] == 0
    assert gpu_return["manifest_npz_file_missing_count"] == 768
    assert gpu_return["manifest_ok_row_missing_npz_file_count"] == 768
    assert gpu_return["manifest_operator_verified_missing_npz_file_count"] == 768
    assert gpu_return["manifest_npz_file_valid_count"] == 0
    assert gpu_return["manifest_npz_file_invalid_count"] == 0
    assert gpu_return["manifest_ok_row_invalid_npz_file_count"] == 0
    assert gpu_return["manifest_operator_verified_invalid_npz_file_count"] == 0
    assert gpu_return["manifest_npz_schema_valid_count"] == 0
    assert gpu_return["manifest_npz_schema_invalid_count"] == 0
    assert gpu_return["manifest_ok_row_invalid_npz_schema_count"] == 0
    assert gpu_return["manifest_operator_verified_invalid_npz_schema_count"] == 0
    assert gpu_return["manifest_npz_identity_valid_count"] == 0
    assert gpu_return["manifest_npz_identity_invalid_count"] == 768
    assert gpu_return["manifest_ok_row_invalid_npz_identity_count"] == 768
    assert gpu_return["manifest_operator_verified_invalid_npz_identity_count"] == 768
    assert gpu_return["manifest_operator_verified"] is True
    assert gpu_return["identity_coverage_ready"] is True
    assert gpu_return["post_run_derivation_validation_ready"] is False
    assert gpu_return["summary_manifest_bound"] is True
    assert gpu_return["summary_manifest_csv"] == "runs/residual_force_trajectory_regeneration_current_manifest.csv"
    assert gpu_return["summary_out_manifest_csv_present"] is True
    assert gpu_return["summary_out_manifest_csv"] == "runs/residual_force_trajectory_regeneration_current_manifest.csv"
    assert gpu_return["summary_out_manifest_csv_bound"] is True
    assert gpu_return["summary_out_summary_json_bound"] is True
    assert gpu_return["summary_out_summary_json"] == "runs/residual_force_trajectory_regeneration_current_summary.json"
    assert gpu_return["summary_manifest_row_counts_consistent"] is True
    assert gpu_return["production_gpu_backend_provenance_ready"] is True
    assert gpu_return["production_gpu_backend_rows"] == 768
    assert gpu_return["production_gpu_backend_non_production_rows"] == 0
    assert gpu_return["production_gpu_backend_prod_mode"] is True
    assert gpu_return["production_gpu_backend_require_rust_hip"] is True
    assert gpu_return["post_run_validation_command_count"] == 18
    assert gpu_return["post_run_validation_commands"][0] == (
        "python3 tools/build_residual_force_gpu_worker_return_receipt.py"
    )
    assert "python3 tools/build_residual_model_registry.py" in gpu_return["post_run_validation_commands"]
    assert "python3 tools/build_residual_force_gpu_worker_return_receipt.py &&" in gpu_return[
        "post_return_validation_command"
    ]
    assert gpu_return["failed_check_ids"] == [
        "actual_manifest_npz_files_exist",
        "actual_manifest_npz_files_valid",
        "actual_manifest_npz_schema_valid",
        "actual_manifest_npz_identity_valid",
        "post_run_force_derivation_validation",
    ]
    assert gpu_return["worker_rocm_manifest_ready"] is True
    assert gpu_return["worker_rocm_visible_device_count"] == 1
    assert "visible_device_count>0" in gpu_return["worker_rocm_manifest_completion_rule"]
    assert len(gpu_return["checks"]) == 20
    assert len(gpu_return["blockers"]) == 5
    assert gpu_return["execution_enabled"] is False
    assert gpu_return["model_promoted"] is False
    assert gpu_return["external_state_mutated"] is False

    promotion = asyncio.run(product.get_product_production_ai_promotion_workbench())
    promotion_source = _artifact_summary("product_production_ai_promotion_workbench_current.json")
    assert promotion["status"] == promotion_source.get("status")
    for key in (
        "promotion_workbench_ready",
        "production_ai_promotion_ready",
        "production_ai_checkpoint_ready",
        "production_promotion_allowed",
        "registry_promotion_upstream_acceptance_ready",
        "registry_promotion_currently_satisfied",
        "gpu_handoff_ready",
        "gpu_operator_action_required",
        "gpu_return_receipt_ready",
        "selected_sidecar_ready",
    ):
        assert promotion[key] is (promotion_source.get(key) is True)
    for key in (
        "registry_promotion_missing_gate_count",
        "trained_model_checkpoint_count",
        "gpu_receipt_expected_queue_rows",
        "gpu_receipt_manifest_identity_row_count",
        "post_return_promotion_ladder_stage_count",
        "post_return_promotion_ladder_ready_stage_count",
        "post_return_promotion_ladder_blocked_stage_count",
        "ready_key_alias_used_count",
    ):
        assert promotion[key] == int(promotion_source.get(key) or 0)
    for key in (
        "registry_promotion_missing_gate_ids",
        "default_residual_mode",
        "ready_key_alias_used_stage_ids",
        "blocked_stage_ids",
        "first_blocked_stage_id",
        "first_blocked_stage_ready_key",
        "selected_sidecar_missing_output_fields",
        "training_data_missing_output_labels",
    ):
        assert promotion[key] == promotion_source.get(key)
    assert promotion["promotion_stages"][0]["stage_id"] == promotion_source["post_return_promotion_ladder_stage_ids"][0]
    assert promotion["promotion_stages"][-1]["stage_id"] == promotion_source["post_return_promotion_ladder_stage_ids"][-1]
    assert "generate_ligand_trajectory_engine.py" in promotion["force_gpu_worker_full_regeneration_command"]
    assert "build_residual_force_gpu_worker_return_receipt.py" in promotion[
        "force_gpu_worker_post_return_validation_command"
    ]
    assert promotion["execution_enabled"] is False
    assert promotion["model_promoted"] is False
    assert promotion["external_state_mutated"] is False

    registry_receipt = asyncio.run(
        product.get_product_production_ai_registry_promotion_operator_receipt()
    )
    assert registry_receipt["status"] == "blocked_production_ai_registry_promotion_operator_receipt"
    assert registry_receipt["operator_receipt_ready"] is False
    assert registry_receipt["receipt_present"] is True
    assert registry_receipt["receipt_row_count"] == 1
    assert registry_receipt["blocked_row_count"] == 1
    assert registry_receipt["first_blocked_artifact_id"] == (
        "residual_model_registry_guarded_promotion"
    )
    assert registry_receipt["first_blocked_row_blocker"] == "operator_placeholders_unfilled"
    assert registry_receipt["approval_token_required"] == (
        "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
    )
    assert registry_receipt["registry_artifact_present"] is True
    assert registry_receipt["checkpoint_readiness_artifact_present"] is True
    assert registry_receipt["observed_registry_default_residual_mode"] == "shadow"
    assert registry_receipt["observed_registry_trained_model_checkpoint_count"] == 1
    assert registry_receipt["observed_checkpoint_registry_promotion_currently_satisfied"] is False
    assert registry_receipt["observed_checkpoint_registry_promotion_missing_gate_ids"] == [
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
        "default_residual_mode_guarded",
    ]
    assert len(registry_receipt["receipt_rows"]) == registry_receipt["receipt_row_count"]
    assert registry_receipt["registry_edited_by_this_tool"] is False
    assert registry_receipt["checkpoint_created_by_this_tool"] is False
    assert registry_receipt["execution_enabled"] is False
    assert registry_receipt["docking_results_emitted"] is False
    assert registry_receipt["external_state_mutated"] is False
    assert registry_receipt["model_promoted"] is False

    registry_priority = asyncio.run(product.get_product_production_ai_registry_promotion_priority())
    assert registry_priority["status"] == "blocked_production_ai_registry_promotion_priority_packet"
    assert registry_priority["priority_packet_ready"] is True
    assert registry_priority["registry_promotion_ready"] is False
    assert registry_priority["operator_receipt_ready"] is False
    assert registry_priority["operator_receipt_status"] == (
        "blocked_production_ai_registry_promotion_operator_receipt"
    )
    assert registry_priority["priority_item_count"] == 4
    assert registry_priority["operator_input_required_count"] == 3
    assert registry_priority["blocked_priority_item_count"] == 3
    assert registry_priority["registry_promotion_missing_gate_ids"] == [
        "default_residual_mode_guarded",
        "production_promotion_allowed",
        "customer_facing_mutation_flags",
    ]
    assert registry_priority["top_gate_id"] == "default_residual_mode_guarded"
    assert registry_priority["top_priority_bucket"] == "guarded_residual_mode_selection_required"
    assert registry_priority["top_acceptance_artifact"] == "runs/residual_model_registry_current.json"
    assert registry_priority["observed_registry_default_residual_mode"] == "shadow"
    assert registry_priority["observed_registry_trained_model_checkpoint_count"] == 1
    assert registry_priority["approval_token_required"] == "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
    assert len(registry_priority["priority_items"]) == registry_priority["priority_item_count"]
    assert registry_priority["priority_items"][0]["gate_id"] == "trained_model_checkpoint_count_positive"
    assert registry_priority["registry_edited_by_this_tool"] is False
    assert registry_priority["checkpoint_created_by_this_tool"] is False
    assert registry_priority["execution_enabled"] is False
    assert registry_priority["docking_results_emitted"] is False
    assert registry_priority["external_state_mutated"] is False
    assert registry_priority["model_promoted"] is False
    assert registry_priority["customer_facing_mutation_enabled"] is False

    scope_breadth = asyncio.run(product.get_product_scope_breadth_contract())
    assert scope_breadth["status"] == "blocked_product_scope_breadth_contract"
    assert scope_breadth["scope_breadth_ready"] is False
    assert scope_breadth["scope_widened"] is False
    assert scope_breadth["scope_claim_posture_ready"] is True
    assert scope_breadth["restricted_scope_claim_allowed"] is True
    assert scope_breadth["allowed_scope_families"] == ["gpcr", "ion_channel", "kinase"]
    assert scope_breadth["domain_count"] == 6
    assert scope_breadth["ready_domain_count"] == 3
    assert scope_breadth["missing_domain_count"] == 3
    assert scope_breadth["ready_domains"] == [
        "ca2",
        "pxr",
        "all_atom",
    ]
    assert scope_breadth["missing_domains"] == [
        "transporter",
        "idp_broad",
        "general_protein_ligand",
    ]
    assert scope_breadth["first_blocked_domain"] == "transporter"
    assert scope_breadth["first_blocked_domain_artifact"] == "runs/transporter_blocker_capture_sheet_current.json"
    assert "supportive=6" in scope_breadth["first_blocked_domain_observed"]
    assert "supportive transporter evidence" in scope_breadth["first_blocked_domain_requirement"]
    assert "Close the remaining AQP1" in scope_breadth["first_blocked_domain_next_action"]
    assert scope_breadth["transporter_p0_closure_packet_ready"] is True
    assert scope_breadth["transporter_p0_current_membrane_open_count"] == 1
    assert scope_breadth["transporter_p0_closure_row_count"] == 1
    assert scope_breadth["transporter_p0_count_matches_readiness"] is True
    assert scope_breadth["transporter_p0_aqp1_core_open_count"] == 1
    assert scope_breadth["transporter_p0_glut1_core_open_count"] == 0
    assert scope_breadth["evidence_queue_next_operator_completion_aqp1_review_sidecar_ready"] is True
    assert scope_breadth["evidence_queue_next_operator_completion_aqp1_review_candidate_name"] == "bacopaside II"
    assert scope_breadth["evidence_queue_next_operator_completion_aqp1_review_source_anchor"] == "PMID 27474162"
    assert scope_breadth["evidence_queue_next_operator_completion_aqp1_review_target_uniprot"] == "P29972"
    assert scope_breadth["evidence_queue_pxr_exact_review_sidecar_row_count"] == 0
    assert scope_breadth["evidence_queue_next_pxr_exact_review_sidecar_ready"] is False
    assert scope_breadth["evidence_queue_next_pxr_exact_review_row_id"] == ""
    assert scope_breadth["evidence_queue_next_pxr_exact_review_candidate_name"] == ""
    assert scope_breadth["evidence_queue_next_pxr_exact_review_required_evidence_mode"] == ""
    assert scope_breadth["evidence_queue_next_pxr_exact_review_target_match_confirmed"] == ""
    assert scope_breadth["evidence_queue_next_pxr_exact_review_replacement_reference_binding_kcal_mol"] == ""
    assert scope_breadth["evidence_queue_next_pxr_exact_review_authoritative_apply_allowed"] is False
    assert scope_breadth["evidence_queue_next_pxr_exact_review_scope_promotion_allowed"] is False
    assert scope_breadth["pxr_source_modality_triage_ready"] is True
    assert scope_breadth["pxr_source_modality_triage_artifact"] == "runs/pxr_source_modality_triage_current.json"
    assert scope_breadth[
        "pxr_source_modality_activity_proxy_or_conflict_surrogate_row_count"
    ] == 0
    assert scope_breadth[
        "pxr_source_modality_direct_or_claim_safe_quantitative_ready_count"
    ] == 0
    assert scope_breadth["pxr_source_modality_next_review_candidate_name"] == ""
    assert scope_breadth["pxr_source_modality_next_review_source_modality"] == ""
    assert scope_breadth["transporter_target_ready_for_promotion_count"] == 1
    assert scope_breadth["transporter_target_blocked_for_promotion_count"] == 1
    assert scope_breadth["transporter_target_ready_for_promotion_ids"] == ["GLUT1"]
    assert scope_breadth["transporter_target_blocked_for_promotion_ids"] == ["AQP1"]
    assert scope_breadth["transporter_primary_blocker_target_id"] == "AQP1"
    assert scope_breadth["transporter_primary_blocker_packet_step"] == "core_binder_01"
    assert scope_breadth["transporter_primary_blocker_candidate_name"] == "bacopaside II"
    assert scope_breadth["blocked_claim_scopes"] == [
        "transporter_domain_promotion",
        "general_protein_ligand_platform",
    ]
    assert scope_breadth["general_platform_claim_allowed"] is False
    assert scope_breadth["general_platform_claim_blocked"] is True
    assert scope_breadth["scope_acceptance_matrix_ready"] is True
    assert scope_breadth["scope_acceptance_stage_count"] == 5
    assert scope_breadth["scope_acceptance_blocked_stage_count"] == 3
    assert scope_breadth["scope_acceptance_next_stage_id"] == "transporter_claim_acceptance"
    assert len(scope_breadth["scope_acceptance_matrix"]) == scope_breadth["scope_acceptance_stage_count"]
    assert scope_breadth["scope_acceptance_stage_evidence_matrix_count"] == 5
    assert scope_breadth["scope_acceptance_current_blocked_stage_evidence_matrix_count"] == 3
    assert len(scope_breadth["domain_rows"]) == scope_breadth["domain_count"]

    scope_guard = asyncio.run(product.get_product_scope_claim_guard())
    assert scope_guard["status"] == "product_scope_breadth_closure_checklist_ready"
    assert scope_guard["scope_breadth_ready"] is False
    assert scope_guard["closure_checklist_ready"] is True
    assert scope_guard["scope_promotion_allowed"] is False
    assert scope_guard["authoritative_apply_allowed"] is False
    assert scope_guard["allowed_scope_families"] == ["gpcr", "ion_channel", "kinase"]
    assert scope_guard["blocked_claim_scopes"] == [
        "transporter_domain_promotion",
        "general_protein_ligand_platform",
    ]
    assert scope_guard["claim_blocked_domains"] == ["transporter", "idp_broad"]
    assert scope_guard["general_platform_claim_allowed"] is False
    assert scope_guard["manual_review_subcheck_count"] == 39
    assert scope_guard["transporter_manual_review_subcheck_count"] == 39
    assert scope_guard["transporter_identity_scaffold_confirmation_required_count"] >= 0
    assert scope_guard["transporter_direct_binding_or_kcal_confirmation_required_count"] >= 0
    assert scope_guard["transporter_negative_quantitative_confirmation_required_count"] >= 0
    assert scope_guard["transporter_direct_binding_missing_count"] >= 0
    assert scope_guard["transporter_negative_quantitative_missing_count"] >= 0
    assert scope_guard["pxr_reconciled_blocked_row_count"] == 0
    assert scope_guard["general_claim_blocker_count"] == 4
    assert scope_guard["ready_for_apply_count"] == 0
    assert len(scope_guard["claim_boundary_matrix"]) == scope_guard["general_claim_blocker_count"]
    assert len(scope_guard["closure_items"]) == scope_guard["checklist_row_count"]

    scope_priority = asyncio.run(product.get_product_scope_evidence_priority())
    assert scope_priority["status"] == "product_scope_breadth_evidence_priority_packet_ready"
    assert scope_priority["priority_packet_ready"] is True
    assert scope_priority["scope_promotion_allowed"] is False
    assert scope_priority["authoritative_apply_allowed"] is False
    assert scope_priority["queue_item_count"] == 15
    assert scope_priority["open_item_count"] == 15
    assert scope_priority["scientific_evidence_request_count"] == 11
    assert scope_priority["local_crosscheck_candidate_count"] == 11
    assert scope_priority["external_primary_exact_evidence_required_count"] == 0
    assert scope_priority["all_operator_packet_bindings_ready"] is True
    assert scope_priority["operator_packet_binding_ready_count"] == 15
    assert scope_priority["operator_packet_binding_missing_count"] == 0
    assert scope_priority["top_item_id"] == "AQP1.core_binder_01"
    assert scope_priority["top_required_evidence_type"] == "exact_transporter_target_pair_quantitative_binder_kcal"
    assert scope_priority["top_review_template_artifact"] == "runs/transporter_manual_review_intake_template_current.json"
    assert scope_priority["top_apply_gate_artifact"] == "runs/transporter_binder_promotion_gate_current.json"
    assert scope_priority["receipt_status"] == "blocked_product_scope_breadth_evidence_receipt"
    assert scope_priority["receipt_ready"] is False
    assert scope_priority["receipt_row_count"] == 6
    assert scope_priority["receipt_blocked_row_count"] == 6
    assert scope_priority["receipt_operator_review_surface_ready_count"] == 6
    assert scope_priority["receipt_operator_review_surface_blocked_count"] == 0
    assert scope_priority["receipt_manual_field_pending_count"] == 36
    assert scope_priority["receipt_evidence_artifact_pending_count"] == 6
    assert scope_priority["receipt_claim_ready_pending_count"] == 6
    assert scope_priority["receipt_reviewer_pending_count"] == 6
    assert scope_priority["receipt_reviewed_at_utc_pending_count"] == 6
    assert scope_priority["receipt_license_ok_pending_count"] == 6
    assert scope_priority["receipt_approval_token_pending_count"] == 6
    assert scope_priority["receipt_first_blocked_scope_blocker_id"] == "direct_binding_evidence_missing"
    assert scope_priority["receipt_first_blocked_evidence_artifact"] == "OPERATOR_FILL_LOCAL_EVIDENCE_JSON"
    assert scope_priority["receipt_first_blocked_expected_evidence_status"] == (
        "product_scope_transporter_direct_binding_evidence_ready"
    )
    assert scope_priority["receipt_first_blocked_observed_evidence_status"] == "missing"
    assert scope_priority["receipt_first_blocked_missing_true_fields"] == [
        "transporter_direct_binding_evidence_ready"
    ]
    assert "operator_placeholders_unfilled" in scope_priority["receipt_first_blocked_row_blockers"]
    assert scope_priority["receipt_most_common_row_blocker"] == "operator_placeholders_unfilled"
    assert scope_priority["receipt_approval_token_required"] == "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
    assert scope_priority["top_priority_items"][0]["item_id"] == "AQP1.core_binder_01"
    assert scope_priority["top_priority_items"][0]["domain"] == "transporter"
    assert len(scope_priority["priority_items"]) == scope_priority["queue_item_count"]

    scope_intake = asyncio.run(product.get_product_scope_evidence_intake_readiness())
    assert scope_intake["status"] == "product_scope_breadth_evidence_intake_readiness_ready"
    assert scope_intake["intake_readiness_ready"] is True
    assert scope_intake["scope_promotion_allowed"] is False
    assert scope_intake["authoritative_apply_allowed"] is False
    assert scope_intake["row_count"] in {15, 16}
    assert scope_intake["local_crosscheck_intake_ready_count"] == 10
    assert scope_intake["external_exact_evidence_required_count"] == 0
    assert scope_intake["all_operator_packet_bindings_ready"] is True
    assert scope_intake["operator_packet_binding_ready_count"] == scope_intake["row_count"]
    assert scope_intake["operator_packet_binding_missing_count"] == 0
    assert scope_intake["next_operator_completion_item_id"] == "AQP1.core_binder_01"
    assert scope_intake["next_operator_completion_domain"] == "transporter"
    assert scope_intake["next_operator_completion_candidate_or_check"] == (
        "aqp1_bacopaside_ii_review_seed"
    )
    assert scope_intake["next_operator_completion_intake_mode"] == "local_crosscheck_triage"
    assert scope_intake["next_operator_completion_required_evidence_type"] == (
        "exact_transporter_target_pair_quantitative_binder_kcal"
    )
    assert "reference_binding_kcal_mol" in scope_intake[
        "next_operator_completion_required_intake_columns"
    ]
    assert scope_intake["next_operator_completion_review_template_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.json"
    )
    assert scope_intake["next_operator_completion_apply_gate_artifact"] == (
        "runs/transporter_binder_promotion_gate_current.json"
    )
    assert scope_intake["next_operator_completion_operator_packet_binding_ready"] is True
    assert scope_intake["next_operator_completion_transporter_claim_safe_blocker"] == (
        "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed"
    )
    assert scope_intake["next_operator_completion_transporter_best_evidence_activity_type"] == "KD"
    assert scope_intake["next_operator_completion_transporter_best_evidence_units"] == "nM"
    assert scope_intake["transporter_operator_review_evidence_matrix_ready"] is True
    assert scope_intake["transporter_claim_safe_local_evidence_ready_count"] == 0
    assert scope_intake["transporter_claim_safe_local_evidence_blocked_count"] == 11
    assert scope_intake["transporter_direct_binding_claim_blocked_count"] == 4
    assert scope_intake["transporter_negative_value_claim_blocked_count"] == 6
    assert scope_intake["transporter_top_claim_safe_blocker"] == (
        "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed"
    )
    assert scope_intake["transporter_manual_review_intake_ready"] is True
    assert scope_intake["transporter_manual_review_template_row_count"] == 8
    assert scope_intake["transporter_manual_review_direct_binding_evidence_required_count"] == 1
    assert scope_intake["transporter_manual_review_negative_quantitative_value_required_count"] == 6
    assert scope_intake["transporter_manual_review_decision_placeholder_count"] == 0
    assert scope_intake["first_review_item_id"] == "AQP1.core_non_binder_01"
    assert scope_intake["first_review_candidate_ligand_id"] == "chembl_chembl2179173"
    assert scope_intake["first_review_replacement_source"] == (
        "chembl_activity::CHEMBL2179173::INHIBITION__%::source_CHEMBL4421726"
    )
    assert scope_intake["first_review_replacement_reference_binding_kcal_mol"] == ""
    assert scope_intake["first_review_direct_binding_evidence_required"] is False
    assert scope_intake["first_review_direct_binding_source_url_or_doi"] == ""
    assert scope_intake["first_review_review_decision"] == "KEEP_BLOCKED"
    assert scope_intake["first_review_p0_slot_overlay_required_missing_fields"] == (
        "replacement_ligand_id,replacement_reference_binding_kcal_mol,"
        "replacement_source,replacement_smiles,replacement_scaffold"
    )
    assert scope_intake["first_review_p0_slot_overlay_scope_promotion_allowed"] is False
    assert scope_intake["scope_operator_transfer_manifest_ready"] is True
    assert scope_intake["scope_operator_transfer_outbound_artifact_count"] == 8
    assert "runs/transporter_manual_review_intake_template_current.json" in scope_intake[
        "scope_operator_transfer_outbound_artifacts"
    ]
    assert scope_intake["scope_operator_transfer_inbound_artifact_count"] == 4
    assert scope_intake["scope_operator_transfer_first_return_artifact"] == (
        "completed runs/transporter_manual_review_intake_template_current.csv with OPERATOR_FILL placeholders resolved"
    )
    assert scope_intake["scope_operator_transfer_acceptance_artifact"] == (
        "runs/product_scope_breadth_contract_current.json"
    )
    assert scope_intake["scope_operator_transfer_acceptance_ready_key"] == "scope_breadth_ready"
    assert scope_intake["scope_operator_transfer_next_acceptance_stage"] == (
        "transporter_claim_acceptance"
    )
    assert "build_transporter_manual_review_intake_template.py" in scope_intake[
        "scope_operator_transfer_post_return_validation_command"
    ]
    assert len(scope_intake["intake_items"]) == scope_intake["row_count"]

    transporter_review = asyncio.run(product.get_product_transporter_manual_review_intake())
    assert transporter_review["status"] == "transporter_manual_review_intake_template_ready"
    assert transporter_review["manual_review_intake_ready"] is True
    assert transporter_review["manual_review_template_row_count"] == 8
    assert transporter_review["direct_binding_evidence_required_count"] == 1
    assert transporter_review["negative_quantitative_value_required_count"] == 6
    assert transporter_review["review_decision_placeholder_count"] == 0
    assert transporter_review["authoritative_apply_requested_placeholder_count"] == 0
    assert transporter_review["first_review_item_id"] == "AQP1.core_non_binder_01"
    assert transporter_review["first_review_target_id"] == "AQP1"
    assert transporter_review["first_review_candidate_ligand_id"] == (
        "chembl_chembl2179173"
    )
    assert transporter_review["first_review_replacement_source"] == (
        "chembl_activity::CHEMBL2179173::INHIBITION__%::source_CHEMBL4421726"
    )
    assert transporter_review["first_review_replacement_reference_binding_kcal_mol"] == ""
    assert transporter_review["first_review_direct_binding_evidence_required"] is False
    assert transporter_review["first_review_direct_binding_source_url_or_doi"] == ""
    assert transporter_review["first_review_review_decision"] == "KEEP_BLOCKED"
    assert transporter_review["first_review_authoritative_apply_requested"] == "false"
    assert transporter_review["first_review_p0_slot_overlay_required_missing_fields"] == (
        "replacement_ligand_id,replacement_reference_binding_kcal_mol,"
        "replacement_source,replacement_smiles,replacement_scaffold"
    )
    assert transporter_review["first_review_p0_slot_overlay_claim_safe_step_ready"] is False
    assert transporter_review["first_review_p0_slot_overlay_scope_promotion_allowed"] is False
    assert transporter_review["review_rows"][0]["review_decision"] == "KEEP_BLOCKED"

    aqp1_candidate = asyncio.run(product.get_product_aqp1_operator_validation_candidate())
    assert aqp1_candidate["status"] == "aqp1_operator_validation_candidate_packet_ready"
    assert aqp1_candidate["packet_ready"] is True
    assert aqp1_candidate["candidate_ready"] is True
    assert aqp1_candidate["candidate_count"] == 1
    assert aqp1_candidate["candidate_claim_safe_ready_count"] == 0
    assert aqp1_candidate["operator_validation_required_count"] == 1
    assert aqp1_candidate["operator_placeholder_count"] == 6
    assert aqp1_candidate["first_candidate_target_id"] == "AQP1"
    assert aqp1_candidate["first_candidate_target_uniprot"] == "P29972"
    assert aqp1_candidate["first_candidate_ligand_external_identifier"] == "CHEMBL20"
    assert aqp1_candidate["first_candidate_ligand_name"] == "acetazolamide"
    assert aqp1_candidate["first_candidate_activity_id"] == "29308926"
    assert aqp1_candidate["first_candidate_standard_type"] == "Kd"
    assert aqp1_candidate["first_candidate_standard_value_nM"] == "174000.0"
    assert aqp1_candidate["first_candidate_reference_binding_kcal_mol"] == "-5.13"
    assert aqp1_candidate["first_candidate_claim_safe_ready"] is False
    assert aqp1_candidate["claim_promotion_allowed"] is False
    assert aqp1_candidate["authoritative_apply_allowed"] is False
    assert "operator_assay_origin_confirmed" in aqp1_candidate[
        "required_operator_decision_fields"
    ]
    assert "data_validity_outside_typical_range" in aqp1_candidate["validation_blockers"]
    assert any(
        "build_product_scope_breadth_contract.py" in command
        for command in aqp1_candidate["post_return_validation_commands"]
    )
    assert aqp1_candidate["rows"][0]["operator_claim_safe_decision"] == (
        "OPERATOR_FILL_APPROVE_CLAIM_SAFE_OR_KEEP_BLOCKED"
    )
    assert aqp1_candidate["execution_enabled"] is False
    assert aqp1_candidate["scope_widened"] is False

    aqp1_procurement = asyncio.run(product.get_product_aqp1_direct_binding_procurement_packet())
    assert aqp1_procurement["status"] == "aqp1_direct_binding_procurement_packet_ready"
    assert aqp1_procurement["procurement_packet_ready"] is True
    assert aqp1_procurement["target_id"] == "AQP1"
    assert aqp1_procurement["target_uniprot"] == "P29972"
    assert aqp1_procurement["current_direct_experimental_binding_row_count"] == 0
    assert aqp1_procurement["current_claim_safe_binding_kcal_ready_count"] == 0
    assert aqp1_procurement["direct_binding_gap_open"] is True
    assert aqp1_procurement["external_primary_evidence_required"] is True
    assert aqp1_procurement["current_operator_candidate_ligand_external_identifier"] == "CHEMBL20"
    assert aqp1_procurement["current_operator_candidate_reference_binding_kcal_mol"] == "-5.13"
    assert aqp1_procurement["current_operator_candidate_claim_safe_ready"] is False
    assert "standard_value_nM" in aqp1_procurement["acceptance_fields"]
    assert "target_uniprot=P29972" in aqp1_procurement["minimum_acceptance_rule"]
    assert aqp1_procurement["first_required_external_action_id"] == (
        "procure_aqp1_bacopaside_ii_direct_binding_measurement"
    )
    assert aqp1_procurement["claim_promotion_allowed"] is False
    assert aqp1_procurement["authoritative_apply_allowed"] is False
    assert aqp1_procurement["execution_enabled"] is False
    assert aqp1_procurement["scope_widened"] is False

    pxr_review = asyncio.run(product.get_product_pxr_exact_review_intake())
    assert pxr_review["status"] == "pxr_exact_evidence_review_intake_template_ready"
    assert pxr_review["pxr_exact_review_intake_ready"] is True
    assert pxr_review["scope_promotion_allowed"] is True
    assert pxr_review["review_template_row_count"] == 0
    assert pxr_review["expected_blocked_row_count"] == 0
    assert pxr_review["conflict_resolution_required_count"] == 0
    assert pxr_review["kcal_placeholder_count"] == 0
    assert pxr_review["source_placeholder_count"] == 0
    assert pxr_review["target_match_placeholder_count"] == 0
    assert pxr_review["next_review_completion_packet_ready"] is False
    assert pxr_review["next_review_candidate_name"] == ""
    assert pxr_review["next_review_operator_review_artifact"] == ""
    assert pxr_review["next_review_completion_packet"]["packet_ready"] is False
    assert len(pxr_review["review_rows"]) == 0

    operator_packet = asyncio.run(product.get_product_commercial_readiness_operator_packet())
    operator_packet_source = _artifact_summary("product_commercial_readiness_operator_packet_current.json")
    assert operator_packet["status"] == operator_packet_source.get("status")
    for key in (
        "packet_ready",
        "source_fingerprint_ready",
        "goal_complete",
        "execution_enabled",
        "docking_results_emitted",
        "external_state_mutated",
        "checkpoint_promoted",
        "scope_widened",
        "delta_force_closure_acceptance_packet_ready",
        "delta_force_closure_ready",
        "scope_closure_acceptance_packet_ready",
        "scope_closure_ready",
        "scope_closure_general_platform_claim_allowed",
        "production_ai_return_operator_completion_packet_ready",
        "production_ai_registry_promotion_operator_completion_packet_ready",
        "production_ai_registry_promotion_operator_receipt_ready",
        "production_ai_registry_promotion_priority_packet_ready",
        "production_ai_registry_promotion_priority_registry_promotion_ready",
        "production_ai_registry_promotion_priority_model_promoted",
        "production_ai_registry_promotion_priority_external_state_mutated",
    ):
        if key in operator_packet_source:
            assert operator_packet[key] is (operator_packet_source.get(key) is True)
    assert operator_packet["goal_audit_artifact"] == operator_packet_source.get("goal_audit_artifact")
    assert len(operator_packet["goal_audit_sha256"]) == 64
    assert len(operator_packet["commercial_readiness_matrix_sha256"]) == 64
    for key in (
        "action_count",
        "blocked_action_count",
        "ready_action_count",
        "parallelizable_action_count",
        "operator_completion_packet_ready_count",
        "production_ai_return_operator_completion_expected_queue_rows",
        "production_ai_return_bundle_required_artifact_count",
        "production_ai_registry_promotion_operator_receipt_blocked_row_count",
        "production_ai_registry_promotion_priority_operator_input_required_count",
        "delta_force_closure_ready_output_field_count",
        "delta_force_closure_blocked_output_field_count",
        "delta_force_closure_failed_stage_count",
        "scope_closure_stage_count",
        "scope_closure_blocked_stage_count",
        "scope_closure_transporter_unresolved_slot_count",
        "scope_closure_pxr_direct_or_claim_safe_quantitative_ready_count",
        "engine_refinement_claim_promotion_blocker_count",
        "engine_refinement_claim_evidence_receipt_blocked_row_count",
        "product_scope_breadth_evidence_receipt_blocked_row_count",
        "product_scope_breadth_evidence_receipt_required_scope_blocker_count",
    ):
        if key in operator_packet_source:
            assert operator_packet[key] == int(operator_packet_source.get(key) or 0)
    for key in (
        "parallelizable_action_ids",
        "first_parallelizable_action_id",
        "first_parallelizable_action_lane_id",
        "first_parallelizable_action_expected_evidence_type",
            "first_parallelizable_action_operator_review_artifact",
            "first_action_id",
            "first_artifact",
            "first_validation_command",
            "production_ai_return_action_id",
        "production_ai_return_action_blocked_by_action_id",
        "production_ai_return_operator_completion_artifact_id",
        "production_ai_return_bundle_next_artifact_failed_check_ids",
        "production_ai_registry_promotion_action_id",
        "production_ai_registry_promotion_operator_completion_artifact_id",
        "production_ai_registry_promotion_operator_receipt_status",
        "production_ai_registry_promotion_operator_receipt_approval_token_required",
        "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker",
        "production_ai_registry_promotion_priority_status",
        "production_ai_registry_promotion_priority_top_gate_id",
        "production_ai_registry_promotion_priority_top_priority_bucket",
        "delta_force_closure_first_blocked_output_field",
        "delta_force_closure_next_stage_id",
        "delta_force_closure_next_stage_artifact",
        "scope_closure_next_stage_id",
        "scope_closure_first_blocked_evidence_row_id",
        "scope_closure_first_blocked_target_id",
        "scope_closure_first_blocked_required_missing_fields",
        "engine_refinement_claim_promotion_action_board_csv",
        "engine_refinement_claim_evidence_receipt_artifact",
        "engine_refinement_claim_evidence_receipt_csv",
        "product_scope_breadth_evidence_receipt_status",
        "product_scope_breadth_evidence_receipt_artifact",
        "product_scope_breadth_evidence_receipt_csv",
    ):
        if key in operator_packet_source:
                assert operator_packet[key] == operator_packet_source.get(key)
        assert len(operator_packet["actions"]) == operator_packet["action_count"]
        assert "reference_binding_kcal_mol" in operator_packet["first_parallelizable_action_required_operator_inputs"]
    assert "target_match_decision" in operator_packet["first_parallelizable_action_required_exact_evidence_fields"]
    assert "functional_surrogate_does_not_authorize_direct_binding_claim" in operator_packet[
        "first_parallelizable_action_required_claim_guardrails"
    ]
    assert any(
        "residual_force_trajectory_regeneration_current_manifest.csv" in artifact
        for artifact in operator_packet["production_ai_return_bundle_required_artifacts"]
    )
    assert "operator_verified_npz_exists" in operator_packet[
        "production_ai_return_bundle_manifest_required_columns"
    ]
    assert "summary alone does not unlock" in operator_packet[
        "production_ai_return_bundle_guardrail"
    ]
    assert "production_promotion_allowed" in operator_packet[
        "production_ai_registry_promotion_operator_completion_required_fields_or_columns"
    ]
    assert any(
        "build_residual_model_registry.py" in command
        for command in operator_packet["production_ai_registry_promotion_operator_completion_diagnostic_commands"]
    )
    assert "registry_promotion_missing_gate_count=0" in operator_packet[
        "production_ai_registry_promotion_operator_completion_completion_rule"
    ]
    assert "build_residual_force_gpu_worker_return_receipt.py" in operator_packet[
        "delta_force_closure_next_stage_validation_command"
    ]
    assert "queue_rows" in operator_packet[
        "delta_force_closure_return_summary_required_fields"
    ]
    assert operator_packet["scope_closure_general_platform_claim_allowed"] is False
    assert operator_packet["engine_refinement_claim_promotion_ready"] is (
        operator_packet_source.get("engine_refinement_claim_promotion_ready") is True
    )
    assert operator_packet["engine_refinement_claim_evidence_receipt_ready"] is (
        operator_packet_source.get("engine_refinement_claim_evidence_receipt_ready") is True
    )
    assert operator_packet["engine_refinement_claim_evidence_operator_field_worksheet_status"] == (
        operator_packet_source.get("engine_refinement_claim_evidence_operator_field_worksheet_status")
    )
    assert operator_packet["engine_refinement_claim_evidence_operator_field_worksheet_ready"] is (
        operator_packet_source.get("engine_refinement_claim_evidence_operator_field_worksheet_ready") is True
    )
    assert (
        operator_packet[
            "engine_refinement_claim_evidence_operator_field_worksheet_operator_fill_complete"
        ]
        is (operator_packet_source.get(
            "engine_refinement_claim_evidence_operator_field_worksheet_operator_fill_complete"
        ) is True)
    )
    assert (
        operator_packet["engine_refinement_claim_evidence_operator_field_worksheet_field_row_count"]
        == int(operator_packet_source.get(
            "engine_refinement_claim_evidence_operator_field_worksheet_field_row_count"
        ) or 0)
    )
    assert (
        operator_packet[
            "engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count"
        ]
        == int(operator_packet_source.get(
            "engine_refinement_claim_evidence_operator_field_worksheet_pending_field_count"
        ) or 0)
    )
    assert (
        operator_packet[
            "engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count"
        ]
        == int(operator_packet_source.get(
            "engine_refinement_claim_evidence_operator_field_worksheet_work_order_pending_field_count"
        ) or 0)
    )
    assert (
        operator_packet[
            "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id"
        ]
        == operator_packet_source.get(
            "engine_refinement_claim_evidence_operator_field_worksheet_top_blocker_id"
        )
    )
    assert (
        operator_packet[
            "engine_refinement_claim_evidence_operator_field_worksheet_top_priority_bucket"
        ]
        == operator_packet_source.get(
            "engine_refinement_claim_evidence_operator_field_worksheet_top_priority_bucket"
        )
    )
    assert (
        operator_packet[
            "engine_refinement_claim_evidence_operator_field_worksheet_external_state_mutated"
        ]
        is (operator_packet_source.get(
            "engine_refinement_claim_evidence_operator_field_worksheet_external_state_mutated"
        ) is True)
    )
    assert operator_packet["product_scope_breadth_evidence_receipt_ready"] is (
        operator_packet_source.get("product_scope_breadth_evidence_receipt_ready") is True
    )
    assert operator_packet["product_scope_breadth_evidence_operator_field_worksheet_status"] == (
        operator_packet_source.get("product_scope_breadth_evidence_operator_field_worksheet_status")
    )
    assert operator_packet["product_scope_breadth_evidence_operator_field_worksheet_ready"] is (
        operator_packet_source.get("product_scope_breadth_evidence_operator_field_worksheet_ready") is True
    )
    assert (
        operator_packet[
            "product_scope_breadth_evidence_operator_field_worksheet_pending_field_count"
        ]
        == int(operator_packet_source.get(
            "product_scope_breadth_evidence_operator_field_worksheet_pending_field_count"
        ) or 0)
    )
    assert (
        operator_packet[
            "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_id"
        ]
        == operator_packet_source.get(
            "product_scope_breadth_evidence_operator_field_worksheet_top_blocker_id"
        )
    )
    assert (
        operator_packet["product_scope_breadth_evidence_operator_field_worksheet_top_item_id"]
        == operator_packet_source.get(
            "product_scope_breadth_evidence_operator_field_worksheet_top_item_id"
        )
    )
    assert operator_packet["product_scope_breadth_evidence_operator_staging_apply_status"] == (
        operator_packet_source.get("product_scope_breadth_evidence_operator_staging_apply_status")
    )
    assert (
        operator_packet["product_scope_breadth_evidence_operator_staging_apply_candidate_receipt_ready"]
        is (operator_packet_source.get(
            "product_scope_breadth_evidence_operator_staging_apply_candidate_receipt_ready"
        ) is True)
    )
    assert (
        operator_packet["product_scope_breadth_evidence_operator_staging_apply_candidate_blocked_row_count"]
        == int(operator_packet_source.get(
            "product_scope_breadth_evidence_operator_staging_apply_candidate_blocked_row_count"
        ) or 0)
    )
    assert (
        operator_packet[
            "product_scope_breadth_evidence_operator_staging_apply_field_worksheet_pending_field_count"
        ]
        == int(operator_packet_source.get(
            "product_scope_breadth_evidence_operator_staging_apply_field_worksheet_pending_field_count"
        ) or 0)
    )
    assert (
        operator_packet[
            "product_scope_breadth_evidence_operator_staging_apply_first_blocked_scope_blocker_id"
        ]
        == operator_packet_source.get(
            "product_scope_breadth_evidence_operator_staging_apply_first_blocked_scope_blocker_id"
        )
    )
    assert operator_packet["product_scope_breadth_evidence_operator_staging_apply_live_copy_allowed"] is (
        operator_packet_source.get("product_scope_breadth_evidence_operator_staging_apply_live_copy_allowed")
        is True
    )
    assert operator_packet["execution_enabled"] is False
    assert operator_packet["checkpoint_promoted"] is False
    assert operator_packet["external_state_mutated"] is False

    operator_freshness = asyncio.run(product.get_product_commercial_readiness_operator_packet_freshness())
    assert operator_freshness["status"] == (
        "product_commercial_readiness_operator_packet_freshness_ready"
    )
    assert operator_freshness["freshness_ready"] is True
    assert operator_freshness["goal_complete"] is False
    assert operator_freshness["current_goal_audit_sha256"] == operator_freshness["operator_goal_audit_sha256"]
    assert operator_freshness["current_commercial_readiness_matrix_sha256"] == (
        operator_freshness["operator_commercial_readiness_matrix_sha256"]
    )
    assert operator_freshness["current_action_count"] == operator_freshness["operator_action_count"]
    assert operator_freshness["current_blocked_action_count"] == (
        operator_freshness["operator_blocked_action_count"]
    )
    assert operator_freshness["current_first_action_id"] == operator_freshness["operator_first_action_id"]
    assert operator_freshness["command_references_ready"] is True
    assert operator_freshness["operator_python_tool_reference_count"] >= 20
    assert operator_freshness["operator_missing_python_tool_reference_count"] == 0
    assert operator_freshness["operator_missing_python_tool_references"] == []
    assert "tools/build_pxr_exact_evidence_review_intake_template.py" in operator_freshness[
        "operator_python_tool_references"
    ]
    assert "tools/validate_pxr_packet_fill_readiness.py" not in operator_freshness[
        "operator_python_tool_references"
    ]
    assert operator_freshness["fail_count"] == 0
    assert operator_freshness["check_count"] == len(operator_freshness["checks"])
    assert operator_freshness["execution_enabled"] is False
    assert operator_freshness["checkpoint_promoted"] is False

    execution_ladder = asyncio.run(product.get_product_commercial_readiness_execution_ladder())
    assert execution_ladder["status"] == "product_commercial_readiness_execution_ladder_ready"
    assert execution_ladder["ladder_ready"] is True
    assert execution_ladder["operator_packet_ready"] is True
    assert execution_ladder["freshness_ready"] is True
    assert execution_ladder["goal_complete"] is False
    assert execution_ladder["action_count"] == 6
    assert execution_ladder["blocked_action_count"] == 4
    assert execution_ladder["parallelizable_action_count"] == 2
    assert execution_ladder["parallelizable_action_ids"] == [
        "transporter_next_slot_exact_evidence",
        "broad_platform_claim_floor",
    ]
    assert execution_ladder["first_parallelizable_action_id"] == (
        "transporter_next_slot_exact_evidence"
    )
    assert execution_ladder["first_parallelizable_action_order"] == 4
    assert execution_ladder["first_parallelizable_action_lane_id"] == "parallel_scope_evidence"
    assert "reference_binding_kcal_mol" in execution_ladder[
        "first_parallelizable_action_required_operator_inputs"
    ]
    assert "target_match_decision" in execution_ladder[
        "first_parallelizable_action_required_exact_evidence_fields"
    ]
    assert "functional_surrogate_does_not_authorize_direct_binding_claim" in execution_ladder[
        "first_parallelizable_action_required_claim_guardrails"
    ]
    assert execution_ladder["first_parallelizable_action_operator_review_artifact"] == (
        "runs/transporter_manual_review_intake_template_current.csv"
    )
    assert "build_product_goal_completion_audit.py" in execution_ladder[
        "first_parallelizable_action_acceptance_gate_commands"
    ]
    assert execution_ladder["first_parallelizable_action_next_slot_source_modality"] == (
        "functional_quantitative_surrogate"
    )
    assert (
        execution_ladder[
            "first_parallelizable_action_next_slot_source_modality_direct_binding_claim_allowed"
        ]
        is False
    )
    assert execution_ladder[
        "first_parallelizable_action_next_slot_source_modality_triage_decision"
    ] == "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal"
    assert execution_ladder[
        "first_parallelizable_action_next_slot_source_modality_computational_binding_energy_row_count"
    ] == 1
    assert execution_ladder["first_parallelizable_action_operator_validation_candidate_ready"] is True
    assert execution_ladder[
        "first_parallelizable_action_operator_validation_candidate_status"
    ] == "operator_validation_required"
    assert execution_ladder[
        "first_parallelizable_action_operator_validation_candidate_ligand_external_identifier"
    ] == "CHEMBL20"
    assert execution_ladder[
        "first_parallelizable_action_operator_validation_candidate_reference_binding_kcal_mol"
    ] == "-5.13"
    assert execution_ladder[
        "first_parallelizable_action_operator_validation_candidate_blocker"
    ] == "data_validity_outside_typical_range_and_assay_origin_unknown"
    assert (
        execution_ladder["first_parallelizable_action_operator_validation_candidate_claim_safe_ready"]
        is False
    )
    assert execution_ladder["first_parallelizable_action_direct_binding_procurement_packet_ready"] is True
    assert execution_ladder["first_parallelizable_action_direct_binding_procurement_packet_artifact"] == (
        "runs/aqp1_direct_binding_procurement_packet_current.json"
    )
    assert execution_ladder[
        "first_parallelizable_action_direct_binding_procurement_first_required_external_action_id"
    ] == "procure_aqp1_bacopaside_ii_direct_binding_measurement"
    assert execution_ladder[
        "first_parallelizable_action_direct_binding_procurement_external_primary_evidence_required"
    ] is True
    assert execution_ladder["first_execution_order"] == 2
    assert execution_ladder["first_action_id"] == "production_ai_registry_guarded_promotion"
    assert execution_ladder["first_operator_input_artifact"] == (
        "runs/residual_model_registry_current.json"
    )
    assert "build_residual_model_registry.py" in execution_ladder["first_validation_command"]
    assert (
        execution_ladder["first_operator_completion_worker_runtime_receipt_contract_ready"]
        is False
    )
    assert execution_ladder["first_operator_completion_diagnostic_command_count"] == 3
    assert any(
        "build_residual_model_registry.py" in command
        for command in execution_ladder["first_operator_completion_diagnostic_commands"]
    )
    assert execution_ladder["ladder"][0]["action_id"] == "production_gpu_execution_environment"
    assert execution_ladder["ladder"][0]["execution_order"] == 1
    assert execution_ladder["ladder"][0]["operator_input_artifact"] == (
        "runs/rocm_environment_manifest_current.json"
    )
    assert execution_ladder["ladder"][0]["execution_command"] == (
        "python3 tools/build_rocm_environment_manifest.py"
    )
    assert execution_ladder["ladder"][0]["operator_completion_diagnostic_command_count"] == 5
    assert "torch.cuda.device_count" in execution_ladder["ladder"][0][
        "operator_completion_diagnostic_commands"
    ]
    assert "visible_device_count>0" in execution_ladder["ladder"][0][
        "operator_completion_diagnostic_completion_rule"
    ]
    assert execution_ladder["all_preconditions_satisfied"] is True
    assert execution_ladder["ladder"][0]["precondition_satisfied"] is True
    assert execution_ladder["ladder"][2]["post_validation_rebuild_command"].endswith(
        "python3 tools/build_product_goal_completion_audit.py"
    )
    assert execution_ladder["production_ai_return_action_id"] == "production_ai_return_summary"
    assert (
        "production_ai_registry_promotion_operator_completion_packet_ready"
        in execution_ladder
    )
    assert execution_ladder["production_ai_return_operator_completion_packet_ready"] is True
    assert execution_ladder["production_ai_return_bundle_next_artifact_id"] == (
        "regenerated_npz_bundles"
    )
    assert "operator_verified_npz_exists" in execution_ladder[
        "production_ai_return_bundle_manifest_required_columns"
    ]
    if execution_ladder["production_ai_registry_promotion_action_id"]:
        assert execution_ladder["production_ai_registry_promotion_action_id"] == (
            "production_ai_registry_guarded_promotion"
        )
        assert (
            execution_ladder[
                "production_ai_registry_promotion_operator_completion_packet_ready"
            ]
            is True
        )
        assert any(
            "build_residual_model_registry.py" in command
            for command in execution_ladder[
                "production_ai_registry_promotion_operator_completion_diagnostic_commands"
            ]
        )
        assert execution_ladder[
            "production_ai_registry_promotion_operator_receipt_status"
        ] == "blocked_production_ai_registry_promotion_operator_receipt"
        assert (
            execution_ladder["production_ai_registry_promotion_operator_receipt_ready"]
            is False
        )
        assert execution_ladder[
            "production_ai_registry_promotion_operator_receipt_approval_token_required"
        ] == "APPROVE_PRODUCTION_AI_REGISTRY_PROMOTION"
        assert execution_ladder[
            "production_ai_registry_promotion_operator_receipt_first_blocked_row_blocker"
        ] == "operator_placeholders_unfilled"
        assert execution_ladder["production_ai_registry_promotion_priority_status"] == (
            "blocked_production_ai_registry_promotion_priority_packet"
        )
        assert execution_ladder[
            "production_ai_registry_promotion_priority_top_gate_id"
        ] == "default_residual_mode_guarded"
        assert execution_ladder[
            "production_ai_registry_promotion_priority_top_priority_bucket"
        ] == "guarded_residual_mode_selection_required"
        assert execution_ladder[
            "production_ai_registry_promotion_priority_model_promoted"
        ] is False
    assert execution_ladder["execution_enabled"] is False
    assert execution_ladder["checkpoint_promoted"] is False

    handoff_bundle = asyncio.run(product.get_product_commercial_readiness_handoff_bundle())
    handoff_bundle_source = _artifact_summary("product_commercial_readiness_handoff_bundle_current.json")
    assert handoff_bundle["status"] == handoff_bundle_source.get("status")
    assert handoff_bundle["handoff_bundle_ready"] is (
        handoff_bundle_source.get("handoff_bundle_ready") is True
    )
    assert handoff_bundle["goal_complete"] is (handoff_bundle_source.get("goal_complete") is True)
    assert handoff_bundle["artifact_count"] == int(handoff_bundle_source.get("artifact_count") or 0)
    assert handoff_bundle["ready_artifact_count"] == int(
        handoff_bundle_source.get("ready_artifact_count") or 0
    )
    assert handoff_bundle["blocked_artifact_count"] == int(
        handoff_bundle_source.get("blocked_artifact_count") or 0
    )
    assert handoff_bundle["operator_packet_ready"] is (
        handoff_bundle_source.get("operator_packet_ready") is True
    )
    assert handoff_bundle["source_fingerprint_ready"] is (
        handoff_bundle_source.get("source_fingerprint_ready") is True
    )
    assert handoff_bundle["freshness_ready"] is (
        handoff_bundle_source.get("freshness_ready") is True
    )
    assert handoff_bundle["execution_ladder_ready"] is (
        handoff_bundle_source.get("execution_ladder_ready") is True
    )
    assert handoff_bundle["operator_action_count"] == int(
        handoff_bundle_source.get("operator_action_count") or 0
    )
    assert handoff_bundle["operator_blocked_action_count"] == int(
        handoff_bundle_source.get("operator_blocked_action_count") or 0
    )
    assert handoff_bundle["ladder_action_count"] == int(
        handoff_bundle_source.get("ladder_action_count") or 0
    )
    assert handoff_bundle["operator_parallelizable_action_count"] == int(
        handoff_bundle_source.get("operator_parallelizable_action_count") or 0
    )
    assert handoff_bundle["operator_parallelizable_action_ids"] == handoff_bundle_source.get(
        "operator_parallelizable_action_ids"
    )
    assert handoff_bundle["ladder_parallelizable_action_count"] == int(
        handoff_bundle_source.get("ladder_parallelizable_action_count") or 0
    )
    assert handoff_bundle["first_parallelizable_action_id"] == handoff_bundle_source.get(
        "first_parallelizable_action_id"
    )
    assert handoff_bundle["artifact_reference_count"] == int(
        handoff_bundle_source.get("artifact_reference_count") or 0
    )
    assert handoff_bundle["artifact_reference_contract_ready"] is (
        handoff_bundle_source.get("artifact_reference_contract_ready") is True
    )
    assert len(handoff_bundle["artifact_reference_manifest"]) >= handoff_bundle["artifact_reference_count"]
    assert handoff_bundle["production_ai_return_operator_completion_packet_ready"] is (
        handoff_bundle_source.get("production_ai_return_operator_completion_packet_ready") is True
    )
    assert handoff_bundle["production_ai_registry_promotion_operator_completion_packet_ready"] is (
        handoff_bundle_source.get("production_ai_registry_promotion_operator_completion_packet_ready")
        is True
    )
    assert handoff_bundle["production_ai_registry_promotion_operator_receipt_status"] == (
        handoff_bundle_source.get("production_ai_registry_promotion_operator_receipt_status")
    )
    assert handoff_bundle[
        "production_ai_registry_promotion_operator_receipt_approval_token_required"
    ] == handoff_bundle_source.get(
        "production_ai_registry_promotion_operator_receipt_approval_token_required"
    )
    assert handoff_bundle["execution_enabled"] is (
        handoff_bundle_source.get("execution_enabled") is True
    )
    assert handoff_bundle["checkpoint_promoted"] is (
        handoff_bundle_source.get("checkpoint_promoted") is True
    )

    scope_receipt_summary = _artifact_summary(
        "product_scope_breadth_evidence_receipt_current.json"
    )
    scope_receipt = asyncio.run(product.get_product_scope_breadth_evidence_receipt())
    assert scope_receipt["status"] == scope_receipt_summary.get("status")
    assert scope_receipt["status"] == "blocked_product_scope_breadth_evidence_receipt"
    assert scope_receipt["full_scope_evidence_receipt_ready"] is False
    assert scope_receipt["receipt_csv_present"] is True
    assert scope_receipt["receipt_row_count"] == 6
    assert scope_receipt["required_scope_blocker_count"] == 6
    assert scope_receipt["blocked_row_count"] == 6
    assert scope_receipt["first_blocked_scope_blocker_id"] == "direct_binding_evidence_missing"
    assert scope_receipt["first_blocked_expected_evidence_status"] == (
        "product_scope_transporter_direct_binding_evidence_ready"
    )
    assert scope_receipt["first_blocked_observed_evidence_status"] == "missing"
    assert scope_receipt["most_common_row_blocker"] == "operator_placeholders_unfilled"
    assert scope_receipt["approval_token_required"] == (
        "APPROVE_PRODUCT_SCOPE_BREADTH_EVIDENCE_RECEIPT"
    )
    assert len(scope_receipt["receipt_rows"]) == scope_receipt["receipt_row_count"]
    assert "scope_blocker_id" in scope_receipt["required_columns"]
    assert scope_receipt["execution_enabled"] is False
    assert scope_receipt["docking_results_emitted"] is False
    assert scope_receipt["external_state_mutated"] is False
    assert scope_receipt["scope_widened"] is False
    assert scope_receipt["claim_promoted"] is False

    engine_receipt_summary = _artifact_summary(
        "engine_refinement_claim_evidence_receipt_current.json"
    )
    engine_receipt = asyncio.run(product.get_product_engine_refinement_claim_evidence_receipt())
    assert engine_receipt["status"] == engine_receipt_summary.get("status")
    assert engine_receipt["status"] == "blocked_engine_refinement_claim_evidence_receipt"
    assert engine_receipt["claim_promotion_evidence_receipt_ready"] is False
    assert engine_receipt["receipt_csv_present"] is True
    assert engine_receipt["receipt_row_count"] == 6
    assert engine_receipt["required_blocker_count"] == 6
    assert engine_receipt["blocked_row_count"] == 6
    assert engine_receipt["first_blocked_blocker_id"] == "public_benchmark_gate_not_ready"
    assert engine_receipt["first_blocked_expected_evidence_status"] == (
        "refine_tier_public_benchmark_ready"
    )
    assert engine_receipt["first_blocked_observed_evidence_status"] == "missing"
    assert engine_receipt["most_common_row_blocker"] == "operator_placeholders_unfilled"
    assert engine_receipt["approval_token_required"] == (
        "APPROVE_ENGINE_REFINEMENT_CLAIM_EVIDENCE_RECEIPT"
    )
    assert len(engine_receipt["receipt_rows"]) == engine_receipt["receipt_row_count"]
    assert "blocker_id" in engine_receipt["required_columns"]
    assert engine_receipt["execution_enabled"] is False
    assert engine_receipt["docking_results_emitted"] is False
    assert engine_receipt["external_state_mutated"] is False
    assert engine_receipt["claim_promoted"] is False

    engine_priority_summary = _artifact_summary(
        "engine_refinement_claim_evidence_priority_packet_current.json"
    )
    engine_priority = asyncio.run(product.get_product_engine_refinement_claim_evidence_priority())
    assert engine_priority["status"] == engine_priority_summary.get("status")
    assert engine_priority["status"] == "blocked_engine_refinement_claim_evidence_priority_packet"
    assert engine_priority["priority_packet_ready"] is (
        engine_priority_summary.get("priority_packet_ready") is True
    )
    assert engine_priority["claim_promotion_allowed"] is (
        engine_priority_summary.get("claim_promotion_allowed") is True
    )
    assert engine_priority["claim_evidence_receipt_ready"] is (
        engine_priority_summary.get("claim_evidence_receipt_ready") is True
    )
    assert engine_priority["priority_item_count"] == int(
        engine_priority_summary.get("priority_item_count") or 0
    )
    assert engine_priority["operator_input_required_count"] == int(
        engine_priority_summary.get("operator_input_required_count") or 0
    )
    assert engine_priority["blocked_priority_item_count"] == int(
        engine_priority_summary.get("blocked_priority_item_count") or 0
    )
    assert engine_priority["public_benchmark_gate_ready"] is (
        engine_priority_summary.get("public_benchmark_gate_ready") is True
    )
    assert engine_priority["public_benchmark_work_order_present"] is (
        engine_priority_summary.get("public_benchmark_work_order_present") is True
    )
    assert engine_priority["public_benchmark_work_order_row_count"] == int(
        engine_priority_summary.get("public_benchmark_work_order_row_count") or 0
    )
    assert engine_priority["public_benchmark_work_order_apply_ready"] is (
        engine_priority_summary.get("public_benchmark_work_order_apply_ready") is True
    )
    assert engine_priority["public_benchmark_work_order_apply_blocked_row_count"] == int(
        engine_priority_summary.get("public_benchmark_work_order_apply_blocked_row_count") or 0
    )
    assert engine_priority["top_blocker_id"] == engine_priority_summary.get("top_blocker_id")
    assert engine_priority["top_priority_bucket"] == engine_priority_summary.get("top_priority_bucket")
    assert engine_priority["top_required_input"] == engine_priority_summary.get("top_required_input")
    assert engine_priority["top_acceptance_artifact"] == engine_priority_summary.get("top_acceptance_artifact")
    assert engine_priority["top_verification_command"] == engine_priority_summary.get(
        "top_verification_command"
    )
    assert engine_priority["approval_token_required"] == engine_priority_summary.get(
        "approval_token_required"
    )
    assert len(engine_priority["priority_items"]) == engine_priority["priority_item_count"]
    assert engine_priority["top_priority_items"][0]["blocker_id"] == "public_benchmark_gate_not_ready"
    assert engine_priority["execution_enabled"] is (engine_priority_summary.get("execution_enabled") is True)
    assert engine_priority["docking_results_emitted"] is (
        engine_priority_summary.get("docking_results_emitted") is True
    )
    assert engine_priority["external_state_mutated"] is (
        engine_priority_summary.get("external_state_mutated") is True
    )
    assert engine_priority["claim_promoted"] is (engine_priority_summary.get("claim_promoted") is True)

    full_matrix_summary = _artifact_summary(
        "product_full_commercial_blocker_evidence_matrix_current.json"
    )
    full_matrix = asyncio.run(product.get_product_full_commercial_blocker_evidence_matrix())
    assert full_matrix["status"] == full_matrix_summary.get("status")
    assert full_matrix["status"] == "blocked_product_full_commercial_blocker_evidence_matrix"
    assert full_matrix["full_commercial_blocker_evidence_matrix_ready"] is False
    assert full_matrix["full_commercial_evidence_receipts_ready"] is False
    assert full_matrix["release_blocker_visibility_ready"] is True
    assert full_matrix["expected_release_blocker_ids"] == [
        "R8_full_scope_claim_closure",
        "R9_engine_refinement_claim_promotion",
    ]
    assert full_matrix["goal_audit_release_blocker_ids"] == full_matrix_summary.get(
        "goal_audit_release_blocker_ids"
    )
    assert full_matrix["bottleneck_release_blocker_ids"] == full_matrix_summary.get(
        "bottleneck_release_blocker_ids"
    )
    assert full_matrix["matrix_row_count"] == int(
        full_matrix_summary.get("matrix_row_count") or 0
    )
    assert full_matrix["blocked_matrix_row_count"] == int(
        full_matrix_summary.get("blocked_matrix_row_count") or 0
    )
    assert full_matrix["approval_token_count"] == int(
        full_matrix_summary.get("approval_token_count") or 0
    )
    assert full_matrix["first_blocked_release_blocker_id"] == full_matrix_summary.get(
        "first_blocked_release_blocker_id"
    )
    assert full_matrix["first_blocked_evidence_row_id"] == full_matrix_summary.get(
        "first_blocked_evidence_row_id"
    )
    assert full_matrix["first_blocked_evidence_artifact"] == full_matrix_summary.get(
        "first_blocked_evidence_artifact"
    )
    assert full_matrix["first_blocked_expected_evidence_status"] == full_matrix_summary.get(
        "first_blocked_expected_evidence_status"
    )
    assert full_matrix["first_blocked_observed_evidence_status"] == full_matrix_summary.get(
        "first_blocked_observed_evidence_status"
    )
    assert full_matrix["first_blocked_row_blockers"] == full_matrix_summary.get(
        "first_blocked_row_blockers"
    )
    assert full_matrix["first_blocked_acceptance_artifact"] == full_matrix_summary.get(
        "first_blocked_acceptance_artifact"
    )
    assert full_matrix["scope_receipt_most_common_row_blocker"] == full_matrix_summary.get(
        "scope_receipt_most_common_row_blocker"
    )
    assert full_matrix["engine_receipt_most_common_row_blocker"] == full_matrix_summary.get(
        "engine_receipt_most_common_row_blocker"
    )
    assert len(full_matrix["evidence_matrix"]) == full_matrix["matrix_row_count"]
    assert full_matrix["execution_enabled"] is False
    assert full_matrix["docking_results_emitted"] is False
    assert full_matrix["external_state_mutated"] is False

    completion = asyncio.run(product.get_product_goal_completion_audit())
    completion_payload = _artifact_payload("product_goal_completion_audit_current.json")
    completion_summary = completion_payload.get("summary") if isinstance(completion_payload.get("summary"), dict) else {}
    completion_rows = completion_payload.get("rows") if isinstance(completion_payload.get("rows"), list) else []
    assert completion["status"] == completion_summary.get("status")
    assert completion["goal_complete"] is (completion_summary.get("goal_complete") is True)
    assert completion["fail_count"] == int(completion_summary.get("fail_count") or 0)
    assert [row["requirement_id"] for row in completion["requirements"] if row["status"] == "fail"] == [
        row.get("requirement_id") for row in completion_rows if row.get("status") == "fail"
    ]
    assert completion["approval_tokens_required"] == list(completion_summary.get("approval_tokens_required") or [])
    assert completion["release_allowed"] is (completion_summary.get("release_allowed") is True)
    assert completion["release_artifact_ready"] is (completion_summary.get("release_artifact_ready") is True)
    assert completion["local_self_hosted_product_ready"] is (
        completion_summary.get("local_self_hosted_product_ready") is True
    )

    assert completion["product_ai_architecture_ready"] is (
        completion_summary.get("product_ai_architecture_ready") is True
    )
    assert completion["product_ai_architecture_gap_status"] == completion_summary.get(
        "product_ai_architecture_gap_status"
    )
    assert completion["product_ai_architecture_all_gaps_closed"] is (
        completion_summary.get("product_ai_architecture_all_gaps_closed") is True
    )
    assert completion["product_ai_architecture_gap_count"] == int(
        completion_summary.get("product_ai_architecture_gap_count") or 0
    )
    assert completion["product_ai_architecture_closed_gap_count"] == int(
        completion_summary.get("product_ai_architecture_closed_gap_count") or 0
    )
    assert completion["product_ai_architecture_open_gap_count"] == int(
        completion_summary.get("product_ai_architecture_open_gap_count") or 0
    )
    assert completion["product_ai_architecture_gap_blocker_matrix_count"] == int(
        completion_summary.get("product_ai_architecture_gap_blocker_matrix_count") or 0
    )
    assert completion["product_ai_production_checkpoint_gap_ready"] is (
        completion_summary.get("product_ai_production_checkpoint_gap_ready") is True
    )
    assert completion["production_ai_checkpoint_readiness_status"] == completion_summary.get(
        "production_ai_checkpoint_readiness_status"
    )
    assert completion["production_ai_checkpoint_ready"] is (
        completion_summary.get("production_ai_checkpoint_ready") is True
    )
    assert completion["production_ai_promotion_workbench_status"] == completion_summary.get(
        "production_ai_promotion_workbench_status"
    )
    assert completion["production_ai_promotion_ready"] is (
        completion_summary.get("production_ai_promotion_ready") is True
    )
    assert completion["production_ai_promotion_allowed"] is (
        completion_summary.get("production_ai_promotion_allowed") is True
    )
    assert completion["production_ai_trained_checkpoint_count"] == int(
        completion_summary.get("production_ai_trained_checkpoint_count") or 0
    )
    assert completion["production_ai_checkpoint_registry_promotion_missing_gate_ids"] == completion_summary.get(
        "production_ai_checkpoint_registry_promotion_missing_gate_ids"
    )
    assert completion["production_ai_checkpoint_registry_promotion_missing_gate_count"] == int(
        completion_summary.get("production_ai_checkpoint_registry_promotion_missing_gate_count") or 0
    )
    assert completion["production_ai_checkpoint_registry_promotion_upstream_acceptance_ready"] is (
        completion_summary.get("production_ai_checkpoint_registry_promotion_upstream_acceptance_ready") is True
    )
    assert completion["production_ai_checkpoint_registry_promotion_currently_satisfied"] is (
        completion_summary.get("production_ai_checkpoint_registry_promotion_currently_satisfied") is True
    )
    assert completion["production_ai_selected_sidecar_ready"] is (
        completion_summary.get("production_ai_selected_sidecar_ready") is True
    )
    assert completion["production_ai_selected_sidecar_missing_output_fields"] == completion_summary.get(
        "production_ai_selected_sidecar_missing_output_fields"
    )

    assert completion["production_ai_gpu_return_intake_status"] == completion_summary.get(
        "production_ai_gpu_return_intake_status"
    )
    assert completion["production_ai_gpu_return_intake_ready"] is (
        completion_summary.get("production_ai_gpu_return_intake_ready") is True
    )
    assert completion["production_ai_gpu_return_artifacts_ready"] is (
        completion_summary.get("production_ai_gpu_return_artifacts_ready") is True
    )
    assert completion["production_ai_gpu_return_fail_check_count"] == int(
        completion_summary.get("production_ai_gpu_return_fail_check_count") or 0
    )
    assert completion["production_ai_gpu_return_failed_check_ids"] == completion_summary.get(
        "production_ai_gpu_return_failed_check_ids"
    )
    assert completion["production_ai_gpu_return_expected_queue_rows"] == int(
        completion_summary.get("production_ai_gpu_return_expected_queue_rows") or 0
    )
    assert completion["production_ai_gpu_manifest_ok_row_count"] == int(
        completion_summary.get("production_ai_gpu_manifest_ok_row_count") or 0
    )
    assert completion["production_ai_gpu_manifest_npz_files_valid"] is (
        completion_summary.get("production_ai_gpu_manifest_npz_files_valid") is True
    )
    assert completion["production_ai_gpu_manifest_npz_schema_valid"] is (
        completion_summary.get("production_ai_gpu_manifest_npz_schema_valid") is True
    )
    assert completion["production_ai_gpu_manifest_npz_identity_valid"] is (
        completion_summary.get("production_ai_gpu_manifest_npz_identity_valid") is True
    )
    assert completion["production_ai_gpu_backend_provenance_ready"] is (
        completion_summary.get("production_ai_gpu_backend_provenance_ready") is True
    )
    assert completion["production_ai_gpu_worker_return_receipt_ready"] is (
        completion_summary.get("production_ai_gpu_worker_return_receipt_ready") is True
    )
    assert completion["production_ai_gpu_worker_rocm_visible_device_count"] == int(
        completion_summary.get("production_ai_gpu_worker_rocm_visible_device_count") or 0
    )

    assert completion["product_scope_breadth_contract_status"] == "blocked_product_scope_breadth_contract"
    assert completion["product_scope_closure_acceptance_ready"] is False
    assert completion["product_scope_closure_acceptance_blocked_stage_count"] == 3
    assert completion["product_scope_closure_acceptance_next_stage_id"] == "transporter_claim_acceptance"
    assert completion["product_scope_closure_acceptance_first_blocked_evidence_row_id"] == "AQP1.core_binder_01"
    assert completion["product_scope_closure_acceptance_first_blocked_target_id"] == "AQP1"
    assert completion["product_scope_closure_acceptance_first_blocked_required_missing_fields"] == (
        "replacement_reference_binding_kcal_mol"
    )
    assert completion["product_scope_authoritative_apply_allowed"] is False
    assert completion["product_scope_general_platform_claim_allowed"] is False
    assert completion["product_scope_claim_blocked_domains"] == ["transporter", "idp_broad"]
    assert completion["product_scope_evidence_priority_queue_item_count"] == 15
    assert completion["product_scope_evidence_priority_open_item_count"] == 15
    assert completion["product_scope_evidence_priority_local_crosscheck_candidate_count"] == 11
    assert completion["product_scope_evidence_priority_external_primary_exact_required_count"] == 0
    assert completion["product_scope_evidence_intake_row_count"] in {15, 16}
    assert completion["product_scope_transporter_manual_review_template_row_count"] == 8
    assert completion["product_scope_transporter_manual_review_direct_binding_evidence_required_count"] == 1
    assert completion["product_scope_transporter_manual_review_negative_quantitative_value_required_count"] == 6
    assert completion["product_scope_transporter_manual_review_decision_placeholder_count"] == 0
    assert completion["product_scope_transporter_top_claim_safe_blocker"] == (
        "direct_pool_exists_but_named_candidate_identity_not_operator_confirmed"
    )
    assert completion["product_scope_claim_expansion_currently_satisfied"] is False
    assert completion["product_scope_claim_expansion_current_blocked_stage_count"] == 3
    assert completion["product_scope_acceptance_next_stage_id"] == "transporter_claim_acceptance"
    assert completion["product_scope_acceptance_stage_evidence_matrix"][1]["first_blocked_evidence_row"][
        "evidence_row_id"
    ] == "AQP1.core_binder_01"

    assert completion["commercial_readiness_handoff_bundle_ready"] is (
        completion_summary.get("commercial_readiness_handoff_bundle_ready") is True
    )
    assert completion["commercial_readiness_handoff_bundle_artifact_reference_count"] == int(
        completion_summary.get("commercial_readiness_handoff_bundle_artifact_reference_count") or 0
    )
    assert completion["commercial_readiness_handoff_bundle_operator_return_pending_artifact_reference_count"] == 1
    assert completion["commercial_readiness_next_action_matrix_ready"] is (
        completion_summary.get("commercial_readiness_next_action_matrix_ready") is True
    )
    assert completion["commercial_readiness_next_action_matrix_count"] == int(
        completion_summary.get("commercial_readiness_next_action_matrix_count") or 0
    )
    assert completion["commercial_readiness_next_action_blocker_count"] == int(
        completion_summary.get("commercial_readiness_next_action_blocker_count") or 0
    )
    assert completion["commercial_readiness_first_next_action_id"] == completion_summary.get(
        "commercial_readiness_first_next_action_id"
    )

    for payload in (
        capabilities,
        structure,
        architecture,
        service_boundary,
        api_contract,
        operational_quality,
        security_deployment,
        public_benchmark,
        public_benchmark_receipts,
        trajectory_sla,
        ai_decision_graph,
        ai_report_ux,
        cameo_live_validation,
        operations,
        license_decision,
        license_options,
        license_work_order,
        commercial,
        release,
        registry,
        checkpoint,
        scope_breadth,
        scope_guard,
        scope_intake,
        transporter_review,
        pxr_review,
        completion,
    ):
        assert payload["execution_enabled"] is False
        assert payload["external_state_mutated"] is False
