from __future__ import annotations

from pathlib import Path
from typing import Any

CLAIM_BOUNDARY = (
    "Product architecture contract only; it consolidates local molecular-structure analysis, ligand-docking, "
    "reproducible public benchmark validation, optional CAMEO live validation, CASP17 transition, and cleanup-control "
    "evidence. It does not run docking, submit CAMEO or CASP predictions, compute native accuracy, choose a license, "
    "delete files, archive files, upload, or mutate external state."
)

CANONICAL_ARCHITECTURE_LANES = (
    "structure_analysis",
    "ligand_docking",
    "scoring_ranking",
    "benchmark_validation",
    "local_delivery",
    "commercial_independence",
    "CAMEO_live_validation",
)


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: Any) -> bool:
    return bool(value is True)


def _token_list(*values: Any) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for value in values:
        for token in _text(value).split(";"):
            token = token.strip()
            if token and token not in seen:
                seen.add(token)
                tokens.append(token)
    return tokens


def _file_contains(root: Path, path_like: str, needle: str) -> bool:
    path = root / path_like
    if not path.is_file():
        return False
    try:
        return needle in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _any_file_contains(root: Path, path_likes: tuple[str, ...], needle: str) -> bool:
    return any(_file_contains(root, path_like, needle) for path_like in path_likes)


def _artifact_present(root: Path, path_like: str) -> bool:
    return (root / path_like).exists()


def _row(
    *,
    lane_id: str,
    domain: str,
    status: str,
    observed: str,
    required: str,
    artifact_path: str,
    reason: str,
    approval_token_required: str = "",
    canonical_lane: str = "",
) -> dict[str, Any]:
    return {
        "lane_id": lane_id,
        "canonical_lane": canonical_lane,
        "domain": domain,
        "status": status,
        "observed": observed,
        "required": required,
        "approval_token_required": approval_token_required,
        "artifact_path": artifact_path,
        "reason": reason,
        "release_blocker": status != "ready",
        "execution_enabled": False,
        "docking_results_emitted": False,
        "cameo_submission_executed": False,
        "casp_submission_executed": False,
        "cleanup_executed": False,
        "external_state_mutated": False,
    }


def _blocker(row: dict[str, Any]) -> dict[str, str]:
    return {
        "code": f"{row['lane_id']}_not_ready",
        "severity": "hard",
        "lane_id": _text(row["lane_id"]),
        "reason": f"{row['reason']} Observed: {row['observed']}; required: {row['required']}.",
    }


def build_product_architecture_contract(
    *,
    product_capability_packet: dict[str, Any],
    product_release_packet: dict[str, Any],
    commercial_independence_packet: dict[str, Any],
    cameo_capability_packet: dict[str, Any],
    cleanup_operations_packet: dict[str, Any],
    cleanup_approval_packet: dict[str, Any],
    ligand_cleanup_work_order_packet: dict[str, Any],
    ligand_cleanup_preflight_packet: dict[str, Any],
    casp17_transition_packet: dict[str, Any],
    product_service_boundary_packet: dict[str, Any] | None = None,
    product_api_contract_packet: dict[str, Any] | None = None,
    product_execution_preflight_packet: dict[str, Any] | None = None,
    public_benchmark_packet: dict[str, Any] | None = None,
    public_benchmark_work_order_packet: dict[str, Any] | None = None,
    cameo_architecture_validation_packet: dict[str, Any] | None = None,
    cleanup_postcheck_packet: dict[str, Any] | None = None,
    cleanup_completion_packet: dict[str, Any] | None = None,
    root: str | Path = ".",
    product_capability_path: str = "runs/product_capability_surface_contract_current.json",
    product_release_path: str = "runs/product_release_operations_dossier_current.json",
    commercial_independence_path: str = "runs/product_commercial_independence_gate_current.json",
    product_service_boundary_path: str = "runs/product_service_boundary_contract_current.json",
    product_api_contract_path: str = "runs/product_api_contract_current.json",
    product_execution_preflight_path: str = "runs/product_execution_preflight_current.json",
    public_benchmark_path: str = "runs/product_public_benchmark_contract_current.json",
    public_benchmark_work_order_path: str = "runs/product_public_benchmark_work_order_current.json",
    cameo_capability_path: str = "runs/cameo_capability_preflight_current.json",
    cameo_architecture_validation_path: str = "runs/cameo_architecture_validation_contract_current.json",
    cleanup_operations_path: str = "runs/cleanup_operations_surface_contract_current.json",
    cleanup_approval_path: str = "runs/cleanup_execution_approval_gate_current.json",
    cleanup_postcheck_path: str = "runs/cleanup_postcheck_contract_current.json",
    cleanup_completion_path: str = "runs/cleanup_completion_gate_current.json",
    ligand_cleanup_work_order_path: str = "runs/ligand_heavy_cleanup_work_order_current.json",
    ligand_cleanup_preflight_path: str = "runs/ligand_heavy_cleanup_execution_preflight_current.json",
    casp17_transition_path: str = "casp17/casp17_transition_surface_contract_current.json",
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    product = _summary(product_capability_packet)
    release = _summary(product_release_packet)
    commercial = _summary(commercial_independence_packet)
    service_boundary = _summary(product_service_boundary_packet or {})
    api_contract = _summary(product_api_contract_packet or {})
    execution_preflight = _summary(product_execution_preflight_packet or {})
    public_benchmark = _summary(public_benchmark_packet or {})
    public_benchmark_work_order = _summary(public_benchmark_work_order_packet or {})
    cameo = _summary(cameo_capability_packet)
    cameo_architecture = _summary(cameo_architecture_validation_packet or {})
    cleanup_ops = _summary(cleanup_operations_packet)
    cleanup_approval = _summary(cleanup_approval_packet)
    cleanup_postcheck = _summary(cleanup_postcheck_packet or {})
    cleanup_completion = _summary(cleanup_completion_packet or {})
    ligand_work = _summary(ligand_cleanup_work_order_packet)
    ligand_preflight = _summary(ligand_cleanup_preflight_packet)
    casp17 = _summary(casp17_transition_packet)

    product_api_present = _artifact_present(root_path, "api/product.py")
    product_architecture_endpoint_present = _any_file_contains(
        root_path,
        ("api/product.py", "api/product_architecture.py"),
        '"/architecture"',
    )
    request_contract_present = _artifact_present(root_path, "betelgeuze_product/docking_request.py")
    execution_preflight_present = _artifact_present(root_path, "betelgeuze_product/execution_preflight.py")
    htvs_command_present = _artifact_present(root_path, "betelgeuze_product/htvs_command.py")
    ligand_pipeline_present = _artifact_present(root_path, "tools/run_ligand_htvs_pipeline.py")
    service_boundary_endpoint_present = _any_file_contains(
        root_path,
        ("api/product.py", "api/product_service_contracts.py"),
        '"/service-boundary"',
    )
    api_contract_endpoint_present = _any_file_contains(
        root_path,
        ("api/product.py", "api/product_service_contracts.py"),
        '"/api-contract"',
    )
    cameo_api_present = _artifact_present(root_path, "api/cameo.py")
    cleanup_api_present = _artifact_present(root_path, "api/cleanup.py")
    casp17_api_present = _artifact_present(root_path, "api/casp17.py")

    structure_ready = (
        _text(product.get("status")) == "product_capability_surface_contract_ready"
        and _bool(product.get("structure_analysis_capability_ready"))
        and product_api_present
        and product_architecture_endpoint_present
        and request_contract_present
    )
    docking_ready = (
        _text(product.get("status")) == "product_capability_surface_contract_ready"
        and _bool(product.get("ligand_docking_capability_ready"))
        and execution_preflight_present
        and htvs_command_present
        and ligand_pipeline_present
    )
    commercial_ready = (
        _text(commercial.get("status")) == "product_commercial_independence_gate_ready"
        and _bool(commercial.get("commercial_independent_product_claim_allowed"))
    )
    service_boundary_ready = (
        _text(service_boundary.get("status")) == "product_service_boundary_contract_ready"
        and _bool(service_boundary.get("service_boundary_ready"))
        and service_boundary_endpoint_present
    )
    api_contract_ready = (
        _text(api_contract.get("status")) == "product_api_contract_ready"
        and _bool(api_contract.get("api_contract_ready"))
        and api_contract_endpoint_present
    )
    public_benchmark_ready = (
        _text(public_benchmark.get("status")) == "product_public_benchmark_contract_ready"
        and _bool(public_benchmark.get("public_benchmark_validation_ready"))
    )
    cameo_local_surface_ready = (
        cameo_api_present
        and _text(cameo.get("status"))
        in {
            "cameo_capability_preflight_ready",
            "cameo_development_capability_preflight_ready",
            "cameo_public_registration_preflight_ready",
            "blocked_cameo_capability_preflight",
        }
        and _bool(cameo.get("api_operations_route_registered"))
    )
    cameo_architecture_contract_present = bool(cameo_architecture)
    cameo_architecture_local_protocol_ready = _bool(cameo_architecture.get("local_validation_protocol_ready"))
    cameo_service_boundary_ready = _bool(cameo_architecture.get("cameo_service_boundary_ready"))
    cameo_api_contract_ready = _bool(cameo_architecture.get("cameo_api_contract_ready"))
    cameo_receiver_smoke_ready = _text(cameo.get("source_receiver_smoke_status")) == "cameo_receiver_smoke_ready"
    cameo_api_dependency_ready = _bool(cameo.get("api_dependency_ready"))
    cameo_official_evidence_ready = _bool(cameo_architecture.get("validation_evidence_ready")) or _bool(
        cameo_architecture.get("official_results_ready")
    )
    cameo_registration_tokens = _token_list(
        cameo.get("registration_approval_token_required"),
        cameo.get("public_registration_approval_token_required"),
        cameo.get("outbound_email_approval_token_required"),
    )
    cameo_validation_ready = (
        cameo_local_surface_ready
        and _bool(cameo_architecture.get("cameo_architecture_validation_ready"))
        and _bool(cameo.get("public_registration_allowed"))
    )
    if not cameo_architecture_contract_present:
        cameo_validation_ready = cameo_local_surface_ready and _bool(cameo.get("public_registration_allowed"))
    cleanup_surface_ready = (
        cleanup_api_present
        and _text(cleanup_ops.get("status")) == "cleanup_operations_surface_contract_ready"
        and _bool(cleanup_ops.get("surface_ready"))
    )
    cleanup_postcheck_ready = (
        _text(cleanup_postcheck.get("status")) == "cleanup_postcheck_contract_ready"
        and _bool(cleanup_postcheck.get("postcheck_contract_ready"))
        and _int(cleanup_postcheck.get("row_count")) > 0
        and _int(cleanup_postcheck.get("blocked_row_count")) == 0
    )
    cleanup_completion_ready = (
        _text(cleanup_completion.get("status")) == "cleanup_completion_gate_ready"
        and _bool(cleanup_completion.get("cleanup_complete"))
        and _int(cleanup_completion.get("blocked_stage_count")) == 0
    )
    cleanup_approved = _bool(cleanup_approval.get("authorized_for_cleanup_execution")) or (
        _text(cleanup_approval.get("status")) == "cleanup_execution_operator_approval_gate_ready"
        and _int(cleanup_approval.get("authorized_row_count")) > 0
        and _int(cleanup_approval.get("awaiting_operator_approval_row_count")) == 0
        and _int(cleanup_approval.get("blocked_row_count")) == 0
    )
    ligand_cleanup_ready = (
        cleanup_completion_ready
        or (
            _text(ligand_work.get("status")) == "cleanup_work_order_ready"
            and _text(ligand_preflight.get("status")) == "ligand_heavy_cleanup_execution_preflight_ready"
            and _int(ligand_preflight.get("blocker_count")) == 0
        )
    )
    casp17_transition_ready = (
        casp17_api_present
        and _text(casp17.get("status")) == "casp17_transition_surface_contract_ready"
        and _bool(casp17.get("surface_ready"))
    )
    product_execution_authorized = _bool(release.get("authorized_for_execution"))
    delivery_ready_claim_allowed = _bool(release.get("delivery_ready_claim_allowed"))
    release_allowed = product_execution_authorized and delivery_ready_claim_allowed
    gate_checks = (
        product_execution_preflight_packet.get("operational_gate_feasibility_checks")
        if isinstance((product_execution_preflight_packet or {}).get("operational_gate_feasibility_checks"), list)
        else []
    )
    ranking_gate = gate_checks[0] if gate_checks and isinstance(gate_checks[0], dict) else {}
    scoring_ranking_ready = (
        _text(execution_preflight.get("status")) == "product_execution_preflight_ready"
        and _text(execution_preflight.get("operational_gate_feasibility_status")) == "pass"
        and _text(ranking_gate.get("status")) == "pass"
        and _int(ranking_gate.get("eval_unique_keys")) >= _int(ranking_gate.get("gate_min_eval_unique_keys"))
        and _float(ranking_gate.get("gate_ef1_min")) > 0
        and bool(_text(ranking_gate.get("ranking_labels_csv")))
    )
    local_delivery_bundle_ready = (
        _bool(product.get("local_delivery_bundle_capability_ready"))
        and _bool(product.get("result_bundle_generation_contract_ready"))
        and _bool(release.get("bundle_assembled"))
        and _bool(release.get("bundle_validation_passed"))
        and _bool(release.get("delivery_ready_claim_allowed"))
        and _bool(release.get("pilot_delivery_ready"))
    )

    rows = [
        _row(
            lane_id="structure_analysis_product_surface",
            canonical_lane="structure_analysis",
            domain="product",
            status="ready" if structure_ready else "blocked",
            observed=(
                f"product_status={_text(product.get('status')) or 'missing'};"
                f"structure_ready={_bool(product.get('structure_analysis_capability_ready'))};"
                f"architecture_endpoint={product_architecture_endpoint_present};request_contract={request_contract_present}"
            ),
            required="ready product capability contract, structure-analysis capability, request contract, and /product/architecture endpoint",
            artifact_path=f"{product_capability_path};api/product.py;api/product_architecture.py;betelgeuze_product/docking_request.py",
            reason="The commercial product architecture needs a visible structure-analysis intake and status surface.",
        ),
        _row(
            lane_id="ligand_docking_execution_contract",
            canonical_lane="ligand_docking",
            domain="product",
            status="ready" if docking_ready else "blocked",
            observed=(
                f"ligand_docking_ready={_bool(product.get('ligand_docking_capability_ready'))};"
                f"execution_preflight={execution_preflight_present};htvs_command={htvs_command_present};pipeline={ligand_pipeline_present}"
            ),
            required="ready ligand-docking capability with execution preflight, HTVS command renderer, and local pipeline entrypoint",
            artifact_path=f"{product_capability_path};betelgeuze_product/execution_preflight.py;betelgeuze_product/htvs_command.py;tools/run_ligand_htvs_pipeline.py",
            reason="The architecture must expose a bounded docking execution contract before any approved run.",
        ),
        _row(
            lane_id="scoring_ranking_contract",
            canonical_lane="scoring_ranking",
            domain="scoring_ranking",
            status="ready" if scoring_ranking_ready else "blocked",
            observed=(
                f"preflight_status={_text(execution_preflight.get('status')) or 'missing'};"
                f"operational_gate={_text(execution_preflight.get('operational_gate_feasibility_status')) or 'missing'};"
                f"ranking_gate_status={_text(ranking_gate.get('status')) or 'missing'};"
                f"eval_unique_keys={_int(ranking_gate.get('eval_unique_keys'))};"
                f"gate_min_eval_unique_keys={_int(ranking_gate.get('gate_min_eval_unique_keys'))};"
                f"gate_ef1_min={_float(ranking_gate.get('gate_ef1_min'))};"
                f"ranking_labels_csv={_text(ranking_gate.get('ranking_labels_csv')) or 'missing'}"
            ),
            required="execution preflight with operational gate pass, ranking labels, eval coverage, and scoring/ranking thresholds",
            artifact_path=product_execution_preflight_path,
            reason="The product architecture needs a distinct scoring/ranking contract, not only a docking command surface.",
        ),
        _row(
            lane_id="commercial_independence_release_gate",
            canonical_lane="commercial_independence",
            domain="product",
            status="ready" if commercial_ready else "blocked",
            observed=(
                f"commercial_status={_text(commercial.get('status')) or 'missing'};"
                f"claim_allowed={_bool(commercial.get('commercial_independent_product_claim_allowed'))};"
                f"dependency_provenance={_bool(commercial.get('dependency_provenance_manifest_present'))};"
                f"requirements_lock={_bool(commercial.get('requirements_lock_artifacts_present'))};"
                f"reproducible_install={_bool(commercial.get('reproducible_install_manifest_ready'))};"
                f"product_execution_authorized={product_execution_authorized};"
                f"delivery_ready_claim_allowed={delivery_ready_claim_allowed};"
                f"release_claim_allowed={commercial_ready}"
            ),
            required="commercial-independence gate ready with license, dependency provenance, reproducible install, and release claim allowed by local evidence",
            artifact_path=f"{commercial_independence_path};{product_release_path}",
            reason="The product cannot be called commercially independent until license, packaging, dependency provenance, and reproducible install evidence clear.",
        ),
        _row(
            lane_id="local_delivery_bundle_validation",
            canonical_lane="local_delivery",
            domain="local_delivery",
            status="ready" if local_delivery_bundle_ready else "blocked",
            observed=(
                f"capability_bundle_ready={_bool(product.get('local_delivery_bundle_capability_ready'))};"
                f"result_bundle_generation_contract_ready={_bool(product.get('result_bundle_generation_contract_ready'))};"
                f"result_bundle_artifact_count={_int(product.get('result_bundle_artifact_count'))};"
                f"bundle_assembled={_bool(release.get('bundle_assembled'))};"
                f"bundle_validation_passed={_bool(release.get('bundle_validation_passed'))};"
                f"delivery_ready_claim_allowed={_bool(release.get('delivery_ready_claim_allowed'))};"
                f"pilot_delivery_ready={_bool(release.get('pilot_delivery_ready'))};"
                f"bundle_tag={_text(release.get('bundle_tag')) or 'missing'}"
            ),
            required="result-bundle generation contract, local-delivery capability, assembled bundle, passing bundle validation, and delivery/pilot evidence",
            artifact_path=f"{product_release_path};runs/product_bundle_contract_current.json;runs/product_delivery_evidence_contract_current.json;runs/product_pilot_packet_contract_current.json",
            reason="A standalone commercial product needs a validated local result bundle lane for structure/docking outputs, separate from benchmark and license gates.",
        ),
        _row(
            lane_id="product_service_boundary_contract",
            domain="product",
            status="ready" if service_boundary_ready else "blocked",
            observed=(
                f"service_boundary_status={_text(service_boundary.get('status')) or 'missing'};"
                f"service_boundary_ready={_bool(service_boundary.get('service_boundary_ready'))};"
                f"service_boundary_endpoint={service_boundary_endpoint_present};"
                f"api_route_count={_int(service_boundary.get('api_route_count'))};"
                f"cli_command_count={_int(service_boundary.get('cli_command_count'))}"
            ),
            required="product service-boundary contract ready, API endpoint present, and CLI/API/artifact registry coherent",
            artifact_path=f"{product_service_boundary_path};api/product.py;api/product_service_contracts.py;betelgeuze_product/cli.py",
            reason="The product architecture should expose a dedicated service-boundary status surface for commercial handoff.",
        ),
        _row(
            lane_id="product_api_contract",
            domain="product",
            status="ready" if api_contract_ready else "blocked",
            observed=(
                f"api_contract_status={_text(api_contract.get('status')) or 'missing'};"
                f"api_contract_ready={_bool(api_contract.get('api_contract_ready'))};"
                f"api_contract_endpoint={api_contract_endpoint_present};"
                f"expected_route_count={_int(api_contract.get('expected_route_count'))};"
                f"missing_route_count={_int(api_contract.get('missing_route_count'))};"
                f"status_response_missing_key_count={_int(api_contract.get('status_response_missing_key_count'))}"
            ),
            required="product API contract ready, /product/api-contract endpoint present, and route/schema/safety flags coherent",
            artifact_path=f"{product_api_contract_path};api/product.py;api/product_service_contracts.py",
            reason="Commercial handoff needs a static API contract for customer integration, not only source-level route presence.",
        ),
        _row(
            lane_id="public_benchmark_validation_gate",
            canonical_lane="benchmark_validation",
            domain="performance_validation",
            status="ready" if public_benchmark_ready else "blocked",
            observed=(
                f"public_benchmark_status={_text(public_benchmark.get('status')) or 'missing'};"
                f"public_benchmark_validation_ready={public_benchmark_ready};"
                f"benchmark_mode={_text(public_benchmark.get('benchmark_mode')) or 'missing'};"
                f"required_suite_count={_int(public_benchmark.get('required_suite_count'))};"
                f"ready_required_suite_count={_int(public_benchmark.get('ready_required_suite_count'))};"
                f"blocked_suite_count={_int(public_benchmark.get('blocked_suite_count'))};"
                f"suite_materialization_manifest_count={_int(public_benchmark.get('suite_materialization_manifest_count'))};"
                f"suite_scorecard_row_csv_count={_int(public_benchmark.get('suite_scorecard_row_csv_count'))};"
                f"suite_threshold_count={_int(public_benchmark.get('suite_threshold_count'))};"
                f"suite_blocker_count={_int(public_benchmark.get('suite_blocker_count'))};"
                f"suite_run_command_count={_int(public_benchmark.get('suite_run_command_count'))};"
                f"suite_materialization_run_command_count={_int(public_benchmark.get('suite_materialization_run_command_count'))};"
                f"suite_result_provenance_command_count={_int(public_benchmark_work_order.get('suite_result_provenance_command_count'))};"
                f"suite_result_provenance_present_count={_int(public_benchmark_work_order.get('suite_result_provenance_present_count'))};"
                f"suite_no_external_dependency_count={_int(public_benchmark.get('suite_no_external_dependency_count'))};"
                f"work_order_status={_text(public_benchmark_work_order.get('status')) or 'missing'};"
                f"work_order_open_suite_count={_int(public_benchmark_work_order.get('open_suite_count'))};"
                f"work_order_materialization_required_suite_count={_int(public_benchmark_work_order.get('materialization_required_suite_count'))};"
                f"work_order_scorecard_required_suite_count={_int(public_benchmark_work_order.get('scorecard_required_suite_count'))};"
                f"work_order_continuous_validation_command_count={_int(public_benchmark_work_order.get('continuous_validation_command_count'))};"
                f"work_order_suite_run_command_count={_int(public_benchmark_work_order.get('suite_run_command_count'))};"
                f"work_order_suite_result_provenance_command_count={_int(public_benchmark_work_order.get('suite_result_provenance_command_count'))};"
                f"work_order_suite_result_provenance_present_count={_int(public_benchmark_work_order.get('suite_result_provenance_present_count'))};"
                f"work_order_suite_threshold_count={_int(public_benchmark_work_order.get('suite_threshold_count'))};"
                f"work_order_suite_materialization_manifest_count={_int(public_benchmark_work_order.get('suite_materialization_manifest_count'))};"
                f"work_order_suite_scorecard_row_csv_count={_int(public_benchmark_work_order.get('suite_scorecard_row_csv_count'))};"
                f"work_order_suite_no_external_dependency_count={_int(public_benchmark_work_order.get('suite_no_external_dependency_count'))};"
                f"work_order_local_artifact_preflight_ready_suite_count={_int(public_benchmark_work_order.get('local_artifact_preflight_ready_suite_count'))};"
                f"work_order_local_artifact_preflight_blocked_suite_count={_int(public_benchmark_work_order.get('local_artifact_preflight_blocked_suite_count'))};"
                f"work_order_missing_local_input_artifact_count={_int(public_benchmark_work_order.get('missing_local_input_artifact_count'))};"
                f"work_order_missing_local_output_artifact_count={_int(public_benchmark_work_order.get('missing_local_output_artifact_count'))};"
                f"requires_24h_server={_bool(public_benchmark.get('requires_24h_server'))};"
                f"requires_competition_season={_bool(public_benchmark.get('requires_competition_season'))};"
                f"requires_paid_vps={_bool(public_benchmark.get('requires_paid_vps'))}"
            ),
            required="ready reproducible public benchmark contract covering ligand screening, pose/affinity, complex docking, and structure-regression suites",
            artifact_path=f"{public_benchmark_path};{public_benchmark_work_order_path}",
            reason=(
                "Commercial product performance validation should be reproducible on public benchmarks without requiring "
                "CAMEO registration, a paid 24-hour server, or an active competition season."
            ),
        ),
        _row(
            lane_id="cameo_optional_live_validation_surface",
            canonical_lane="CAMEO_live_validation",
            domain="cameo_validation",
            status="ready" if cameo_local_surface_ready else "blocked",
            observed=(
                f"cameo_status={_text(cameo.get('status')) or 'missing'};"
                f"api_operations_route_registered={_bool(cameo.get('api_operations_route_registered'))};"
                f"architecture_validation_status={_text(cameo_architecture.get('status')) or 'missing'};"
                f"local_validation_protocol_ready={cameo_architecture_local_protocol_ready};"
                f"official_evidence_ready={cameo_official_evidence_ready};"
                f"receiver_smoke_status={_text(cameo.get('source_receiver_smoke_status')) or 'missing'};"
                f"api_dependency_ready={cameo_api_dependency_ready};"
                f"public_registration_allowed={_bool(cameo.get('public_registration_allowed'))};"
                f"public_registration_blocker_count={_int(cameo.get('public_registration_blocker_count'))};"
                f"registration_tokens={';'.join(cameo_registration_tokens)}"
            ),
            required="optional CAMEO operations API surface connected; official evidence and registration remain separate non-release live-validation add-ons",
            artifact_path=f"{cameo_capability_path};{cameo_architecture_validation_path};api/cameo.py",
            reason=(
                "CAMEO remains useful as an optional live external benchmark, but the product release path no longer "
                "depends on public server registration or outbound email."
            ),
        ),
        _row(
            lane_id="cleanup_control_surface",
            domain="cleanup",
            status="ready" if cleanup_surface_ready else "blocked",
            observed=(
                f"cleanup_ops={_text(cleanup_ops.get('status')) or 'missing'};"
                f"surface_ready={_bool(cleanup_ops.get('surface_ready'))};"
                f"approval_endpoint={_bool(cleanup_ops.get('cleanup_approval_gate_endpoint_present'))}"
            ),
            required="read-only cleanup operations surface and approval-gate endpoint",
            artifact_path=f"{cleanup_operations_path};api/cleanup.py",
            reason="Large data cleanup must be visible and operator-gated before any destructive action.",
        ),
        _row(
            lane_id="cleanup_postcheck_contract",
            domain="cleanup",
            status="ready" if cleanup_postcheck_ready else "blocked",
            observed=(
                f"postcheck_status={_text(cleanup_postcheck.get('status')) or 'missing'};"
                f"postcheck_ready={cleanup_postcheck_ready};"
                f"row_count={_int(cleanup_postcheck.get('row_count'))};"
                f"blocked_row_count={_int(cleanup_postcheck.get('blocked_row_count'))};"
                f"global_refresh_command_count={_int(cleanup_postcheck.get('global_refresh_command_count'))}"
            ),
            required="cleanup postcheck contract ready, row_count>0, blocked_row_count=0, and global refresh commands recorded",
            artifact_path=cleanup_postcheck_path,
            reason="Cleanup completion and release claims need row-specific postcheck evidence before any approved cleanup is treated as complete.",
        ),
        _row(
            lane_id="ligand_heavy_cleanup_preflight",
            domain="cleanup",
            status=(
                "ready"
                if cleanup_completion_ready or (ligand_cleanup_ready and cleanup_approved)
                else ("approval_required" if ligand_cleanup_ready else "blocked")
            ),
            observed=(
                f"work_order={_text(ligand_work.get('status')) or 'missing'};"
                f"preflight={_text(ligand_preflight.get('status')) or 'missing'};"
                f"cleanup_approved={cleanup_approved};"
                f"completion={_text(cleanup_completion.get('status')) or 'missing'};"
                f"cleanup_complete={cleanup_completion_ready}"
            ),
            required="ligand-heavy cleanup work order/preflight plus approval, or cleanup completion gate ready after approved execution",
            approval_token_required=(
                ""
                if cleanup_completion_ready
                else _text(
                    ligand_preflight.get("approval_token_required")
                    or ligand_work.get("approval_token_required")
                    or cleanup_approval.get("approval_token_required")
                )
            ),
            artifact_path=f"{ligand_cleanup_work_order_path};{ligand_cleanup_preflight_path};{cleanup_approval_path};{cleanup_completion_path}",
            reason=(
                "The ligand-heavy cleanup lane must either remain approval-gated before execution or be backed by "
                "explicit cleanup completion evidence after approved execution."
            ),
        ),
        _row(
            lane_id="casp17_transition_surface",
            domain="casp17_transition",
            status="ready" if casp17_transition_ready else "blocked",
            observed=(
                f"casp17_status={_text(casp17.get('status')) or 'missing'};"
                f"surface_ready={_bool(casp17.get('surface_ready'))};casp17_api={casp17_api_present}"
            ),
            required="CASP17 read-only transition/upload surface contract and API route",
            artifact_path=f"{casp17_transition_path};api/casp17.py",
            reason="CASP17 carry-over state must stay inspectable while upload, native accuracy, and stale-folder cleanup remain gated.",
        ),
        _row(
            lane_id="fail_closed_claim_boundary",
            domain="guardrails",
            status="ready",
            observed="execution_enabled=False;docking_results_emitted=False;cameo_submission_executed=False;casp_submission_executed=False;cleanup_executed=False;external_state_mutated=False",
            required="architecture contract reports status only and performs no execution, submission, cleanup, upload, or external mutation",
            artifact_path="betelgeuze_product/architecture.py",
            reason="Commercial product architecture evidence must not imply scientific results or destructive/external actions that did not happen.",
        ),
    ]

    blockers = [_blocker(row) for row in rows if row["status"] == "blocked"]
    approval_required = [row for row in rows if row["status"] == "approval_required"]
    ready_count = sum(1 for row in rows if row["status"] == "ready")
    canonical_lane_statuses = {
        _text(row.get("canonical_lane")): _text(row.get("status"))
        for row in rows
        if _text(row.get("canonical_lane"))
    }
    canonical_lane_ids = {
        _text(row.get("canonical_lane")): _text(row.get("lane_id"))
        for row in rows
        if _text(row.get("canonical_lane"))
    }
    missing_canonical_lanes = [
        lane for lane in CANONICAL_ARCHITECTURE_LANES if lane not in canonical_lane_statuses
    ]
    blocked_canonical_lanes = [
        lane for lane in CANONICAL_ARCHITECTURE_LANES if canonical_lane_statuses.get(lane) != "ready"
    ]
    local_architecture_surface_ready = (
        structure_ready
        and docking_ready
        and scoring_ranking_ready
        and local_delivery_bundle_ready
        and service_boundary_ready
        and api_contract_ready
        and public_benchmark_ready
        and cleanup_surface_ready
        and cleanup_postcheck_ready
        and casp17_transition_ready
        and cameo_local_surface_ready
    )
    architecture_release_ready = ready_count == len(rows)
    status = "product_architecture_contract_ready" if architecture_release_ready else "blocked_product_architecture_contract"
    summary = {
        "packet_type": "product_architecture_contract",
        "status": status,
        "lane_count": len(rows),
        "ready_lane_count": ready_count,
        "blocked_lane_count": len(blockers),
        "approval_required_lane_count": len(approval_required),
        "canonical_architecture_lanes_required": list(CANONICAL_ARCHITECTURE_LANES),
        "canonical_architecture_lane_count": len(CANONICAL_ARCHITECTURE_LANES),
        "canonical_architecture_required_lanes_present": not missing_canonical_lanes,
        "canonical_architecture_missing_lanes": missing_canonical_lanes,
        "canonical_architecture_lane_statuses": canonical_lane_statuses,
        "canonical_architecture_lane_ids": canonical_lane_ids,
        "canonical_architecture_ready_lane_count": sum(
            1 for lane in CANONICAL_ARCHITECTURE_LANES if canonical_lane_statuses.get(lane) == "ready"
        ),
        "canonical_architecture_blocked_lane_count": len(blocked_canonical_lanes),
        "canonical_architecture_blocked_lanes": blocked_canonical_lanes,
        "local_architecture_surface_ready": local_architecture_surface_ready,
        "architecture_release_ready": architecture_release_ready,
        "structure_analysis_product_surface_ready": structure_ready,
        "ligand_docking_execution_contract_ready": docking_ready,
        "scoring_ranking_contract_ready": scoring_ranking_ready,
        "scoring_ranking_eval_unique_keys": _int(ranking_gate.get("eval_unique_keys")),
        "scoring_ranking_gate_min_eval_unique_keys": _int(ranking_gate.get("gate_min_eval_unique_keys")),
        "scoring_ranking_gate_ef1_min": _float(ranking_gate.get("gate_ef1_min")),
        "local_delivery_bundle_validation_ready": local_delivery_bundle_ready,
        "result_bundle_generation_contract_ready": _bool(product.get("result_bundle_generation_contract_ready")),
        "result_bundle_expected_dir": _text(product.get("result_bundle_expected_dir")),
        "result_bundle_artifact_count": _int(product.get("result_bundle_artifact_count")),
        "result_bundle_planned_artifact_paths": product.get("result_bundle_planned_artifact_paths")
        if isinstance(product.get("result_bundle_planned_artifact_paths"), list)
        else [],
        "result_bundle_validation_command_matches": _bool(product.get("result_bundle_validation_command_matches")),
        "result_bundle_rerun_command_present": _bool(product.get("result_bundle_rerun_command_present")),
        "local_delivery_bundle_assembled": _bool(release.get("bundle_assembled")),
        "local_delivery_bundle_validation_passed": _bool(release.get("bundle_validation_passed")),
        "local_delivery_pilot_delivery_ready": _bool(release.get("pilot_delivery_ready")),
        "product_service_boundary_ready": service_boundary_ready,
        "product_api_contract_ready": api_contract_ready,
        "public_benchmark_validation_ready": public_benchmark_ready,
        "public_benchmark_status": _text(public_benchmark.get("status")),
        "public_benchmark_required_suite_count": _int(public_benchmark.get("required_suite_count")),
        "public_benchmark_ready_required_suite_count": _int(public_benchmark.get("ready_required_suite_count")),
        "public_benchmark_blocked_suite_count": _int(public_benchmark.get("blocked_suite_count")),
        "public_benchmark_suite_materialization_manifest_count": _int(
            public_benchmark.get("suite_materialization_manifest_count")
        ),
        "public_benchmark_suite_scorecard_row_csv_count": _int(public_benchmark.get("suite_scorecard_row_csv_count")),
        "public_benchmark_suite_threshold_count": _int(public_benchmark.get("suite_threshold_count")),
        "public_benchmark_suite_blocker_count": _int(public_benchmark.get("suite_blocker_count")),
        "public_benchmark_suite_run_command_count": _int(public_benchmark.get("suite_run_command_count")),
        "public_benchmark_suite_materialization_run_command_count": _int(
            public_benchmark.get("suite_materialization_run_command_count")
        ),
        "public_benchmark_suite_result_provenance_command_count": _int(
            public_benchmark_work_order.get("suite_result_provenance_command_count")
        ),
        "public_benchmark_suite_result_provenance_present_count": _int(
            public_benchmark_work_order.get("suite_result_provenance_present_count")
        ),
        "public_benchmark_suite_no_external_dependency_count": _int(
            public_benchmark.get("suite_no_external_dependency_count")
        ),
        "public_benchmark_requires_24h_server": _bool(public_benchmark.get("requires_24h_server")),
        "public_benchmark_requires_competition_season": _bool(public_benchmark.get("requires_competition_season")),
        "public_benchmark_requires_paid_vps": _bool(public_benchmark.get("requires_paid_vps")),
        "public_benchmark_work_order_status": _text(public_benchmark_work_order.get("status")),
        "public_benchmark_work_order_artifact": public_benchmark_work_order_path,
        "public_benchmark_work_order_open_suite_count": _int(public_benchmark_work_order.get("open_suite_count")),
        "public_benchmark_work_order_materialization_required_suite_count": _int(
            public_benchmark_work_order.get("materialization_required_suite_count")
        ),
        "public_benchmark_work_order_scorecard_required_suite_count": _int(
            public_benchmark_work_order.get("scorecard_required_suite_count")
        ),
        "public_benchmark_work_order_continuous_validation_command_count": _int(
            public_benchmark_work_order.get("continuous_validation_command_count")
        ),
        "public_benchmark_work_order_suite_run_command_count": _int(
            public_benchmark_work_order.get("suite_run_command_count")
        ),
        "public_benchmark_work_order_suite_result_provenance_command_count": _int(
            public_benchmark_work_order.get("suite_result_provenance_command_count")
        ),
        "public_benchmark_work_order_suite_result_provenance_present_count": _int(
            public_benchmark_work_order.get("suite_result_provenance_present_count")
        ),
        "public_benchmark_work_order_suite_threshold_count": _int(
            public_benchmark_work_order.get("suite_threshold_count")
        ),
        "public_benchmark_work_order_suite_materialization_manifest_count": _int(
            public_benchmark_work_order.get("suite_materialization_manifest_count")
        ),
        "public_benchmark_work_order_suite_scorecard_row_csv_count": _int(
            public_benchmark_work_order.get("suite_scorecard_row_csv_count")
        ),
        "public_benchmark_work_order_suite_no_external_dependency_count": _int(
            public_benchmark_work_order.get("suite_no_external_dependency_count")
        ),
        "public_benchmark_work_order_local_artifact_preflight_ready_suite_count": _int(
            public_benchmark_work_order.get("local_artifact_preflight_ready_suite_count")
        ),
        "public_benchmark_work_order_local_artifact_preflight_blocked_suite_count": _int(
            public_benchmark_work_order.get("local_artifact_preflight_blocked_suite_count")
        ),
        "public_benchmark_work_order_missing_local_input_artifact_count": _int(
            public_benchmark_work_order.get("missing_local_input_artifact_count")
        ),
        "public_benchmark_work_order_missing_local_output_artifact_count": _int(
            public_benchmark_work_order.get("missing_local_output_artifact_count")
        ),
        "public_benchmark_work_order_missing_local_input_artifacts": public_benchmark_work_order.get(
            "missing_local_input_artifacts"
        )
        or [],
        "public_benchmark_work_order_missing_local_output_artifacts": public_benchmark_work_order.get(
            "missing_local_output_artifacts"
        )
        or [],
        "public_benchmark_work_order_continuous_validation_command": _text(
            public_benchmark_work_order.get("continuous_validation_command")
        ),
        "commercial_independence_ready": commercial_ready,
        "commercial_dependency_provenance_manifest_present": _bool(commercial.get("dependency_provenance_manifest_present")),
        "commercial_requirements_lock_artifacts_present": _bool(commercial.get("requirements_lock_artifacts_present")),
        "commercial_reproducible_install_manifest_ready": _bool(commercial.get("reproducible_install_manifest_ready")),
        "commercial_dependency_provenance_git_short_commit": _text(
            commercial.get("dependency_provenance_git_short_commit")
        ),
        "commercial_dependency_provenance_requirements_lock_txt_sha256": _text(
            commercial.get("dependency_provenance_requirements_lock_txt_sha256")
        ),
        "cameo_local_surface_ready": cameo_local_surface_ready,
        "cameo_service_boundary_ready": cameo_service_boundary_ready,
        "cameo_service_boundary_status": _text(cameo_architecture.get("cameo_service_boundary_status")),
        "cameo_service_boundary_api_route_count": _int(cameo_architecture.get("cameo_service_boundary_api_route_count")),
        "cameo_service_boundary_cli_command_count": _int(cameo_architecture.get("cameo_service_boundary_cli_command_count")),
        "cameo_api_contract_ready": cameo_api_contract_ready,
        "cameo_api_contract_status": _text(cameo_architecture.get("cameo_api_contract_status")),
        "cameo_api_contract_expected_route_count": _int(cameo_architecture.get("cameo_api_contract_expected_route_count")),
        "cameo_api_contract_missing_route_count": _int(cameo_architecture.get("cameo_api_contract_missing_route_count")),
        "cameo_api_contract_status_response_missing_key_count": _int(
            cameo_architecture.get("cameo_api_contract_status_response_missing_key_count")
        ),
        "cameo_architecture_validation_protocol_ready": cameo_architecture_local_protocol_ready,
        "cameo_architecture_validation_ready": cameo_validation_ready,
        "cameo_official_validation_evidence_ready": cameo_official_evidence_ready,
        "cameo_official_results_status": _text(cameo_architecture.get("official_results_status")),
        "cameo_accepted_official_result_count": _int(cameo_architecture.get("accepted_official_result_count")),
        "cameo_model1_official_result_ready": _bool(cameo_architecture.get("model1_official_result_ready")),
        "cameo_operator_intake_csv": _text(cameo_architecture.get("operator_intake_csv")),
        "cameo_public_registration_status": _text(cameo_architecture.get("public_registration_status")),
        "cameo_public_registration_authorized": _bool(cameo_architecture.get("public_registration_authorized")),
        "cameo_receiver_smoke_ready": cameo_receiver_smoke_ready,
        "cameo_receiver_smoke_status": _text(cameo.get("source_receiver_smoke_status")),
        "cameo_api_dependency_ready": cameo_api_dependency_ready,
        "cameo_api_dependency_status": _text(cameo.get("source_api_dependency_status")),
        "cameo_public_registration_allowed": _bool(cameo.get("public_registration_allowed")),
        "cameo_public_registration_blocker_count": _int(cameo.get("public_registration_blocker_count")),
        "cameo_registration_approval_token_required": _text(cameo.get("registration_approval_token_required")),
        "cameo_outbound_email_approval_token_required": _text(cameo.get("outbound_email_approval_token_required")),
        "cameo_registration_approval_token_count": len(cameo_registration_tokens),
        "cameo_registration_approval_tokens_required": cameo_registration_tokens,
        "cleanup_control_surface_ready": cleanup_surface_ready,
        "cleanup_postcheck_contract_ready": cleanup_postcheck_ready,
        "cleanup_postcheck_row_count": _int(cleanup_postcheck.get("row_count")),
        "cleanup_postcheck_blocked_row_count": _int(cleanup_postcheck.get("blocked_row_count")),
        "cleanup_postcheck_global_refresh_command_count": _int(cleanup_postcheck.get("global_refresh_command_count")),
        "ligand_heavy_cleanup_preflight_ready": ligand_cleanup_ready,
        "cleanup_completion_ready": cleanup_completion_ready,
        "casp17_transition_surface_ready": casp17_transition_ready,
        "cleanup_execution_approved": cleanup_approved,
        "cleanup_reclaim_size_gb": _float(cleanup_approval.get("total_reclaim_size_gb")),
        "product_execution_authorized": product_execution_authorized,
        "delivery_ready_claim_allowed": delivery_ready_claim_allowed,
        "release_claim_allowed": architecture_release_ready,
        "release_allowed": release_allowed,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "cameo_submission_executed": False,
        "casp_submission_executed": False,
        "cleanup_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            (
                "Local architecture surfaces are connected; resolve commercial license/package blockers and optional CAMEO registration only if live validation is desired."
                if cleanup_completion_ready
                else "Local architecture surfaces are connected; resolve commercial license/package blockers, public benchmark scorecards, and cleanup approval gates."
            )
            if local_architecture_surface_ready
            else "Repair blocked local architecture and public benchmark surfaces before moving to release claims."
        ),
    }
    return {"summary": summary, "blockers": blockers, "approval_required": approval_required, "rows": rows}
