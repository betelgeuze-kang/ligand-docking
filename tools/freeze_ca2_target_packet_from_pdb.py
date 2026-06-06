#!/usr/bin/env python3
from __future__ import annotations

from tools.product.freeze_ca2_target_packet_from_pdb import *  # noqa: F401,F403
from tools.product.freeze_ca2_target_packet_from_pdb import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
