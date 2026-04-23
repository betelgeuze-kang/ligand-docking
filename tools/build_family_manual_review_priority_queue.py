#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BURNDOWN_JSON = "runs/family_manual_review_burndown_current.json"
DEFAULT_CA2_SLICE_JSON = "runs/ca2_next_verification_slice_current.json"
DEFAULT_PXR_SLICE_JSON = "runs/pxr_next_verification_slice_current.json"
DEFAULT_TRANSPORTER_PACKETS_JSON = "runs/transporter_manual_verdict_packets_current.json"
DEFAULT_OUT_JSON = "runs/family_manual_review_priority_queue_current.json"
DEFAULT_OUT_CSV = "runs/family_manual_review_priority_queue_current.csv"
DEFAULT_OUT_MD = "runs/family_manual_review_priority_queue_current.md"


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


def _burndown_lookup(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("family", "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("family", "")).strip()
    }


def _append_ca2_rows(rows: list[dict[str, Any]], burndown_row: dict[str, Any], payload: dict[str, Any], family_rank: int) -> None:
    for row in payload.get("rows", []) or []:
        rows.append(
            {
                "family_band_rank": family_rank,
                "family": "ca2",
                "item_priority_rank": int(str(row.get("priority_rank", "999")).strip() or 999),
                "work_type": "negative_policy_review",
                "item_id": str(row.get("packet_step", "")).strip(),
                "candidate_or_ligand": str(row.get("replacement_ligand_id", "")).strip(),
                "recommended_action": str(row.get("next_required_action", "")).strip(),
                "policy_bucket": "review_only",
                "assay_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "ready_count": int(burndown_row.get("ready_count", 0) or 0),
                "review_only_count": int(burndown_row.get("review_only_count", 0) or 0),
                "defer_count": int(burndown_row.get("defer_count", 0) or 0),
                "pending_manual_count": int(burndown_row.get("pending_manual_count", 0) or 0),
                "family_stage": str(burndown_row.get("current_stage", "")).strip(),
                "handoff_note": str(row.get("notes", "")).strip(),
            }
        )


def _append_pxr_rows(rows: list[dict[str, Any]], burndown_row: dict[str, Any], payload: dict[str, Any], family_rank: int) -> None:
    for row in payload.get("rows", []) or []:
        action = str(row.get("next_required_action", "")).strip()
        policy_bucket = "review_only" if action == "manual_negative_evidence_review" else "defer"
        rows.append(
            {
                "family_band_rank": family_rank,
                "family": "pxr",
                "item_priority_rank": int(str(row.get("priority_rank", "999")).strip() or 999),
                "work_type": "pending_policy_review",
                "item_id": str(row.get("packet_step", "")).strip(),
                "candidate_or_ligand": str(row.get("replacement_ligand_id", "")).strip(),
                "recommended_action": action,
                "policy_bucket": policy_bucket,
                "assay_honesty": str(row.get("assay_type_honesty", "")).strip(),
                "ready_count": int(burndown_row.get("ready_count", 0) or 0),
                "review_only_count": int(burndown_row.get("review_only_count", 0) or 0),
                "defer_count": int(burndown_row.get("defer_count", 0) or 0),
                "pending_manual_count": int(burndown_row.get("pending_manual_count", 0) or 0),
                "family_stage": str(burndown_row.get("current_stage", "")).strip(),
                "handoff_note": str(row.get("review_reason", "")).strip(),
            }
        )


def _append_transporter_rows(rows: list[dict[str, Any]], burndown_row: dict[str, Any], packet: dict[str, Any], family_rank: int) -> None:
    family = str(packet.get("target_id", "")).strip().lower()
    for row in packet.get("rows", []) or []:
        rows.append(
            {
                "family_band_rank": family_rank,
                "family": family,
                "item_priority_rank": int(str(row.get("priority_rank", "999")).strip() or 999),
                "work_type": "manual_verdict_fill",
                "item_id": str(row.get("packet_step", "")).strip(),
                "candidate_or_ligand": str(row.get("candidate_name", "")).strip(),
                "recommended_action": "fill_manual_verdict_update",
                "policy_bucket": str(row.get("suggested_manual_verdict", "")).strip(),
                "assay_honesty": str(row.get("promotion_blocker", "")).strip(),
                "ready_count": int(burndown_row.get("ready_count", 0) or 0),
                "review_only_count": int(burndown_row.get("review_only_count", 0) or 0),
                "defer_count": int(burndown_row.get("defer_count", 0) or 0),
                "pending_manual_count": int(burndown_row.get("pending_manual_count", 0) or 0),
                "family_stage": str(burndown_row.get("current_stage", "")).strip(),
                "handoff_note": str(row.get("manual_decision_note_template", "")).strip(),
            }
        )


def build_payload(
    burndown_payload: dict[str, Any],
    ca2_slice_payload: dict[str, Any],
    pxr_slice_payload: dict[str, Any],
    transporter_packets_payload: dict[str, Any],
) -> dict[str, Any]:
    burndown = _burndown_lookup(burndown_payload)
    rows: list[dict[str, Any]] = []

    _append_ca2_rows(rows, burndown["ca2"], ca2_slice_payload, 1)
    _append_pxr_rows(rows, burndown["pxr"], pxr_slice_payload, 2)

    packets = {
        str(packet.get("target_id", "")).strip().lower(): dict(packet)
        for packet in transporter_packets_payload.get("target_packets", []) or []
    }
    _append_transporter_rows(rows, burndown["aqp1"], packets["aqp1"], 3)
    _append_transporter_rows(rows, burndown["glut1"], packets["glut1"], 4)

    policy_order = {
        "review_only": 0,
        "keep_review_only": 0,
        "caution_only": 1,
        "defer": 2,
    }
    rows.sort(
        key=lambda row: (
            row["family_band_rank"],
            policy_order.get(str(row["policy_bucket"]), 9),
            row["item_priority_rank"],
            row["family"],
            row["item_id"],
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["queue_rank"] = idx

    summary = {
        "queue_row_count": len(rows),
        "family_count": len({row["family"] for row in rows}),
        "family_band_order": ["ca2", "pxr", "aqp1", "glut1"],
        "next_required_step": "Work top-down through the queue: preserve CA2/PXR manual-only policy first, then fill AQP1 first-wave verdicts, then GLUT1 second-wave verdicts.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Family Manual Review Priority Queue",
        "",
        f"- queue_row_count: `{s['queue_row_count']}`",
        f"- family_count: `{s['family_count']}`",
        f"- family_band_order: `{', '.join(s['family_band_order'])}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Queue",
        "",
        "| queue_rank | family | item_priority_rank | work_type | item_id | candidate_or_ligand | recommended_action | policy_bucket | ready_count | review_only_count | defer_count | pending_manual_count |",
        "| ---: | --- | ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['family']}` | {row['item_priority_rank']} | "
            f"`{row['work_type']}` | `{row['item_id']}` | `{row['candidate_or_ligand']}` | "
            f"`{row['recommended_action']}` | `{row['policy_bucket']}` | {row['ready_count']} | "
            f"{row['review_only_count']} | {row['defer_count']} | {row['pending_manual_count']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a manual-review priority queue across CA2, PXR, AQP1, and GLUT1.")
    parser.add_argument("--burndown-json", default=DEFAULT_BURNDOWN_JSON)
    parser.add_argument("--ca2-slice-json", default=DEFAULT_CA2_SLICE_JSON)
    parser.add_argument("--pxr-slice-json", default=DEFAULT_PXR_SLICE_JSON)
    parser.add_argument("--transporter-packets-json", default=DEFAULT_TRANSPORTER_PACKETS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.burndown_json),
        _load_json(args.ca2_slice_json),
        _load_json(args.pxr_slice_json),
        _load_json(args.transporter_packets_json),
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
