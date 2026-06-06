#!/usr/bin/python3
from __future__ import annotations

from tools.gpcr_replay.build_gpcr_atom_window_anchor_feature_cache import *  # noqa: F401,F403
from tools.gpcr_replay.build_gpcr_atom_window_anchor_feature_cache import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
