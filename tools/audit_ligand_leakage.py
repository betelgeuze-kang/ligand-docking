#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.audit_ligand_leakage import *  # noqa: F401,F403
from tools.product.audit_ligand_leakage import main as _main
from tools.product import audit_ligand_leakage as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    _main()
