#!/usr/bin/env python3
from __future__ import annotations

from tools.cleanup.archive_ligand_stress_runs import *  # noqa: F401,F403
from tools.cleanup.archive_ligand_stress_runs import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
