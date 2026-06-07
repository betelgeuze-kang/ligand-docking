#!/usr/bin/python3
from __future__ import annotations

from tools.gpcr_replay.build_gpcr_coverage_v2_crossfit_rank_rescue_shadow_replay import *  # noqa: F401,F403
from tools.gpcr_replay.build_gpcr_coverage_v2_crossfit_rank_rescue_shadow_replay import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
