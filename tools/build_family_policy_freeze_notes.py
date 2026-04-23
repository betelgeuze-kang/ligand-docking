#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CA2_PENDING_JSON = "runs/ca2_pending_row_disposition_current.json"
DEFAULT_PXR_PENDING_JSON = "runs/pxr_pending_row_disposition_current.json"
DEFAULT_OUT_JSON = "runs/family_policy_freeze_notes_current.json"
DEFAULT_OUT_MD = "runs/family_policy_freeze_notes_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(ca2_pending: dict[str, Any], pxr_pending: dict[str, Any]) -> dict[str, Any]:
    ca2_s = dict(ca2_pending.get("summary", {}) or {})
    pxr_s = dict(pxr_pending.get("summary", {}) or {})
    rows = [
        {
            "family": "CA2",
            "decision": "keep all remaining negative-like rows review-only and blocked from authoritative apply until direct CA2 target-specific negative evidence with explicit provenance is curated; do not inject proxy quantitative values.",
            "review_only_rows": ca2_s.get("review_only_rows", ""),
            "defer_rows": ca2_s.get("defer_rows", ""),
        },
        {
            "family": "PXR",
            "decision": "keep current review-only negative-like PXR rows frozen at review-only; keep deferred binder/conflict rows deferred until blocker-reducing human PXR evidence is curated, and keep supportive-binder manual-confirmation rows out of authoritative apply until their claim-safe blocker is reduced.",
            "review_only_rows": pxr_s.get("review_only_rows", ""),
            "defer_rows": pxr_s.get("defer_rows", ""),
        },
    ]
    return {
        "summary": {
            "family_count": 2,
            "next_required_step": "Treat these as frozen policy lines for the current local-evidence state. Only reopen them when new target-specific evidence is added to the repo.",
        },
        "rows": rows,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Family Policy Freeze Notes",
        "",
        f"- family_count: `{payload['summary']['family_count']}`",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Notes",
        "",
    ]
    for row in payload["rows"]:
        lines.append(f"- `{row['family']}`: {row['decision']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build short policy-freeze notes for CA2 and PXR pending rows.")
    parser.add_argument("--ca2-pending-json", default=DEFAULT_CA2_PENDING_JSON)
    parser.add_argument("--pxr-pending-json", default=DEFAULT_PXR_PENDING_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.ca2_pending_json), _load_json(args.pxr_pending_json))
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
