"""Compatibility shim; canonical module: tools.product.promote_biorxiv_external_validation_package."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

from tools.product.promote_biorxiv_external_validation_package import *  # noqa: F401,F403
from tools.product.promote_biorxiv_external_validation_package import main as _main

_module = _import_module("tools.product.promote_biorxiv_external_validation_package")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
