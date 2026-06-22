#!/usr/bin/env python3
"""Compatibility shim; canonical module: betelgeuze_engine.product.runners.tier_beta_vertical_slice."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module
from pathlib import Path as _Path

_repo = _Path(__file__).resolve().parent
if str(_repo.parent) not in _sys.path:
    _sys.path.insert(0, str(_repo.parent))

from betelgeuze_engine.product.runners.tier_beta_vertical_slice import *  # noqa: E402,F401,F403
from betelgeuze_engine.product.runners.tier_beta_vertical_slice import main as _main  # noqa: E402

_module = _import_module("betelgeuze_engine.product.runners.tier_beta_vertical_slice")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
