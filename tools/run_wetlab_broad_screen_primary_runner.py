#!/usr/bin/env python3
from __future__ import annotations

import runpy as _runpy
import sys as _sys

from tools.wetlab.run_wetlab_broad_screen_primary_runner import *  # noqa: F401,F403
from tools.wetlab import run_wetlab_broad_screen_primary_runner as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    _runpy.run_module("tools.wetlab.run_wetlab_broad_screen_primary_runner", run_name="__main__")
