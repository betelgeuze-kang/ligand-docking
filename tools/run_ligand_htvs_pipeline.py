"""Compatibility shim; canonical module: betelgeuze_engine.product.runners.htvs_pipeline."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module
from pathlib import Path as _Path

_repo = _Path(__file__).resolve().parent
if str(_repo.parent) not in _sys.path:
    _sys.path.insert(0, str(_repo.parent))

from betelgeuze_engine.product.runners.htvs_pipeline import *  # noqa: F401,F403

_module = _import_module("betelgeuze_engine.product.runners.htvs_pipeline")
try:
    from tools.product.subprocess_runner import run_cmd as _p0_run_cmd

    _module._run_cmd = _p0_run_cmd
except Exception:  # pragma: no cover - keep legacy shim import-safe
    pass

_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_module.main())
