#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.wetlab.run_wetlab_tcruzi_pde_rescue_only_branch import *  # noqa: F401,F403
from tools.wetlab.run_wetlab_tcruzi_pde_rescue_only_branch import main as _main
from tools.wetlab import run_wetlab_tcruzi_pde_rescue_only_branch as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    _main()
