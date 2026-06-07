#!/usr/bin/python3
from __future__ import annotations

from tools.cameo.build_cameo_repair_execution_preflight import *  # noqa: F401,F403
from tools.cameo.build_cameo_repair_execution_preflight import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
