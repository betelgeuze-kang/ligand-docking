#!/usr/bin/env python3
from __future__ import annotations

import importlib
import sys

from tools.wetlab.run_wetlab_cathepsin_k_allatom_refinement import *  # noqa: F401,F403
from tools.wetlab.run_wetlab_cathepsin_k_allatom_refinement import main as _main

_module = importlib.import_module("tools.wetlab.run_wetlab_cathepsin_k_allatom_refinement")
sys.modules[__name__] = _module


if __name__ == "__main__":
    _main()
