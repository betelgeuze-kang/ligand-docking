from __future__ import annotations

import ast
import json
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
LICENSE_APPROVAL_TOKEN = "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
LICENSE_GENERATION_COMMAND_TEMPLATE = (
    "APPROVE_PRODUCT_LICENSE_FILE_CREATION=1 "
    "python3 tools/write_product_license_file.py "
    "--work-order-json runs/product_license_file_creation_work_order_current.json "
    "--license-template OPERATOR_APPROVED_LICENSE_TEXT_FILE --out LICENSE"
)
DEPLOYMENT_CANDIDATES = ("Dockerfile", "Dockerfile.product", "requirements-deploy.txt")
EXTERNAL_API_RUNTIME_DEPENDENCIES = {"openai"}
NON_CORE_RUNTIME_DEPENDENCIES = {"fastapi", "uvicorn", "mlflow", "optuna", "torch-geometric", "gputil"}
REQUIRED_CONSOLE_SCRIPTS = {
    "betelgeuze-product": "betelgeuze_product.cli:main",
    "betelgeuze-cameo": "betelgeuze_cameo.cli:main",
    "betelgeuze-cleanup": "betelgeuze_cleanup.cli:main",
}
REQUIRED_PACKAGE_PATTERNS = ("betelgeuze_product*", "betelgeuze_cameo*", "betelgeuze_cleanup*")
DEFAULT_ENVIRONMENT_MANIFEST_JSON = "runs/local_delivery_environment_manifest_current.json"
DEFAULT_REQUIREMENTS_LOCK_JSON = "runs/local_delivery_requirements_lock_current.json"
DEFAULT_REQUIREMENTS_LOCK_MD = "runs/local_delivery_requirements_lock_current.md"
DEFAULT_REQUIREMENTS_LOCK_TXT = "runs/local_delivery_requirements_lock_current.txt"
DEFAULT_PRODUCT_SERVICE_BOUNDARY_JSON = "runs/product_service_boundary_contract_current.json"
DEFAULT_PRODUCT_API_CONTRACT_JSON = "runs/product_api_contract_current.json"
DEFAULT_PRODUCT_CAPABILITY_JSON = "runs/product_capability_surface_contract_current.json"
DEFAULT_PRODUCT_BUNDLE_JSON = "runs/product_bundle_contract_current.json"
DEFAULT_PRODUCT_DELIVERY_EVIDENCE_JSON = "runs/product_delivery_evidence_contract_current.json"
DEFAULT_PRODUCT_PILOT_JSON = "runs/product_pilot_packet_contract_current.json"
DEFAULT_PUBLIC_BENCHMARK_JSON = "runs/product_public_benchmark_contract_current.json"


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _bool(value: Any) -> bool:
    return bool(value is True)


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


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
    environment_manifest_json: str = DEFAULT_ENVIRONMENT_MANIFEST_JSON,
    requirements_lock_json: str = DEFAULT_REQUIREMENTS_LOCK_JSON,
    requirements_lock_md: str = DEFAULT_REQUIREMENTS_LOCK_MD,
    requirements_lock_txt: str = DEFAULT_REQUIREMENTS_LOCK_TXT,
    product_service_boundary_json: str = DEFAULT_PRODUCT_SERVICE_BOUNDARY_JSON,
    product_api_contract_json: str = DEFAULT_PRODUCT_API_CONTRACT_JSON,
    product_capability_json: str = DEFAULT_PRODUCT_CAPABILITY_JSON,
    product_bundle_json: str = DEFAULT_PRODUCT_BUNDLE_JSON,
    product_delivery_evidence_json: str = DEFAULT_PRODUCT_DELIVERY_EVIDENCE_JSON,
    product_pilot_json: str = DEFAULT_PRODUCT_PILOT_JSON,
    public_benchmark_json: str = DEFAULT_PUBLIC_BENCHMARK_JSON,
    public_benchmark_work_order_json: str = "runs/product_public_benchmark_work_order_current.json",
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
    environment_manifest_path = root_path / environment_manifest_json
    requirements_lock_json_path = root_path / requirements_lock_json
    requirements_lock_md_path = root_path / requirements_lock_md
    requirements_lock_txt_path = root_path / requirements_lock_txt
    product_service_boundary_path = root_path / product_service_boundary_json
    product_api_contract_path = root_path / product_api_contract_json
    product_capability_path = root_path / product_capability_json
    product_bundle_path = root_path / product_bundle_json
    product_delivery_evidence_path = root_path / product_delivery_evidence_json
    product_pilot_path = root_path / product_pilot_json
    public_benchmark_path = root_path / public_benchmark_json
    public_benchmark_work_order_path = root_path / public_benchmark_work_order_json
    environment_manifest_payload = _read_json(environment_manifest_path)
    requirements_lock_payload = _read_json(requirements_lock_json_path)
    product_service_boundary = _summary(_read_json(product_service_boundary_path))
    product_api_contract = _summary(_read_json(product_api_contract_path))
    product_capability = _summary(_read_json(product_capability_path))
    product_bundle = _summary(_read_json(product_bundle_path))
    product_delivery_evidence = _summary(_read_json(product_delivery_evidence_path))
    product_pilot = _summary(_read_json(product_pilot_path))
    public_benchmark = _summary(_read_json(public_benchmark_path))
    public_benchmark_work_order = _summary(_read_json(public_benchmark_work_order_path))
    environment_manifest = _summary(environment_manifest_payload)
    requirements_lock = _summary(requirements_lock_payload)
    requirements_lock_generated_at = _text(requirements_lock.get("generated_at") or requirements_lock_payload.get("generated_at"))

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
    dependency_provenance_manifest_present = bool(environment_manifest_path.is_file() and environment_manifest)
    requirements_lock_artifacts_present = bool(
        requirements_lock_json_path.is_file()
        and requirements_lock_md_path.is_file()
        and requirements_lock_txt_path.is_file()
        and requirements_lock
    )
    requirements_lock_complete = (
        requirements_lock_artifacts_present
        and _int(requirements_lock.get("missing_count")) == 0
        and _int(requirements_lock.get("loose_source_requirement_count")) == 0
        and _int(requirements_lock.get("missing_input_file_count")) == 0
    )
    reproducible_install_manifest_ready = (
        dependency_provenance_manifest_present
        and requirements_lock_artifacts_present
        and _bool(environment_manifest.get("requirements_lock_complete"))
        and _text(environment_manifest.get("requirements_lock_txt_sha256"))
        and requirements_lock_generated_at
    )
    product_service_boundary_ready = (
        _text(product_service_boundary.get("status")) == "product_service_boundary_contract_ready"
        and _bool(product_service_boundary.get("service_boundary_ready"))
        and _int(product_service_boundary.get("api_route_count")) > 0
        and _int(product_service_boundary.get("cli_command_count")) > 0
    )
    product_api_contract_ready = (
        _text(product_api_contract.get("status")) == "product_api_contract_ready"
        and _bool(product_api_contract.get("api_contract_ready"))
        and _int(product_api_contract.get("missing_route_count")) == 0
        and _int(product_api_contract.get("status_response_missing_key_count")) == 0
    )
    allowed_scope_families = [str(item) for item in product_capability.get("allowed_scope_families") or []]
    blocked_claim_scopes = [str(item) for item in product_capability.get("blocked_claim_scopes") or []]
    general_platform_claim_allowed = _bool(product_capability.get("general_platform_claim_allowed"))
    restricted_commercial_scope_claim_ready = (
        _text(product_capability.get("status")) == "product_capability_surface_contract_ready"
        and _bool(product_capability.get("restricted_scope_claim_guard_ready"))
        and allowed_scope_families == ["gpcr", "ion_channel", "kinase"]
        and "general_protein_ligand_platform" in blocked_claim_scopes
        and not general_platform_claim_allowed
    )
    commercial_claim_scope_tier = "restricted_family_local_product" if restricted_commercial_scope_claim_ready else "scope_claim_not_ready"
    commercial_claim_scope_detail = (
        f"tier={commercial_claim_scope_tier};"
        f"allowed_scope_families={','.join(allowed_scope_families)};"
        f"blocked_claim_scopes={','.join(blocked_claim_scopes)};"
        f"general_platform_claim_allowed={general_platform_claim_allowed}"
    )
    local_delivery_bundle_ready = (
        _text(product_bundle.get("status")) == "product_bundle_contract_ready"
        and _bool(product_bundle.get("bundle_assembled"))
        and _bool(product_bundle.get("bundle_validation_passed"))
        and _text(product_delivery_evidence.get("status")) == "product_delivery_evidence_contract_ready"
        and _bool(product_delivery_evidence.get("delivery_ready_claim_allowed"))
        and _text(product_pilot.get("status")) == "product_pilot_packet_ready"
        and _bool(product_pilot.get("pilot_delivery_ready"))
        and _bool(product_pilot.get("bundle_validation_passed"))
    )
    local_self_hosted_operation_ready = (
        core_product_surface_present
        and external_api_free_core_runtime
        and product_service_boundary_ready
        and product_api_contract_ready
        and product_cli_present
        and local_delivery_bundle_ready
    )
    public_benchmark_required_suite_count = _int(public_benchmark.get("required_suite_count"))
    public_benchmark_ready_required_suite_count = _int(public_benchmark.get("ready_required_suite_count"))
    public_benchmark_blocked_suite_count = _int(public_benchmark.get("blocked_suite_count"))
    public_benchmark_suite_materialization_manifest_count = _int(
        public_benchmark.get("suite_materialization_manifest_count")
    )
    public_benchmark_suite_scorecard_row_csv_count = _int(public_benchmark.get("suite_scorecard_row_csv_count"))
    public_benchmark_suite_threshold_count = _int(public_benchmark.get("suite_threshold_count"))
    public_benchmark_suite_blocker_count = _int(public_benchmark.get("suite_blocker_count"))
    public_benchmark_suite_run_command_count = _int(public_benchmark.get("suite_run_command_count"))
    public_benchmark_suite_materialization_run_command_count = _int(
        public_benchmark.get("suite_materialization_run_command_count")
    )
    public_benchmark_suite_result_provenance_command_count = _int(
        public_benchmark_work_order.get("suite_result_provenance_command_count")
    )
    public_benchmark_suite_result_provenance_present_count = _int(
        public_benchmark_work_order.get("suite_result_provenance_present_count")
    )
    public_benchmark_suite_no_external_dependency_count = _int(
        public_benchmark.get("suite_no_external_dependency_count")
    )
    public_benchmark_work_order_status = _text(public_benchmark_work_order.get("status"))
    public_benchmark_work_order_local_artifact_preflight_ready_suite_count = _int(
        public_benchmark_work_order.get("local_artifact_preflight_ready_suite_count")
    )
    public_benchmark_work_order_local_artifact_preflight_blocked_suite_count = _int(
        public_benchmark_work_order.get("local_artifact_preflight_blocked_suite_count")
    )
    public_benchmark_work_order_missing_local_input_artifact_count = _int(
        public_benchmark_work_order.get("missing_local_input_artifact_count")
    )
    public_benchmark_work_order_missing_local_output_artifact_count = _int(
        public_benchmark_work_order.get("missing_local_output_artifact_count")
    )
    public_benchmark_work_order_local_artifact_preflight_ready = (
        public_benchmark_required_suite_count > 0
        and public_benchmark_work_order_status in {
            "product_public_benchmark_work_order_ready",
            "product_public_benchmark_work_order_clear",
        }
        and public_benchmark_work_order_local_artifact_preflight_ready_suite_count >= public_benchmark_required_suite_count
        and public_benchmark_work_order_local_artifact_preflight_blocked_suite_count == 0
        and public_benchmark_work_order_missing_local_input_artifact_count == 0
        and public_benchmark_work_order_missing_local_output_artifact_count == 0
    )
    public_benchmark_suite_coverage_ready = (
        public_benchmark_required_suite_count > 0
        and public_benchmark_suite_materialization_manifest_count >= public_benchmark_required_suite_count
        and public_benchmark_suite_scorecard_row_csv_count >= public_benchmark_required_suite_count
        and public_benchmark_suite_threshold_count >= public_benchmark_required_suite_count
        and public_benchmark_suite_blocker_count >= public_benchmark_required_suite_count
        and public_benchmark_suite_run_command_count >= public_benchmark_required_suite_count
        and public_benchmark_suite_materialization_run_command_count >= public_benchmark_required_suite_count
        and public_benchmark_suite_result_provenance_command_count >= public_benchmark_required_suite_count
        and public_benchmark_suite_no_external_dependency_count >= public_benchmark_required_suite_count
    )
    public_benchmark_evidence_ready = (
        _text(public_benchmark.get("status")) == "product_public_benchmark_contract_ready"
        and _bool(public_benchmark.get("public_benchmark_validation_ready"))
        and public_benchmark_ready_required_suite_count == public_benchmark_required_suite_count
        and public_benchmark_blocked_suite_count == 0
        and public_benchmark_suite_coverage_ready
        and public_benchmark_work_order_local_artifact_preflight_ready
    )

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
            "dependency_provenance_manifest_present",
            dependency_provenance_manifest_present,
            (
                f"python={_text(environment_manifest.get('python_version')) or 'missing'};"
                f"git={_text(environment_manifest.get('git_short_commit')) or 'missing'};"
                f"lock_sha={_text(environment_manifest.get('requirements_lock_txt_sha256')) or 'missing'}"
            ),
            "local delivery environment manifest with python, git, and requirements-lock provenance",
            environment_manifest_json,
            "Commercial handoff needs an explicit dependency provenance artifact tied to the local delivery environment.",
        ),
        _row(
            "requirements_lock_artifacts_present",
            requirements_lock_artifacts_present,
            (
                f"json={requirements_lock_json_path.is_file()};md={requirements_lock_md_path.is_file()};"
                f"txt={requirements_lock_txt_path.is_file()};declared={_int(requirements_lock.get('declared_count'))}"
            ),
            "requirements lock JSON, Markdown, and TXT artifacts present",
            f"{requirements_lock_json};{requirements_lock_md};{requirements_lock_txt}",
            "Reproducible install evidence needs machine-readable, human-readable, and installable lock artifacts.",
        ),
        _row(
            "reproducible_install_manifest_ready",
            reproducible_install_manifest_ready and requirements_lock_complete,
            (
                f"manifest_lock_complete={_bool(environment_manifest.get('requirements_lock_complete'))};"
                f"lock_missing={_int(requirements_lock.get('missing_count'))};"
                f"lock_loose_source={_int(requirements_lock.get('loose_source_requirement_count'))};"
                f"lock_missing_inputs={_int(requirements_lock.get('missing_input_file_count'))}"
            ),
            "environment manifest references complete requirements lock with no missing or loose source requirements",
            f"{environment_manifest_json};{requirements_lock_json}",
            "The product release gate should prove local install reproduction with explicit lock provenance, not only loose requirements files.",
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
        _row(
            "product_service_boundary_ready",
            product_service_boundary_ready,
            (
                f"status={_text(product_service_boundary.get('status')) or 'missing'};"
                f"service_boundary_ready={_bool(product_service_boundary.get('service_boundary_ready'))};"
                f"api_route_count={_int(product_service_boundary.get('api_route_count'))};"
                f"cli_command_count={_int(product_service_boundary.get('cli_command_count'))}"
            ),
            "product service boundary contract ready with API and CLI command coverage",
            product_service_boundary_json,
            "Commercial independence needs an audited product API/CLI service boundary, not just source files.",
        ),
        _row(
            "product_api_contract_ready",
            product_api_contract_ready,
            (
                f"status={_text(product_api_contract.get('status')) or 'missing'};"
                f"api_contract_ready={_bool(product_api_contract.get('api_contract_ready'))};"
                f"missing_route_count={_int(product_api_contract.get('missing_route_count'))};"
                f"status_response_missing_key_count={_int(product_api_contract.get('status_response_missing_key_count'))}"
            ),
            "product API contract ready with no missing routes or status response keys",
            product_api_contract_json,
            "Commercial handoff needs a verified API contract for local/self-hosted operation.",
        ),
        _row(
            "restricted_commercial_scope_claim_ready",
            restricted_commercial_scope_claim_ready,
            commercial_claim_scope_detail,
            "capability surface declares restricted gpcr/ion_channel/kinase scope, blocks transporter/PXR/general platform claims, and general_platform_claim_allowed=false",
            product_capability_json,
            "Commercial independence must be tied to the current restricted product scope, not a broad protein-ligand platform claim.",
        ),
        _row(
            "local_self_hosted_operation_ready",
            local_self_hosted_operation_ready,
            (
                f"core_product_surface={core_product_surface_present};"
                f"external_api_runtime_dependency_count={len(external_api_runtime)};"
                f"service_boundary_ready={product_service_boundary_ready};"
                f"api_contract_ready={product_api_contract_ready};"
                f"cli_surface={product_cli_present};"
                f"local_delivery_bundle_ready={local_delivery_bundle_ready}"
            ),
            "core API/package/CLI present, no external API SDK in runtime, service/API contracts ready, and local delivery bundle ready",
            (
                f"api/product.py;betelgeuze_product/__init__.py;betelgeuze_product/cli.py;"
                f"{product_service_boundary_json};{product_api_contract_json};{product_bundle_json};"
                f"{product_delivery_evidence_json};{product_pilot_json};{runtime_requirements}"
            ),
            "The commercial product must be operable from local/self-hosted API and CLI surfaces without a SaaS runtime dependency.",
        ),
        _row(
            "local_delivery_bundle_ready",
            local_delivery_bundle_ready,
            (
                f"bundle_status={_text(product_bundle.get('status')) or 'missing'};"
                f"bundle_assembled={_bool(product_bundle.get('bundle_assembled'))};"
                f"bundle_validation_passed={_bool(product_bundle.get('bundle_validation_passed'))};"
                f"delivery_status={_text(product_delivery_evidence.get('status')) or 'missing'};"
                f"delivery_ready_claim_allowed={_bool(product_delivery_evidence.get('delivery_ready_claim_allowed'))};"
                f"pilot_status={_text(product_pilot.get('status')) or 'missing'};"
                f"pilot_delivery_ready={_bool(product_pilot.get('pilot_delivery_ready'))}"
            ),
            "validated local delivery bundle, delivery evidence, and pilot packet ready",
            f"{product_bundle_json};{product_delivery_evidence_json};{product_pilot_json}",
            "A commercial independent product needs local bundle and delivery evidence before customer-facing claims.",
        ),
        _row(
            "public_benchmark_evidence_ready",
            public_benchmark_evidence_ready,
            (
                f"status={_text(public_benchmark.get('status')) or 'missing'};"
                f"validation_ready={_bool(public_benchmark.get('public_benchmark_validation_ready'))};"
                f"ready_required_suites={public_benchmark_ready_required_suite_count};"
                f"required_suites={public_benchmark_required_suite_count};"
                f"blocked_suites={public_benchmark_blocked_suite_count};"
                f"suite_materialization_manifest_count={public_benchmark_suite_materialization_manifest_count};"
                f"suite_scorecard_row_csv_count={public_benchmark_suite_scorecard_row_csv_count};"
                f"suite_threshold_count={public_benchmark_suite_threshold_count};"
                f"suite_blocker_count={public_benchmark_suite_blocker_count};"
                f"suite_run_command_count={public_benchmark_suite_run_command_count};"
                f"suite_materialization_run_command_count={public_benchmark_suite_materialization_run_command_count};"
                f"suite_no_external_dependency_count={public_benchmark_suite_no_external_dependency_count};"
                f"work_order_status={public_benchmark_work_order_status or 'missing'};"
                f"work_order_local_artifact_preflight_ready={public_benchmark_work_order_local_artifact_preflight_ready};"
                f"work_order_local_artifact_preflight_ready_suite_count={public_benchmark_work_order_local_artifact_preflight_ready_suite_count};"
                f"work_order_local_artifact_preflight_blocked_suite_count={public_benchmark_work_order_local_artifact_preflight_blocked_suite_count};"
                f"work_order_missing_local_input_artifact_count={public_benchmark_work_order_missing_local_input_artifact_count};"
                f"work_order_missing_local_output_artifact_count={public_benchmark_work_order_missing_local_output_artifact_count}"
            ),
            "public benchmark contract ready with all required suites passing and suite-level manifest/scorecard/threshold/blocker/run-command evidence",
            f"{public_benchmark_json};{public_benchmark_work_order_json}",
            "Commercial independence claims need reproducible public benchmark evidence, independent of live CAMEO.",
        ),
    ]
    for row in rows:
        if row["check"] == "license_file_present":
            row.update(
                {
                    "approval_token_required": "" if license_present else LICENSE_APPROVAL_TOKEN,
                    "operator_required_input": (
                        "none"
                        if license_present
                        else "operator-approved license template and explicit approval token before LICENSE creation"
                    ),
                    "operator_required_output": "non-empty LICENSE, LICENSE.md, or LICENSE.txt",
                    "next_command_template": "" if license_present else LICENSE_GENERATION_COMMAND_TEMPLATE,
                    "license_creation_executed": False,
                }
            )
            break

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
        "license_approval_token_required": "" if license_present else LICENSE_APPROVAL_TOKEN,
        "license_operator_required_input": (
            "none"
            if license_present
            else "operator-approved license template and explicit approval token before LICENSE creation"
        ),
        "license_required_output": "non-empty LICENSE, LICENSE.md, or LICENSE.txt",
        "license_generation_command_template": "" if license_present else LICENSE_GENERATION_COMMAND_TEMPLATE,
        "license_creation_executed": False,
        "runtime_requirements_present": runtime_requirements_present,
        "runtime_dependency_count": len(runtime_lines),
        "loose_runtime_dependency_count": len(loose_runtime),
        "loose_runtime_dependencies": loose_runtime,
        "dependency_provenance_manifest_present": dependency_provenance_manifest_present,
        "dependency_provenance_python_version": _text(environment_manifest.get("python_version")),
        "dependency_provenance_git_short_commit": _text(environment_manifest.get("git_short_commit")),
        "dependency_provenance_requirements_lock_txt_sha256": _text(
            environment_manifest.get("requirements_lock_txt_sha256")
        ),
        "requirements_lock_artifacts_present": requirements_lock_artifacts_present,
        "requirements_lock_complete": requirements_lock_complete,
        "requirements_lock_declared_count": _int(requirements_lock.get("declared_count")),
        "requirements_lock_missing_count": _int(requirements_lock.get("missing_count")),
        "requirements_lock_loose_source_requirement_count": _int(requirements_lock.get("loose_source_requirement_count")),
        "requirements_lock_missing_input_file_count": _int(requirements_lock.get("missing_input_file_count")),
        "requirements_lock_generated_at": requirements_lock_generated_at,
        "reproducible_install_manifest_ready": reproducible_install_manifest_ready and requirements_lock_complete,
        "external_api_runtime_dependency_count": len(external_api_runtime),
        "external_api_runtime_dependencies": external_api_runtime,
        "external_saas_runtime_dependency_count": len(external_api_runtime),
        "external_saas_runtime_dependencies": external_api_runtime,
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
        "product_service_boundary_ready": product_service_boundary_ready,
        "product_service_boundary_api_route_count": _int(product_service_boundary.get("api_route_count")),
        "product_service_boundary_cli_command_count": _int(product_service_boundary.get("cli_command_count")),
        "product_api_contract_ready": product_api_contract_ready,
        "product_api_contract_missing_route_count": _int(product_api_contract.get("missing_route_count")),
        "restricted_commercial_scope_claim_ready": restricted_commercial_scope_claim_ready,
        "commercial_claim_scope_tier": commercial_claim_scope_tier,
        "commercial_claim_scope_detail": commercial_claim_scope_detail,
        "allowed_scope_families": allowed_scope_families,
        "blocked_claim_scopes": blocked_claim_scopes,
        "general_platform_claim_allowed": general_platform_claim_allowed,
        "local_self_hosted_operation_ready": local_self_hosted_operation_ready,
        "local_self_hosted_core_product_surface_present": core_product_surface_present,
        "local_self_hosted_external_saas_free_runtime": external_api_free_core_runtime,
        "local_self_hosted_api_cli_ready": product_service_boundary_ready and product_api_contract_ready and product_cli_present,
        "local_delivery_bundle_ready": local_delivery_bundle_ready,
        "local_delivery_bundle_assembled": _bool(product_bundle.get("bundle_assembled")),
        "local_delivery_bundle_validation_passed": _bool(product_bundle.get("bundle_validation_passed")),
        "local_delivery_pilot_delivery_ready": _bool(product_pilot.get("pilot_delivery_ready")),
        "public_benchmark_evidence_ready": public_benchmark_evidence_ready,
        "public_benchmark_status": _text(public_benchmark.get("status")),
        "public_benchmark_ready_required_suite_count": public_benchmark_ready_required_suite_count,
        "public_benchmark_required_suite_count": public_benchmark_required_suite_count,
        "public_benchmark_blocked_suite_count": public_benchmark_blocked_suite_count,
        "public_benchmark_suite_coverage_ready": public_benchmark_suite_coverage_ready,
        "public_benchmark_suite_materialization_manifest_count": public_benchmark_suite_materialization_manifest_count,
        "public_benchmark_suite_scorecard_row_csv_count": public_benchmark_suite_scorecard_row_csv_count,
        "public_benchmark_suite_threshold_count": public_benchmark_suite_threshold_count,
        "public_benchmark_suite_blocker_count": public_benchmark_suite_blocker_count,
        "public_benchmark_suite_run_command_count": public_benchmark_suite_run_command_count,
        "public_benchmark_suite_materialization_run_command_count": public_benchmark_suite_materialization_run_command_count,
        "public_benchmark_suite_result_provenance_command_count": public_benchmark_suite_result_provenance_command_count,
        "public_benchmark_suite_result_provenance_present_count": public_benchmark_suite_result_provenance_present_count,
        "public_benchmark_suite_no_external_dependency_count": public_benchmark_suite_no_external_dependency_count,
        "public_benchmark_work_order_status": public_benchmark_work_order_status,
        "public_benchmark_work_order_local_artifact_preflight_ready": public_benchmark_work_order_local_artifact_preflight_ready,
        "public_benchmark_work_order_local_artifact_preflight_ready_suite_count": public_benchmark_work_order_local_artifact_preflight_ready_suite_count,
        "public_benchmark_work_order_local_artifact_preflight_blocked_suite_count": public_benchmark_work_order_local_artifact_preflight_blocked_suite_count,
        "public_benchmark_work_order_missing_local_input_artifact_count": public_benchmark_work_order_missing_local_input_artifact_count,
        "public_benchmark_work_order_missing_local_output_artifact_count": public_benchmark_work_order_missing_local_output_artifact_count,
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
            else "Add license evidence and pass the public benchmark contract before commercial independent-product claims."
            if blocker_checks == {"license_file_present", "public_benchmark_evidence_ready"}
            else "Materialize public benchmarks and pass all required scorecards before commercial independent-product claims."
            if blocker_checks == {"public_benchmark_evidence_ready"}
            else "Resolve the listed license, dependency, packaging, and product-surface blockers before commercial independent-product claims."
            if blockers
            else "Commercial-independence packaging gate is clear; keep this packet with final bundle evidence before customer-facing claims."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}
