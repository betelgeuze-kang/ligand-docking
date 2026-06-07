#!/usr/bin/python3
from __future__ import annotations

from tools.casp17.sync_casp17_historical_seed_clearance_to_identity_intake import *  # noqa: F401,F403
from tools.casp17.sync_casp17_historical_seed_clearance_to_identity_intake import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
