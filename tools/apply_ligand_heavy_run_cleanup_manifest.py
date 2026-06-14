#!/usr/bin/python3
from __future__ import annotations

from tools.accounting.apply_ligand_heavy_run_cleanup_manifest import *  # noqa: F401,F403
from tools.accounting.apply_ligand_heavy_run_cleanup_manifest import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
