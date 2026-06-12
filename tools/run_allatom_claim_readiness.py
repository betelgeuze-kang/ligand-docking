"""Compatibility shim; canonical module: tools.product.run_allatom_claim_readiness."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

from tools.product.run_allatom_claim_readiness import *  # noqa: F401,F403
from tools.product.run_allatom_claim_readiness import main as _main

_module = _import_module("tools.product.run_allatom_claim_readiness")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
