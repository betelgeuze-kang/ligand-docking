from __future__ import annotations

from pathlib import Path
import re

from betelgeuze_engine_v2 import DISTRIBUTION_NAME, DISTRIBUTION_VERSION
from tools.check_engine_v2_architecture import inspect_package


def test_independent_package_metadata_matches_version_taxonomy() -> None:
    text = Path("packaging/engine-v2/pyproject.toml").read_text(encoding="utf-8")
    name = re.search(r'^name\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    version = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    python_range = re.search(r'^requires-python\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    assert name and name.group(1) == DISTRIBUTION_NAME
    assert version and version.group(1) == DISTRIBUTION_VERSION
    assert python_range and python_range.group(1) == ">=3.10,<3.13"
    assert '"cryptography==46.0.5"' in text
    assert '"torch==2.6.0"' in text
    assert '"numpy>=1.26,<3"' in text
    assert 'include = ["betelgeuze_engine_v2*"]' in text


def test_ast_architecture_guard_accepts_canonical_engine_package() -> None:
    violations = inspect_package(Path("betelgeuze_engine_v2").resolve())
    assert violations == []


def test_overlap_matrix_records_both_independent_merge_lanes() -> None:
    text = Path("docs/engine_v2_pr_overlap_matrix.md").read_text(encoding="utf-8")
    for marker in ("#43", "#44", "#45", "#46", "#47", "#48", "#49"):
        assert marker in text
    assert "#50 -> #51 -> #52 -> #53 -> #54 -> V2-F" in text
    assert "#44 -> #45 -> #46 -> #47 -> #48" in text
    assert "통째 병합 금지" in text
