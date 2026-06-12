"""Compatibility shim; canonical module: tools.accounting.build_selected_allatom_visual_bundle."""
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

_module = _import_module("tools.accounting.build_selected_allatom_visual_bundle")
globals().update({k: v for k, v in _module.__dict__.items() if not k.startswith("__")})


def _sync_module_state():
    for _name in (
        "ROOT",
        "_build_dashboard",
        "resolve_repo_native_entry",
        "load_shared_repo_native_registry",
        "visual_polish_mod",
    ):
        if _name in globals():
            setattr(_module, _name, globals()[_name])


def build_payload(*args, **kwargs):
    _sync_module_state()
    return _module.build_payload(*args, **kwargs)


def main(*args, **kwargs):
    _sync_module_state()
    return _module.main(*args, **kwargs)


if __name__ == "__main__":
    _entry = main
    if _entry is None:
        raise SystemExit("builder has no main(): tools.accounting.build_selected_allatom_visual_bundle")
    raise SystemExit(_entry(_sys.argv[1:]) or 0)
