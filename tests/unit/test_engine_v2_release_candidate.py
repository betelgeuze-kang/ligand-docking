from __future__ import annotations

import json
from pathlib import Path
import tomllib

from betelgeuze_engine_v2.contracts import DISTRIBUTION_VERSION, VERSION_TAXONOMY
from tools.build_engine_v2_sbom import SPDX_VERSION


def test_release_candidate_versions_and_typed_package_metadata_match() -> None:
    metadata = tomllib.loads(
        Path("packaging/engine-v2/pyproject.toml").read_text(encoding="utf-8")
    )
    assert DISTRIBUTION_VERSION == "0.2.0rc1"
    assert VERSION_TAXONOMY.distribution_version == DISTRIBUTION_VERSION
    assert metadata["project"]["version"] == DISTRIBUTION_VERSION
    assert metadata["project"]["requires-python"] == ">=3.10,<3.13"
    assert "Typing :: Typed" in metadata["project"]["classifiers"]
    assert metadata["tool"]["setuptools"]["package-data"]["betelgeuze_engine_v2"] == ["py.typed"]
    assert Path("betelgeuze_engine_v2/py.typed").is_file()


def test_static_analysis_configuration_is_scoped_to_independent_contracts() -> None:
    pyright = json.loads(
        Path("packaging/engine-v2/pyrightconfig.json").read_text(encoding="utf-8")
    )
    assert pyright["typeCheckingMode"] == "basic"
    assert any("betelgeuze_engine_v2/contracts" in path for path in pyright["include"])
    assert "../../betelgeuze_engine_v2/molecular/legacy.py" in pyright["exclude"]

    metadata = tomllib.loads(
        Path("packaging/engine-v2/pyproject.toml").read_text(encoding="utf-8")
    )
    assert set(metadata["tool"]["ruff"]["lint"]["select"]) == {"E4", "E7", "E9", "F"}


def test_release_candidate_documents_preserve_non_promotion_boundary() -> None:
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    release = Path("docs/engine_v2_0_2_0rc1.md").read_text(encoding="utf-8")
    assert "0.2.0rc1" in changelog
    assert "does not establish" in changelog
    assert "claim_safe=true" in release
    assert "customer_execution_enabled=true" in release
    assert "byte-identical wheel SHA-256" in release


def test_sbom_contract_uses_spdx_23() -> None:
    assert SPDX_VERSION == "SPDX-2.3"
    source = Path("tools/build_engine_v2_sbom.py").read_text(encoding="utf-8")
    assert "DEPENDS_ON" in source
    assert "wheel_sha256" in source
