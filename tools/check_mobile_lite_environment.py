#!/usr/bin/env python3
"""Validate the dependency boundary for the mobile-lite development lane."""

from __future__ import annotations

import importlib.util
import json
import sys

REQUIRED_MODULES = (
    "yaml",
    "pydantic",
    "fastapi",
    "pydantic_settings",
    "prometheus_client",
    "pytest",
)
EXCLUDED_MODULES = ("torch", "rdkit", "openmm", "h5py")


def _availability(module_names: tuple[str, ...]) -> dict[str, bool]:
    return {name: importlib.util.find_spec(name) is not None for name in module_names}


def main() -> int:
    required = _availability(REQUIRED_MODULES)
    excluded = _availability(EXCLUDED_MODULES)
    missing_required = sorted(name for name, available in required.items() if not available)
    installed_excluded = sorted(name for name, available in excluded.items() if available)

    report = {
        "profile": "mobile-lite",
        "required_modules": required,
        "excluded_modules": excluded,
        "missing_required": missing_required,
        "installed_excluded": installed_excluded,
        "gpu_validation_performed": False,
        "scientific_claim_promotion_allowed": False,
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    if missing_required:
        print(
            "mobile-lite environment is missing required dependency-light modules",
            file=sys.stderr,
        )
        return 1
    if installed_excluded:
        print(
            "mobile-lite environment unexpectedly contains heavy optional modules",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
