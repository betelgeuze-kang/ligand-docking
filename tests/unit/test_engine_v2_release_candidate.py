from __future__ import annotations

import json
from pathlib import Path
import re

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10 CI
    import tomli as tomllib

from betelgeuze_engine_v2.contracts import (
    ALL_ATOM_SCHEMA_VERSION,
    CHECKPOINT_SCHEMA_VERSION,
    DISTRIBUTION_VERSION,
    ENGINE_API_VERSION,
    ENGINE_RESULT_SCHEMA_VERSION,
    RUNTIME_INPUT_SCHEMA_VERSION,
    VERSION_TAXONOMY,
)
from tools.build_engine_v2_sbom import SPDX_VERSION


def test_release_candidate_versions_and_typed_package_metadata_match() -> None:
    metadata = tomllib.loads(
        Path("packaging/engine-v2/pyproject.toml").read_text(encoding="utf-8")
    )
    assert DISTRIBUTION_VERSION == "0.2.0rc5"
    assert VERSION_TAXONOMY.distribution_version == DISTRIBUTION_VERSION
    assert ENGINE_API_VERSION == "2.0.0"
    assert ALL_ATOM_SCHEMA_VERSION == "2.0.0"
    assert ENGINE_RESULT_SCHEMA_VERSION == "2.0.0"
    assert CHECKPOINT_SCHEMA_VERSION == "2.0.0"
    assert RUNTIME_INPUT_SCHEMA_VERSION == "2.1.0"
    assert VERSION_TAXONOMY.engine_api_version != DISTRIBUTION_VERSION
    assert metadata["project"]["version"] == DISTRIBUTION_VERSION
    assert metadata["project"]["requires-python"] == ">=3.10,<3.13"
    assert set(metadata["project"]["dependencies"]) == {
        "cryptography==46.0.5",
        "numpy>=1.26,<3",
        "torch==2.6.0",
    }
    assert metadata["build-system"]["requires"] == [
        "setuptools==75.8.2",
        "wheel==0.45.1",
    ]
    assert "Typing :: Typed" in metadata["project"]["classifiers"]
    assert metadata["tool"]["setuptools"]["package-data"]["betelgeuze_engine_v2"] == ["py.typed"]
    assert metadata["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "betelgeuze_engine_v2*"
    ]
    assert Path("betelgeuze_engine_v2/py.typed").is_file()


def test_static_analysis_configuration_is_scoped_to_independent_contracts() -> None:
    pyright = json.loads(
        Path("packaging/engine-v2/pyrightconfig.json").read_text(encoding="utf-8")
    )
    assert pyright["typeCheckingMode"] == "basic"
    assert any("betelgeuze_engine_v2/contracts" in path for path in pyright["include"])
    assert "../../betelgeuze_engine_v2/molecular/legacy.py" in pyright["exclude"]
    assert pyright["extraPaths"] == ["../.."]

    metadata = tomllib.loads(
        Path("packaging/engine-v2/pyproject.toml").read_text(encoding="utf-8")
    )
    assert set(metadata["tool"]["ruff"]["lint"]["select"]) == {"E4", "E7", "E9", "F"}


def test_release_candidate_documents_preserve_non_promotion_boundary() -> None:
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/engine_v2_0_2_0rc5.md").read_text(encoding="utf-8")
    assert "0.2.0rc5" in changelog
    assert "does not establish" in changelog
    for flag in (
        "claim_safe",
        "scientifically_validated",
        "benchmark_validated",
        "customer_execution_enabled",
    ):
        assert f"{flag}=false" in release
        assert f"{flag}=true" not in release
    assert "byte-identical wheel SHA-256" in release


def test_sbom_contract_uses_spdx_23() -> None:
    assert SPDX_VERSION == "SPDX-2.3"
    source = Path("tools/build_engine_v2_sbom.py").read_text(encoding="utf-8")
    assert "DEPENDS_ON" in source
    assert "wheel_sha256" in source


def test_release_workflow_splits_pinned_static_and_matrix_jobs() -> None:
    workflow = Path(
        ".github/workflows/ci-engine-v2-release-candidate.yml"
    ).read_text(encoding="utf-8")
    assert "\n  static-analysis:\n" in workflow
    assert "\n  release-matrix:\n" in workflow
    assert 'python-version: "3.11"' in workflow
    assert 'python-version: ["3.10", "3.11", "3.12"]' in workflow
    assert "Upload static-analysis diagnostics\n        if: always()" in workflow
    assert "persist-credentials: false" in workflow
    assert "clean: true" in workflow
    assert workflow.count("python -m pip install pip==25.0.1") >= 2
    assert '"$venv/bin/python" -m pip install pip==25.0.1' in workflow
    assert "docs/engine_v2_pr_overlap_matrix.md" in workflow
    assert ".github/workflows/ci-engine-v2-release-candidate.yml" in workflow
    action_refs = re.findall(r"uses: [^@\s]+@([^\s]+)", workflow)
    assert action_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)


def test_all_wheel_build_lanes_install_the_exact_backend_contract() -> None:
    required = (
        "build==1.2.2.post1",
        "setuptools==75.8.2",
        "wheel==0.45.1",
    )
    for path in (
        ".github/workflows/ci-engine-v2-main.yml",
        ".github/workflows/ci-engine-v2-package.yml",
        ".github/workflows/ci-engine-v2-release-candidate.yml",
    ):
        workflow = Path(path).read_text(encoding="utf-8")
        for requirement in required:
            assert requirement in workflow, f"{path} does not install {requirement}"
