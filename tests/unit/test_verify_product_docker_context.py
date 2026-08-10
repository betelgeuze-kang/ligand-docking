from __future__ import annotations

from pathlib import Path

import pytest

from tools.check_external_oracle_architecture import (
    LEGACY_BENCHMARK_DOCKER_EXCLUSIONS,
)
from tools.verify_product_docker_context import (
    MANDATORY_ORACLE_EXCLUSIONS,
    materialize_product_context,
)


_DOCKING_SEARCH_V2_OPERATOR_EXCLUSIONS = {
    "tools/run_docking_search_v2_development_cohort.py",
    "tools/benchmarking/__init__.py",
    "tools/benchmarking/build_docking_search_v2_development_evidence.py",
}


def _write(path: Path, payload: str = "fixture\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _fixture(root: Path) -> None:
    _write(root / "Dockerfile.product", "FROM scratch\nCOPY tools ./tools\n")
    _write(root / "tools/product_runtime.py")
    _write(root / "benchmarks/oracles/forged.py")
    for relative in LEGACY_BENCHMARK_DOCKER_EXCLUSIONS:
        _write(root / relative)
    lines = [
        "*",
        "!Dockerfile.product",
        "!tools",
        "!tools/**",
        "benchmarks",
        "benchmarks/**",
        *sorted(LEGACY_BENCHMARK_DOCKER_EXCLUSIONS),
    ]
    _write(root / ".dockerignore", "\n".join(lines) + "\n")


def test_materialized_product_context_is_oracle_free_and_deterministic(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repository"
    _fixture(root)

    first = materialize_product_context(root, tmp_path / "context-a")
    second = materialize_product_context(root, tmp_path / "context-b")

    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert first["file_count"] == second["file_count"] == 2
    assert (tmp_path / "context-a/tools/product_runtime.py").is_file()
    assert not (tmp_path / "context-a/benchmarks").exists()
    for relative in LEGACY_BENCHMARK_DOCKER_EXCLUSIONS:
        assert not (tmp_path / "context-a" / relative).exists()
    assert _DOCKING_SEARCH_V2_OPERATOR_EXCLUSIONS.issubset(
        LEGACY_BENCHMARK_DOCKER_EXCLUSIONS
    )


@pytest.mark.parametrize(
    "deleted_rule",
    sorted(MANDATORY_ORACLE_EXCLUSIONS),
)
def test_deleting_mandatory_dockerignore_rows_fails_closed(
    tmp_path: Path,
    deleted_rule: str,
) -> None:
    root = tmp_path / "repository"
    _fixture(root)
    dockerignore = root / ".dockerignore"
    lines = dockerignore.read_text(encoding="utf-8").splitlines()
    lines.remove(deleted_rule)
    dockerignore.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(
        RuntimeError, match="mandatory oracle Docker exclusions missing"
    ):
        materialize_product_context(root, tmp_path / "context")


def test_late_dockerignore_reinclusion_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    _fixture(root)
    dockerignore = root / ".dockerignore"
    dockerignore.write_text(
        dockerignore.read_text(encoding="utf-8") + "!benchmarks/**\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError, match="oracle file entered product Docker context"
    ):
        materialize_product_context(root, tmp_path / "context")
