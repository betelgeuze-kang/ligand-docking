#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BRIEF_INDEX_JSON = "runs/wetlab_wave1_target_brief_index_current.json"
DEFAULT_RENDER_SUITE_JSON = "runs/caix_render_suite_current.json"
DEFAULT_EXPORT_JSON = "runs/caix_oncology_export_current.json"
DEFAULT_CONDITION_CARD_JSON = "runs/caix_condition_card_current.json"
DEFAULT_OUT_JSON = "runs/caix_launch_packet_current.json"
DEFAULT_OUT_CSV = "runs/caix_launch_packet_current.csv"
DEFAULT_OUT_MD = "runs/caix_launch_packet_current.md"


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


def _rows_by_target(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("target_id", "")): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get("target_id", "")).strip()
    }


def build_payload(
    brief_index: dict[str, Any],
    render_suite: dict[str, Any],
    export_payload: dict[str, Any],
    condition_card: dict[str, Any],
) -> dict[str, Any]:
    brief = _rows_by_target(brief_index)["CA IX"]
    suite_s = dict(render_suite.get("summary", {}) or {})
    export_s = dict(export_payload.get("summary", {}) or {})
    condition_s = dict(condition_card.get("structured", {}) or {})
    suite_rows = [dict(row) for row in render_suite.get("rows", []) or []]

    required_rows = [
        {
            "requirement_rank": str(idx),
            "artifact_kind": str(row.get("artifact_kind", "")).strip(),
            "artifact_path": str(row.get("artifact_path", "")).strip(),
            "launch_requirement": "must_exist_before_run",
            "queue_blocking": "hard_block",
            "handoff_role": (
                "wet_lab_context"
                if str(row.get("artifact_kind", "")).strip() == "condition_card"
                else "selectivity_panel"
                if str(row.get("artifact_kind", "")).strip() == "selectivity_panel"
                else "execution_stack"
                if str(row.get("artifact_kind", "")).strip() == "assay_packet"
                else "decision_gate"
                if str(row.get("artifact_kind", "")).strip() == "go_no_go_card"
                else "partner_export"
            ),
        }
        for idx, row in enumerate(suite_rows, start=1)
    ]

    summary = {
        "status": "caix_launch_packet_ready",
        "target_id": "CA IX",
        "serialized_queue_rank": 2,
        "serialized_run_order": "2_of_3",
        "execution_mode": "serialized_by_protein_target",
        "parallel_prep_allowed": True,
        "partner_track_id": str(suite_s.get("partner_track_id", export_s.get("partner_track_id", ""))).strip(),
        "render_suite_status": str(suite_s.get("status", "")).strip(),
        "export_status": str(export_s.get("status", "")).strip(),
        "required_artifact_count": len(required_rows),
        "acidic_primary_arm": str(condition_s.get("acidic_primary_arm", "")).strip(),
        "neutral_contrast_arm": str(condition_s.get("neutral_contrast_arm", "")).strip(),
        "launch_readiness": "ready_for_serialized_execution",
        "execution_goal": "Open the condition-aware oncology packet only after Mpro clears, with acidic-arm execution and same-packet CA II / CA XII deselection fixed from the start.",
        "blocking_rule": "Do not start T. cruzi PDE execution until this CA IX packet reaches result-ready or explicit hold.",
        "next_target_on_success": "T. cruzi PDE",
        "next_target_on_hold": "T. cruzi PDE",
        "headline": str(brief.get("headline", "")).strip(),
        "next_required_step": "Launch CA IX second in the serialized protein queue after Mpro reaches result-ready or explicit hold, while T. cruzi PDE remains prep-only.",
    }
    return {"summary": summary, "rows": required_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# CA IX Launch Packet",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- serialized_queue_rank: `{s['serialized_queue_rank']}`",
        f"- serialized_run_order: `{s['serialized_run_order']}`",
        f"- execution_mode: `{s['execution_mode']}`",
        f"- parallel_prep_allowed: `{s['parallel_prep_allowed']}`",
        f"- partner_track_id: `{s['partner_track_id']}`",
        f"- render_suite_status: `{s['render_suite_status']}`",
        f"- export_status: `{s['export_status']}`",
        f"- required_artifact_count: `{s['required_artifact_count']}`",
        f"- launch_readiness: `{s['launch_readiness']}`",
        "",
        "## Execution Framing",
        "",
        f"- headline: {s['headline']}",
        f"- acidic_primary_arm: `{s['acidic_primary_arm']}`",
        f"- neutral_contrast_arm: `{s['neutral_contrast_arm']}`",
        f"- execution_goal: {s['execution_goal']}",
        f"- blocking_rule: {s['blocking_rule']}",
        f"- next_target_on_success: `{s['next_target_on_success']}`",
        f"- next_target_on_hold: `{s['next_target_on_hold']}`",
        "",
        "## Required Artifacts",
        "",
        "| requirement_rank | artifact_kind | artifact_path | launch_requirement | queue_blocking | handoff_role |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['requirement_rank']}` | `{row['artifact_kind']}` | `{row['artifact_path']}` | `{row['launch_requirement']}` | `{row['queue_blocking']}` | `{row['handoff_role']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the serialized execution launch packet for CA IX.")
    parser.add_argument("--brief-index-json", default=DEFAULT_BRIEF_INDEX_JSON)
    parser.add_argument("--render-suite-json", default=DEFAULT_RENDER_SUITE_JSON)
    parser.add_argument("--export-json", default=DEFAULT_EXPORT_JSON)
    parser.add_argument("--condition-card-json", default=DEFAULT_CONDITION_CARD_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.brief_index_json),
        _load_json(args.render_suite_json),
        _load_json(args.export_json),
        _load_json(args.condition_card_json),
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
