#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.curate_structure_quality import *  # noqa: F401,F403
from tools.product.curate_structure_quality import main as _main
from tools.product import curate_structure_quality as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
