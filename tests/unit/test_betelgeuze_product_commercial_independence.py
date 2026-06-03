from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_product.commercial_independence import build_product_commercial_independence_gate


def _write_minimal_product_tree(root: Path, requirements: str, *, license_text: str = "Proprietary\n") -> None:
    (root / "api").mkdir()
    (root / "api" / "product.py").write_text("# product API\n", encoding="utf-8")
    (root / "betelgeuze_product").mkdir()
    (root / "betelgeuze_product" / "__init__.py").write_text("", encoding="utf-8")
    (root / "betelgeuze_product" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "betelgeuze_cameo").mkdir()
    (root / "betelgeuze_cameo" / "__init__.py").write_text("", encoding="utf-8")
    (root / "betelgeuze_cameo" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "betelgeuze_cleanup").mkdir()
    (root / "betelgeuze_cleanup" / "__init__.py").write_text("", encoding="utf-8")
    (root / "betelgeuze_cleanup" / "cli.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        """
[project]
name = "betelgeuze-md-product"
version = "0.1.0"
requires-python = ">=3.11"

[project.scripts]
betelgeuze-product = "betelgeuze_product.cli:main"
betelgeuze-cameo = "betelgeuze_cameo.cli:main"
betelgeuze-cleanup = "betelgeuze_cleanup.cli:main"

[tool.setuptools.packages.find]
include = ["betelgeuze_product*", "betelgeuze_cameo*", "betelgeuze_cleanup*"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "LICENSE").write_text(license_text, encoding="utf-8")
    (root / "requirements.txt").write_text(requirements, encoding="utf-8")
    for name in ("requirements-api.txt", "requirements-deploy.txt", "requirements-optional.txt", "requirements-train.txt"):
        (root / name).write_text("# optional profile\nexample-extra==1.0.0\n", encoding="utf-8")
    runs = root / "runs"
    runs.mkdir()
    (runs / "local_delivery_requirements_lock_current.txt").write_text(requirements, encoding="utf-8")
    (runs / "local_delivery_requirements_lock_current.md").write_text("# Requirements Lock\n", encoding="utf-8")
    (runs / "local_delivery_requirements_lock_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "generated_at": "2026-06-03T00:00:00+09:00",
                    "declared_count": len([line for line in requirements.splitlines() if line.strip()]),
                    "missing_count": 0,
                    "loose_source_requirement_count": 0,
                    "missing_input_file_count": 0,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "local_delivery_environment_manifest_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "python_version": "3.12.2",
                    "git_short_commit": "abc1234",
                    "requirements_lock_complete": True,
                    "requirements_lock_txt_sha256": "abc123",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "product_service_boundary_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_service_boundary_contract_ready",
                    "service_boundary_ready": True,
                    "api_route_count": 14,
                    "cli_command_count": 11,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "product_api_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_api_contract_ready",
                    "api_contract_ready": True,
                    "missing_route_count": 0,
                    "status_response_missing_key_count": 0,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "product_bundle_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_bundle_contract_ready",
                    "bundle_assembled": True,
                    "bundle_validation_passed": True,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "product_delivery_evidence_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_delivery_evidence_contract_ready",
                    "delivery_ready_claim_allowed": True,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "product_pilot_packet_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_pilot_packet_ready",
                    "pilot_delivery_ready": True,
                    "bundle_validation_passed": True,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (runs / "product_public_benchmark_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "product_public_benchmark_contract_ready",
                    "public_benchmark_validation_ready": True,
                    "required_suite_count": 5,
                    "ready_required_suite_count": 5,
                    "blocked_suite_count": 0,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_product_commercial_independence_gate_ready_for_pinned_local_product_tree(tmp_path: Path) -> None:
    _write_minimal_product_tree(tmp_path, "numpy==1.26.4\ntorch==2.3.1\npydantic==2.7.4\n")

    payload = build_product_commercial_independence_gate(root=tmp_path)

    assert payload["summary"]["status"] == "product_commercial_independence_gate_ready"
    assert payload["summary"]["commercial_independent_product_claim_allowed"] is True
    assert payload["summary"]["license_approval_token_required"] == ""
    assert payload["summary"]["license_generation_command_template"] == ""
    assert payload["summary"]["license_creation_executed"] is False
    assert payload["summary"]["product_cli_surface_present"] is True
    assert payload["summary"]["pyproject_packaging_metadata_present"] is True
    assert payload["summary"]["package_discovery_present"] is True
    assert payload["summary"]["console_entrypoint_targets_present"] is True
    assert payload["summary"]["dependency_provenance_manifest_present"] is True
    assert payload["summary"]["requirements_lock_artifacts_present"] is True
    assert payload["summary"]["reproducible_install_manifest_ready"] is True
    assert payload["summary"]["product_service_boundary_ready"] is True
    assert payload["summary"]["product_api_contract_ready"] is True
    assert payload["summary"]["local_self_hosted_operation_ready"] is True
    assert payload["summary"]["local_self_hosted_external_saas_free_runtime"] is True
    assert payload["summary"]["local_self_hosted_api_cli_ready"] is True
    assert payload["summary"]["external_saas_runtime_dependency_count"] == 0
    assert payload["summary"]["local_delivery_bundle_ready"] is True
    assert payload["summary"]["public_benchmark_evidence_ready"] is True
    assert payload["summary"]["blocker_count"] == 0
    assert all(row["status"] == "pass" for row in payload["rows"])


def test_product_commercial_independence_gate_blocks_loose_external_runtime_and_missing_license(tmp_path: Path) -> None:
    _write_minimal_product_tree(tmp_path, "numpy\ntorch\nopenai\n", license_text="")

    payload = build_product_commercial_independence_gate(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_product_commercial_independence_gate"
    assert payload["summary"]["commercial_independent_product_claim_allowed"] is False
    assert payload["summary"]["license_approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
    assert "operator-approved license template" in payload["summary"]["license_operator_required_input"]
    assert payload["summary"]["license_required_output"] == "non-empty LICENSE, LICENSE.md, or LICENSE.txt"
    assert "write_product_license_file.py" in payload["summary"]["license_generation_command_template"]
    assert payload["summary"]["license_creation_executed"] is False
    assert payload["summary"]["loose_runtime_dependency_count"] == 3
    assert payload["summary"]["external_api_runtime_dependencies"] == ["openai"]
    assert payload["summary"]["external_saas_runtime_dependencies"] == ["openai"]
    assert payload["summary"]["local_self_hosted_operation_ready"] is False
    assert payload["summary"]["reproducible_install_manifest_ready"] is True
    failed_checks = {row["check"] for row in payload["rows"] if row["status"] == "fail"}
    assert {
        "license_file_present",
        "runtime_dependencies_pinned",
        "external_api_free_core_runtime",
        "local_self_hosted_operation_ready",
    } <= failed_checks
    license_row = next(row for row in payload["rows"] if row["check"] == "license_file_present")
    assert license_row["approval_token_required"] == "APPROVE_PRODUCT_LICENSE_FILE_CREATION"
    assert "operator-approved license template" in license_row["operator_required_input"]
    assert "write_product_license_file.py" in license_row["next_command_template"]
    assert license_row["license_creation_executed"] is False


def test_product_commercial_independence_gate_blocks_missing_install_provenance(tmp_path: Path) -> None:
    _write_minimal_product_tree(tmp_path, "numpy==1.26.4\n")
    for path in (tmp_path / "runs").iterdir():
        path.unlink()

    payload = build_product_commercial_independence_gate(root=tmp_path)

    failed_checks = {row["check"] for row in payload["rows"] if row["status"] == "fail"}
    assert {
        "dependency_provenance_manifest_present",
        "requirements_lock_artifacts_present",
        "reproducible_install_manifest_ready",
    } <= failed_checks
    assert payload["summary"]["reproducible_install_manifest_ready"] is False


def test_product_commercial_independence_gate_blocks_missing_release_evidence(tmp_path: Path) -> None:
    _write_minimal_product_tree(tmp_path, "numpy==1.26.4\n")
    for path in (tmp_path / "runs").glob("product_*_current.json"):
        path.unlink()

    payload = build_product_commercial_independence_gate(root=tmp_path)

    failed_checks = {row["check"] for row in payload["rows"] if row["status"] == "fail"}
    assert {
        "product_service_boundary_ready",
        "product_api_contract_ready",
        "local_delivery_bundle_ready",
        "public_benchmark_evidence_ready",
    } <= failed_checks
    assert payload["summary"]["product_service_boundary_ready"] is False
    assert payload["summary"]["product_api_contract_ready"] is False
    assert payload["summary"]["local_self_hosted_operation_ready"] is False
    assert payload["summary"]["local_delivery_bundle_ready"] is False
    assert payload["summary"]["public_benchmark_evidence_ready"] is False


def test_product_commercial_independence_gate_blocks_failed_public_benchmarks(tmp_path: Path) -> None:
    _write_minimal_product_tree(tmp_path, "numpy==1.26.4\n")
    (tmp_path / "runs" / "product_public_benchmark_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {
                    "status": "blocked_product_public_benchmark_contract",
                    "public_benchmark_validation_ready": False,
                    "required_suite_count": 5,
                    "ready_required_suite_count": 0,
                    "blocked_suite_count": 5,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = build_product_commercial_independence_gate(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_product_commercial_independence_gate"
    assert payload["summary"]["public_benchmark_evidence_ready"] is False
    assert payload["summary"]["public_benchmark_blocked_suite_count"] == 5
    assert next(row for row in payload["rows"] if row["check"] == "public_benchmark_evidence_ready")["status"] == "fail"


def test_product_commercial_independence_gate_blocks_non_core_runtime_dependencies(tmp_path: Path) -> None:
    _write_minimal_product_tree(tmp_path, "numpy==1.26.4\nfastapi==0.111.0\n")

    payload = build_product_commercial_independence_gate(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_product_commercial_independence_gate"
    assert payload["summary"]["optional_profiles_separated"] is False
    assert next(row for row in payload["rows"] if row["check"] == "optional_profiles_separated")["status"] == "fail"


def test_product_commercial_independence_gate_blocks_missing_console_scripts(tmp_path: Path) -> None:
    _write_minimal_product_tree(tmp_path, "numpy==1.26.4\n")
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "betelgeuze-md-product"
version = "0.1.0"
requires-python = ">=3.11"

[project.scripts]
betelgeuze-product = "betelgeuze_product.cli:main"

[tool.setuptools.packages.find]
include = ["betelgeuze_product*"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    payload = build_product_commercial_independence_gate(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_product_commercial_independence_gate"
    assert payload["summary"]["pyproject_packaging_metadata_present"] is False
    assert payload["summary"]["package_discovery_present"] is False
    failed_checks = {row["check"] for row in payload["rows"] if row["status"] == "fail"}
    assert {"pyproject_packaging_metadata_present", "package_discovery_present"} <= failed_checks


def test_product_commercial_independence_gate_blocks_missing_entrypoint_target(tmp_path: Path) -> None:
    _write_minimal_product_tree(tmp_path, "numpy==1.26.4\n")
    (tmp_path / "betelgeuze_cleanup" / "cli.py").write_text("# missing main\n", encoding="utf-8")

    payload = build_product_commercial_independence_gate(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_product_commercial_independence_gate"
    assert payload["summary"]["console_entrypoint_targets_present"] is False
    assert payload["summary"]["missing_console_entrypoint_targets"] == [
        "betelgeuze-cleanup=missing_attr:betelgeuze_cleanup.cli:main"
    ]
    assert next(row for row in payload["rows"] if row["check"] == "console_entrypoint_targets_present")["status"] == "fail"
