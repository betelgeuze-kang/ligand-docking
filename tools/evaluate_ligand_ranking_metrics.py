#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.evaluate_ligand_ranking_metrics import *  # noqa: F401,F403
from tools.product.evaluate_ligand_ranking_metrics import main as _main
from tools.product import evaluate_ligand_ranking_metrics as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
