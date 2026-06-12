#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.calibrate_ligand_mmpbsa_proxy import *  # noqa: F401,F403
from tools.product.calibrate_ligand_mmpbsa_proxy import main as _main
from tools.product import calibrate_ligand_mmpbsa_proxy as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    _main()
