"""Compatibility shim; canonical module: tools.accounting.build_aqp1_direct_binding_external_evidence_one_shot_chain."""
from __future__ import annotations

import importlib

_module = importlib.import_module("tools.accounting.build_aqp1_direct_binding_external_evidence_one_shot_chain")

globals().update({k: v for k, v in _module.__dict__.items() if not k.startswith("__")})

if __name__ == "__main__":
    main = getattr(_module, "main", None)
    if main is None:
        raise SystemExit(
            "builder has no main(): tools.accounting.build_aqp1_direct_binding_external_evidence_one_shot_chain"
        )
    raise SystemExit(main())
