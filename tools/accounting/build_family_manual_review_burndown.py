#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CA2_READINESS_JSON = "runs/ca2_packet_replacement_readiness_current.json"
DEFAULT_CA2_QUEUE_JSON = "runs/ca2_manual_review_queue_current.json"
DEFAULT_PXR_READINESS_JSON = "runs/pxr_packet_fill_readiness_current.json"
DEFAULT_PXR_QUEUE_JSON = "runs/pxr_manual_review_queue_current.json"
DEFAULT_AQP1_VERDICT_JSON = "runs/aqp1_candidate_verdict_sheet_current.json"
DEFAULT_AQP1_BINDER_SHEET_JSON = "runs/aqp1_binder_verdict_update_sheet_current.json"
DEFAULT_GLUT1_VERDICT_JSON = "runs/glut1_candidate_verdict_sheet_current.json"
DEFAULT_GLUT1_BINDER_SHEET_JSON = "runs/glut1_binder_verdict_update_sheet_current.json"
DEFAULT_OUT_JSON = "runs/family_manual_review_burndown_current.json"
DEFAULT_OUT_CSV = "runs/family_manual_review_burndown_current.csv"
DEFAULT_OUT_MD = "runs/family_manual_review_burndown_current.md"


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


def _ca2_row(readiness: dict[str, Any], queue: dict[str, Any]) -> dict[str, Any]:
    rs = dict(readiness.get("summary", {}) or {})
    qs = dict(queue.get("summary", {}) or {})
    return {
        "family": "ca2",
        "ready_count": int(rs.get("ready_row_count", 0) or 0),
        "review_only_count": int(qs.get("review_only_negative_count", 0) or 0),
        "defer_count": int(qs.get("defer_binder_count", 0) or 0),
        "pending_manual_count": int(qs.get("policy_fixed_pending_count", 0) or 0),
        "current_stage": "partial_authoritative_rows_plus_negative_review",
        "next_required_step": str(qs.get("next_required_step", rs.get("next_required_step", ""))).strip(),
    }


def _pxr_row(readiness: dict[str, Any], queue: dict[str, Any]) -> dict[str, Any]:
    rs = dict(readiness.get("summary", {}) or {})
    qs = dict(queue.get("summary", {}) or {})
    return {
        "family": "pxr",
        "ready_count": int(rs.get("ready_for_apply_row_count", 0) or 0),
        "review_only_count": int(qs.get("review_only_negative_count", 0) or 0),
        "defer_count": int(qs.get("defer_binder_count", 0) or 0),
        "pending_manual_count": int(qs.get("policy_fixed_pending_count", 0) or 0),
        "current_stage": "partial_authoritative_rows_plus_pending_policy",
        "next_required_step": str(qs.get("next_required_step", rs.get("next_required_step", ""))).strip(),
    }


def _transporter_row(
    family: str,
    verdict: dict[str, Any],
    binder_sheet: dict[str, Any],
    stage_label: str,
) -> dict[str, Any]:
    vs = dict(verdict.get("summary", {}) or {})
    bs = dict(binder_sheet.get("summary", {}) or {})
    pending_manual_count = int(bs.get("pending_manual_verdict_count", 0) or 0)
    return {
        "family": family,
        "ready_count": 0,
        "review_only_count": int(vs.get("keep_review_only_count", 0) or 0),
        "defer_count": int(vs.get("defer_count", 0) or 0),
        "pending_manual_count": pending_manual_count,
        "current_stage": (
            stage_label
            if pending_manual_count > 0
            else ("first_wave_seed_row_promotion" if family == "aqp1" else "second_wave_seed_row_hold")
        ),
        "next_required_step": (
            str(bs.get("next_required_step", vs.get("next_required_step", ""))).strip()
            if pending_manual_count > 0
            else (
                "Advance AQP1 seed-row promotion and keep authoritative apply blocked while placeholder rows remain."
                if family == "aqp1"
                else "Keep GLUT1 second-wave staged behind AQP1 seed-row promotion until blocker closure advances."
            )
        ),
    }


def build_payload(
    ca2_readiness: dict[str, Any],
    ca2_queue: dict[str, Any],
    pxr_readiness: dict[str, Any],
    pxr_queue: dict[str, Any],
    aqp1_verdict: dict[str, Any],
    aqp1_binder_sheet: dict[str, Any],
    glut1_verdict: dict[str, Any],
    glut1_binder_sheet: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        _ca2_row(ca2_readiness, ca2_queue),
        _pxr_row(pxr_readiness, pxr_queue),
        _transporter_row(
            "aqp1",
            aqp1_verdict,
            aqp1_binder_sheet,
            "first_wave_manual_review",
        ),
        _transporter_row(
            "glut1",
            glut1_verdict,
            glut1_binder_sheet,
            "second_wave_manual_review",
        ),
    ]
    summary = {
        "family_count": len(rows),
        "ready_count_total": sum(int(row["ready_count"]) for row in rows),
        "review_only_count_total": sum(int(row["review_only_count"]) for row in rows),
        "defer_count_total": sum(int(row["defer_count"]) for row in rows),
        "pending_manual_count_total": sum(int(row["pending_manual_count"]) for row in rows),
        "families_with_ready_rows": sum(1 for row in rows if int(row["ready_count"]) > 0),
        "families_with_pending_manual": sum(1 for row in rows if int(row["pending_manual_count"]) > 0),
        "next_required_step": (
            "Hold CA2/PXR policy-fixed rows manual-only, advance AQP1 first-wave seed-row promotion, and keep GLUT1 second-wave staged behind it."
            if sum(int(row["pending_manual_count"]) for row in rows) == 0
            else "Burn down pending-manual work family by family: keep CA2/PXR policy-fixed rows manual-only, then clear AQP1 first-wave verdicts before GLUT1 second-wave."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Family Manual Review Burndown",
        "",
        f"- family_count: `{s['family_count']}`",
        f"- ready_count_total: `{s['ready_count_total']}`",
        f"- review_only_count_total: `{s['review_only_count_total']}`",
        f"- defer_count_total: `{s['defer_count_total']}`",
        f"- pending_manual_count_total: `{s['pending_manual_count_total']}`",
        f"- families_with_ready_rows: `{s['families_with_ready_rows']}`",
        f"- families_with_pending_manual: `{s['families_with_pending_manual']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Families",
        "",
        "| family | ready_count | review_only_count | defer_count | pending_manual_count | current_stage | next_required_step |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | {row['ready_count']} | {row['review_only_count']} | {row['defer_count']} | "
            f"{row['pending_manual_count']} | `{row['current_stage']}` | {row['next_required_step']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a manual review burndown board across CA2, PXR, AQP1, and GLUT1.")
    parser.add_argument("--ca2-readiness-json", default=DEFAULT_CA2_READINESS_JSON)
    parser.add_argument("--ca2-queue-json", default=DEFAULT_CA2_QUEUE_JSON)
    parser.add_argument("--pxr-readiness-json", default=DEFAULT_PXR_READINESS_JSON)
    parser.add_argument("--pxr-queue-json", default=DEFAULT_PXR_QUEUE_JSON)
    parser.add_argument("--aqp1-verdict-json", default=DEFAULT_AQP1_VERDICT_JSON)
    parser.add_argument("--aqp1-binder-sheet-json", default=DEFAULT_AQP1_BINDER_SHEET_JSON)
    parser.add_argument("--glut1-verdict-json", default=DEFAULT_GLUT1_VERDICT_JSON)
    parser.add_argument("--glut1-binder-sheet-json", default=DEFAULT_GLUT1_BINDER_SHEET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.ca2_readiness_json),
        _load_json(args.ca2_queue_json),
        _load_json(args.pxr_readiness_json),
        _load_json(args.pxr_queue_json),
        _load_json(args.aqp1_verdict_json),
        _load_json(args.aqp1_binder_sheet_json),
        _load_json(args.glut1_verdict_json),
        _load_json(args.glut1_binder_sheet_json),
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
