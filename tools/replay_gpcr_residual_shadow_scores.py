#!/usr/bin/python3
from __future__ import annotations

from tools.product.replay_gpcr_residual_shadow_scores import *  # noqa: F401,F403
from tools.product.replay_gpcr_residual_shadow_scores import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
