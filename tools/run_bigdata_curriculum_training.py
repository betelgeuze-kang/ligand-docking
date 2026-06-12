"""Compatibility shim; canonical module: tools.product.run_bigdata_curriculum_training."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

from tools.product.run_bigdata_curriculum_training import *  # noqa: F401,F403
from tools.product.run_bigdata_curriculum_training import main as _main

_module = _import_module("tools.product.run_bigdata_curriculum_training")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
