#!/usr/bin/python3
from __future__ import annotations

from tools.cleanup.apply_runs_cleanup_batch2 import *  # noqa: F401,F403
from tools.cleanup.apply_runs_cleanup_batch2 import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
