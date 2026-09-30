#!/usr/bin/env python3
"""Repository CLI for the fixed public 5-HT6 transcription reconciliation."""
# ruff: noqa: E402
from pathlib import Path
import sys

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from tools.product.primary_5ht6_2024_cross_artifact_reconciliation_v1 import main


if __name__ == "__main__":
    raise SystemExit(main())
