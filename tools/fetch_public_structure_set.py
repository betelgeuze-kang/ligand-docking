#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.fetch_public_structure_set import *  # noqa: F401,F403
from tools.product.fetch_public_structure_set import main as _main
from tools.product import fetch_public_structure_set as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
