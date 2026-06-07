"""Compatibility shim; canonical module: tools.accounting.build_product_infrastructure_gap_closure."""
from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("tools.accounting.build_product_infrastructure_gap_closure")
sys.modules[__name__] = _module

if __name__ == "__main__":
    if hasattr(_module, "main"):
        _module.main()
    else:
        raise SystemExit("builder has no main(): tools.accounting.build_product_infrastructure_gap_closure")
