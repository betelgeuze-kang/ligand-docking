"""Compatibility shim; canonical module: tools.cleanup.prune_runs_files."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

from tools.cleanup.prune_runs_files import *  # noqa: F401,F403
from tools.cleanup.prune_runs_files import main as _main

_module = _import_module("tools.cleanup.prune_runs_files")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
