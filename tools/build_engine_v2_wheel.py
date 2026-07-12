#!/usr/bin/env python3
"""Build the independent Engine v2 wheel from the canonical source package.

The monorepo product ``pyproject.toml`` intentionally remains unchanged. This
script creates a temporary build context containing only ``betelgeuze_engine_v2``
and the dedicated package metadata, preventing API, legacy core, product, train,
or operations modules from entering the wheel.
"""

from __future__ import annotations

import argparse
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


def _verify_wheel_members(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if not name.endswith("/")]
    for member in members:
        if member.startswith(PROHIBITED_WHEEL_PREFIXES):
            raise RuntimeError(f"prohibited package entered Engine v2 wheel: {member}")
    package_members = [name for name in members if name.startswith("betelgeuze_engine_v2/")]
    if not package_members:
        raise RuntimeError("Engine v2 wheel contains no betelgeuze_engine_v2 package")
    top_levels = {
        member.split("/", 1)[0]
        for member in members
        if ".dist-info/" not in member and ".data/" not in member
    }
    unexpected = sorted(top_levels - ALLOWED_TOP_LEVEL)
    if unexpected:
        raise RuntimeError("unexpected top-level wheel packages: " + ", ".join(unexpected))


def build_wheel(repository_root: Path, output_dir: Path) -> Path:
    source_package = repository_root / "betelgeuze_engine_v2"
    package_pyproject = repository_root / "packaging" / "engine-v2" / "pyproject.toml"
    if not source_package.is_dir():
        raise FileNotFoundError(f"missing source package: {source_package}")
    if not package_pyproject.is_file():
        raise FileNotFoundError(f"missing package metadata: {package_pyproject}")

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="betelgeuze-engine-v2-build-") as tmp:
        build_root = Path(tmp)
        shutil.copytree(source_package, build_root / "betelgeuze_engine_v2")
        shutil.copy2(package_pyproject, build_root / "pyproject.toml")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(output_dir.resolve()),
                str(build_root),
            ],
            check=True,
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
    args = parser.parse_args()
    wheel = build_wheel(
        Path(args.repository_root).resolve(),
        Path(args.output_dir).resolve(),
    )
    print(wheel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
