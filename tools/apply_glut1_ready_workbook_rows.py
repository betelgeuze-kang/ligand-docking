#!/usr/bin/python3
from __future__ import annotations

from tools.product.apply_glut1_ready_workbook_rows import *  # noqa: F401,F403
from tools.product.apply_glut1_ready_workbook_rows import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
