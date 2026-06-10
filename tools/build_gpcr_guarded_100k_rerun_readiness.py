"""Compatibility shim; canonical module: tools.accounting.build_gpcr_guarded_100k_rerun_readiness."""
import sys as _sys
from pathlib import Path as _Path
_repo = _Path(__file__).resolve()
for _ in range(12):
    if (_repo / 'pyproject.toml').exists():
        if str(_repo) not in _sys.path:
            _sys.path.insert(0, str(_repo))
        break
    _repo = _repo.parent

from importlib import import_module as _import_module
import sys as _sys

_module = _import_module("tools.accounting.build_gpcr_guarded_100k_rerun_readiness")
globals().update({k: v for k, v in _module.__dict__.items() if not k.startswith("__")})

if __name__ == "__main__":
    result = _module.main()
    if result is not None:
        raise SystemExit(result)
