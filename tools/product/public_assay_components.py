"""Compatibility import; implementation is owned by betelgeuze_product."""
import sys
from betelgeuze_product import public_assay_components as _implementation

sys.modules[__name__] = _implementation
