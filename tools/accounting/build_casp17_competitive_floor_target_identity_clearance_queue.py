#!/usr/bin/env python3
from __future__ import annotations

from tools.casp17.build_casp17_competitive_floor_target_identity_clearance_queue import *  # noqa: F401,F403
from tools.casp17.build_casp17_competitive_floor_target_identity_clearance_queue import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
