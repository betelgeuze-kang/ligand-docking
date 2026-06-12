#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.append_keep_green_lane_history import *  # noqa: F401,F403
from tools.product.append_keep_green_lane_history import main as _main
from tools.product import append_keep_green_lane_history as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    _main()
