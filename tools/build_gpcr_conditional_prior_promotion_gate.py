"""Compatibility shim; canonical module: tools.accounting.build_gpcr_conditional_prior_promotion_gate."""
from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("tools.accounting.build_gpcr_conditional_prior_promotion_gate")
sys.modules[__name__] = _module

if __name__ == "__main__":
    if hasattr(_module, "main"):
        _module.main()
    else:
        raise SystemExit("builder has no main(): tools.accounting.build_gpcr_conditional_prior_promotion_gate")
