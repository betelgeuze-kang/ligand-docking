"""Compatibility shim; canonical module: tools.accounting.build_ligand_mapping_queue.

The command-line entry point routes through ``tools.product.strict_ligand_mapping_queue``
so product runs get P0 input-provenance columns and optional fail-closed strict mode
without changing the accounting module's import surface.
"""
# ruff: noqa: E402
import sys as _sys
from pathlib import Path as _Path

_repo = _Path(__file__).resolve()
for _ in range(12):
    if (_repo / "pyproject.toml").exists():
        if str(_repo) not in _sys.path:
            _sys.path.insert(0, str(_repo))
        break
    _repo = _repo.parent

from importlib import import_module as _import_module

_module = _import_module("tools.accounting.build_ligand_mapping_queue")
globals().update({k: v for k, v in _module.__dict__.items() if not k.startswith("__")})

if __name__ == "__main__":
    _wrapper = _import_module("tools.product.strict_ligand_mapping_queue")
    _entry = getattr(_wrapper, "main", None)
    if _entry is None:
        raise SystemExit("strict wrapper has no main(): tools.product.strict_ligand_mapping_queue")
    _result = _entry(_sys.argv[1:])
    raise SystemExit(_result or 0)
