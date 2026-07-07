"""Compatibility shim; canonical module: tools.product.pdb_loader.

Keep this shim import-light. Some queue/provenance tests only need the
``load_native_structure`` symbol to exist, and they provide explicit pocket
coordinates so the function is never called. Importing the canonical backend at
module import time pulls in torch through ``tools.product.pdb_loader`` and makes
small CI smoke tests pay the full runtime dependency cost. Delegate lazily
instead.
"""

from __future__ import annotations

from importlib import import_module as _import_module
from typing import Any

_MODULE_NAME = "tools.product.pdb_loader"


def _module() -> Any:
    return _import_module(_MODULE_NAME)


def load_native_structure(target_name: str):
    return _module().load_native_structure(target_name)


def __getattr__(name: str) -> Any:
    return getattr(_module(), name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_module())))
