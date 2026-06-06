#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build local Rust HIP extension for ldi_arc_rust.")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("rust_engine"),
        help="Path to Rust crate directory containing Cargo.toml",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Build debug profile instead of release",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("."),
        help="Directory to place built Python extension",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    profile = "debug" if args.debug else "release"
    cmd = ["cargo", "build", "--release"] if profile == "release" else ["cargo", "build"]
    subprocess.check_call(cmd, cwd=str(source))

    lib_name = "libldi_arc_rust.so"
    built_lib = source / "target" / profile / lib_name
    if not built_lib.exists():
        raise FileNotFoundError(f"Built library not found: {built_lib}")

    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if not ext_suffix:
        raise RuntimeError("Failed to determine Python EXT_SUFFIX")
    dst = output_dir / f"ldi_arc_rust{ext_suffix}"
    shutil.copy2(built_lib, dst)
    print(f"Built and copied: {dst}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
