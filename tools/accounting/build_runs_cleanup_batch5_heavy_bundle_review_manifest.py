#!/usr/bin/python3
from __future__ import annotations

from tools.cleanup.build_runs_cleanup_batch5_heavy_bundle_review_manifest import *  # noqa: F401,F403
from tools.cleanup.build_runs_cleanup_batch5_heavy_bundle_review_manifest import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
