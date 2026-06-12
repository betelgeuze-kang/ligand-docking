#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.monitor_biorxiv_external_validation import *  # noqa: F401,F403
from tools.product.monitor_biorxiv_external_validation import main as _main
from tools.product import monitor_biorxiv_external_validation as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
