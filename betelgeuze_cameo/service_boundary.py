from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from betelgeuze_cameo.cli import ARTIFACTS as CAMEO_CLI_ARTIFACTS
from betelgeuze_product.commercial_independence import _read_pyproject_metadata

CLAIM_BOUNDARY = (
    "CAMEO service boundary contract only; it audits local CAMEO API routes, CLI commands, console script metadata, "
    "and artifact registry coherence. It does not start a server, register a CAMEO server, submit predictions, send "
    "email, fetch official results, use local native accuracy, or mutate external state."
)

EXPECTED_API_ROUTES = {
    ("POST", "/targets"),
    ("GET", "/targets"),
    ("GET", "/operations"),
    ("GET", "/architecture-validation"),
    ("GET", "/official-results"),
    ("GET", "/registration-approval"),
    ("GET", "/api-contract"),
    ("GET", "/service-boundary"),
    ("GET", "/evidence-integrity"),
}

EXPECTED_CLI_COMMANDS = {
    "operator-inputs",
    "repair-preflight",
    "readiness",
    "official-results",
    "performance",
    "runtime",
    "receiver-smoke",
    "capability",
    "operations",
    "architecture",
    "api-contract",
    "service-boundary",
    "evidence-integrity",
    "registration-approval",
}

EXPECTED_CONSOLE_SCRIPT = {"betelgeuze-cameo": "betelgeuze_cameo.cli:main"}
EXPECTED_ARTIFACTS = {
    "operator-inputs": "runs/cameo_operator_input_validation_current.json",
    "repair-preflight": "runs/cameo_repair_execution_preflight_current.json",
    "readiness": "runs/cameo_validation_readiness_gate_current.json",
    "official-results": "runs/cameo_official_results_intake_gate_current.json",
    "performance": "runs/cameo_performance_scorecard_current.json",
    "runtime": "runs/cameo_api_dependency_readiness_current.json",
    "receiver-smoke": "runs/cameo_receiver_smoke_contract_current.json",
    "capability": "runs/cameo_capability_preflight_current.json",
    "operations": "runs/cameo_validation_operations_dossier_current.json",
    "architecture": "runs/cameo_architecture_validation_contract_current.json",
    "api-contract": "runs/cameo_api_contract_current.json",
    "service-boundary": "runs/cameo_service_boundary_contract_current.json",
    "evidence-integrity": "runs/cameo_evidence_integrity_contract_current.json",
    "registration-approval": "runs/cameo_public_registration_approval_gate_current.json",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _route_decorators(root: Path, rel_path: str) -> set[tuple[str, str]]:
    path = root / rel_path
    if not path.is_file():
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    routes: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr not in {"get", "post"}:
                continue
            if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                continue
            route_path = decorator.args[0].value
            if isinstance(route_path, str):
                routes.add((func.attr.upper(), route_path))
    return routes


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
        "release_blocker": status != "pass",
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


def build_cameo_service_boundary_contract(*, root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    api_routes = _route_decorators(root_path, "api/cameo.py")
    api_missing = sorted(EXPECTED_API_ROUTES - api_routes)
    api_extra = sorted(route for route in api_routes if route[1].startswith("/") and route not in EXPECTED_API_ROUTES)

    cli_commands = set(CAMEO_CLI_ARTIFACTS)
    cli_missing = sorted(EXPECTED_CLI_COMMANDS - cli_commands)
    artifact_mismatches = sorted(
        command
        for command, expected_path in EXPECTED_ARTIFACTS.items()
        if _text(CAMEO_CLI_ARTIFACTS.get(command)) != expected_path
    )

    pyproject = _read_pyproject_metadata(root_path / "pyproject.toml")
    scripts = pyproject["scripts"]
    console_missing = sorted(
        name for name, target in EXPECTED_CONSOLE_SCRIPT.items() if _text(scripts.get(name)) != target
    )

    rows = [
        _row(
            check="cameo_api_route_surface",
            status="pass" if not api_missing else "fail",
            observed=(
                f"route_count={len(api_routes)};"
                f"missing={','.join(f'{method} {path}' for method, path in api_missing) or 'none'};"
                f"extra={','.join(f'{method} {path}' for method, path in api_extra) or 'none'}"
            ),
            required="all expected CAMEO intake and read-only status routes are declared",
            artifact_path="api/cameo.py",
            reason="CAMEO validation must expose a coherent local API boundary for intake, operations, official results, registration approval, API contract, and service-boundary status.",
        ),
        _row(
            check="cameo_cli_command_surface",
            status="pass" if not cli_missing else "fail",
            observed=f"command_count={len(cli_commands)};missing={','.join(cli_missing) or 'none'}",
            required="all expected CAMEO status commands are registered in betelgeuze_cameo.cli.ARTIFACTS",
            artifact_path="betelgeuze_cameo/cli.py",
            reason="CAMEO operators need CLI access to the same local validation surfaces used by API and release gates.",
        ),
        _row(
            check="cameo_cli_artifact_registry",
            status="pass" if not artifact_mismatches else "fail",
            observed=f"mismatched={','.join(artifact_mismatches) or 'none'}",
            required="CAMEO CLI commands map to the expected local runs/ artifacts",
            artifact_path="betelgeuze_cameo/cli.py;runs/cameo_service_boundary_contract_current.json",
            reason="Service operators need stable artifact paths for every CAMEO validation status command.",
        ),
        _row(
            check="cameo_console_script_target",
            status="pass" if not console_missing else "fail",
            observed=f"missing_or_mismatched={','.join(console_missing) or 'none'}",
            required="pyproject exposes betelgeuze-cameo = betelgeuze_cameo.cli:main",
            artifact_path="pyproject.toml;betelgeuze_cameo/cli.py",
            reason="Commercial package metadata must preserve the CAMEO command-line entry point.",
        ),
    ]
    blockers = [_blocker(row) for row in rows if row["status"] != "pass"]
    service_boundary_ready = not blockers
    summary = {
        "packet_type": "cameo_service_boundary_contract",
        "status": "cameo_service_boundary_contract_ready" if service_boundary_ready else "blocked_cameo_service_boundary_contract",
        "service_boundary_ready": service_boundary_ready,
        "check_count": len(rows),
        "pass_count": sum(1 for row in rows if row["status"] == "pass"),
        "blocker_count": len(blockers),
        "api_route_count": len(api_routes),
        "expected_api_route_count": len(EXPECTED_API_ROUTES),
        "missing_api_route_count": len(api_missing),
        "cli_command_count": len(cli_commands),
        "expected_cli_command_count": len(EXPECTED_CLI_COMMANDS),
        "missing_cli_command_count": len(cli_missing),
        "artifact_registry_mismatch_count": len(artifact_mismatches),
        "console_script_ready": not console_missing,
        "server_started": False,
        "server_registration_mutated": False,
        "prediction_generation_enabled": False,
        "outbound_email_enabled": False,
        "official_results_fetched": False,
        "native_local_accuracy_used": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "CAMEO service boundary is ready; architecture validation still depends on official results and public registration approval."
            if service_boundary_ready
            else "Repair blocked CAMEO service-boundary rows before treating the CAMEO validation service as handoff-ready."
        ),
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}
