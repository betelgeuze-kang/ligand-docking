"""Compatibility shim; canonical module: tools.product.promote_verified_binding_rows_to_workbook."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

from tools.product.promote_verified_binding_rows_to_workbook import *  # noqa: F401,F403
from tools.product.promote_verified_binding_rows_to_workbook import main as _main

_module = _import_module("tools.product.promote_verified_binding_rows_to_workbook")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
