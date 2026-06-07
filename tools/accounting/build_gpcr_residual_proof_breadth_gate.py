#!/usr/bin/python3
from __future__ import annotations

from tools.product.build_gpcr_residual_proof_breadth_gate import *  # noqa: F401,F403
from tools.product.build_gpcr_residual_proof_breadth_gate import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
