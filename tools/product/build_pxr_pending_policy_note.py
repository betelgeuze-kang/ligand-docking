#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUEUE_JSON = "runs/pxr_manual_review_queue_current.json"
DEFAULT_OUT_JSON = "runs/pxr_pending_policy_note_current.json"
DEFAULT_OUT_MD = "runs/pxr_pending_policy_note_current.md"


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


def build_payload(queue_payload: dict[str, Any]) -> dict[str, Any]:
    rows = list(queue_payload.get("rows", []) or [])
    review_only = [
        str(row.get("replacement_ligand_id", "")).strip()
        for row in rows
        if str(row.get("review_bucket", "")).strip() == "review_only_negative"
    ]
    deferred = [
        str(row.get("replacement_ligand_id", "")).strip()
        for row in rows
        if str(row.get("review_bucket", "")).strip() == "defer_pending_target_specific_evidence"
    ]
    return {
        "summary": {
            "review_only_rows": review_only,
            "defer_rows": deferred,
            "policy_line": (
                f"Keep review-only PXR rows ({', '.join(review_only) or 'none'}) locked to review-only negative-like documentation, "
                f"and keep deferred rows ({', '.join(deferred) or 'none'}) deferred until local target-specific human PXR evidence reduces their blockers."
            ),
            "next_required_step": (
                "Do not auto-promote deferred or review-only PXR rows. "
                "Only revisit classifications when target-specific human evidence is added locally and clearly reduces the current blocker."
            ),
        }
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# PXR Pending Policy Note",
        "",
        f"- review_only_rows: `{', '.join(s['review_only_rows'])}`",
        f"- defer_rows: `{', '.join(s['defer_rows'])}`",
        "",
        s["policy_line"],
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a concise operator-facing PXR pending-row policy note.")
    parser.add_argument("--queue-json", default=DEFAULT_QUEUE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.queue_json))
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
