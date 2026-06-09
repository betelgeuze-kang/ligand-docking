"""Compatibility shim; canonical module: tools.product.build_residual_production_promotion_gate."""
from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("tools.product.build_residual_production_promotion_gate")
globals().update({k: v for k, v in _module.__dict__.items() if not k.startswith("__")})

if __name__ == "__main__":
    _entry = getattr(_module, "main", None)
    if _entry is None:
        raise SystemExit("builder has no main(): tools.product.build_residual_production_promotion_gate")
    raise SystemExit(_entry(sys.argv[1:]) or 0)
