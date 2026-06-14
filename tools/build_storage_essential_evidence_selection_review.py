#!/usr/bin/python3
from __future__ import annotations

from tools.accounting.build_storage_essential_evidence_selection_review import *  # noqa: F401,F403
from tools.accounting.build_storage_essential_evidence_selection_review import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
