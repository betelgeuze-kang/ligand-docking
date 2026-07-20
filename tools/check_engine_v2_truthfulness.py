#!/usr/bin/env python3
"""Validate Engine v2 lifecycle, scoped metric, and review-evidence contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from betelgeuze_engine_v2.truthfulness import (  # noqa: E402
    capability_truthfulness_snapshot,
    require_capability_truthfulness_snapshot,
    require_scoped_metric_evidence_row,
    require_truthfulness_policy_document,
    verify_release_review_evidence,
)


DEFAULT_POLICY = ROOT / "config" / "independent_engine_v2_truthfulness_policy.json"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read canonical JSON from {path}: {exc}") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate fail-closed Engine v2 truthfulness evidence.",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_POLICY,
        help="truthfulness policy JSON",
    )
    parser.add_argument(
        "--metric-row",
        type=Path,
        help="optional scoped metric evidence JSON",
    )
    parser.add_argument(
        "--review-evidence",
        type=Path,
        help="optional external release review evidence JSON",
    )
    parser.add_argument(
        "--print-snapshot",
        action="store_true",
        help="print the derived capability lifecycle snapshot",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    policy = _read_json(args.policy)
    require_truthfulness_policy_document(policy)
    snapshot = capability_truthfulness_snapshot()
    require_capability_truthfulness_snapshot(snapshot)

    output: dict[str, object] = {
        "policy_sha256": snapshot["policy_sha256"],
        "capability_count": len(snapshot["capabilities"]),
        "production_execution_authorized": False,
        "scientific_validity_green": False,
        "claim_safe": False,
    }
    if args.metric_row is not None:
        metric = require_scoped_metric_evidence_row(_read_json(args.metric_row))
        output["metric_evidence_sha256"] = metric.to_dict()["evidence_sha256"]
    if args.review_evidence is not None:
        verification = verify_release_review_evidence(
            _read_json(args.review_evidence)
        )
        output["review_evidence_sha256"] = verification["evidence_sha256"]
        output["operational_review_evidence_verified"] = True
    if args.print_snapshot:
        output["snapshot"] = snapshot
    print(
        json.dumps(
            output,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
