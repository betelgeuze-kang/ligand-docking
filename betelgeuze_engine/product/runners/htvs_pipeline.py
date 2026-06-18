"""Product runner adapter for ligand HTVS pipeline.

The allowlisted CLI path remains ``tools/run_ligand_htvs_pipeline.py``.
This module is the product-engine import surface used by that shim while the
implementation continues to live in ``tools.product`` during migration.
"""

from __future__ import annotations

from importlib import import_module
import sys

_module = import_module("tools.product.run_ligand_htvs_pipeline")

globals().update(
    {
        name: value
        for name, value in _module.__dict__.items()
        if not (name.startswith("__") and name.endswith("__"))
    }
)

main = getattr(_module, "main")

__all__ = [name for name in globals() if not (name.startswith("__") and name.endswith("__"))]

sys.modules[__name__] = _module
