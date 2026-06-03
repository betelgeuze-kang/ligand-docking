from __future__ import annotations

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


def test_product_commercial_independence_gate_ready_for_pinned_local_product_tree(tmp_path: Path) -> None:
    _write_minimal_product_tree(tmp_path, "numpy==1.26.4\ntorch==2.3.1\npydantic==2.7.4\n")

    payload = build_product_commercial_independence_gate(root=tmp_path)

    assert payload["summary"]["status"] == "product_commercial_independence_gate_ready"
    assert payload["summary"]["commercial_independent_product_claim_allowed"] is True
    assert payload["summary"]["product_cli_surface_present"] is True
    assert payload["summary"]["pyproject_packaging_metadata_present"] is True
    assert payload["summary"]["package_discovery_present"] is True
    assert payload["summary"]["console_entrypoint_targets_present"] is True
    assert payload["summary"]["blocker_count"] == 0
    assert all(row["status"] == "pass" for row in payload["rows"])


def test_product_commercial_independence_gate_blocks_loose_external_runtime_and_missing_license(tmp_path: Path) -> None:
    _write_minimal_product_tree(tmp_path, "numpy\ntorch\nopenai\n", license_text="")

    payload = build_product_commercial_independence_gate(root=tmp_path)

    assert payload["summary"]["status"] == "blocked_product_commercial_independence_gate"
    assert payload["summary"]["commercial_independent_product_claim_allowed"] is False
    assert payload["summary"]["loose_runtime_dependency_count"] == 3
    assert payload["summary"]["external_api_runtime_dependencies"] == ["openai"]
    failed_checks = {row["check"] for row in payload["rows"] if row["status"] == "fail"}
    assert {"license_file_present", "runtime_dependencies_pinned", "external_api_free_core_runtime"} <= failed_checks


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
