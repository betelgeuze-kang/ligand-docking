#!/usr/bin/env python3
from __future__ import annotations

from tools.wetlab.monitor_wetlab_broad_screen import *  # noqa: F401,F403
from tools.wetlab.monitor_wetlab_broad_screen import parse_args as _parse_args
from tools.wetlab.monitor_wetlab_broad_screen import run_monitor as _run_monitor


if __name__ == "__main__":
    _run_monitor(_parse_args())
