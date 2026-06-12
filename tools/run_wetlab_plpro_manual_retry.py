#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.wetlab.run_wetlab_plpro_manual_retry import *  # noqa: F401,F403
from tools.wetlab.run_wetlab_plpro_manual_retry import main as _main
from tools.wetlab import run_wetlab_plpro_manual_retry as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    _main()
