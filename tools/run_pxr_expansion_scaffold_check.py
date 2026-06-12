#!/usr/bin/env python3
from __future__ import annotations

import importlib
import sys

from tools.product.run_pxr_expansion_scaffold_check import *  # noqa: F401,F403
from tools.product.run_pxr_expansion_scaffold_check import main as _main

_module = importlib.import_module("tools.product.run_pxr_expansion_scaffold_check")
sys.modules[__name__] = _module


if __name__ == "__main__":
    raise SystemExit(_main())
