#!/usr/bin/env python3
from __future__ import annotations

from tools.casp17.apply_casp17_historical_seed_current_target_prefill import *  # noqa: F401,F403
from tools.casp17.apply_casp17_historical_seed_current_target_prefill import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
