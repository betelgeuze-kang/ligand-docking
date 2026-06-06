#!/usr/bin/python3
from __future__ import annotations

from tools.cleanup.apply_runs_artifact_inventory_root_archive import *  # noqa: F401,F403
from tools.cleanup.apply_runs_artifact_inventory_root_archive import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
