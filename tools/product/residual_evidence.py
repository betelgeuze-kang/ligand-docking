"""Compatibility import; implementation is owned by betelgeuze_product."""
import sys
from betelgeuze_product import residual_evidence as _implementation

sys.modules[__name__] = _implementation
