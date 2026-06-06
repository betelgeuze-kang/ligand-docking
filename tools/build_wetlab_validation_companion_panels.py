"""Compatibility shim; canonical module: tools.accounting.build_wetlab_validation_companion_panels."""
from importlib import import_module as _import_module
import sys as _sys

_module = _import_module("tools.accounting.build_wetlab_validation_companion_panels")
globals().update({k: v for k, v in _module.__dict__.items() if not k.startswith("__")})

if __name__ == "__main__":
    _entry = getattr(_module, "main", None)
    if _entry is None:
        raise SystemExit("builder has no main(): tools.accounting.build_wetlab_validation_companion_panels")
    raise SystemExit(_entry(_sys.argv[1:]) or 0)
