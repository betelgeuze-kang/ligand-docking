#!/usr/bin/env python3
from __future__ import annotations

import runpy as _runpy
import sys as _sys

from tools.wetlab.wetlab_broad_screen_antitarget_watcher_state import *  # noqa: F401,F403
from tools.wetlab import wetlab_broad_screen_antitarget_watcher_state as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    _runpy.run_module("tools.wetlab.wetlab_broad_screen_antitarget_watcher_state", run_name="__main__")
