"""Compatibility shim; canonical module: tools.wetlab.render_readme_molecular_figures."""

from __future__ import annotations

import sys as _sys
from importlib import import_module as _import_module

from tools.wetlab.render_readme_molecular_figures import *  # noqa: F401,F403
from tools.wetlab.render_readme_molecular_figures import main as _main

_module = _import_module("tools.wetlab.render_readme_molecular_figures")
_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_main())
