#!/usr/bin/python3
from __future__ import annotations

from tools.casp17.build_casp17_historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates import *  # noqa: F401,F403
from tools.casp17.build_casp17_historical_seed_strict_blind_replacement_first_slot_official_archive_source_candidates import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
