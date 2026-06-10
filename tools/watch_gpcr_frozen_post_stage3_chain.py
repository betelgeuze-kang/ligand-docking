#!/usr/bin/env python3
from __future__ import annotations

import importlib

_module = importlib.import_module("tools.gpcr_replay.watch_gpcr_frozen_post_stage3_chain")

if __name__ == "__main__":
    _module.main()
