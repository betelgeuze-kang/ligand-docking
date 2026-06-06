#!/usr/bin/python3
from __future__ import annotations

from tools.cameo.build_cameo_validation_repair_work_order import *  # noqa: F401,F403
from tools.cameo.build_cameo_validation_repair_work_order import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
