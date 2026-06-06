"""Compatibility shim; canonical module: tools.accounting.build_casp17_protein_complex_massivefold_self_assessment_packet."""
from importlib import import_module as _import_module
import sys as _sys

_module = _import_module("tools.accounting.build_casp17_protein_complex_massivefold_self_assessment_packet")
globals().update({k: v for k, v in _module.__dict__.items() if not k.startswith("__")})

if __name__ == "__main__":
    _entry = getattr(_module, "main", None)
    if _entry is None:
        raise SystemExit("builder has no main(): tools.accounting.build_casp17_protein_complex_massivefold_self_assessment_packet")
    raise SystemExit(_entry(_sys.argv[1:]) or 0)
