#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from betelgeuze_product.capability_matrix import (  # noqa: E402
    build_product_capability_matrix_verification,
    load_product_capability_matrix,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the local BioDiscovery product capability matrix.")
    parser.add_argument("--matrix", default="config/product_capability_matrix.yaml", help="Capability matrix YAML path.")
    parser.add_argument("--out-json", default="", help="Optional path to write the verification payload.")
    parser.add_argument("--quiet", action="store_true", help="Do not print the JSON payload to stdout.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    matrix_path = Path(args.matrix)
    matrix_path = matrix_path if matrix_path.is_absolute() else ROOT / matrix_path
    payload = build_product_capability_matrix_verification(load_product_capability_matrix(matrix_path))
    if args.out_json:
        out_path = Path(args.out_json)
        out_path = out_path if out_path.is_absolute() else ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if not args.quiet:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if payload["summary"]["capability_matrix_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
