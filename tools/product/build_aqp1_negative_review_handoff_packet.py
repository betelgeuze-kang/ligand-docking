#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_LOCAL_EVIDENCE_JSON = "runs/aqp1_local_evidence_note_current.json"
DEFAULT_MANUAL_QUEUE_JSON = "runs/aqp1_manual_review_queue_current.json"
DEFAULT_NEXT_SLICE_JSON = "runs/aqp1_next_verification_slice_current.json"
DEFAULT_CANDIDATE_VERDICT_JSON = "runs/aqp1_candidate_verdict_sheet_current.json"
DEFAULT_OUT_JSON = "runs/aqp1_negative_review_handoff_packet_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_negative_review_handoff_packet_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_negative_review_handoff_packet_current.md"


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


def _index_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row.get(key, "")).strip()
        if value:
            out[value] = row
    return out


def build_payload(
    local_evidence_payload: dict[str, Any],
    manual_queue_payload: dict[str, Any],
    next_slice_payload: dict[str, Any],
    candidate_verdict_payload: dict[str, Any],
) -> dict[str, Any]:
    next_by_step = _index_by(next_slice_payload.get("rows", []) or [], "packet_step")
    caution_candidates = [
        row
        for row in (candidate_verdict_payload.get("rows", []) or [])
        if str(row.get("proposed_packet_step", "")).strip() == "caution_only"
    ]

    rows: list[dict[str, Any]] = []
    for queue_row in manual_queue_payload.get("rows", []) or []:
        packet_step = str(queue_row.get("packet_step", "")).strip()
        if not packet_step.startswith("core_non_binder_"):
            continue
        next_row = next_by_step.get(packet_step, {})
        rows.append(
            {
                "section": "negative_slot_policy",
                "priority_rank": str(queue_row.get("priority_rank", "")).strip(),
                "packet_step": packet_step,
                "label": str(queue_row.get("current_ligand_id", "")).strip(),
                "review_bucket": str(queue_row.get("review_bucket", "")).strip(),
                "recommended_resolution": str(queue_row.get("recommended_resolution", "")).strip(),
                "promotion_blocker": str(queue_row.get("promotion_blocker", "")).strip(),
                "next_action": str(next_row.get("next_action", queue_row.get("next_required_action", ""))).strip(),
                "notes": str(next_row.get("notes", queue_row.get("notes", ""))).strip(),
            }
        )

    for idx, verdict_row in enumerate(caution_candidates, start=1):
        rows.append(
            {
                "section": "caution_or_defer_signal",
                "priority_rank": str(idx),
                "packet_step": str(verdict_row.get("proposed_packet_step", "")).strip(),
                "label": str(verdict_row.get("candidate_name", "")).strip(),
                "review_bucket": str(verdict_row.get("review_bucket", "")).strip(),
                "recommended_resolution": str(verdict_row.get("recommended_verdict", "")).strip(),
                "promotion_blocker": str(verdict_row.get("promotion_policy", "")).strip(),
                "next_action": "review_primary_source_and_keep_out_of_negative_packet_rows",
                "notes": str(verdict_row.get("caution", "")).strip(),
            }
        )

    blocker_rows = [
        {
            "section": "local_blocker_signal",
            "priority_rank": "",
            "packet_step": str(row.get("check_id", "")).strip(),
            "label": str(row.get("signal", "")).strip(),
            "review_bucket": str(row.get("status", "")).strip(),
            "recommended_resolution": "keep_review_only_blocked",
            "promotion_blocker": str(row.get("check_id", "")).strip(),
            "next_action": "do_not_inject_proxy_negative_values",
            "notes": str(row.get("notes", "")).strip(),
        }
        for row in (local_evidence_payload.get("rows", []) or [])
        if str(row.get("check_id", "")).strip() in {"negative_evidence", "ligand_packet_placeholders", "fit_donor_policy"}
    ]
    rows.extend(blocker_rows)

    summary = {
        "target_id": str(local_evidence_payload.get("summary", {}).get("target_id", "AQP1_TRANSPORT_BLIND")).strip(),
        "endpoint_status": str(local_evidence_payload.get("summary", {}).get("endpoint_status", "")).strip(),
        "local_quantitative_negative_evidence_curated": bool(
            local_evidence_payload.get("summary", {}).get("local_quantitative_negative_evidence_curated", False)
        ),
        "negative_slot_count": sum(1 for row in rows if row["section"] == "negative_slot_policy"),
        "caution_or_defer_reference_count": sum(1 for row in rows if row["section"] == "caution_or_defer_signal"),
        "local_blocker_signal_count": sum(1 for row in rows if row["section"] == "local_blocker_signal"),
        "authoritative_negative_apply_allowed": False,
        "next_required_step": "Use this packet to review AQP1 non-binder and caution signals only. Keep all negative slots review-only and do not inject proxy quantitative non-binder values.",
    }
    checklist = [
        "Keep all three AQP1 non-binder slots review-only until transporter-specific negative evidence is curated.",
        "Do not reinterpret tetraethylammonium or acetazolamide as negative packet rows; they remain caution/defer references only.",
        "Do not reopen fit-donor or authoritative apply discussions from negative review alone.",
    ]
    return {"summary": summary, "checklist": checklist, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 Negative Review Handoff Packet",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- endpoint_status: `{s['endpoint_status']}`",
        f"- local_quantitative_negative_evidence_curated: `{s['local_quantitative_negative_evidence_curated']}`",
        f"- negative_slot_count: `{s['negative_slot_count']}`",
        f"- caution_or_defer_reference_count: `{s['caution_or_defer_reference_count']}`",
        f"- local_blocker_signal_count: `{s['local_blocker_signal_count']}`",
        f"- authoritative_negative_apply_allowed: `{s['authoritative_negative_apply_allowed']}`",
        "",
        "## Reviewer Checklist",
        "",
    ]
    for item in payload["checklist"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Handoff Rows",
            "",
            "| section | priority_rank | packet_step | label | review_bucket | recommended_resolution | next_action |",
            "| --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"]:
        lines.append(
            f"| `{row['section']}` | {row['priority_rank']} | `{row['packet_step']}` | `{row['label']}` | "
            f"`{row['review_bucket']}` | `{row['recommended_resolution']}` | `{row['next_action']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an AQP1 negative-review handoff packet from existing review-only and caution artifacts.")
    parser.add_argument("--local-evidence-json", default=DEFAULT_LOCAL_EVIDENCE_JSON)
    parser.add_argument("--manual-queue-json", default=DEFAULT_MANUAL_QUEUE_JSON)
    parser.add_argument("--next-slice-json", default=DEFAULT_NEXT_SLICE_JSON)
    parser.add_argument("--candidate-verdict-json", default=DEFAULT_CANDIDATE_VERDICT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.local_evidence_json),
        _load_json(args.manual_queue_json),
        _load_json(args.next_slice_json),
        _load_json(args.candidate_verdict_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
