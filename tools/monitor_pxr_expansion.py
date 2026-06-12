#!/usr/bin/env python3
from __future__ import annotations

import importlib
import sys

from tools.product.monitor_pxr_expansion import *  # noqa: F401,F403
from tools.product.monitor_pxr_expansion import main as _main

_module = importlib.import_module("tools.product.monitor_pxr_expansion")
sys.modules[__name__] = _module


if __name__ == "__main__":
    raise SystemExit(_main())
