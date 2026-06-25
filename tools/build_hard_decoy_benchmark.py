"""Compatibility shim; canonical module: tools.accounting.build_hard_decoy_benchmark."""
# ruff: noqa: E402
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
from inspect import signature as _signature
import sys as _sys

_module = _import_module("tools.accounting.build_hard_decoy_benchmark")
globals().update({k: v for k, v in _module.__dict__.items() if not k.startswith("__")})


def _sync_generation_hooks() -> None:
    for _name in (
        "Chem",
        "BRICS",
        "_rdkit_desc",
        "_passes_3d_relaxation",
        "_derive_scaffold",
        "_canonicalize_smiles",
        "_template_smiles_candidates",
        "_relaxed_beads_from_smiles",
    ):
        setattr(_module, _name, globals().get(_name, getattr(_module, _name)))


def _generate_synthetic_unique_decoys(*args, **kwargs):
    _sync_generation_hooks()
    return _module._generate_synthetic_unique_decoys(*args, **kwargs)

if __name__ == "__main__":
    _entry = getattr(_module, "main", None)
    if _entry is None:
        raise SystemExit("builder has no main(): tools.accounting.build_hard_decoy_benchmark")
    _params = _signature(_entry).parameters
    _result = _entry(_sys.argv[1:]) if _params else _entry()
    raise SystemExit(_result or 0)
