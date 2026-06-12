"""Compatibility wrapper for tools.casp17.validate_casp17_confidence_calibration."""
from tools.casp17.validate_casp17_confidence_calibration import *  # noqa: F401,F403

try:
    from tools.casp17.validate_casp17_confidence_calibration import main as _main
except ImportError:
    _main = None

if __name__ == "__main__":
    if _main is None:
        raise SystemExit("target module has no main(): tools.casp17.validate_casp17_confidence_calibration")
    raise SystemExit(_main())
