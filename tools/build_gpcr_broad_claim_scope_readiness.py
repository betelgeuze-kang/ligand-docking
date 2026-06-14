"""Compatibility shim; canonical module: tools.accounting.build_gpcr_broad_claim_scope_readiness."""
from __future__ import annotations

from importlib import import_module as _import_module

_module = _import_module("tools.accounting.build_gpcr_broad_claim_scope_readiness")

globals().update(
    {
        name: getattr(_module, name)
        for name in dir(_module)
        if not name.startswith("__") or name in {"__doc__", "__all__"}
    }
)

if __name__ == "__main__":
    if not hasattr(_module, "main"):
        raise SystemExit("builder has no main(): tools.accounting.build_gpcr_broad_claim_scope_readiness")
    result = _module.main()
    if result is not None:
        raise SystemExit(result)
