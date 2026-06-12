"""Compatibility shim; canonical module: tools.product.run_openmm_2bead_strict_release."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module
from pathlib import Path as _Path

_repo = _Path(__file__).resolve().parent
if str(_repo.parent) not in _sys.path:
    _sys.path.insert(0, str(_repo.parent))

from tools.product.run_openmm_2bead_strict_release import *  # noqa: F401,F403
from tools.product.run_openmm_2bead_strict_release import main as _main

_module = _import_module("tools.product.run_openmm_2bead_strict_release")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
