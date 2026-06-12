"""Compatibility shim; canonical module: tools.product.report_md_gap."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

from tools.product.report_md_gap import *  # noqa: F401,F403
from tools.product.report_md_gap import main as _main

_module = _import_module("tools.product.report_md_gap")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
