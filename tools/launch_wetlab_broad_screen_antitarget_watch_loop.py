#!/usr/bin/env python3
from __future__ import annotations

from tools.wetlab.launch_wetlab_broad_screen_antitarget_watch_loop import *  # noqa: F401,F403
from tools.wetlab.launch_wetlab_broad_screen_antitarget_watch_loop import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
