#!/usr/bin/python3
from __future__ import annotations

from tools.product.build_cross_family_residual_shell_spec import *  # noqa: F401,F403
from tools.product.build_cross_family_residual_shell_spec import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
