#!/usr/bin/env python3
from __future__ import annotations

from tools.product.build_refine_tier_public_benchmark_cv_failure_analysis_packet import *  # noqa: F401,F403
from tools.product.build_refine_tier_public_benchmark_cv_failure_analysis_packet import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
