#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.builder_table_utils import *  # noqa: F401,F403
from tools.product import builder_table_utils as _module

_sys.modules[__name__] = _module
