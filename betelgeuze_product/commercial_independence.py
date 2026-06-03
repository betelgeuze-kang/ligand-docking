from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

CLAIM_BOUNDARY = (
    "Product commercial-independence gate only; it audits repository packaging, dependency, license, and "
    "deployment evidence from local files. It does not install packages, run docking, assemble bundles, emit "
    "customer-facing claims, upload, register, send email, delete data, or mutate external state."
)

RUNTIME_REQUIREMENTS = "requirements.txt"
OPTIONAL_REQUIREMENTS = (
    "requirements-api.txt",
    "requirements-deploy.txt",
    "requirements-optional.txt",
    "requirements-train.txt",
)
LICENSE_CANDIDATES = ("LICENSE", "LICENSE.md", "LICENSE.txt")
DEPLOYMENT_CANDIDATES = ("Dockerfile", "Dockerfile.product", "requirements-deploy.txt")
EXTERNAL_API_RUNTIME_DEPENDENCIES = {"openai"}
NON_CORE_RUNTIME_DEPENDENCIES = {"fastapi", "uvicorn", "mlflow", "optuna", "torch-geometric", "gputil"}
REQUIRED_CONSOLE_SCRIPTS = {
    "betelgeuze-product": "betelgeuze_product.cli:main",
    "betelgeuze-cameo": "betelgeuze_cameo.cli:main",
    "betelgeuze-cleanup": "betelgeuze_cleanup.cli:main",
}
REQUIRED_PACKAGE_PATTERNS = ("betelgeuze_product*", "betelgeuze_cameo*", "betelgeuze_cleanup*")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _row(check: str, passed: bool, observed: str, required: str, artifact_path: str, reason: str) -> dict[str, Any]:
    return {
        "check": check,
        "status": "pass" if passed else "fail",
        "observed": observed,
        "required": required,
        "artifact_path": artifact_path,
        "reason": reason,
        "release_blocker": not passed,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "outbound_email_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
    }


def _blocker(row: dict[str, Any]) -> dict[str, str]:
    return {
        "code": f"{row['check']}_not_ready",
        "severity": "hard",
        "check": _text(row["check"]),
        "reason": f"{row['reason']} Observed: {row['observed']}; required: {row['required']}.",
    }


def _read_requirement_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def _requirement_name(line: str) -> str:
    if line.startswith("-r "):
        return "-r"
    for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "[", ";", " @ "):
        if sep in line:
            return line.split(sep, 1)[0].strip().lower()
    return line.strip().lower()


def _is_pinned_runtime_requirement(line: str) -> bool:
    if line.startswith(("-r ", "--")):
        return False
    return "==" in line or " @ " in line


def _read_pyproject_metadata(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"project": {}, "scripts": {}, "package_includes": ()}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"project": {}, "scripts": {}, "package_includes": ()}

    project: dict[str, str] = {}
    scripts: dict[str, str] = {}
    includes: list[str] = []
    section = ""
    collecting_include = False
    include_chunks: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.strip("[]")
            collecting_include = False
            include_chunks = []
            continue
        if collecting_include:
            include_chunks.append(line)
            if "]" in line:
                includes = re.findall(r'"([^"]+)"', " ".join(include_chunks))
                collecting_include = False
            continue
        if section == "project" and "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            if key in {"name", "version", "requires-python"}:
                matches = re.findall(r'"([^"]*)"', value)
                project[key] = matches[0] if matches else value.strip()
        elif section == "project.scripts" and "=" in line:
            key, value = line.split("=", 1)
            matches = re.findall(r'"([^"]*)"', value)
            scripts[key.strip()] = matches[0] if matches else value.strip()
        elif section == "tool.setuptools.packages.find" and line.startswith("include") and "=" in line:
            _, value = line.split("=", 1)
            include_chunks = [value.strip()]
            if "]" in value:
                includes = re.findall(r'"([^"]+)"', value)
            else:
                collecting_include = True
    return {"project": project, "scripts": scripts, "package_includes": tuple(includes)}


def _entrypoint_target_status(root_path: Path, target: str) -> tuple[bool, str]:
    module_name, _, attr_name = target.partition(":")
    if not module_name or not attr_name:
        return False, "invalid_target"
    module_path = root_path / Path(*module_name.split(".")).with_suffix(".py")
    package_path = root_path / Path(*module_name.split(".")) / "__init__.py"
    path = module_path if module_path.is_file() else package_path
    if not path.is_file():
        return False, f"missing:{module_name}"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False, f"unreadable:{module_name}"
    found = any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == attr_name
        for node in tree.body
    )
    return (True, f"{module_name}:{attr_name}") if found else (False, f"missing_attr:{module_name}:{attr_name}")


def build_product_commercial_independence_gate(
    *,
    root: str | Path = ".",
    runtime_requirements: str = RUNTIME_REQUIREMENTS,
    optional_requirements: tuple[str, ...] = OPTIONAL_REQUIREMENTS,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    runtime_path = root_path / runtime_requirements
    pyproject_path = root_path / "pyproject.toml"
    runtime_lines = _read_requirement_lines(runtime_path)
    runtime_names = {_requirement_name(line) for line in runtime_lines}
    pyproject = _read_pyproject_metadata(pyproject_path)
    project = pyproject["project"]
    scripts = pyproject["scripts"]
    package_includes = pyproject["package_includes"]

    license_path = next((root_path / name for name in LICENSE_CANDIDATES if (root_path / name).is_file()), None)
    license_present = bool(license_path and license_path.read_text(encoding="utf-8", errors="ignore").strip())
    optional_profile_paths = [root_path / name for name in optional_requirements]
    optional_profiles_present = all(path.is_file() for path in optional_profile_paths)
    deployment_path = next((root_path / name for name in DEPLOYMENT_CANDIDATES if (root_path / name).is_file()), None)
    deployment_manifest_present = deployment_path is not None
    product_api_present = (root_path / "api" / "product.py").is_file()
    product_package_present = (root_path / "betelgeuze_product" / "__init__.py").is_file()
    product_cli_present = (root_path / "betelgeuze_product" / "cli.py").is_file()
    core_product_surface_present = product_api_present and product_package_present and product_cli_present
    pyproject_packaging_metadata_present = (
        pyproject_path.is_file()
        and _text(project.get("name")) == "betelgeuze-md-product"
        and bool(_text(project.get("version")))
        and bool(_text(project.get("requires-python")))
        and all(script in scripts and _text(scripts.get(script)) == target for script, target in REQUIRED_CONSOLE_SCRIPTS.items())
    )
    entrypoint_statuses = {
        script: _entrypoint_target_status(root_path, target)
        for script, target in REQUIRED_CONSOLE_SCRIPTS.items()
        if _text(scripts.get(script)) == target
    }
    missing_entrypoint_targets = [
        f"{script}={status}"
        for script, (ok, status) in entrypoint_statuses.items()
        if not ok
    ]
    missing_entrypoint_targets.extend(
        f"{script}=missing_script"
        for script in REQUIRED_CONSOLE_SCRIPTS
        if script not in scripts
    )
    console_entrypoint_targets_present = not missing_entrypoint_targets and len(entrypoint_statuses) == len(REQUIRED_CONSOLE_SCRIPTS)
    package_discovery_present = all(pattern in package_includes for pattern in REQUIRED_PACKAGE_PATTERNS)
    runtime_requirements_present = runtime_path.is_file() and bool(runtime_lines)
    loose_runtime = [line for line in runtime_lines if not _is_pinned_runtime_requirement(line)]
    runtime_dependencies_pinned = runtime_requirements_present and not loose_runtime
    external_api_runtime = sorted(runtime_names & EXTERNAL_API_RUNTIME_DEPENDENCIES)
    non_core_runtime = sorted(runtime_names & NON_CORE_RUNTIME_DEPENDENCIES)
    optional_profiles_separated = optional_profiles_present and not non_core_runtime
    external_api_free_core_runtime = not external_api_runtime

    rows = [
        _row(
            "license_file_present",
            license_present,
            str(license_path.relative_to(root_path)) if license_path else "missing",
            "non-empty LICENSE, LICENSE.md, or LICENSE.txt",
            str(license_path.relative_to(root_path)) if license_path else "LICENSE",
            "Commercial distribution needs an explicit license artifact before independent-product claims.",
        ),
        _row(
            "runtime_requirements_present",
            runtime_requirements_present,
            f"{runtime_requirements};line_count={len(runtime_lines)}",
            "non-empty requirements.txt",
            runtime_requirements,
            "The product runtime dependency surface must be inspectable from a stable local requirements file.",
        ),
        _row(
            "runtime_dependencies_pinned",
            runtime_dependencies_pinned,
            ";".join(loose_runtime[:8]) if loose_runtime else "all pinned",
            "all runtime requirements use exact pins or direct references",
            runtime_requirements,
            "Commercial handoff needs reproducible runtime dependency resolution rather than loose package names.",
        ),
        _row(
            "external_api_free_core_runtime",
            external_api_free_core_runtime,
            ";".join(external_api_runtime) if external_api_runtime else "none",
            "no external API SDKs in core runtime requirements",
            runtime_requirements,
            "The core molecular-structure and ligand-docking product should not require an external API SDK to run.",
        ),
        _row(
            "optional_profiles_separated",
            optional_profiles_separated,
            f"optional_profiles_present={optional_profiles_present};non_core_runtime={';'.join(non_core_runtime) or 'none'}",
            "api/deploy/train/optional dependencies kept outside requirements.txt",
            ";".join(optional_requirements),
            "Commercial local delivery should keep optional server, deployment, training, and hardware-extension profiles separate from the core runtime.",
        ),
        _row(
            "deployment_manifest_present",
            deployment_manifest_present,
            str(deployment_path.relative_to(root_path)) if deployment_path else "missing",
            "Dockerfile, Dockerfile.product, or requirements-deploy.txt",
            str(deployment_path.relative_to(root_path)) if deployment_path else "requirements-deploy.txt",
            "Independent productization needs at least one deployment profile or container manifest tracked in the repository.",
        ),
        _row(
            "pyproject_packaging_metadata_present",
            pyproject_packaging_metadata_present,
            (
                f"name={_text(project.get('name')) or 'missing'};"
                f"version={_text(project.get('version')) or 'missing'};"
                f"requires_python={_text(project.get('requires-python')) or 'missing'};"
                f"scripts={','.join(sorted(str(key) for key in scripts.keys())) or 'missing'}"
            ),
            "pyproject.toml with project name, version, requires-python, and product/cameo/cleanup console scripts",
            "pyproject.toml",
            "Commercial handoff needs installable package metadata and stable console entry points.",
        ),
        _row(
            "package_discovery_present",
            package_discovery_present,
            ";".join(package_includes) if package_includes else "missing",
            "setuptools package discovery includes product, CAMEO, and cleanup packages",
            "pyproject.toml",
            "Installable product metadata must include the local product, validation, and cleanup packages.",
        ),
        _row(
            "console_entrypoint_targets_present",
            console_entrypoint_targets_present,
            ";".join(missing_entrypoint_targets) if missing_entrypoint_targets else "all entrypoint targets present",
            "all required pyproject console scripts point at existing local module functions",
            "pyproject.toml;betelgeuze_product/cli.py;betelgeuze_cameo/cli.py;betelgeuze_cleanup/cli.py",
            "Commercial command-line entry points must resolve to local callable targets before packaging handoff.",
        ),
        _row(
            "core_product_surface_present",
            core_product_surface_present,
            f"api/product.py={product_api_present};betelgeuze_product={product_package_present};betelgeuze_product/cli.py={product_cli_present}",
            "api/product.py, betelgeuze_product package, and read-only product CLI present",
            "api/product.py;betelgeuze_product/__init__.py;betelgeuze_product/cli.py",
            "The product lane must expose API, local package, and CLI status surfaces before it can be treated as a standalone product.",
        ),
    ]

    blockers = [_blocker(row) for row in rows if row["status"] != "pass"]
    blocker_checks = {blocker["check"] for blocker in blockers}
    commercial_independent_product_claim_allowed = not blockers
    status = (
        "product_commercial_independence_gate_ready"
        if commercial_independent_product_claim_allowed
        else "blocked_product_commercial_independence_gate"
    )
    summary = {
        "packet_type": "product_commercial_independence_gate",
        "status": status,
        "blocker_count": len(blockers),
        "check_count": len(rows),
        "license_present": license_present,
        "runtime_requirements_present": runtime_requirements_present,
        "runtime_dependency_count": len(runtime_lines),
        "loose_runtime_dependency_count": len(loose_runtime),
        "loose_runtime_dependencies": loose_runtime,
        "external_api_runtime_dependency_count": len(external_api_runtime),
        "external_api_runtime_dependencies": external_api_runtime,
        "optional_profiles_present": optional_profiles_present,
        "optional_profiles_separated": optional_profiles_separated,
        "deployment_manifest_present": deployment_manifest_present,
        "pyproject_packaging_metadata_present": pyproject_packaging_metadata_present,
        "package_discovery_present": package_discovery_present,
        "console_entrypoint_targets_present": console_entrypoint_targets_present,
        "missing_console_entrypoint_targets": missing_entrypoint_targets,
        "required_console_scripts": dict(REQUIRED_CONSOLE_SCRIPTS),
        "core_product_surface_present": core_product_surface_present,
        "product_cli_surface_present": product_cli_present,
        "commercial_independent_product_claim_allowed": commercial_independent_product_claim_allowed,
        "execution_enabled": False,
        "docking_results_emitted": False,
        "bundle_assembled": False,
        "outbound_email_enabled": False,
        "delete_executed": False,
        "external_state_mutated": False,
        "validated_without_install": True,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Add explicit operator-approved license evidence before commercial independent-product claims."
            if blocker_checks == {"license_file_present"}
            else "Resolve the listed license, dependency, packaging, and product-surface blockers before commercial independent-product claims."
            if blockers
            else "Commercial-independence packaging gate is clear; keep this packet with final bundle evidence before customer-facing claims."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}
