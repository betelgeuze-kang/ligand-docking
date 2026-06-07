#!/usr/bin/python3
from __future__ import annotations

from tools.gpcr_replay.build_gpcr_cationic_pose_distortion_frozen_cache_mode_review import *  # noqa: F401,F403
from tools.gpcr_replay.build_gpcr_cationic_pose_distortion_frozen_cache_mode_review import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
