#!/usr/bin/env python3
"""Reconcile declared PR full-suite counts with two JUnit reproductions."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


SCHEMA_ID = "betelgeuze.engine_v2_stage0_full_suite_reconciliation/1.0.0"
DECLARED_PR_COUNTS = {"failed": 216, "errors": 3}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _junit_rows(
    path: Path,
) -> tuple[bytes, Counter[tuple[str, str, str]], Counter[str]]:
    raw = path.read_bytes()
    root = ET.fromstring(raw)
    rows: Counter[tuple[str, str, str]] = Counter()
    kinds: Counter[str] = Counter()
    for case in root.iter("testcase"):
        kind = "failure" if case.find("failure") is not None else "error"
        if case.find(kind) is None:
            continue
        rows[(case.attrib.get("classname", ""), case.attrib.get("name", ""), kind)] += 1
        kinds[kind] += 1
    return raw, rows, kinds


def build_reconciliation(
    historical_junit: Path,
    current_junit: Path,
    *,
    historical_source_commit_sha: str,
) -> dict[str, Any]:
    historical_raw, historical_rows, historical_kinds = _junit_rows(historical_junit)
    current_raw, current_rows, current_kinds = _junit_rows(current_junit)
    historical_counts = {
        "failed": historical_kinds["failure"],
        "errors": historical_kinds["error"],
    }
    current_counts = {
        "failed": current_kinds["failure"],
        "errors": current_kinds["error"],
    }
    payload: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "declared_pr_counts": dict(DECLARED_PR_COUNTS),
        "historical_source_commit_sha": historical_source_commit_sha,
        "historical_junit_sha256": hashlib.sha256(historical_raw).hexdigest(),
        "historical_reproduction": historical_counts,
        "current_junit_sha256": hashlib.sha256(current_raw).hexdigest(),
        "current_reproduction": current_counts,
        "unresolved_declared_failure_count": max(
            0, DECLARED_PR_COUNTS["failed"] - historical_counts["failed"]
        ),
        "declared_aggregate_reproduced": historical_counts == DECLARED_PR_COUNTS,
        "historical_and_current_row_multisets_equal": historical_rows == current_rows,
        "only_historical_rows": [
            [*row, occurrence]
            for row, occurrence in sorted((historical_rows - current_rows).items())
        ],
        "only_current_rows": [
            [*row, occurrence]
            for row, occurrence in sorted((current_rows - historical_rows).items())
        ],
        "review_required": historical_counts != DECLARED_PR_COUNTS,
    }
    payload["receipt_sha256"] = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-junit", type=Path, required=True)
    parser.add_argument("--current-junit", type=Path, required=True)
    parser.add_argument("--historical-source-commit-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    payload = build_reconciliation(
        arguments.historical_junit,
        arguments.current_junit,
        historical_source_commit_sha=arguments.historical_source_commit_sha,
    )
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(payload["receipt_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
