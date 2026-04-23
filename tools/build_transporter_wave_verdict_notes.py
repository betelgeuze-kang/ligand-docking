#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WAVE_DECISION_JSON = "runs/transporter_wave_decision_current.json"
DEFAULT_AQP1_QUEUE_JSON = "runs/aqp1_manual_review_queue_current.json"
DEFAULT_AQP1_VERDICT_JSON = "runs/aqp1_candidate_verdict_sheet_current.json"
DEFAULT_GLUT1_QUEUE_JSON = "runs/glut1_manual_review_queue_current.json"
DEFAULT_GLUT1_VERDICT_JSON = "runs/glut1_candidate_verdict_sheet_current.json"
DEFAULT_OUT_JSON = "runs/transporter_wave_verdict_notes_current.json"
DEFAULT_OUT_CSV = "runs/transporter_wave_verdict_notes_current.csv"
DEFAULT_OUT_MD = "runs/transporter_wave_verdict_notes_current.md"


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


def _wave_label_for_target(wave_decision: dict[str, Any], target_id: str) -> str:
    for row in wave_decision.get("rows", []):
        if str(row.get("target_id", "")).upper() == target_id.upper():
            return str(row.get("wave_label", "")).strip()
    return ""


def _top_candidates(queue_payload: dict[str, Any], limit: int = 3) -> list[str]:
    rows = queue_payload.get("rows", []) or []
    candidates: list[str] = []
    for row in rows:
        value = str(row.get("suggested_external_candidate", "")).strip()
        if value:
            candidates.append(value)
        if len(candidates) >= limit:
            break
    return candidates


def _family_row(
    target_id: str,
    wave_decision: dict[str, Any],
    queue_payload: dict[str, Any],
    verdict_payload: dict[str, Any],
) -> dict[str, Any]:
    verdict_summary = dict(verdict_payload.get("summary", {}) or {})
    queue_summary = dict(queue_payload.get("summary", {}) or {})
    next_step = str(queue_summary.get("next_required_step", "")).strip()
    return {
        "target_id": target_id,
        "wave_label": _wave_label_for_target(wave_decision, target_id),
        "top_candidates": ", ".join(_top_candidates(queue_payload)),
        "keep_review_only_count": verdict_summary.get("keep_review_only_count", 0),
        "caution_only_count": verdict_summary.get("caution_only_count", 0),
        "defer_count": verdict_summary.get("defer_count", 0),
        "policy_status": "reviewer_state_only_blocker_closure",
        "hard_stop": "no_authoritative_apply_without_transporter_specific_packet_evidence",
        "next_required_step": next_step,
    }


def build_payload(
    wave_decision: dict[str, Any],
    aqp1_queue: dict[str, Any],
    aqp1_verdict: dict[str, Any],
    glut1_queue: dict[str, Any],
    glut1_verdict: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        _family_row("AQP1", wave_decision, aqp1_queue, aqp1_verdict),
        _family_row("GLUT1", wave_decision, glut1_queue, glut1_verdict),
    ]
    summary = {
        "family_count": len(rows),
        "first_wave_target": "AQP1",
        "second_wave_target": "GLUT1",
        "policy_status": "reviewer_state_only_blocker_closure",
        "next_required_step": (
            "Treat AQP1 as the first-wave blocker-closure target and GLUT1 as the second-wave follow-up. "
            "Use the top candidates below only as review prompts, and keep all transporter rows out of authoritative apply until transporter-specific packet evidence exists."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# Transporter Wave Verdict Notes",
        "",
        f"- family_count: `{summary['family_count']}`",
        f"- first_wave_target: `{summary['first_wave_target']}`",
        f"- second_wave_target: `{summary['second_wave_target']}`",
        f"- policy_status: `{summary['policy_status']}`",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
        "## Wave Notes",
        "",
        "| target_id | wave_label | top_candidates | keep_review_only_count | caution_only_count | defer_count | hard_stop |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['wave_label']}` | {row['top_candidates']} | {row['keep_review_only_count']} | {row['caution_only_count']} | {row['defer_count']} | `{row['hard_stop']}` |"
        )
        lines.append(f"| `{row['target_id']}` next |  | {row['next_required_step']} |  |  |  |  |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build concise wave verdict notes for transporter first-wave and second-wave review.")
    parser.add_argument("--wave-decision-json", default=DEFAULT_WAVE_DECISION_JSON)
    parser.add_argument("--aqp1-queue-json", default=DEFAULT_AQP1_QUEUE_JSON)
    parser.add_argument("--aqp1-verdict-json", default=DEFAULT_AQP1_VERDICT_JSON)
    parser.add_argument("--glut1-queue-json", default=DEFAULT_GLUT1_QUEUE_JSON)
    parser.add_argument("--glut1-verdict-json", default=DEFAULT_GLUT1_VERDICT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.wave_decision_json),
        _load_json(args.aqp1_queue_json),
        _load_json(args.aqp1_verdict_json),
        _load_json(args.glut1_queue_json),
        _load_json(args.glut1_verdict_json),
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
