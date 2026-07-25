from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import zipfile

import pytest

from betelgeuze_engine_v2 import DISTRIBUTION_NAME, DISTRIBUTION_VERSION
from tools.check_engine_v2_architecture import inspect_package


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "betelgeuze_engine_v2"
PREFLIGHT = ROOT / "betelgeuze_engine_v2_preflight.py"
METADATA = ROOT / "packaging" / "engine-v2" / "pyproject.toml"
BUILDER = ROOT / "tools" / "build_engine_v2_wheel.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "engine_v2_wheel_builder_for_tests",
        BUILDER,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_independent_package_metadata_matches_version_taxonomy() -> None:
    text = METADATA.read_text(encoding="utf-8")
    name = re.search(r'^name\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    version = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    python_range = re.search(
        r'^requires-python\s*=\s*"([^"]+)"',
        text,
        flags=re.MULTILINE,
    )
    assert name and name.group(1) == DISTRIBUTION_NAME
    assert version and version.group(1) == DISTRIBUTION_VERSION
    assert python_range and python_range.group(1) == ">=3.10,<3.13"
    assert '"cryptography==46.0.5"' in text
    assert '"torch==2.6.0"' in text
    assert '"numpy>=1.26,<3"' in text
    assert 'include = ["betelgeuze_engine_v2*"]' in text
    assert 'py-modules = ["betelgeuze_engine_v2_preflight"]' in text
    assert (
        'betelgeuze-engine-v2 = "betelgeuze_engine_v2_preflight:main"'
        in text
    )
    assert (
        'betelgeuze-engine-v2 = "betelgeuze_engine_v2.cli_dispatch:main"'
        not in text
    )


def test_ast_architecture_guard_accepts_canonical_engine_package() -> None:
    violations = inspect_package(PACKAGE.resolve())
    assert violations == []


def test_overlap_matrix_records_both_independent_merge_lanes() -> None:
    text = (ROOT / "docs" / "engine_v2_pr_overlap_matrix.md").read_text(
        encoding="utf-8"
    )
    for marker in ("#43", "#44", "#45", "#46", "#47", "#48", "#49"):
        assert marker in text
    assert "#50 -> #51 -> #52 -> #53 -> #54 -> V2-F" in text
    assert "#44 -> #45 -> #46 -> #47 -> #48" in text
    assert "통째 병합 금지" in text


def test_package_and_preflight_sources_have_no_legacy_runtime_imports() -> None:
    assert PREFLIGHT.is_file()
    forbidden = (
        "from api",
        "import api",
        "from core",
        "import core",
        "from train",
        "import train",
        "from betelgeuze_product",
        "import betelgeuze_product",
    )
    sources = [PREFLIGHT]
    sources.extend(sorted(PACKAGE.rglob("*.py")))
    for path in sources:
        source = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in source, f"{path} contains {marker!r}"


def test_isolated_builder_whitelists_package_and_preflight_only() -> None:
    builder = _load_builder()
    assert builder.PACKAGE_NAME == "betelgeuze_engine_v2"
    assert builder.PREFLIGHT_MODULE_NAME == "betelgeuze_engine_v2_preflight.py"
    assert builder.ALLOWED_TOP_LEVEL == {
        "betelgeuze_engine_v2",
        "betelgeuze_engine_v2_preflight.py",
    }
    assert "api/" in builder.FORBIDDEN_WHEEL_PREFIXES
    assert "core/" in builder.FORBIDDEN_WHEEL_PREFIXES
    assert "train/" in builder.FORBIDDEN_WHEEL_PREFIXES
    assert "betelgeuze_product/" in builder.FORBIDDEN_WHEEL_PREFIXES


def test_wheel_member_guard_rejects_legacy_payload(tmp_path: Path) -> None:
    builder = _load_builder()
    wheel = tmp_path / "invalid.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("betelgeuze_engine_v2/__init__.py", "")
        archive.writestr("betelgeuze_engine_v2_preflight.py", "")
        archive.writestr("core/secret.py", "VALUE = 1\n")
        archive.writestr(
            "betelgeuze_engine_v2-0.2.0rc2.dist-info/METADATA",
            "Name: betelgeuze-engine-v2\nVersion: 0.2.0rc2\n",
        )
    with pytest.raises(
        SystemExit,
        match="unexpected top-level|forbidden legacy",
    ):
        builder._verify_wheel_members(wheel)


def test_wheel_member_guard_requires_preflight_launcher(tmp_path: Path) -> None:
    builder = _load_builder()
    wheel = tmp_path / "missing-preflight.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("betelgeuze_engine_v2/__init__.py", "")
        archive.writestr(
            "betelgeuze_engine_v2-0.2.0rc2.dist-info/METADATA",
            "Name: betelgeuze-engine-v2\nVersion: 0.2.0rc2\n",
        )
    with pytest.raises(SystemExit, match="missing the stdlib-only preflight"):
        builder._verify_wheel_members(wheel)
