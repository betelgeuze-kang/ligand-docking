#!/usr/bin/env python3
from __future__ import annotations

import importlib

_module = importlib.import_module("tools.gpcr_replay.build_gpcr_frozen_trajectory_storage_gap_packet")

if __name__ == "__main__":
    main = getattr(_module, "main", None)
    if main is None:
        raise SystemExit("builder has no main(): tools.gpcr_replay.build_gpcr_frozen_trajectory_storage_gap_packet")
    main()
