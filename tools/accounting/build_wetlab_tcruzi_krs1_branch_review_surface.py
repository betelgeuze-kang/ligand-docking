#!/usr/bin/python3
from __future__ import annotations

from tools.wetlab.build_wetlab_tcruzi_krs1_branch_review_surface import *  # noqa: F401,F403
from tools.wetlab.build_wetlab_tcruzi_krs1_branch_review_surface import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
