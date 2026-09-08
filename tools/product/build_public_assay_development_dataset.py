#!/usr/bin/env python3
"""Build a hash-bound development pool from already downloaded public sources."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import tempfile
import time

from tools.product.public_assay_dataset import (
    build_dataset,
    file_sha,
    json_text,
    require_sha,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "mapping", "assays", "exclusions"):
        parser.add_argument("--" + name, type=Path, required=True)
        parser.add_argument("--" + name + "-sha256", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--target", action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        raise ValueError("output_already_exists")
    require_sha(file_sha(args.exclusions), args.exclusions_sha256)
    exclusions = json.loads(args.exclusions.read_text())
    wall, cpu = time.perf_counter(), time.process_time()
    rows, ledger, summary = build_dataset(
        source_path=args.source,
        source_sha256=args.source_sha256,
        source_url=args.source_url,
        release=args.release,
        mapping_path=args.mapping,
        mapping_sha256=args.mapping_sha256,
        assay_path=args.assays,
        assay_sha256=args.assays_sha256,
        exclusions=exclusions,
        targets=set(args.target),
    )
    require_sha(file_sha(args.exclusions), args.exclusions_sha256)
    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=".public-assay-", dir=args.output_dir.parent)
    )
    try:
        for name, data in (("records.jsonl", rows), ("ledger.jsonl", ledger)):
            (staging / name).write_text(
                "".join(json_text(row) + "\n" for row in data), encoding="utf-8"
            )
        summary.update(
            records_sha256=file_sha(staging / "records.jsonl"),
            ledger_sha256=file_sha(staging / "ledger.jsonl"),
            exclusion_file_sha256=args.exclusions_sha256,
            implementation_sha256=file_sha(
                Path(__file__).with_name("public_assay_dataset.py")
            ),
            cli_sha256=file_sha(Path(__file__)),
            wall_seconds=time.perf_counter() - wall,
            cpu_seconds=time.process_time() - cpu,
            process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            cost_scope="offline intake process; downloads and model training excluded",
        )
        (staging / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n"
        )
        # mkdir above is allowed; no existing output bundle can be overwritten.
        if args.output_dir.exists():
            raise ValueError("output_already_exists")
        os.rename(staging, args.output_dir)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
