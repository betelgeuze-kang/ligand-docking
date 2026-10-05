"""Data-driven route registration contracts for the product API suite."""

from __future__ import annotations

import importlib
from collections import Counter
from types import ModuleType


ROUTER_REQUIRED_ROUTE_PATHS = {
    "api.product_architecture": (
        "/product/architecture",
        "/product/architecture-validation",
    ),
    "api.product_benchmark": (
        "/product/external-metrics",
        "/product/public-benchmark",
        "/product/trajectory-sla-contract",
        "/product/rollout-execution-smoke-receipt",
    ),
    "api.product_capabilities": (
        "/product/capabilities",
    ),
    "api.product_docking": (
        "/product/docking/jobs",
        "/product/structure/analyze",
    ),
    "api.product_service_contracts": (
        "/product/service-boundary",
        "/product/api-contract",
    ),
    "api.product_operational": (
        "/product/operational-quality",
        "/product/security-deployment-contract",
    ),
    "api.product_release_ops": (
        "/product/operations",
        "/product/commercial-independence",
        "/product/release-readiness",
        "/product/job-orchestration-contract",
    ),
    "api.product_ai_surface": (
        "/product/ai-decision-graph",
        "/product/pose-sampling-readiness",
        "/product/ai-report-ux",
        "/product/residual-model-registry",
    ),
    "api.product_cameo_runner": (
        "/product/cameo-live-validation",
        "/product/cameo-official-result-fetch-preflight",
        "/product/api-runner-profile-promotion-operator-receipt",
        "/product/api-runner-profile-promotion-operator-staging-apply",
    ),
    "api.product_license": (
        "/product/license-decision",
        "/product/license-options",
        "/product/license-file-work-order",
        "/product/self-hosted-license-distribution-audit",
    ),
    "api.product_production_ai": (
        "/product/production-ai-checkpoint-readiness",
        "/product/production-ai-gpu-worker-dispatch-manifest",
        "/product/production-ai-gpu-worker-dispatch-bundle",
        "/product/production-ai-gpu-worker-execution-runbook",
        "/product/production-ai-gpu-return-intake",
        "/product/production-ai-promotion-workbench",
        "/product/production-ai-registry-promotion-operator-receipt",
        "/product/production-ai-registry-promotion-priority",
    ),
    "api.product_scope": (
        "/product/scope-breadth-contract",
        "/product/scope-claim-guard",
        "/product/scope-evidence-priority",
        "/product/scope-evidence-intake-readiness",
        "/product/transporter-manual-review-intake",
        "/product/pxr-exact-review-intake",
        "/product/aqp1-operator-validation-candidate",
        "/product/aqp1-direct-binding-procurement-packet",
    ),
    "api.product_commercial_readiness": (
        "/product/commercial-readiness-operator-packet",
        "/product/commercial-readiness-operator-packet-freshness",
        "/product/commercial-readiness-execution-ladder",
        "/product/commercial-readiness-handoff-bundle",
    ),
    "api.product_evidence_goal": (
        "/product/scope-breadth-evidence-receipt",
        "/product/engine-refinement-claim-evidence-receipt",
        "/product/engine-refinement-claim-evidence-priority",
        "/product/full-commercial-blocker-evidence-matrix",
        "/product/goal-completion-audit",
    ),
    "api.product_hbond_backmap": (
        "/product/hbond-backmap-report",
    ),
    "api.product_gpcr_hard_decoy": (
        "/product/gpcr-hard-decoy-suite-report",
    ),
}


MAIN_ONLY_REQUIRED_ROUTE_PATHS = (
    "/product/docking/jobs/{job_id}",
    "/product/docking/jobs/{job_id}/history",
    "/product/docking/jobs/{job_id}/cancel",
    "/product/docking/jobs/{job_id}/retry",
    "/product/tier-beta/docking/jobs",
)


ALLOW_MULTIPLE_MAIN_ROUTE_PATHS = frozenset((
    "/product/structure/analyze",
    "/product/docking/jobs",
    "/product/docking/jobs/{job_id}",
    "/product/docking/jobs/{job_id}/history",
    "/product/docking/jobs/{job_id}/cancel",
    "/product/docking/jobs/{job_id}/retry",
    "/product/tier-beta/docking/jobs",
))


OWNER_ROUTE_PATHS = tuple(
    path
    for required_paths in ROUTER_REQUIRED_ROUTE_PATHS.values()
    for path in required_paths
)
MAIN_REQUIRED_ROUTE_PATHS = OWNER_ROUTE_PATHS + MAIN_ONLY_REQUIRED_ROUTE_PATHS
UNIQUE_MAIN_ROUTE_PATHS = tuple(
    path
    for path in MAIN_REQUIRED_ROUTE_PATHS
    if path not in ALLOW_MULTIPLE_MAIN_ROUTE_PATHS
)


def _route_path_counts(routes) -> Counter[str]:
    return Counter(route.path for route in routes)


def _missing_paths(
    required: tuple[str, ...],
    observed: Counter[str],
) -> list[str]:
    return [path for path in required if observed[path] == 0]


def assert_product_routes_registered() -> ModuleType:
    """Assert main-app and owner-router registration, then return ``api.product``."""

    main = importlib.import_module("api.main")
    product = importlib.import_module("api.product")
    router_modules = {
        module_name: importlib.import_module(module_name)
        for module_name in ROUTER_REQUIRED_ROUTE_PATHS
    }

    main_counts = _route_path_counts(main.app.routes)
    missing_main = _missing_paths(MAIN_REQUIRED_ROUTE_PATHS, main_counts)
    assert not missing_main, f"product routes missing from api.main: {missing_main}"

    for module_name, required_paths in ROUTER_REQUIRED_ROUTE_PATHS.items():
        observed = _route_path_counts(router_modules[module_name].router.routes)
        missing = _missing_paths(required_paths, observed)
        assert not missing, f"product routes missing from {module_name}: {missing}"

    non_unique = {
        path: main_counts[path]
        for path in UNIQUE_MAIN_ROUTE_PATHS
        if main_counts[path] != 1
    }
    assert not non_unique, f"product routes are not unique on api.main: {non_unique}"

    return product
