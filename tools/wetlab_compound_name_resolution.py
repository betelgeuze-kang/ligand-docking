#!/usr/bin/python3
from __future__ import annotations

from tools.wetlab.wetlab_compound_name_resolution import *  # noqa: F401,F403
from tools.wetlab.wetlab_compound_name_resolution import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
