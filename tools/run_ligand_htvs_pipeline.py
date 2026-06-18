"""Compatibility shim; canonical module: betelgeuze_engine.product.runners.htvs_pipeline."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module
from pathlib import Path as _Path

_repo = _Path(__file__).resolve().parent
if str(_repo.parent) not in _sys.path:
    _sys.path.insert(0, str(_repo.parent))

from betelgeuze_engine.product.runners.htvs_pipeline import *  # noqa: F401,F403
from betelgeuze_engine.product.runners.htvs_pipeline import main as _main

_module = _import_module("betelgeuze_engine.product.runners.htvs_pipeline")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
