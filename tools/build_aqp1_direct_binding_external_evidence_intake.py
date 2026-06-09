"""Compatibility shim; canonical module: tools.product.build_aqp1_direct_binding_external_evidence_intake."""
from __future__ import annotations

import importlib
import sys

_module = importlib.import_module("tools.product.build_aqp1_direct_binding_external_evidence_intake")

if __name__ == "__main__":
    main = getattr(_module, "main", None)
    if main is None:
        raise SystemExit(
            "builder has no main(): tools.product.build_aqp1_direct_binding_external_evidence_intake"
        )
    raise SystemExit(main())
