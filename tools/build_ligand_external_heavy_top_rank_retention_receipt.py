#!/usr/bin/python3
from __future__ import annotations

from tools.accounting.build_ligand_external_heavy_top_rank_retention_receipt import *  # noqa: F401,F403
from tools.accounting.build_ligand_external_heavy_top_rank_retention_receipt import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
