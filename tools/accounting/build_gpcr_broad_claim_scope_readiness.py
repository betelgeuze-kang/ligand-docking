#!/usr/bin/python3
from __future__ import annotations

from tools.gpcr_replay.build_gpcr_broad_claim_scope_readiness import *  # noqa: F401,F403
from tools.gpcr_replay.build_gpcr_broad_claim_scope_readiness import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
