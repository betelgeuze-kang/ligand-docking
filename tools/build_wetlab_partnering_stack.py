"""Compatibility shim; canonical module: tools.accounting.build_wetlab_partnering_stack."""
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

_module = _import_module("tools.accounting.build_wetlab_partnering_stack")
globals().update({k: v for k, v in _module.__dict__.items() if not k.startswith("__")})
_CANONICAL_BUILD_PAYLOAD = _module.build_payload


def _sync_workspace():
    root = globals().get("ROOT", getattr(_module, "ROOT", None))
    if root is not None:
        _module.ROOT = root
    visual_resolver = globals().get(
        "resolve_selected_allatom_visual_bundle",
        getattr(_module, "resolve_selected_allatom_visual_bundle", None),
    )
    if visual_resolver is not None:
        _module.resolve_selected_allatom_visual_bundle = visual_resolver
    for name in ("_load_json", "_maybe_load_json", "_write_markdown"):
        value = globals().get(name, getattr(_module, name, None))
        if value is not None:
            setattr(_module, name, value)
    payload_builder = globals().get("build_payload")
    _module.build_payload = (
        payload_builder
        if payload_builder is not None and payload_builder is not _SHIM_BUILD_PAYLOAD
        else _CANONICAL_BUILD_PAYLOAD
    )


def build_payload(*args, **kwargs):
    _sync_workspace()
    return _CANONICAL_BUILD_PAYLOAD(*args, **kwargs)


build_payload.__signature__ = _signature(_CANONICAL_BUILD_PAYLOAD)
_SHIM_BUILD_PAYLOAD = build_payload


def main(*args, **kwargs):
    _sync_workspace()
    return _module.main(*args, **kwargs)

if __name__ == "__main__":
    _entry = getattr(_module, "main", None)
    if _entry is None:
        raise SystemExit("builder has no main(): tools.accounting.build_wetlab_partnering_stack")
    _params = _signature(_entry).parameters
    _result = _entry(_sys.argv[1:]) if _params else _entry()
    raise SystemExit(_result or 0)
