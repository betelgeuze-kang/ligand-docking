#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_BLUEPRINT_JSON = "runs/wetlab_wave1_campaign_blueprint_current.json"
DEFAULT_COMPANION_JSON = "runs/wetlab_validation_companion_panels_current.json"
DEFAULT_OUTREACH_JSON = "runs/wetlab_partner_outreach_tracks_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_wave1_packet_queue_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_wave1_packet_queue_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_wave1_packet_queue_current.md"

TRACK_FOR_TARGET = {
    "T. cruzi PDE": "DNDi_IPK",
    "Cruzain": "DNDi_IPK",
    "Leishmania braziliensis DHODH": "DNDi_IPK",
    "ALK2": "M4K_open_science",
    "STK17B (DRAK2)": "SGC_dark_kinase",
    "CA IX": "oncology_condition_aware",
    "SARS-CoV-2 PLpro": "READDI_Korea",
    "SARS-CoV-2 Mpro": "READDI_Korea",
}

BRIEF_SLUG_FOR_TARGET = {
    "T. cruzi PDE": "tcruzi_pde",
    "Cruzain": "cruzain",
    "Leishmania braziliensis DHODH": "lbdhodh",
    "ALK2": "alk2",
    "STK17B (DRAK2)": "stk17b",
    "CA IX": "caix",
    "SARS-CoV-2 PLpro": "sarscov2_plpro",
    "SARS-CoV-2 Mpro": "sarscov2_mpro",
}


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


def build_payload(portfolio: dict[str, Any], blueprint: dict[str, Any], companion: dict[str, Any], outreach: dict[str, Any]) -> dict[str, Any]:
    blueprint_rows = {row["target_id"]: dict(row) for row in blueprint.get("rows", []) or []}
    companion_rows = {row["target_id"]: dict(row) for row in companion.get("rows", []) or []}
    outreach_rows = {row["track_id"]: dict(row) for row in outreach.get("rows", []) or []}

    rows = []
    for row in portfolio.get("rows", []) or []:
        if row.get("wave") != "Wave 1":
            continue
        target = str(row["target_id"])
        track_id = TRACK_FOR_TARGET[target]
        b = blueprint_rows[target]
        c = companion_rows[target]
        o = outreach_rows[track_id]
        rows.append(
            {
                "target_id": target,
                "track_id": track_id,
                "track_label": o["track_label"],
                "brief_artifact_planned": f"runs/wetlab_target_brief_{BRIEF_SLUG_FOR_TARGET[target]}_current.md",
                "first_assay": b["first_assay"],
                "anti_target_panel": c["primary_companion_panel"],
                "repurposing_slot_count": b["repurposing_lane_slots"],
                "novelty_slot_count": b["novelty_lane_slots"],
                "queue_status": "ready_for_target_specific_fill",
                "next_required_step": "Fill top-3 repurposing, top-3 novelty, and one explicit negative/control lane before outreach.",
            }
        )

    summary = {
        "status": "wetlab_wave1_packet_queue_ready",
        "wave1_target_count": len(rows),
        "ready_for_target_specific_fill_count": sum(1 for row in rows if row["queue_status"] == "ready_for_target_specific_fill"),
        "next_required_step": "Use this queue to build target-specific one-page briefs in Wave 1 order, starting with DNDi/IPK, CA IX, and the antiviral protease pair.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Wave 1 Packet Queue",
        "",
        f"- status: `{s['status']}`",
        f"- wave1_target_count: `{s['wave1_target_count']}`",
        f"- ready_for_target_specific_fill_count: `{s['ready_for_target_specific_fill_count']}`",
        "",
        "| target_id | track_id | track_label | brief_artifact_planned | first_assay | anti_target_panel | repurposing_slots | novelty_slots | queue_status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['track_id']}` | `{row['track_label']}` | `{row['brief_artifact_planned']}` | {row['first_assay']} | {row['anti_target_panel']} | `{row['repurposing_slot_count']}` | `{row['novelty_slot_count']}` | `{row['queue_status']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Wave 1 target-specific packet queue.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--blueprint-json", default=DEFAULT_BLUEPRINT_JSON)
    parser.add_argument("--companion-json", default=DEFAULT_COMPANION_JSON)
    parser.add_argument("--outreach-json", default=DEFAULT_OUTREACH_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.portfolio_json),
        _load_json(args.blueprint_json),
        _load_json(args.companion_json),
        _load_json(args.outreach_json),
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
