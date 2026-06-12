"""Compatibility shim; canonical module: tools.product.build_product_rollout_execution_smoke_receipt."""
from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("tools.product.build_product_rollout_execution_smoke_receipt")
sys.modules[__name__] = _module

if __name__ == "__main__":
    if hasattr(_module, "main"):
        _module.main()
    else:
        raise SystemExit("builder has no main(): tools.product.build_product_rollout_execution_smoke_receipt")
