#!/usr/bin/python3
from __future__ import annotations

from tools.wetlab.build_wetlab_wave1_target_packets import *  # noqa: F401,F403
from tools.wetlab.build_wetlab_wave1_target_packets import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
