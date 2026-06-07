from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

CLAIM_BOUNDARY = (
    "CAMEO API contract only; it statically audits the local CAMEO validation API route and status surface. "
    "It does not start a server, register a CAMEO server, submit predictions, send email, fetch official results, "
    "use local native accuracy, or mutate external state."
)

EXPECTED_ROUTES = {
    "receive_cameo_target_post": ("POST", "/targets"),
    "receive_cameo_target_get": ("GET", "/targets"),
    "get_cameo_operations": ("GET", "/operations"),
    "get_cameo_architecture_validation": ("GET", "/architecture-validation"),
    "get_cameo_registration_approval": ("GET", "/registration-approval"),
    "get_cameo_official_results_status": ("GET", "/official-results"),
    "get_cameo_api_contract": ("GET", "/api-contract"),
    "get_cameo_service_boundary": ("GET", "/service-boundary"),
    "get_cameo_evidence_integrity": ("GET", "/evidence-integrity"),
}

EXPECTED_RESPONSE_MODEL_FIELDS = {
    "CameoIntakeResponse": {"job_id", "status", "message", "parsed_sequence_count", "capability_lane"},
}

REQUIRED_STATUS_RESPONSE_KEYS = {
    "status",
    "artifact_path",
    "prediction_generation_enabled",
    "outbound_email_enabled",
    "external_state_mutated",
    "claim_boundary",
}

REQUIRED_STATUS_DOMAIN_KEYS = {
    "get_cameo_operations": {
        "official_results_intake_status",
        "official_results_operator_template_csv",
        "official_results_operator_intake_csv",
        "official_results_required_columns",
        "official_results_missing_required_columns",
        "official_results_blocker_count",
        "official_results_blocker_codes",
        "evidence_integrity_status",
        "evidence_integrity_ready",
        "evidence_integrity_blocker_count",
        "official_results_pending_honest",
        "no_local_native_accuracy_substitution",
        "external_mutation_flags_clear",
        "registration_gate_status",
        "registration_operator_approval_csv",
        "registration_approval_token_required",
        "outbound_email_approval_token_required",
        "receiver_smoke_status",
        "api_dependency_status",
        "server_registration_mutated",
        "native_local_accuracy_used",
    },
    "get_cameo_architecture_validation": {
        "cameo_architecture_validation_ready",
        "official_results_gate_status",
        "official_model1_result_ready",
        "official_results_operator_intake_csv",
        "official_results_missing_required_columns",
        "official_results_blocker_count",
        "official_results_blocker_codes",
        "official_cameo_results_used",
        "public_registration_authorized",
        "server_registration_mutated",
        "native_local_accuracy_used",
    },
    "get_cameo_registration_approval": {
        "authorized_for_registration_review",
        "registration_approval_token_required",
        "outbound_email_approval_token_required",
        "server_registration_mutated",
        "prediction_generation_enabled",
    },
    "get_cameo_official_results_status": {
        "model1_official_result_ready",
        "operator_template_csv",
        "operator_intake_csv",
        "blocker_count",
        "blocker_codes",
        "required_columns",
        "missing_required_columns",
        "official_metric_columns",
        "disallowed_local_accuracy_columns",
        "official_cameo_results_used",
        "native_local_accuracy_used",
    },
    "get_cameo_service_boundary": {
        "service_boundary_ready",
        "api_route_count",
        "expected_api_route_count",
        "cli_command_count",
        "expected_cli_command_count",
        "artifact_registry_mismatch_count",
        "console_script_ready",
        "server_registration_mutated",
        "prediction_generation_enabled",
    },
    "get_cameo_evidence_integrity": {
        "evidence_integrity_ready",
        "official_result_provenance_honest",
        "official_result_schema_visible",
        "official_results_pending_honest",
        "no_local_native_accuracy_substitution",
        "external_mutation_flags_clear",
        "registration_and_email_gated",
        "local_protocol_connected",
        "official_results_fetched",
        "native_local_accuracy_used",
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
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
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
    path = root / "api" / "cameo.py"
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


def build_cameo_api_contract(*, root: str | Path = ".") -> dict[str, Any]:
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
        for model, expected in EXPECTED_RESPONSE_MODEL_FIELDS.items()
        for field in expected - model_fields.get(model, set())
    )

    status_function_names = [
        name
        for name in EXPECTED_ROUTES
        if name.startswith("get_cameo_") and name not in {"get_cameo_api_contract"}
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
    api_contract_keys = _literal_return_keys(functions.get("get_cameo_api_contract"))
    api_contract_missing = sorted(
        {
            "status",
            "api_contract_ready",
            "check_count",
            "blocker_count",
            "server_started",
            "prediction_generation_enabled",
            "outbound_email_enabled",
            "external_state_mutated",
            "claim_boundary",
        }
        - api_contract_keys
    )

    rows = [
        _row(
            check="cameo_api_routes_declared",
            status="pass" if tree is not None and not missing_routes else "fail",
            observed=f"missing={','.join(missing_routes) or 'none'}",
            required="all expected CAMEO API functions use the expected HTTP method and route path",
            artifact_path="api/cameo.py",
            reason="CAMEO validation needs stable routes for target intake, operations, official evidence, registration approval, and API contract status.",
        ),
        _row(
            check="cameo_intake_response_model_declared",
            status="pass" if not missing_model_fields else "fail",
            observed=f"missing={','.join(missing_model_fields) or 'none'}",
            required="CameoIntakeResponse exposes the expected fail-closed intake response fields",
            artifact_path="api/cameo.py",
            reason="CAMEO target intake must return a durable fail-closed schema without implying prediction generation.",
        ),
        _row(
            check="cameo_status_response_safety_flags",
            status="pass" if not status_missing and not api_contract_missing else "fail",
            observed=(
                f"status_missing={','.join(status_missing) or 'none'};"
                f"api_contract_missing={','.join(api_contract_missing) or 'none'}"
            ),
            required="read-only CAMEO status responses expose disabled prediction/email/external-mutation flags",
            artifact_path="api/cameo.py",
            reason="CAMEO status endpoints must make non-execution, non-registration, and non-email boundaries explicit.",
        ),
        _row(
            check="cameo_status_response_domain_keys",
            status="pass" if not domain_status_missing else "fail",
            observed=f"missing={','.join(domain_status_missing) or 'none'}",
            required="operations, architecture-validation, official-results, and registration endpoints expose official evidence and registration handoff keys",
            artifact_path="api/cameo.py",
            reason="Architecture validation needs stable fields for official CAMEO evidence, receiver smoke, API dependency, and public registration approval state.",
        ),
    ]
    blockers = [_blocker(row) for row in rows if row["status"] != "pass"]
    api_contract_ready = not blockers
    summary = {
        "packet_type": "cameo_api_contract",
        "status": "cameo_api_contract_ready" if api_contract_ready else "blocked_cameo_api_contract",
        "api_contract_ready": api_contract_ready,
        "check_count": len(rows),
        "pass_count": sum(1 for row in rows if row["status"] == "pass"),
        "blocker_count": len(blockers),
        "expected_route_count": len(EXPECTED_ROUTES),
        "missing_route_count": len(missing_routes),
        "response_model_count": len(EXPECTED_RESPONSE_MODEL_FIELDS),
        "missing_response_model_field_count": len(missing_model_fields),
        "status_response_missing_key_count": len(status_missing) + len(api_contract_missing) + len(domain_status_missing),
        "status_response_domain_missing_key_count": len(domain_status_missing),
        "server_started": False,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "CAMEO API contract is ready; architecture validation still depends on official CAMEO results and registration approval gates."
            if api_contract_ready
            else "Repair blocked CAMEO API contract rows before treating the CAMEO validation API as handoff-ready."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}
