"""Compatibility shim; canonical module: tools.product.monitor_idp_holdout_progress."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

from tools.product.monitor_idp_holdout_progress import *  # noqa: F401,F403
from tools.product.monitor_idp_holdout_progress import main as _main

_module = _import_module("tools.product.monitor_idp_holdout_progress")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
