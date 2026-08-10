from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from tools import build_engine_v2_wheel as wheel_builder


_VALID_MEMBERS = {
    "betelgeuze_engine_v2/__init__.py": b"",
    "betelgeuze_engine_v2/py.typed": b"",
    "betelgeuze_engine_v2/docking/synthetic_d0_fixture_admission.json": b"{}\n",
    "betelgeuze_engine_v2-0.2.0rc5.dist-info/METADATA": b"Metadata-Version: 2.4\n",
}


def _valid_wheel(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, payload in _VALID_MEMBERS.items():
            archive.writestr(name, payload)
    wheel_builder._verify_wheel_members(path)
    return path


@pytest.mark.parametrize(
    "leaked_member",
    (
        "benchmarks/",
        "benchmarks/oracles/openmm/adapter.py",
        "benchmarks.py",
        "betelgeuze_engine_v2-0.2.0rc5.data/purelib/benchmarks/oracles/openmm/adapter.py",
        "betelgeuze_engine_v2-0.2.0rc5.data/purelib/benchmarks.py",
        "another_distribution.data/platlib/benchmarks/oracles/vina/adapter.py",
        "another_distribution.data/platlib/benchmarks.py",
    ),
)
def test_forged_wheel_benchmark_mutations_fail_closed(
    tmp_path: Path,
    leaked_member: str,
) -> None:
    wheel = _valid_wheel(tmp_path / "valid.whl")
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr(leaked_member, b"forged benchmark payload")

    with pytest.raises(RuntimeError, match="benchmark oracle entered"):
        wheel_builder.verify_no_benchmark_package_members(wheel)
    with pytest.raises(RuntimeError, match="benchmark oracle entered"):
        wheel_builder._verify_wheel_members(wheel)


def test_data_scripts_named_benchmarks_is_not_an_importable_package(
    tmp_path: Path,
) -> None:
    wheel = _valid_wheel(tmp_path / "valid.whl")
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr(
            "betelgeuze_engine_v2-0.2.0rc5.data/scripts/benchmarks",
            b"#!/usr/bin/env python3\n",
        )

    wheel_builder._verify_wheel_members(wheel)


@pytest.mark.parametrize(
    "member",
    (
        "/benchmarks/oracles/openmm.py",
        "distribution.data/purelib/package/../benchmarks/oracles/vina.py",
        "distribution.data/purelib\\benchmarks.py",
        "distribution.data//purelib/benchmarks.py",
    ),
)
def test_noncanonical_wheel_member_paths_fail_closed(
    tmp_path: Path,
    member: str,
) -> None:
    wheel = _valid_wheel(tmp_path / "valid.whl")
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr(member, b"forged")

    with pytest.raises(RuntimeError, match="non-canonical member"):
        wheel_builder.verify_no_benchmark_package_members(wheel)
