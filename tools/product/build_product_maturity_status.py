#!/usr/bin/env python3
"""Emit the single four-axis product status packet (P0-6).

The four axes are reported separately so a strong result on one axis cannot
imply strength on another. Axis values come from an operator-maintained source
config, never from a blended readiness score.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from betelgeuze_product.maturity_status import (  # noqa: E402
    MATURITY_STATUS_SCHEMA_VERSION,
    STATUS_AXES,
    MaturityStatusError,
    parse_maturity_status,
)

DEFAULT_SOURCE_JSON = "config/product_maturity_status_current.json"
DEFAULT_OUT_JSON = "runs/product_maturity_status_current.json"
DEFAULT_OUT_MD = "docs/PRODUCT_MATURITY_STATUS_CURRENT.md"

CLAIM_BOUNDARY = (
    "Four-axis product status reporting only; it restates operator-maintained distribution, scientific, "
    "benchmark, and product maturity values. It does not run benchmarks, promote claims, widen scope, "
    "or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path)


def build_product_maturity_status(
    *,
    source_json: str | Path = DEFAULT_SOURCE_JSON,
) -> dict[str, Any]:
    source_path = _resolve(source_json)
    if not source_path.is_file():
        return {
            "summary": {
                "status": "blocked_product_maturity_status",
                "maturity_status_schema_version": MATURITY_STATUS_SCHEMA_VERSION,
                "source_json": str(source_json),
                "blocked_checks": ["product_maturity_status_source_missing"],
                "axes_reported_separately": True,
                "external_state_mutated": False,
            },
            "claim_boundary": CLAIM_BOUNDARY,
        }
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    raw = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    try:
        status = parse_maturity_status(raw)
    except MaturityStatusError as exc:
        return {
            "summary": {
                "status": "blocked_product_maturity_status",
                "maturity_status_schema_version": MATURITY_STATUS_SCHEMA_VERSION,
                "source_json": str(source_json),
                "blocked_checks": [str(exc)],
                "axes_reported_separately": True,
                "external_state_mutated": False,
            },
            "claim_boundary": CLAIM_BOUNDARY,
        }
    summary: dict[str, Any] = {
        "status": "product_maturity_status_ready",
        "source_json": str(source_json),
        "blocked_checks": [],
        "axes_reported_separately": True,
        "axis_count": len(STATUS_AXES),
        "external_state_mutated": False,
    }
    summary.update(status.receipt())
    return {"summary": summary, "claim_boundary": CLAIM_BOUNDARY, "axes": list(STATUS_AXES)}


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary", {})
    lines = [
        "# Product Maturity Status (current)",
        "",
        "Generated packet. Do not hand-edit axis values here; edit the source config and regenerate.",
        "",
        f"- status: `{summary.get('status')}`",
        f"- maturity_status_schema_version: `{summary.get('maturity_status_schema_version')}`",
        "",
        "## Axes (reported separately, never merged)",
        "",
    ]
    for axis in STATUS_AXES:
        lines.append(f"- {axis}: `{summary.get(axis, '')}`")
    blocked = summary.get("blocked_checks") or []
    lines.extend(
        [
            "",
            f"- blocked_checks: `{','.join(str(item) for item in blocked) or 'none'}`",
            f"- external_state_mutated: `{summary.get('external_state_mutated')}`",
            "",
            "## Claim Boundary",
            "",
            f"{packet.get('claim_boundary', '')}",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the four-axis product maturity status packet.")
    parser.add_argument("--source-json", default=DEFAULT_SOURCE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = build_product_maturity_status(source_json=args.source_json)
    out_json = _resolve(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if args.out_md:
        out_md = _resolve(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(packet), encoding="utf-8")
    summary = packet.get("summary", {})
    if not args.quiet:
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if summary.get("status") == "product_maturity_status_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
