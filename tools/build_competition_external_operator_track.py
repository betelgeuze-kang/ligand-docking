#!/usr/bin/env python3
"""Compatibility shim; canonical module: tools.product.build_competition_external_operator_track."""
import sys as _sys
from pathlib import Path as _Path

_repo = _Path(__file__).resolve()
for _ in range(12):
    if (_repo / "pyproject.toml").exists():
        if str(_repo) not in _sys.path:
            _sys.path.insert(0, str(_repo))
        break
    _repo = _repo.parent

from tools.product.build_competition_external_operator_track import main

if __name__ == "__main__":
    main(_sys.argv[1:])
