from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from betelgeuze_product.cli import ARTIFACTS as PRODUCT_CLI_ARTIFACTS
from betelgeuze_product.commercial_independence import _read_pyproject_metadata

CLAIM_BOUNDARY = (
    "Product service boundary contract only; it audits local API routes, CLI commands, console script metadata, and "
    "artifact registry coherence for the product status surface. It does not run docking, assemble bundles, choose or "
    "write a license, submit CAMEO/CASP predictions, delete data, upload, or mutate external state."
)

EXPECTED_API_ROUTES = {
    ("POST", "/docking/jobs"),
    ("GET", "/docking/jobs/{job_id}"),
    ("POST", "/structure/analyze"),
    ("GET", "/capabilities"),
    ("GET", "/architecture"),
    ("GET", "/service-boundary"),
    ("GET", "/api-contract"),
    ("GET", "/operational-quality"),
    ("GET", "/operations"),
    ("GET", "/license-decision"),
    ("GET", "/license-options"),
    ("GET", "/license-file-work-order"),
    ("GET", "/commercial-independence"),
    ("GET", "/release-readiness"),
}

EXPECTED_CLI_COMMANDS = {
    "capabilities",
    "architecture",
    "service-boundary",
    "api-contract",
    "operational-quality",
    "operations",
    "commercial-independence",
    "license-decision",
    "license-options",
    "license-file-work-order",
    "release-readiness",
}

EXPECTED_CONSOLE_SCRIPT = {"betelgeuze-product": "betelgeuze_product.cli:main"}
EXPECTED_ARTIFACTS = {
    "capabilities": "runs/product_capability_surface_contract_current.json",
    "architecture": "runs/product_architecture_contract_current.json",
    "service-boundary": "runs/product_service_boundary_contract_current.json",
    "api-contract": "runs/product_api_contract_current.json",
    "operational-quality": "runs/product_operational_quality_contract_current.json",
    "operations": "runs/product_release_operations_dossier_current.json",
    "commercial-independence": "runs/product_commercial_independence_gate_current.json",
    "license-decision": "runs/product_license_decision_gate_current.json",
    "license-options": "runs/product_license_decision_packet_current.json",
    "license-file-work-order": "runs/product_license_file_creation_work_order_current.json",
    "release-readiness": "runs/product_release_operations_dossier_current.json",
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


def build_product_service_boundary_contract(*, root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    api_routes = _route_decorators(root_path, "api/product.py")
    api_missing = sorted(EXPECTED_API_ROUTES - api_routes)
    api_extra = sorted(route for route in api_routes if route[1].startswith("/") and route not in EXPECTED_API_ROUTES)

    cli_commands = set(PRODUCT_CLI_ARTIFACTS)
    cli_missing = sorted(EXPECTED_CLI_COMMANDS - cli_commands)
    artifact_mismatches = sorted(
        command
        for command, expected_path in EXPECTED_ARTIFACTS.items()
        if _text(PRODUCT_CLI_ARTIFACTS.get(command)) != expected_path
    )

    pyproject = _read_pyproject_metadata(root_path / "pyproject.toml")
    scripts = pyproject["scripts"]
    console_missing = sorted(
        name for name, target in EXPECTED_CONSOLE_SCRIPT.items() if _text(scripts.get(name)) != target
    )

    rows = [
        _row(
            check="product_api_route_surface",
            status="pass" if not api_missing else "fail",
            observed=(
                f"route_count={len(api_routes)};"
                f"missing={','.join(f'{method} {path}' for method, path in api_missing) or 'none'};"
                f"extra={','.join(f'{method} {path}' for method, path in api_extra) or 'none'}"
            ),
            required="all expected read-only product status routes plus guarded structure/docking intake routes",
            artifact_path="api/product.py",
            reason="A standalone product must expose a coherent API status boundary for capabilities, architecture, operations, licensing, service-boundary, and release readiness.",
        ),
        _row(
            check="product_cli_command_surface",
            status="pass" if not cli_missing else "fail",
            observed=f"command_count={len(cli_commands)};missing={','.join(cli_missing) or 'none'}",
            required="all expected product status commands are registered in betelgeuze_product.cli.ARTIFACTS",
            artifact_path="betelgeuze_product/cli.py",
            reason="The product CLI must expose the same local status surfaces used by the API and package metadata.",
        ),
        _row(
            check="product_cli_artifact_registry",
            status="pass" if not artifact_mismatches else "fail",
            observed=f"mismatched={','.join(artifact_mismatches) or 'none'}",
            required="CLI commands map to the expected local runs/ artifacts",
            artifact_path="betelgeuze_product/cli.py;runs/product_service_boundary_contract_current.json",
            reason="Service operators need stable artifact paths for every product status command.",
        ),
        _row(
            check="product_console_script_target",
            status="pass" if not console_missing else "fail",
            observed=f"missing_or_mismatched={','.join(console_missing) or 'none'}",
            required="pyproject exposes betelgeuze-product = betelgeuze_product.cli:main",
            artifact_path="pyproject.toml;betelgeuze_product/cli.py",
            reason="Commercial package metadata must preserve the product command-line entry point.",
        ),
    ]
    blockers = [_blocker(row) for row in rows if row["status"] != "pass"]
    service_boundary_ready = not blockers
    summary = {
        "packet_type": "product_service_boundary_contract",
        "status": "product_service_boundary_contract_ready" if service_boundary_ready else "blocked_product_service_boundary_contract",
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
        "execution_enabled": False,
        "docking_results_emitted": False,
        "license_file_written": False,
        "bundle_assembled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": "Service boundary is ready; release still depends on license, approved execution, CAMEO evidence, and cleanup approvals.",
    }
    return {"summary": summary, "rows": rows, "blockers": blockers}
