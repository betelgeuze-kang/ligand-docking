#!/usr/bin/python3
from __future__ import annotations

from tools.casp17.build_casp17_win_tier_metric_surface_contract import *  # noqa: F401,F403
from tools.casp17.build_casp17_win_tier_metric_surface_contract import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
