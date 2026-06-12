"""Compatibility shim; canonical module: tools.accounting.build_local_delivery_engine_provenance."""

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

from tools.accounting.build_local_delivery_engine_provenance import *  # noqa: E402,F401,F403

_module = _import_module("tools.accounting.build_local_delivery_engine_provenance")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    _entry = getattr(_module, "main", None)
    if _entry is None:
        raise SystemExit("builder has no main(): tools.accounting.build_local_delivery_engine_provenance")
    raise SystemExit(_entry(_sys.argv[1:]) or 0)
