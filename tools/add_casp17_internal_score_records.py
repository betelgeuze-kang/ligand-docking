#!/usr/bin/python3
from __future__ import annotations

from tools.casp17.add_casp17_internal_score_records import *  # noqa: F401,F403
from tools.casp17.add_casp17_internal_score_records import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
