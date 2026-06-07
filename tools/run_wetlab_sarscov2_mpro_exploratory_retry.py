#!/usr/bin/python3
from __future__ import annotations

from tools.wetlab.run_wetlab_sarscov2_mpro_exploratory_retry import *  # noqa: F401,F403
from tools.wetlab.run_wetlab_sarscov2_mpro_exploratory_retry import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
