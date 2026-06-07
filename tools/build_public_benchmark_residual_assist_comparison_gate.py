"""Compatibility shim; canonical module: tools.accounting.build_public_benchmark_residual_assist_comparison_gate."""
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

_module = _import_module("tools.accounting.build_public_benchmark_residual_assist_comparison_gate")
globals().update({k: v for k, v in _module.__dict__.items() if not k.startswith("__")})

if __name__ == "__main__":
    _entry = getattr(_module, "main", None)
    if _entry is None:
        raise SystemExit("builder has no main(): tools.accounting.build_public_benchmark_residual_assist_comparison_gate")
    raise SystemExit(_entry(_sys.argv[1:]) or 0)
