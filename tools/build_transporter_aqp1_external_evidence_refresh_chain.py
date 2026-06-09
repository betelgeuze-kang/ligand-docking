"""Compatibility shim; canonical module: tools.accounting.build_transporter_aqp1_external_evidence_refresh_chain."""
from __future__ import annotations

import importlib

_module = importlib.import_module("tools.accounting.build_transporter_aqp1_external_evidence_refresh_chain")

if __name__ == "__main__":
    main = getattr(_module, "main", None)
    if main is None:
        raise SystemExit(
            "builder has no main(): tools.accounting.build_transporter_aqp1_external_evidence_refresh_chain"
        )
    raise SystemExit(main())
