"""Compatibility shim; canonical module: tools.product.tune_target_neighbor_rebuild."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module
from pathlib import Path as _Path

_repo = _Path(__file__).resolve().parent
if str(_repo.parent) not in _sys.path:
    _sys.path.insert(0, str(_repo.parent))

from tools.product.tune_target_neighbor_rebuild import *  # noqa: F401,F403
from tools.product.tune_target_neighbor_rebuild import main as _main

_module = _import_module("tools.product.tune_target_neighbor_rebuild")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
