#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MPRO_RENDER_SUITE_JSON = "runs/sarscov2_mpro_render_suite_current.json"
DEFAULT_CAIX_RENDER_SUITE_JSON = "runs/caix_render_suite_current.json"
DEFAULT_TCRUZI_RENDER_SUITE_JSON = "runs/tcruzi_pde_render_suite_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_prep_artifact_lane_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_prep_artifact_lane_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_prep_artifact_lane_current.md"


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


def _render_status(payload: dict[str, Any]) -> str:
    return str((payload.get("summary") or {}).get("status", "")).strip()


def build_payload(
    mpro_render_suite: dict[str, Any],
    caix_render_suite: dict[str, Any],
    tcruzi_render_suite: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        {
            "execution_target": "SARS-CoV-2 Mpro",
            "serialized_execution_slot": "active_slot_1",
            "parallel_prep_targets": "CA IX; T. cruzi PDE",
            "allowed_parallel_work": "launch packet polish, partner export proofread, artifact regeneration, queue updates",
            "execution_block_rule": "No second protein execution opens while Mpro is running.",
            "render_suite_status": _render_status(mpro_render_suite),
        },
        {
            "execution_target": "CA IX",
            "serialized_execution_slot": "active_slot_2",
            "parallel_prep_targets": "T. cruzi PDE",
            "allowed_parallel_work": "PDE launch packet polish, DNDi/IPK export proofread, artifact regeneration, queue updates",
            "execution_block_rule": "CA IX waits for Mpro result-ready or explicit hold before execution opens.",
            "render_suite_status": _render_status(caix_render_suite),
        },
        {
            "execution_target": "T. cruzi PDE",
            "serialized_execution_slot": "active_slot_3",
            "parallel_prep_targets": "",
            "allowed_parallel_work": "close documentation, result rollup, and outbound follow-up only",
            "execution_block_rule": "T. cruzi PDE waits for both Mpro and CA IX to resolve first.",
            "render_suite_status": _render_status(tcruzi_render_suite),
        },
    ]
    summary = {
        "status": "wetlab_prep_artifact_lane_ready",
        "target_count": len(rows),
        "serialized_execution_rule": "Exactly one protein target executes at a time.",
        "parallel_artifact_rule": "Non-execution prep and artifact work may continue for later queue targets while the current execution slot is active.",
        "ready_render_suite_count": sum(1 for row in rows if row["render_suite_status"].endswith("_render_suite_ready")),
        "next_required_step": "Use this lane together with the priority-three protein run queue so execution stays serialized while documentation and packet prep keep moving.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Prep / Artifact Lane",
        "",
        f"- status: `{s['status']}`",
        f"- target_count: `{s['target_count']}`",
        f"- serialized_execution_rule: {s['serialized_execution_rule']}",
        f"- parallel_artifact_rule: {s['parallel_artifact_rule']}",
        f"- ready_render_suite_count: `{s['ready_render_suite_count']}`",
        "",
        "| execution_target | serialized_execution_slot | parallel_prep_targets | allowed_parallel_work | execution_block_rule | render_suite_status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['execution_target']}` | `{row['serialized_execution_slot']}` | `{row['parallel_prep_targets']}` | {row['allowed_parallel_work']} | {row['execution_block_rule']} | `{row['render_suite_status']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the parallel prep/artifact lane for the serialized Mpro -> CA IX -> T. cruzi PDE execution queue.")
    parser.add_argument("--mpro-render-suite-json", default=DEFAULT_MPRO_RENDER_SUITE_JSON)
    parser.add_argument("--caix-render-suite-json", default=DEFAULT_CAIX_RENDER_SUITE_JSON)
    parser.add_argument("--tcruzi-render-suite-json", default=DEFAULT_TCRUZI_RENDER_SUITE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.mpro_render_suite_json),
        _load_json(args.caix_render_suite_json),
        _load_json(args.tcruzi_render_suite_json),
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
