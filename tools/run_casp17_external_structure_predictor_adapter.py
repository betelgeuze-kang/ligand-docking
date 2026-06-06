#!/usr/bin/python3
from __future__ import annotations

from tools.casp17.run_casp17_external_structure_predictor_adapter import *  # noqa: F401,F403
from tools.casp17.run_casp17_external_structure_predictor_adapter import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
