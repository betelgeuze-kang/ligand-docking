#!/usr/bin/env python3
from __future__ import annotations

import importlib
import runpy
import sys

from tools.wetlab.run_wetlab_broad_screen_antitarget_runner import *  # noqa: F401,F403

_module = importlib.import_module("tools.wetlab.run_wetlab_broad_screen_antitarget_runner")
sys.modules[__name__] = _module


if __name__ == "__main__":
    runpy.run_module("tools.wetlab.run_wetlab_broad_screen_antitarget_runner", run_name="__main__")
