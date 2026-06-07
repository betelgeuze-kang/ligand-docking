#!/usr/bin/python3
from __future__ import annotations

from tools.product.run_ligand_scaleup_100k_pilot_current import *  # noqa: F401,F403
from tools.product.run_ligand_scaleup_100k_pilot_current import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
