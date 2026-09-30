#!/usr/bin/env python3
"""Repository CLI for public 5-HT6 endpoint/prepared-model evidence intake."""
# ruff: noqa: E402
from pathlib import Path
import sys

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from tools.product.primary_5ht6_endpoint_prepared_intake_v1 import main


if __name__ == "__main__":
    raise SystemExit(main())
