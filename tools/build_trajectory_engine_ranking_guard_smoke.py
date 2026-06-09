"""Compatibility shim; canonical module: tools.product.build_trajectory_engine_ranking_guard_smoke."""

from __future__ import annotations

from importlib import import_module as _import_module

_module = _import_module("tools.product.build_trajectory_engine_ranking_guard_smoke")

if __name__ == "__main__":
    if hasattr(_module, "main"):
        _module.main()
    else:
        raise SystemExit("builder has no main(): tools.product.build_trajectory_engine_ranking_guard_smoke")
