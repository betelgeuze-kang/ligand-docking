#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from tools.product.generate_openmm_ca_md_references import *  # noqa: F401,F403
from tools.product.generate_openmm_ca_md_references import main as _main
from tools.product import generate_openmm_ca_md_references as _module

_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
