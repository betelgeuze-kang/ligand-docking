#!/usr/bin/python3
from __future__ import annotations

from tools.product.build_glut1_p0_packet_plan import *  # noqa: F401,F403
from tools.product.build_glut1_p0_packet_plan import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
