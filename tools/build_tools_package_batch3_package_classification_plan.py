"""Compatibility shim; canonical module: tools.accounting.build_tools_package_batch3_package_classification_plan."""
from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

_module = _import_module("tools.accounting.build_tools_package_batch3_package_classification_plan")
globals().update({key: value for key, value in _module.__dict__.items() if not key.startswith("__")})
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_module.main(_sys.argv[1:]) or 0)
