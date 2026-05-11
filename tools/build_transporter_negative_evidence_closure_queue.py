#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

RUNS = Path("runs")

DEFAULT_NEGATIVE_DAY_PLAN_JSON = RUNS / "transporter_negative_reviewer_day_plan_current.json"
DEFAULT_PLACEHOLDER_QUEUE_JSON = RUNS / "transporter_placeholder_burndown_queue_current.json"
DEFAULT_TARGET_PACKETS_JSON = RUNS / "transporter_negative_evidence_target_packets_current.json"
DEFAULT_GLUT1_NEGATIVE_HANDOFF_JSON = RUNS / "glut1_negative_review_handoff_packet_current.json"
DEFAULT_OUT_JSON = RUNS / "transporter_negative_evidence_closure_queue_current.json"
DEFAULT_OUT_CSV = RUNS / "transporter_negative_evidence_closure_queue_current.csv"
DEFAULT_OUT_MD = RUNS / "transporter_negative_evidence_closure_queue_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (Path(__file__).resolve().parents[1] / path).resolve()


def _load_json(path_like: str | Path) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _target_context(
    target_id: str,
    row: dict[str, Any],
    target_packet_summary: dict[str, Any],
    glut1_negative_handoff_summary: dict[str, Any],
) -> dict[str, Any]:
    if target_id == "AQP1":
        return {
            "source_context_artifact": _text(target_packet_summary.get("aqp1_negative_confirmation_artifact"))
            or "runs/aqp1_negative_evidence_confirmation_packet_current.md",
            "source_context_support_artifact": _text(target_packet_summary.get("aqp1_negative_exact_source_outcome_artifact"))
            or "runs/aqp1_negative_exact_source_outcome_packet_current.md",
            "negative_handoff_artifact": _text(target_packet_summary.get("aqp1_negative_slot_resolution_artifact"))
            or "runs/aqp1_negative_slot_resolution_packet_current.md",
            "source_context_focus_ligand": _text(
                target_packet_summary.get("aqp1_negative_primary_probe_resolution_candidate")
            )
            or _text(target_packet_summary.get("aqp1_negative_exact_source_primary_probe_candidate")),
            "source_context_role": "exact_source_confirmation_not_authoritative_negative",
            "source_context_row_count": _int(target_packet_summary.get("aqp1_negative_confirmation_row_count")),
            "source_context_direct_negative_quantitative_row_found_count": _int(
                target_packet_summary.get("aqp1_negative_exact_source_direct_negative_quantitative_row_found_count")
            ),
            "source_context_authoritative_negative_apply_allowed_count": _int(
                target_packet_summary.get("aqp1_negative_exact_source_authoritative_negative_apply_allowed_count")
            ),
            "source_context_authoritative_negative_apply_allowed": False,
        }
    if target_id == "GLUT1":
        return {
            "source_context_artifact": _text(glut1_negative_handoff_summary.get("source_context_artifact"))
            or _text(row.get("source_confirmation_packet_artifact"))
            or "runs/glut1_second_wave_source_confirmation_packet_current.md",
            "source_context_support_artifact": _text(row.get("source_confirmation_packet_artifact"))
            or "runs/glut1_second_wave_source_confirmation_packet_current.md",
            "negative_handoff_artifact": _text(glut1_negative_handoff_summary.get("packet_artifact"))
            or "runs/glut1_negative_review_handoff_packet_current.md",
            "source_context_focus_ligand": _text(glut1_negative_handoff_summary.get("source_context_primary_focus_ligand"))
            or _text(row.get("source_confirmation_packet_primary_focus_ligand")),
            "source_context_role": "positive_or_binder_context_not_negative_evidence",
            "source_context_row_count": _int(row.get("source_confirmation_packet_row_count")),
            "source_context_direct_negative_quantitative_row_found_count": 0,
            "source_context_authoritative_negative_apply_allowed_count": 0,
            "source_context_authoritative_negative_apply_allowed": _bool(
                glut1_negative_handoff_summary.get("authoritative_negative_apply_allowed")
            ),
        }
    return {
        "source_context_artifact": _text(row.get("source_confirmation_packet_artifact"))
        or "runs/transporter_negative_reviewer_day_plan_current.md",
        "source_context_support_artifact": "",
        "negative_handoff_artifact": "",
        "source_context_focus_ligand": _text(row.get("source_confirmation_packet_primary_focus_ligand")),
        "source_context_role": "unresolved_negative_context",
        "source_context_row_count": _int(row.get("source_confirmation_packet_row_count")),
        "source_context_direct_negative_quantitative_row_found_count": 0,
        "source_context_authoritative_negative_apply_allowed_count": 0,
        "source_context_authoritative_negative_apply_allowed": False,
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Transporter Negative Evidence Closure Queue",
        "",
        f"- review_mode: `{s['review_mode']}`",
        f"- row_count: `{s['row_count']}`",
        f"- aqp1_negative_slot_count: `{s['aqp1_negative_slot_count']}`",
        f"- glut1_negative_slot_count: `{s['glut1_negative_slot_count']}`",
        f"- caution_reference_row_count: `{s['caution_reference_row_count']}`",
        f"- blocker_reference_row_count: `{s['blocker_reference_row_count']}`",
        f"- placeholder_driven_rows_remaining: `{s['placeholder_driven_rows_remaining']}`",
        f"- staged_non_authoritative_rows: `{s['staged_non_authoritative_rows']}`",
        f"- top_queue_id: `{s['top_queue_id']}`",
        f"- top_target_id: `{s['top_target_id']}`",
        f"- top_packet_step: `{s['top_packet_step']}`",
        f"- top_source_context_artifact: `{s['top_source_context_artifact']}`",
        f"- top_source_context_role: `{s['top_source_context_role']}`",
        f"- aqp1_source_context_artifact: `{s['aqp1_source_context_artifact']}`",
        f"- aqp1_source_context_focus_ligand: `{s['aqp1_source_context_focus_ligand']}`",
        f"- aqp1_source_context_direct_negative_quantitative_row_found_count: `{s['aqp1_source_context_direct_negative_quantitative_row_found_count']}`",
        f"- aqp1_source_context_authoritative_negative_apply_allowed_count: `{s['aqp1_source_context_authoritative_negative_apply_allowed_count']}`",
        f"- glut1_negative_handoff_artifact: `{s['glut1_negative_handoff_artifact']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Queue",
        "",
        "| queue_rank | queue_id | target_id | packet_step | review_bucket | promotion_blocker | closure_mode | source_context_artifact | source_context_role | next_required_action |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['queue_rank']} | `{row['queue_id']}` | `{row['target_id']}` | `{row['packet_step']}` | "
            f"`{row['review_bucket']}` | `{row['promotion_blocker']}` | `{row['closure_mode']}` | "
            f"`{row['source_context_artifact']}` | `{row['source_context_role']}` | `{row['next_required_action']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(
    negative_day_plan: dict[str, Any],
    placeholder_queue: dict[str, Any],
    target_packets: dict[str, Any] | None = None,
    glut1_negative_handoff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    negative_rows = [
        row
        for row in negative_day_plan.get("review_rows", []) or []
        if _text(row.get("review_phase")) == "negative_slots_first"
    ]
    rows: list[dict[str, Any]] = []
    target_packet_summary = dict((target_packets or {}).get("summary", {}) or {})
    glut1_negative_handoff_summary = dict((glut1_negative_handoff or {}).get("summary", {}) or {})
    for idx, row in enumerate(negative_rows, start=1):
        target_id = _text(row.get("target_id"))
        packet_step = _text(row.get("packet_step"))
        context = _target_context(target_id, row, target_packet_summary, glut1_negative_handoff_summary)
        rows.append(
            {
                "queue_rank": idx,
                "queue_id": f"{target_id}__{packet_step}",
                "target_id": target_id,
                "wave_priority": _text(row.get("wave_priority")),
                "packet_step": packet_step,
                "candidate_or_label": _text(row.get("candidate_or_label")),
                "review_bucket": _text(row.get("review_bucket")),
                "recommended_resolution": _text(row.get("recommended_resolution")),
                "promotion_blocker": _text(row.get("promotion_blocker")) or "no_quantitative_transporter_negative_evidence_curated",
                "closure_mode": "direct_negative_evidence_required",
                "source_context_artifact": context["source_context_artifact"],
                "source_context_support_artifact": context["source_context_support_artifact"],
                "negative_handoff_artifact": context["negative_handoff_artifact"],
                "source_context_focus_ligand": context["source_context_focus_ligand"],
                "source_context_role": context["source_context_role"],
                "source_context_row_count": context["source_context_row_count"],
                "source_context_direct_negative_quantitative_row_found_count": context[
                    "source_context_direct_negative_quantitative_row_found_count"
                ],
                "source_context_authoritative_negative_apply_allowed_count": context[
                    "source_context_authoritative_negative_apply_allowed_count"
                ],
                "source_context_authoritative_negative_apply_allowed": context[
                    "source_context_authoritative_negative_apply_allowed"
                ],
                "next_required_action": _text(row.get("next_required_action")) or "manual_negative_evidence_review",
            }
        )

    day_summary = dict(negative_day_plan.get("summary", {}) or {})
    placeholder_summary = dict(placeholder_queue.get("summary", {}) or {})
    top_row = rows[0] if rows else {}
    summary = {
        "review_mode": "negative_evidence_closure_only",
        "row_count": len(rows),
        "aqp1_negative_slot_count": sum(1 for row in rows if row["target_id"] == "AQP1"),
        "glut1_negative_slot_count": sum(1 for row in rows if row["target_id"] == "GLUT1"),
        "caution_reference_row_count": _int(day_summary.get("caution_reference_row_count")),
        "blocker_reference_row_count": _int(day_summary.get("blocker_reference_row_count")),
        "placeholder_driven_rows_remaining": _int(placeholder_summary.get("placeholder_driven_rows")),
        "staged_non_authoritative_rows": _int(placeholder_summary.get("staged_non_authoritative_rows")),
        "top_queue_id": _text(top_row.get("queue_id")),
        "top_target_id": _text(top_row.get("target_id")),
        "top_packet_step": _text(top_row.get("packet_step")),
        "top_source_context_artifact": _text(top_row.get("source_context_artifact")),
        "top_source_context_role": _text(top_row.get("source_context_role")),
        "aqp1_source_context_artifact": _text(target_packet_summary.get("aqp1_negative_confirmation_artifact"))
        or "runs/aqp1_negative_evidence_confirmation_packet_current.md",
        "aqp1_source_context_focus_ligand": _text(
            target_packet_summary.get("aqp1_negative_primary_probe_resolution_candidate")
        )
        or _text(target_packet_summary.get("aqp1_negative_exact_source_primary_probe_candidate")),
        "aqp1_source_context_direct_negative_quantitative_row_found_count": _int(
            target_packet_summary.get("aqp1_negative_exact_source_direct_negative_quantitative_row_found_count")
        ),
        "aqp1_source_context_authoritative_negative_apply_allowed_count": _int(
            target_packet_summary.get("aqp1_negative_exact_source_authoritative_negative_apply_allowed_count")
        ),
        "glut1_source_context_artifact": _text(glut1_negative_handoff_summary.get("source_context_artifact"))
        or _text(day_summary.get("glut1_second_wave_source_confirmation_packet_artifact")),
        "glut1_source_context_primary_focus_ligand": _text(
            glut1_negative_handoff_summary.get("source_context_primary_focus_ligand")
        )
        or _text(day_summary.get("glut1_second_wave_source_confirmation_primary_focus_ligand")),
        "glut1_negative_handoff_artifact": _text(glut1_negative_handoff_summary.get("packet_artifact"))
        or "runs/glut1_negative_review_handoff_packet_current.md",
        "next_required_step": (
            "Close transporter negatives in strict order: AQP1 core_non_binder_01 through core_non_binder_03 first, "
            "then GLUT1 core_non_binder_01 through core_non_binder_03. Treat caution and blocker rows as references only, "
            "keep all six rows review-only until direct negative evidence is curated, and do not reopen binder staging or donor-policy work while this queue is open."
        ),
    }
    return {"summary": summary, "rows": rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the transporter negative-evidence closure queue.")
    parser.add_argument("--negative-day-plan-json", default=str(DEFAULT_NEGATIVE_DAY_PLAN_JSON))
    parser.add_argument("--placeholder-queue-json", default=str(DEFAULT_PLACEHOLDER_QUEUE_JSON))
    parser.add_argument("--target-packets-json", default=str(DEFAULT_TARGET_PACKETS_JSON))
    parser.add_argument("--glut1-negative-handoff-json", default=str(DEFAULT_GLUT1_NEGATIVE_HANDOFF_JSON))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.negative_day_plan_json),
        _load_json(args.placeholder_queue_json),
        _load_json(args.target_packets_json),
        _load_json(args.glut1_negative_handoff_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
