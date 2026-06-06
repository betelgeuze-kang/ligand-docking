#!/usr/bin/python3
from __future__ import annotations

from tools.casp17.build_casp17_current_post_native_scoring_scaffold import *  # noqa: F401,F403
from tools.casp17.build_casp17_current_post_native_scoring_scaffold import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
