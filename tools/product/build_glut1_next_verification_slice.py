#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXTERNAL_SEED_JSON = "runs/glut1_external_evidence_seed_current.json"
DEFAULT_MANUAL_QUEUE_JSON = "runs/glut1_manual_review_queue_current.json"
DEFAULT_OUT_JSON = "runs/glut1_next_verification_slice_current.json"
DEFAULT_OUT_CSV = "runs/glut1_next_verification_slice_current.csv"
DEFAULT_OUT_MD = "runs/glut1_next_verification_slice_current.md"


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(external_seed: dict[str, Any], manual_queue: dict[str, Any]) -> dict[str, Any]:
    seed_rows = [dict(row) for row in (external_seed.get("rows", []) or [])]
    queue_rows = [dict(row) for row in (manual_queue.get("rows", []) or [])]
    prioritized_rows: list[dict[str, Any]] = []
    rank = 1
    for seed_row in seed_rows:
        prioritized_rows.append(
            {
                "priority_rank": rank,
                "work_item_type": "external_candidate_review",
                "label": str(seed_row.get("candidate_name", "")).strip(),
                "packet_step": str(seed_row.get("proposed_packet_step", "")).strip(),
                "review_bucket": str(seed_row.get("recommended_review_bucket", "")).strip(),
                "next_action": "review_primary_source_and_decide_keep_review_only_or_defer",
                "source_anchor": str(seed_row.get("source_anchor", "")).strip(),
            }
        )
        rank += 1
    for queue_row in queue_rows:
        if str(queue_row.get("replacement_is_binder", "")).strip() == "1":
            continue
        prioritized_rows.append(
            {
                "priority_rank": rank,
                "work_item_type": "negative_slot_review",
                "label": str(queue_row.get("current_ligand_id", "")).strip(),
                "packet_step": str(queue_row.get("packet_step", "")).strip(),
                "review_bucket": str(queue_row.get("review_bucket", "")).strip(),
                "next_action": str(queue_row.get("next_required_action", "")).strip(),
                "source_anchor": str(queue_row.get("suggested_external_source_anchor", "")).strip(),
            }
        )
        rank += 1

    summary = {
        "target_id": "GLUT1_TRANSPORT_BLIND",
        "row_count": len(prioritized_rows),
        "external_candidate_review_count": len(seed_rows),
        "negative_slot_review_count": sum(1 for row in prioritized_rows if row["work_item_type"] == "negative_slot_review"),
        "next_required_step": "Hold GLUT1 as second-wave. Review cytochalasin B, WZB117, and STF-31 first, keep forskolin and gossypol caution-only, then finish the three GLUT1 review-only negative slots without injecting proxy values.",
    }
    return {"summary": summary, "rows": prioritized_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GLUT1 Next Verification Slice",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- row_count: `{s['row_count']}`",
        f"- external_candidate_review_count: `{s['external_candidate_review_count']}`",
        f"- negative_slot_review_count: `{s['negative_slot_review_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Queue",
        "",
        "| priority | work_item_type | label | packet_step | review_bucket | next_action | source_anchor |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | {row['work_item_type']} | `{row['label']}` | `{row['packet_step']}` | "
            f"`{row['review_bucket']}` | `{row['next_action']}` | `{row['source_anchor']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the next verification slice for GLUT1 transporter review.")
    parser.add_argument("--external-seed-json", default=DEFAULT_EXTERNAL_SEED_JSON)
    parser.add_argument("--manual-queue-json", default=DEFAULT_MANUAL_QUEUE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.external_seed_json), _load_json(args.manual_queue_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
