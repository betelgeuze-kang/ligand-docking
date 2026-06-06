#!/usr/bin/python3
from __future__ import annotations

from tools.casp17.build_casp17_historical_winner_normalized_bands import *  # noqa: F401,F403
from tools.casp17.build_casp17_historical_winner_normalized_bands import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
