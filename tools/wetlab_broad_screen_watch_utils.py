#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.wetlab.wetlab_broad_screen_watch_utils import *  # noqa: F401,F403
from tools.wetlab import wetlab_broad_screen_watch_utils as _module

_sys.modules[__name__] = _module
