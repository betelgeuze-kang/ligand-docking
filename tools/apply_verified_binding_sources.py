#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.apply_verified_binding_sources import *  # noqa: F401,F403
from tools.product.apply_verified_binding_sources import main as _main
from tools.product import apply_verified_binding_sources as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    _main()
