"""Compatibility shim; canonical module: tools.accounting.build_wetlab_rescue_three_bead_candidates."""
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

_module = _import_module("tools.accounting.build_wetlab_rescue_three_bead_candidates")
globals().update({k: v for k, v in _module.__dict__.items() if not k.startswith("__")})
_ORIGINAL_ARCHIVE_ROOT = _module.DEFAULT_ARCHIVE_ROOT


def _sync_workspace():
    root = globals().get("ROOT", getattr(_module, "ROOT", None))
    if root is not None:
        _module.ROOT = root
    archive_root = globals().get("DEFAULT_ARCHIVE_ROOT", getattr(_module, "DEFAULT_ARCHIVE_ROOT", None))
    if archive_root is not None and archive_root != _ORIGINAL_ARCHIVE_ROOT:
        _module.DEFAULT_ARCHIVE_ROOT = archive_root
    elif root is not None:
        _module.DEFAULT_ARCHIVE_ROOT = root / "runs" / "archive"
    loader = globals().get("load_json", getattr(_module, "load_json", None))
    if loader is not None:
        _module.load_json = loader


def _resolve_rescue_lane_payload(*args, **kwargs):
    _sync_workspace()
    return _module._resolve_rescue_lane_payload(*args, **kwargs)


def build_payload(*args, **kwargs):
    _sync_workspace()
    return _module.build_payload(*args, **kwargs)

if __name__ == "__main__":
    _entry = getattr(_module, "main", None)
    if _entry is None:
        raise SystemExit("builder has no main(): tools.accounting.build_wetlab_rescue_three_bead_candidates")
    _params = _signature(_entry).parameters
    _result = _entry(_sys.argv[1:]) if _params else _entry()
    raise SystemExit(_result or 0)
