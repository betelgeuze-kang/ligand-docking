from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

CLAIM_BOUNDARY = (
    "Product API contract only; it statically audits the local product API route and schema surface for commercial "
    "handoff. It does not start a server, run docking, write licenses, assemble bundles, upload, or mutate external "
    "state."
)

EXPECTED_ROUTES = {
    "submit_docking_job": ("POST", "/docking/jobs"),
    "get_docking_job": ("GET", "/docking/jobs/{job_id}"),
    "analyze_product_structure": ("POST", "/structure/analyze"),
    "get_product_capabilities": ("GET", "/capabilities"),
    "get_product_architecture": ("GET", "/architecture"),
    "get_product_service_boundary": ("GET", "/service-boundary"),
    "get_product_api_contract": ("GET", "/api-contract"),
    "get_product_operational_quality": ("GET", "/operational-quality"),
    "get_product_public_benchmark": ("GET", "/public-benchmark"),
    "get_product_cameo_live_validation": ("GET", "/cameo-live-validation"),
    "get_product_operations": ("GET", "/operations"),
    "get_product_license_decision": ("GET", "/license-decision"),
    "get_product_license_options": ("GET", "/license-options"),
    "get_product_license_file_work_order": ("GET", "/license-file-work-order"),
    "get_product_commercial_independence": ("GET", "/commercial-independence"),
    "get_product_release_readiness": ("GET", "/release-readiness"),
}

EXPECTED_MODEL_FIELDS = {
    "LigandInput": {"ligand_id", "smiles", "sdf_path", "mol2_path", "pdbqt_path", "inchi", "compound_id"},
    "DockingJobRequest": {
        "request_type",
        "family",
        "target_id",
        "target_name",
        "pdb_id",
        "pdb_path",
        "pdb_content",
        "mmcif_path",
        "mmcif_content",
        "ligands",
        "metadata",
    },
    "StructureAnalysisRequest": {"pdb_id", "pdb_path", "pdb_content", "mmcif_path", "mmcif_content"},
}

REQUIRED_DOCKING_RESPONSE_KEYS = {
    "job_id",
    "status",
    "validation_status",
    "blocker_count",
    "warning_count",
    "structure_analysis_status",
    "structure_source_available",
    "structure_atom_count",
    "structure_chain_count",
    "structure_ligand_like_residue_count",
    "execution_enabled",
    "docking_results_emitted",
    "ledger_path",
    "claim_boundary",
}

REQUIRED_STATUS_RESPONSE_KEYS = {
    "status",
    "artifact_path",
    "execution_enabled",
    "docking_results_emitted",
    "external_state_mutated",
    "claim_boundary",
}

REQUIRED_STATUS_DOMAIN_KEYS = {
    "get_product_architecture": {
        "architecture_release_ready",
        "lane_count",
        "product_service_boundary_ready",
        "product_api_contract_ready",
        "cameo_service_boundary_ready",
        "cameo_service_boundary_status",
        "cameo_api_contract_ready",
        "cameo_api_contract_status",
        "cleanup_postcheck_contract_ready",
        "cleanup_postcheck_blocked_row_count",
    },
    "get_product_operations": {
        "architecture_contract_ready",
        "architecture_local_surface_ready",
        "architecture_release_ready",
        "architecture_blocked_lane_count",
        "architecture_approval_required_lane_count",
        "operational_quality_ready",
        "source_operational_quality_status",
        "operational_quality_blocker_count",
        "product_service_boundary_ready",
        "product_api_contract_ready",
        "public_benchmark_work_order_status",
        "public_benchmark_work_order_artifact",
        "public_benchmark_work_order_open_suite_count",
        "public_benchmark_work_order_materialization_required_suite_count",
        "public_benchmark_work_order_scorecard_required_suite_count",
        "public_benchmark_work_order_continuous_validation_command_count",
        "public_benchmark_work_order_continuous_validation_command",
        "public_benchmark_work_order_suite_run_command_count",
        "public_benchmark_work_order_suite_threshold_count",
        "public_benchmark_work_order_suite_materialization_manifest_count",
        "public_benchmark_work_order_suite_scorecard_row_csv_count",
        "public_benchmark_work_order_suite_no_external_dependency_count",
        "cleanup_postcheck_contract_ready",
        "blocked_stage_count",
        "approval_required_stage_count",
        "approval_token_count",
        "approval_tokens_required",
        "stages",
        "execution_approval_token_required",
        "license_file_creation_work_order_status",
        "license_file_creation_review_ready",
        "source_license_file_creation_work_order_status",
        "license_file_creation_work_order_blocker_count",
        "license_file_creation_work_order_artifact",
    },
    "get_product_public_benchmark": {
        "public_benchmark_validation_ready",
        "open_suite_count",
        "materialization_required_suite_count",
        "scorecard_required_suite_count",
        "continuous_validation_command_count",
        "continuous_validation_command",
        "suite_run_command_count",
        "suite_threshold_count",
        "suite_materialization_manifest_count",
        "suite_scorecard_row_csv_count",
        "suite_required_output_count",
        "suite_no_external_dependency_count",
        "requires_24h_server",
        "requires_competition_season",
        "requires_paid_vps",
        "suites",
    },
    "get_product_cameo_live_validation": {
        "validation_ready",
        "validation_readiness_status",
        "official_result_required",
        "official_results_intake_ready",
        "official_results_intake_status",
        "official_results_intake_blocker_count",
        "official_results_gate_status",
        "official_results_result_row_count",
        "official_results_accepted_count",
        "official_results_rejected_count",
        "official_results_blocker_codes",
        "official_results_operator_template_csv",
        "official_results_operator_intake_csv",
        "official_results_required_columns",
        "official_results_missing_required_columns",
        "official_results_metric_columns",
        "official_model1_result_ready",
        "official_cameo_results_used",
        "official_results_pending_honest",
        "receiver_smoke_status",
        "api_dependency_status",
        "evidence_integrity_ready",
        "public_registration_allowed",
        "registration_gate_status",
        "registration_authorized_for_review",
        "registration_operator_template_csv",
        "registration_operator_approval_csv",
        "registration_blocker_count",
        "registration_blockers",
        "registration_approval_token_required",
        "outbound_email_approval_token_required",
        "approval_tokens_required",
        "next_required_step",
        "stages",
        "server_started",
        "outbound_email_enabled",
        "server_registration_mutated",
    },
    "get_product_commercial_independence": {
        "commercial_independent_product_claim_allowed",
        "license_decision_status",
        "license_decision_packet_status",
        "license_decision_packet_ready",
        "license_decision_option_count",
        "license_file_creation_work_order_status",
        "license_file_creation_review_ready",
        "source_license_file_creation_work_order_status",
        "license_file_creation_work_order_blocker_count",
        "license_file_creation_work_order_artifact",
        "operator_template_csv",
        "operator_intake_csv",
        "required_fields",
        "required_decision",
        "approval_token_required",
        "license_file_written",
    },
    "get_product_release_readiness": {
        "product_architecture_status",
        "product_architecture_release_ready",
        "operational_quality_ready",
        "source_operational_quality_status",
        "operational_quality_blocker_count",
        "product_architecture_cleanup_postcheck_ready",
        "public_benchmark_work_order_status",
        "public_benchmark_work_order_artifact",
        "public_benchmark_work_order_open_suite_count",
        "public_benchmark_work_order_materialization_required_suite_count",
        "public_benchmark_work_order_scorecard_required_suite_count",
        "public_benchmark_work_order_continuous_validation_command_count",
        "public_benchmark_work_order_continuous_validation_command",
        "public_benchmark_work_order_suite_run_command_count",
        "public_benchmark_work_order_suite_threshold_count",
        "public_benchmark_work_order_suite_materialization_manifest_count",
        "public_benchmark_work_order_suite_scorecard_row_csv_count",
        "public_benchmark_work_order_suite_no_external_dependency_count",
        "commercial_independence_status",
        "commercial_independent_product_ready",
        "license_present",
        "license_decision_status",
        "license_decision_packet_status",
        "license_decision_packet_ready",
        "license_decision_option_count",
        "license_file_creation_work_order_status",
        "license_file_creation_review_ready",
        "source_license_file_creation_work_order_status",
        "license_file_creation_work_order_blocker_count",
        "license_file_creation_work_order_artifact",
        "license_operator_template_csv",
        "license_operator_intake_csv",
        "license_required_fields",
        "license_required_decision",
        "license_approval_token_required",
        "license_file_written",
        "blocked_stage_count",
        "approval_required_stage_count",
    },
    "get_product_license_file_work_order": {
        "license_file_creation_review_ready",
        "approval_token_required",
        "target_license_path",
        "license_review_manifest_ready",
        "license_review_manifest",
        "license_review_manifest_fingerprint_sha256",
        "license_decision_gate_status",
        "authorized_for_license_file_creation_review",
        "commercial_gate_only_license_blocked",
        "license_file_written",
        "work_items",
    },
    "get_product_operational_quality": {
        "operational_quality_ready",
        "fail_closed_docking_intake_ready",
        "ledger_payload_privacy_ready",
        "request_traceability_ready",
        "scope_limit_enforcement_ready",
        "heavy_artifact_policy_ready",
        "input_payload_persisted",
        "checks",
    },
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _row(
    *,
    check: str,
    status: str,
    observed: str,
    required: str,
    artifact_path: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "check": check,
        "status": status,
        "observed": observed,
        "required": required,
        "artifact_path": artifact_path,
        "reason": reason,
        "server_started": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
    }


def _blocker(row: dict[str, Any]) -> dict[str, str]:
    return {
        "code": f"{row['check']}_not_ready",
        "severity": "hard",
        "check": _text(row["check"]),
        "reason": f"{row['reason']} Observed: {row['observed']}; required: {row['required']}.",
    }


def _parse_api(root: Path) -> ast.Module | None:
    path = root / "api" / "product.py"
    if not path.is_file():
        return None
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None


def _function_nodes(tree: ast.Module | None) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    if tree is None:
        return {}
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _route_for(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, str] | None:
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        if decorator.func.attr not in {"get", "post"}:
            continue
        if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
            return decorator.func.attr.upper(), decorator.args[0].value
    return None


def _model_fields(tree: ast.Module | None) -> dict[str, set[str]]:
    if tree is None:
        return {}
    fields: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(getattr(base, "id", "") == "BaseModel" for base in node.bases):
            continue
        names: set[str] = set()
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                names.add(stmt.target.id)
        fields[node.name] = names
    return fields


def _literal_return_keys(node: ast.FunctionDef | ast.AsyncFunctionDef | None) -> set[str]:
    if node is None:
        return set()
    keys: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Return):
            continue
        value = child.value
        if isinstance(value, ast.Dict):
            for key in value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return keys


def build_product_api_contract(*, root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    tree = _parse_api(root_path)
    functions = _function_nodes(tree)
    routes = {name: _route_for(functions[name]) for name in functions}
    missing_routes = sorted(
        f"{method} {path}" for name, (method, path) in EXPECTED_ROUTES.items() if routes.get(name) != (method, path)
    )

    model_fields = _model_fields(tree)
    missing_model_fields = sorted(
        f"{model}.{field}"
        for model, expected in EXPECTED_MODEL_FIELDS.items()
        for field in expected - model_fields.get(model, set())
    )

    docking_keys = _literal_return_keys(functions.get("submit_docking_job"))
    docking_missing = sorted(REQUIRED_DOCKING_RESPONSE_KEYS - docking_keys)
    status_function_names = [
        name
        for name in EXPECTED_ROUTES
        if name.startswith("get_product_") and name not in {"get_product_api_contract"}
    ]
    status_missing = sorted(
        f"{name}.{key}"
        for name in status_function_names
        for key in REQUIRED_STATUS_RESPONSE_KEYS - _literal_return_keys(functions.get(name))
    )
    domain_status_missing = sorted(
        f"{name}.{key}"
        for name, required_keys in REQUIRED_STATUS_DOMAIN_KEYS.items()
        for key in required_keys - _literal_return_keys(functions.get(name))
    )
    api_contract_keys = _literal_return_keys(functions.get("get_product_api_contract"))
    api_contract_missing = sorted(
        {"status", "api_contract_ready", "check_count", "blocker_count", "execution_enabled", "external_state_mutated", "claim_boundary"}
        - api_contract_keys
    )

    rows = [
        _row(
            check="product_api_routes_declared",
            status="pass" if tree is not None and not missing_routes else "fail",
            observed=f"missing={','.join(missing_routes) or 'none'}",
            required="all expected product API functions use the expected HTTP method and route path",
            artifact_path="api/product.py",
            reason="Commercial API consumers need stable route paths for structure analysis, docking intake, and read-only product status.",
        ),
        _row(
            check="product_api_request_models_declared",
            status="pass" if not missing_model_fields else "fail",
            observed=f"missing={','.join(missing_model_fields) or 'none'}",
            required="LigandInput, DockingJobRequest, and StructureAnalysisRequest expose the expected fields",
            artifact_path="api/product.py",
            reason="The product API needs a durable request schema for customer integration and local smoke validation.",
        ),
        _row(
            check="product_docking_response_contract",
            status="pass" if not docking_missing else "fail",
            observed=f"missing={','.join(docking_missing) or 'none'}",
            required="docking intake response includes job, validation, structure-analysis, ledger, and disabled-execution flags",
            artifact_path="api/product.py",
            reason="Docking intake must return an auditable queued/blocked record without pretending to emit scientific results.",
        ),
        _row(
            check="product_status_response_safety_flags",
            status="pass" if not status_missing and not api_contract_missing else "fail",
            observed=(
                f"status_missing={','.join(status_missing) or 'none'};"
                f"api_contract_missing={','.join(api_contract_missing) or 'none'}"
            ),
            required="read-only product status responses expose artifact/status plus disabled execution and external-mutation flags",
            artifact_path="api/product.py",
            reason="Commercial status endpoints must fail closed and make non-execution/non-mutation explicit.",
        ),
        _row(
            check="product_status_response_domain_keys",
            status="pass" if not domain_status_missing else "fail",
            observed=f"missing={','.join(domain_status_missing) or 'none'}",
            required="architecture, operations, and release-readiness endpoints expose product-architecture and cleanup-postcheck handoff keys",
            artifact_path="api/product.py",
            reason="Commercial API consumers need stable domain fields for architecture status, release operations, and cleanup postcheck evidence.",
        ),
    ]
    blockers = [_blocker(row) for row in rows if row["status"] != "pass"]
    api_contract_ready = not blockers
    summary = {
        "packet_type": "product_api_contract",
        "status": "product_api_contract_ready" if api_contract_ready else "blocked_product_api_contract",
        "api_contract_ready": api_contract_ready,
        "check_count": len(rows),
        "pass_count": sum(1 for row in rows if row["status"] == "pass"),
        "blocker_count": len(blockers),
        "expected_route_count": len(EXPECTED_ROUTES),
        "missing_route_count": len(missing_routes),
        "request_model_count": len(EXPECTED_MODEL_FIELDS),
        "missing_request_model_field_count": len(missing_model_fields),
        "docking_response_missing_key_count": len(docking_missing),
        "status_response_missing_key_count": len(status_missing) + len(api_contract_missing) + len(domain_status_missing),
        "status_response_domain_missing_key_count": len(domain_status_missing),
        "server_started": False,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Product API contract is ready; release still depends on license approval, approved execution, CAMEO evidence, and cleanup gates."
            if api_contract_ready
            else "Repair blocked API contract rows before treating the product API as commercially handoff-ready."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}
