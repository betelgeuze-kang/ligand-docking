from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPOSITORY_ROOT / ".github/workflows/ci-external-oracle-pack.yml"
ORACLE_REQUIREMENTS = (
    REPOSITORY_ROOT / "benchmarks/oracles/requirements-ci-py311-linux-x86_64.txt"
)


def test_external_oracle_ci_paths_cover_pack_and_contract_tests() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    for path_filter in (
        '      - "benchmarks/**"',
        '      - "tests/unit/test_external_oracle_*.py"',
        '      - "tests/unit/test_external_engine_adapters.py"',
    ):
        assert source.count(path_filter) == 2


def test_external_oracle_ci_pins_composite_runtime_and_sandbox() -> None:
    requirements = ORACLE_REQUIREMENTS.read_text(encoding="utf-8")
    assert "numpy==1.26.4" in requirements
    assert "openmm==8.4.0.post2" in requirements
    assert requirements.count("--hash=sha256:") == 2
    assert (
        "666dbfb6ec68962c033a450943ded891bed2d54e6755e35e5835d63f4f6931d5"
        in requirements
    )
    assert (
        "12ffcd82d596bded1382e30af55907754ee481aafc0fc4a921a97de2ea7a8c55"
        in requirements
    )

    source = WORKFLOW.read_text(encoding="utf-8")
    assert "runs-on: ubuntu-22.04" in source
    assert "command -v unshare" in source
    assert "unshare --version" in source
    for namespace_flag in (
        "--user",
        "--map-current-user",
        "--ipc",
        "--net",
        "--pid",
        "--uts",
        "--fork",
        "--kill-child=SIGKILL",
        "--mount-proc",
    ):
        assert namespace_flag in source
    assert 'ctypes.util.find_library("seccomp")' in source
    assert 'library.endswith(".so.2")' in source
    assert "sudo apt-get" not in source
    assert "sudo apt " not in source
    assert "--require-hashes" in source
    assert "--only-binary=:all:" in source
    assert "openmm_runtime_dependency_distributions_sha256" in source
    assert 'approved_versions = {"OpenMM": "8.4.0.post2", "numpy": "1.26.4"}' in source
    assert '"betelgeuze.openmm_runtime_dependency_distributions/3.0.0"' in source
    assert (
        "APPROVED_RUNTIME_SHA256 = (\n"
        '              "093f35a9cca838d4bf2d35c03c092aef2aed2e85f1e9c22cd1428dae7e92df38"'
        in source
    )
    assert 'APPROVED_RUNTIME_ARTIFACT_COUNTS = {"OpenMM": 523, "numpy": 913}' in source
    assert "assert first == second == APPROVED_RUNTIME_SHA256" in source
    assert "tools/verify_product_docker_context.py" in source
