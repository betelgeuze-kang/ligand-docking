#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.cleanup.classify_runs_files import *  # noqa: F401,F403
from tools.cleanup.classify_runs_files import main as _main
from tools.cleanup import classify_runs_files as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    _main()
