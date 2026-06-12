#!/usr/bin/env python3
from __future__ import annotations

import runpy as _runpy
import sys as _sys

from tools.product.generate_perturbed_data import *  # noqa: F401,F403
from tools.product import generate_perturbed_data as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    _runpy.run_module("tools.product.generate_perturbed_data", run_name="__main__")
