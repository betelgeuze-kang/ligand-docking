#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.bootstrap_real_md_metadata import *  # noqa: F401,F403
from tools.product.bootstrap_real_md_metadata import main as _main
from tools.product import bootstrap_real_md_metadata as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    _main()
