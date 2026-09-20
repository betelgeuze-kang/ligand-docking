"""Compatibility import; implementation is owned by betelgeuze_product."""
import sys
from betelgeuze_product import public_assay_preflight as _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

sys.modules[__name__] = _implementation
