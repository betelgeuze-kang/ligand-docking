#!/usr/bin/env python3
"""Build the isolated Engine v2 wheel with deterministic archive inputs."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ALLOWED_TOP_LEVEL = {"betelgeuze_engine_v2"}
PROHIBITED_WHEEL_PREFIXES = (
    "api/",
    "core/",
    "train/",
    "betelgeuze_engine/",
    "betelgeuze_product/",
    "betelgeuze_ai_md/",
)
DEFAULT_SOURCE_DATE_EPOCH = 1_735_689_600  # 2025-01-01T00:00:00Z


def _verify_wheel_members(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
    for member in members:
        if member.startswith(PROHIBITED_WHEEL_PREFIXES):
            raise RuntimeError(f"prohibited package entered Engine v2 wheel: {member}")
    package_members = [name for name in members if name.startswith("betelgeuze_engine_v2/")]
    if not package_members:
        raise RuntimeError("Engine v2 wheel contains no betelgeuze_engine_v2 package")
    if "betelgeuze_engine_v2/py.typed" not in package_members:
        raise RuntimeError("Engine v2 wheel is missing the PEP 561 py.typed marker")
    admission_resource = (
        "betelgeuze_engine_v2/docking/synthetic_d0_fixture_admission.json"
    )
    if admission_resource not in package_members:
        raise RuntimeError(
            "Engine v2 wheel is missing the synthetic D0 admission manifest"
        )
    top_levels = {
        member.split("/", 1)[0]
        for member in members
        if ".dist-info/" not in member and ".data/" not in member
    }
    unexpected = sorted(top_levels - ALLOWED_TOP_LEVEL)
    if unexpected:
        raise RuntimeError("unexpected top-level wheel packages: " + ", ".join(unexpected))


def _normalized_epoch(value: int | str | None) -> int:
    raw = DEFAULT_SOURCE_DATE_EPOCH if value is None else int(value)
    # ZIP timestamps cannot predate 1980; wheel tooling also expects an integer.
    return max(raw, 315_532_800)


def _normalize_build_tree(path: Path, *, epoch: int) -> None:
    for candidate in sorted(path.rglob("*")):
        if candidate.name == "__pycache__" and candidate.is_dir():
            shutil.rmtree(candidate)
            continue
        if candidate.is_symlink():
            raise RuntimeError(f"Engine v2 build context may not contain symlinks: {candidate}")
        os.utime(candidate, (epoch, epoch), follow_symlinks=False)
    os.utime(path, (epoch, epoch), follow_symlinks=False)


def build_wheel(
    repository_root: Path,
    output_dir: Path,
    *,
    source_date_epoch: int | str | None = None,
) -> Path:
    source_package = repository_root / "betelgeuze_engine_v2"
    package_pyproject = repository_root / "packaging" / "engine-v2" / "pyproject.toml"
    if not source_package.is_dir():
        raise FileNotFoundError(f"missing source package: {source_package}")
    if not package_pyproject.is_file():
        raise FileNotFoundError(f"missing package metadata: {package_pyproject}")

    epoch = _normalized_epoch(source_date_epoch or os.environ.get("SOURCE_DATE_EPOCH"))
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("betelgeuze_engine_v2-*.whl"):
        stale.unlink()

    with tempfile.TemporaryDirectory(prefix="betelgeuze-engine-v2-build-") as tmp:
        build_root = Path(tmp)
        shutil.copytree(
            source_package,
            build_root / "betelgeuze_engine_v2",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
        )
        shutil.copy2(package_pyproject, build_root / "pyproject.toml")
        _normalize_build_tree(build_root, epoch=epoch)
        env = dict(os.environ)
        env.update(
            {
                "SOURCE_DATE_EPOCH": str(epoch),
                "PYTHONHASHSEED": "0",
                "TZ": "UTC",
                "LC_ALL": "C.UTF-8",
                "LANG": "C.UTF-8",
            }
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--no-isolation",
                "--outdir",
                str(output_dir.resolve()),
                str(build_root),
            ],
            check=True,
            env=env,
        )

    wheels = sorted(output_dir.glob("betelgeuze_engine_v2-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected exactly one Engine v2 wheel, observed {len(wheels)}")
    _verify_wheel_members(wheels[0])
    return wheels[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--output-dir", default="dist-engine-v2")
    parser.add_argument("--source-date-epoch", type=int)
    args = parser.parse_args()
    wheel = build_wheel(
        Path(args.repository_root).resolve(),
        Path(args.output_dir).resolve(),
        source_date_epoch=args.source_date_epoch,
    )
    print(wheel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
