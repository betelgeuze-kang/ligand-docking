#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import socket
import sys
import time
from pathlib import Path
from uuid import uuid4

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.config import settings
from api.job_store import SQLiteJobStore
from api.worker import process_next_job_once


def _default_worker_id() -> str:
    return f"{socket.gethostname()}-{uuid4()}"


async def _run_worker(args: argparse.Namespace) -> int:
    store = SQLiteJobStore(settings.api_job_store_path)
    processed = 0
    while True:
        result = await process_next_job_once(
            store,
            worker_id=args.worker_id,
            lease_seconds=args.lease_seconds,
            heartbeat_interval_seconds=args.heartbeat_interval_seconds,
        )
        if result is not None:
            processed += 1
            if args.once:
                return 0
            continue
        if args.once:
            return 0
        time.sleep(args.poll_interval_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the API simulation queue worker.")
    parser.add_argument("--worker-id", default=_default_worker_id())
    parser.add_argument("--lease-seconds", type=int, default=settings.api_worker_lease_seconds)
    parser.add_argument(
        "--heartbeat-interval-seconds",
        type=float,
        default=settings.api_worker_heartbeat_interval_seconds,
    )
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit.")
    args = parser.parse_args()
    return asyncio.run(_run_worker(args))


if __name__ == "__main__":
    raise SystemExit(main())
