#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.wetlab.wetlab_rescue_only_branch_builder import *  # noqa: F401,F403
from tools.wetlab import wetlab_rescue_only_branch_builder as _module

_sys.modules[__name__] = _module
