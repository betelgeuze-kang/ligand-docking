"""Compatibility shim; canonical module: tools.product.build_ai_md_product_evidence_bundle."""
from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module
from pathlib import Path as _Path

_repo = _Path(__file__).resolve()
for _ in range(12):
    if (_repo / "pyproject.toml").exists():
        if str(_repo) not in _sys.path:
            _sys.path.insert(0, str(_repo))
        break
    _repo = _repo.parent

_module = _import_module("tools.product.build_ai_md_product_evidence_bundle")
globals().update({k: v for k, v in _module.__dict__.items() if not k.startswith("__")})

if __name__ == "__main__":
    _entry = getattr(_module, "main", None)
    if _entry is None:
        raise SystemExit("builder has no main(): tools.product.build_ai_md_product_evidence_bundle")
    raise SystemExit(_entry(_sys.argv[1:]) or 0)
