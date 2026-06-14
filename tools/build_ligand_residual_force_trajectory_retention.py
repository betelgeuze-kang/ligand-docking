#!/usr/bin/python3
from __future__ import annotations

from importlib import import_module as _import_module

_module = _import_module("tools.accounting.build_ligand_residual_force_trajectory_retention")

for _name in dir(_module):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_module, _name)


if __name__ == "__main__":
    if hasattr(_module, "main"):
        _module.main()
    else:  # pragma: no cover
        raise SystemExit("builder has no main(): tools.accounting.build_ligand_residual_force_trajectory_retention")
