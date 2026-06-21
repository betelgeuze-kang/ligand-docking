"""Compatibility shim; canonical module: betelgeuze_engine.product.runners.topk_delivery."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

from betelgeuze_engine.product.runners.topk_delivery import *  # noqa: F401,F403
from betelgeuze_engine.product.runners.topk_delivery import main as _main

_module = _import_module("betelgeuze_engine.product.runners.topk_delivery")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
