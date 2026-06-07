#!/usr/bin/python3
from __future__ import annotations

from tools.product.build_public_benchmark_residual_regression_gate import *  # noqa: F401,F403
from tools.product.build_public_benchmark_residual_regression_gate import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
