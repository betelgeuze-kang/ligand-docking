"""Compatibility shim; canonical module: tools.accounting.build_wetlab_openmm_claim_promotion_boundary."""
from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("tools.accounting.build_wetlab_openmm_claim_promotion_boundary")
sys.modules[__name__] = _module

if __name__ == "__main__":
    if hasattr(_module, "main"):
        _module.main()
    else:
        raise SystemExit("builder has no main(): tools.accounting.build_wetlab_openmm_claim_promotion_boundary")
