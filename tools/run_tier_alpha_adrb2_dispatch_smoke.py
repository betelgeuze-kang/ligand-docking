"""Compatibility shim; canonical module: tools.product.run_tier_alpha_adrb2_dispatch_smoke."""
from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("tools.product.run_tier_alpha_adrb2_dispatch_smoke")
sys.modules[__name__] = _module

if __name__ == "__main__":
    _module.main()
