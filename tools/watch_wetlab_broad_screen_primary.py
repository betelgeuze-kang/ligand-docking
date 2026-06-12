#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.wetlab.watch_wetlab_broad_screen_primary import *  # noqa: F401,F403
from tools.wetlab.watch_wetlab_broad_screen_primary import main as _main
from tools.wetlab import watch_wetlab_broad_screen_primary as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
