"""Compatibility shim; canonical module: tools.product.build_docking_ranking_mutation_e2e_smoke."""
from __future__ import annotations

from importlib import import_module as _import_module

_module = _import_module("tools.product.build_docking_ranking_mutation_e2e_smoke")

if __name__ == "__main__":
    result = _module.main()
    if result is not None:
        raise SystemExit(result)
