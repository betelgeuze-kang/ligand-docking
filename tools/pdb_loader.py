"""Compatibility shim; canonical module: tools.product.pdb_loader."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

from tools.product.pdb_loader import *  # noqa: F401,F403

_module = _import_module("tools.product.pdb_loader")
_sys.modules[__name__] = _module
