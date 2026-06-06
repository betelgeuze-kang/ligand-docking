#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.config import settings
from api.docking_dispatch import dispatch_ready_docking_jobs
from api.product import _jobs_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll docking ledger and enqueue eligible jobs to SQLite worker queue.")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    jobs_dir = _jobs_dir()
    dispatched_total = 0
    while True:
        outcomes = dispatch_ready_docking_jobs(jobs_dir, limit=int(args.limit))
        if outcomes:
            dispatched_total += len(outcomes)
            if args.once:
                break
        elif args.once:
            break
        time.sleep(float(args.poll_interval_seconds))
    print({"dispatched_total": dispatched_total, "jobs_dir": str(jobs_dir), "store": settings.api_job_store_path})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
