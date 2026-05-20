#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENV_COMMAND_TEMPLATE = "CASP17_STRUCTURE_PREDICTOR_COMMAND"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _render(args: argparse.Namespace) -> str:
    template = _text(args.predictor_command_template) or _text(os.environ.get(ENV_COMMAND_TEMPLATE))
    if not template:
        raise ValueError(
            f"missing predictor command template; pass --predictor-command-template or set {ENV_COMMAND_TEMPLATE}"
        )
    values = {
        "target_id": _text(args.target_id).upper(),
        "fasta": _artifact(args.fasta),
        "sequence_path": _artifact(args.fasta),
        "out_dir": _artifact(args.out_dir),
        "raw_pdb": _artifact(args.raw_pdb),
    }
    return template.format(**values)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed adapter that renders and runs an operator-supplied CASP17 structure predictor command."
    )
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--fasta", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--raw-pdb", required=True)
    parser.add_argument("--predictor-command-template", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    out_dir = _resolve(args.out_dir)
    raw_pdb = _resolve(args.raw_pdb)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_pdb.parent.mkdir(parents=True, exist_ok=True)
    try:
        rendered = _render(args)
    except ValueError as exc:
        print(str(exc))
        raise SystemExit(2)
    print(f"CASP17 external predictor adapter command: {rendered}")
    run = subprocess.run(shlex.split(rendered), check=False, cwd=str(ROOT))
    raise SystemExit(int(run.returncode))


if __name__ == "__main__":
    main()
