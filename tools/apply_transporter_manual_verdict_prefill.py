#!/usr/bin/python3
from __future__ import annotations

from tools.product.apply_transporter_manual_verdict_prefill import *  # noqa: F401,F403
from tools.product.apply_transporter_manual_verdict_prefill import main as _main


if __name__ == "__main__":
    result = _main()
    if result is not None:
        raise SystemExit(result)
