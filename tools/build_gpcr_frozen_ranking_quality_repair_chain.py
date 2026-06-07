"""Compatibility shim; canonical module: tools.gpcr_replay.build_gpcr_frozen_ranking_quality_repair_chain."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_module = importlib.import_module("tools.gpcr_replay.build_gpcr_frozen_ranking_quality_repair_chain")
main = getattr(_module, "main", None)
if main is None:
    raise SystemExit("builder has no main(): tools.gpcr_replay.build_gpcr_frozen_ranking_quality_repair_chain")

if __name__ == "__main__":
    main()
