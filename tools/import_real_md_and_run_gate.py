#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.import_real_md_and_run_gate import *  # noqa: F401,F403
from tools.product.import_real_md_and_run_gate import main as _main
from tools.product import import_real_md_and_run_gate as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
