#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BLUEPRINT_JSON = "runs/wetlab_wave1_campaign_blueprint_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_wave1_candidate_slot_workbook_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_wave1_candidate_slot_workbook_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_wave1_candidate_slot_workbook_current.md"

SLOT_PRESETS: dict[str, dict[str, str]] = {
    "T. cruzi PDE": {
        "repurposing": "Cheap approved or commoditized PDE-active scaffold with plausible parasite pocket fit and an early plan for human PDE deselection.",
        "novelty": "Cross-family-discriminative scaffold that exploits parasite-specific pocket geometry or hydration beyond known human-PDE chemotypes.",
    },
    "Cruzain": {
        "repurposing": "Low-cost approved or tool-like cysteine-protease-active scaffold that is not broadly thiol-reactive and can survive a simple reactivity sanity check.",
        "novelty": "Desolvation-aware Cruzain chemotype aimed at dynamic surface-groove capture without generic electrophile noise.",
    },
    "ALK2": {
        "repurposing": "Approved or clinically familiar kinase scaffold with plausible ALK2 engagement and an acceptable CNS/BBB starting story.",
        "novelty": "ALK2-biased state-discriminative scaffold that exploits dynamic kinase geometry beyond generic hinge-binding motifs.",
    },
    "STK17B (DRAK2)": {
        "repurposing": "Drug-like kinase-active scaffold with enough tractability to benchmark against the open-probe ecosystem, even if true repurposing odds are modest.",
        "novelty": "Dynamic P-loop-aware chemotype that separates from known dark-kinase probe space while keeping kinase-like tractability.",
    },
    "CA IX": {
        "repurposing": "Cheap approved carbonic-anhydrase inhibitor class member that can be retested under acidic tumor-like buffer with CA II/CA XII counterscreens.",
        "novelty": "Condition-aware CA IX scaffold designed to gain preference in acidic tumor-like buffer rather than merely copying generic sulfonamide behavior.",
    },
    "SARS-CoV-2 PLpro": {
        "repurposing": "Low-cost approved or accessible protease-active scaffold that can enter a fast PLpro biochemical screen and survive host-like counterscreens.",
        "novelty": "Shallow-pocket PLpro chemotype optimized for dynamic surface anchoring without looking like a generic cysteine-protease false positive.",
    },
    "SARS-CoV-2 Mpro": {
        "repurposing": "Approved or highly accessible protease-relevant scaffold suitable for the cheapest fluorogenic Mpro triage stack.",
        "novelty": "Dynamics-first Mpro chemotype that keeps tractable biochemistry but avoids a too-generic crowded-field story.",
    },
    "Leishmania braziliensis DHODH": {
        "repurposing": "Affordable enzyme-active scaffold with enough precedent to support a quick neglected-disease enzyme triage screen, even if repurposing odds are lower.",
        "novelty": "Parasite-DHODH-biased scaffold that emphasizes host-enzyme separation early and can support a novel chemistry neglected-disease story.",
    },
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


def build_payload(blueprint: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for target_row in blueprint.get("rows", []) or []:
        target_id = str(target_row.get("target_id", ""))
        preset = SLOT_PRESETS[target_id]
        for lane_key, criteria_text in (("repurposing", preset["repurposing"]), ("novelty", preset["novelty"])):
            for slot_rank in range(1, 4):
                rows.append(
                    {
                        "target_id": target_id,
                        "lane": lane_key,
                        "slot_rank": slot_rank,
                        "slot_label": f"{lane_key}_slot_{slot_rank}",
                        "slot_criteria": criteria_text,
                        "compound_name": "",
                        "source_or_vendor": "",
                        "why_this_slot": "",
                        "status": "ready_for_manual_fill",
                    }
                )
    summary = {
        "status": "wetlab_wave1_candidate_slot_workbook_ready",
        "target_count": len({row["target_id"] for row in rows}),
        "row_count": len(rows),
        "repurposing_slot_count": sum(1 for row in rows if row["lane"] == "repurposing"),
        "novelty_slot_count": sum(1 for row in rows if row["lane"] == "novelty"),
        "next_required_step": "Fill compound_name, source_or_vendor, and why_this_slot for each Wave 1 repurposing and novelty slot before exporting target-specific one-page briefs.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Wave 1 Candidate Slot Workbook",
        "",
        f"- status: `{s['status']}`",
        f"- target_count: `{s['target_count']}`",
        f"- row_count: `{s['row_count']}`",
        f"- repurposing_slot_count: `{s['repurposing_slot_count']}`",
        f"- novelty_slot_count: `{s['novelty_slot_count']}`",
        "",
        "| target_id | lane | slot_rank | slot_criteria | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['lane']}` | `{row['slot_rank']}` | {row['slot_criteria']} | `{row['status']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Wave 1 candidate slot workbook for repurposing and novelty lanes.")
    parser.add_argument("--blueprint-json", default=DEFAULT_BLUEPRINT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.blueprint_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
