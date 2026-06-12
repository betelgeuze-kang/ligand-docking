"""Compatibility shim; canonical module: tools.product.resume_biorxiv_external_validation."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

from tools.product.resume_biorxiv_external_validation import *  # noqa: F401,F403
from tools.product.resume_biorxiv_external_validation import main as _main

_module = _import_module("tools.product.resume_biorxiv_external_validation")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
