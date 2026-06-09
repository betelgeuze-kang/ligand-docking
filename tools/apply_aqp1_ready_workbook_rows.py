#!/usr/bin/env python3
from __future__ import annotations

import importlib

_module = importlib.import_module("tools.product.apply_aqp1_ready_workbook_rows")

if __name__ == "__main__":
    main = getattr(_module, "main", None)
    if main is None:
        raise SystemExit("builder has no main(): tools.product.apply_aqp1_ready_workbook_rows")
    main()
