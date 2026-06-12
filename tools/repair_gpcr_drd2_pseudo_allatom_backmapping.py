#!/usr/bin/env python3
from __future__ import annotations

import importlib
import sys

from tools.gpcr_replay.repair_gpcr_drd2_pseudo_allatom_backmapping import *  # noqa: F401,F403
from tools.gpcr_replay.repair_gpcr_drd2_pseudo_allatom_backmapping import main as _main

_module = importlib.import_module("tools.gpcr_replay.repair_gpcr_drd2_pseudo_allatom_backmapping")
sys.modules[__name__] = _module


if __name__ == "__main__":
    _main()
