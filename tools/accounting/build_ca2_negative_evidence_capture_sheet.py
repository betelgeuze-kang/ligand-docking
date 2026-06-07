#!/usr/bin/python3
from __future__ import annotations

from tools.product.build_ca2_negative_evidence_capture_sheet import *  # noqa: F401,F403
from tools.product.build_ca2_negative_evidence_capture_sheet import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
