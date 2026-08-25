#!/usr/bin/env python3
"""Render or check the Engine V2 current-state Markdown companion."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from verify_engine_v2_current_state_v1 import (
    CurrentStateError,
    _load_json,
    render_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    source = root / "config/engine_v2_current_state_v1.json"
    output = root / "docs/engine_v2_current_state_v1.md"
    try:
        rendered = render_markdown(_load_json(source)).encode("utf-8")
    except (CurrentStateError, KeyError, TypeError) as exc:
        print(f"current-state render failed: {exc}", file=sys.stderr)
        return 1

    if args.check:
        try:
            observed = output.read_bytes()
        except OSError as exc:
            print(f"current-state check failed: {exc}", file=sys.stderr)
            return 1
        if observed != rendered:
            print(
                "current-state check failed: Markdown is not the exact rendered JSON summary",
                file=sys.stderr,
            )
            return 1
        print("current-state Markdown matches the JSON source")
        return 0

    if args.write:
        output.write_bytes(rendered)
        print(output)
        return 0

    sys.stdout.buffer.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
