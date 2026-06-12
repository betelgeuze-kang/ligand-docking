#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.collect_feature_matrix import *  # noqa: F401,F403
from tools.product.collect_feature_matrix import main as _main
from tools.product import collect_feature_matrix as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    _main()
