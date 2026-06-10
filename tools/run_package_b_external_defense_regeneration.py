"""Compatibility shim; canonical module: tools.product.run_package_b_external_defense_regeneration."""
from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("tools.product.run_package_b_external_defense_regeneration")
sys.modules[__name__] = _module

if __name__ == "__main__":
    _module.main()
