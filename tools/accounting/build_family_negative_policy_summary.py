#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CA2_QUEUE_JSON = "runs/ca2_manual_review_queue_current.json"
DEFAULT_PXR_QUEUE_JSON = "runs/pxr_manual_review_queue_current.json"
DEFAULT_OUT_JSON = "runs/family_negative_policy_summary_current.json"
DEFAULT_OUT_MD = "runs/family_negative_policy_summary_current.md"


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


def _extract_family_summary(payload: dict[str, Any]) -> dict[str, Any]:
    rows = list(payload.get("rows", []) or [])
    summary = dict(payload.get("summary", {}) or {})
    review_only_rows = [
        str(row.get("replacement_ligand_id", "")).strip()
        for row in rows
        if str(row.get("review_bucket", "")).strip() == "review_only_negative"
    ]
    deferred_rows = [
        str(row.get("replacement_ligand_id", "")).strip()
        for row in rows
        if str(row.get("review_bucket", "")).strip() == "defer_pending_target_specific_evidence"
    ]
    review_only = list(dict.fromkeys(ligand for ligand in review_only_rows if ligand))
    deferred = list(dict.fromkeys(ligand for ligand in deferred_rows if ligand))
    return {
        "family": str(summary.get("family", "")).strip(),
        "review_only_negative_count": len(review_only_rows),
        "defer_count": len(deferred_rows),
        "review_only_negative_ligands": review_only,
        "deferred_ligands": deferred,
        "next_required_step": str(summary.get("next_required_step", "")).strip(),
    }


def build_payload(ca2_queue: dict[str, Any], pxr_queue: dict[str, Any]) -> dict[str, Any]:
    ca2 = _extract_family_summary(ca2_queue)
    pxr = _extract_family_summary(pxr_queue)
    return {
        "summary": {
            "family_count": 2,
            "policy_statement": (
                "Only keep ligands in review-only negative status when local target-specific evidence is weak/upper-bound-like. "
                "Otherwise defer them instead of asserting a non-binder label."
            ),
            "next_required_step": (
                "Use review-only negatives as the only manual-negative queue, and keep deferred rows out of authoritative apply until target-specific evidence changes."
            ),
        },
        "rows": [ca2, pxr],
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Family Negative Policy Summary",
        "",
        f"- family_count: `{payload['summary']['family_count']}`",
        f"- policy_statement: {payload['summary']['policy_statement']}",
        "",
        "## Next Step",
        "",
        f"- {payload['summary']['next_required_step']}",
        "",
        "## Families",
        "",
        "| family | review_only_negative_count | defer_count | review_only_negative_ligands | deferred_ligands |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['family']} | {row['review_only_negative_count']} | {row['defer_count']} | "
            f"`{', '.join(row['review_only_negative_ligands'])}` | `{', '.join(row['deferred_ligands'])}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize review-only negative vs deferred ligand policy for CA2 and PXR.")
    p.add_argument("--ca2-queue-json", default=DEFAULT_CA2_QUEUE_JSON)
    p.add_argument("--pxr-queue-json", default=DEFAULT_PXR_QUEUE_JSON)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.ca2_queue_json),
        _load_json(args.pxr_queue_json),
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
