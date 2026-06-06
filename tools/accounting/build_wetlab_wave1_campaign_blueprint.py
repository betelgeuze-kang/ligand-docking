#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_wave1_campaign_blueprint_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_wave1_campaign_blueprint_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_wave1_campaign_blueprint_current.md"

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

CAMPAIGN_PRESETS: dict[str, dict[str, str]] = {
    "T. cruzi PDE": {
        "first_assay": "recombinant PDE enzyme inhibition panel plus human PDE anti-target screen",
        "first_partner_type": "DNDi/IPK neglected-disease screening partner",
        "anti_target_panel": "human PDE selectivity mini-panel",
        "first_go_no_go": "parasite PDE signal with early human PDE separation",
    },
    "Cruzain": {
        "first_assay": "fluorogenic protease assay plus cysteine-reactivity sanity check",
        "first_partner_type": "DNDi/IPK or Chagas-focused academic protease lab",
        "anti_target_panel": "host cysteine protease and generic thiol-reactivity panel",
        "first_go_no_go": "clean Cruzain inhibition without broad reactive noise",
    },
    "ALK2": {
        "first_assay": "kinase biochemical assay or DSF plus mutant/wild-type comparison",
        "first_partner_type": "M4K-aligned open-science kinase or DIPG translational lab",
        "anti_target_panel": "ALK2 close-kinase selectivity mini-panel",
        "first_go_no_go": "ALK2 engagement with acceptable selectivity and tractable CNS path",
    },
    "STK17B (DRAK2)": {
        "first_assay": "DSF or kinase engagement assay with open-probe benchmark controls",
        "first_partner_type": "SGC/open-probe structural biology or kinase lab",
        "anti_target_panel": "dark-kinase neighborhood selectivity panel",
        "first_go_no_go": "signal beyond existing probe/negative-control baseline",
    },
    "CA IX": {
        "first_assay": "CA IX enzyme assay at acidic tumor-like buffer plus CA II/CA XII counterscreen",
        "first_partner_type": "oncology lab with hypoxia or extracellular pH assays",
        "anti_target_panel": "CA II plus CA XII selectivity panel",
        "first_go_no_go": "acidic-condition advantage with CA IX-biased selectivity",
    },
    "SARS-CoV-2 PLpro": {
        "first_assay": "fluorogenic PLpro assay plus host DUB-like counterscreen",
        "first_partner_type": "READDI-linked antiviral or protease lab",
        "anti_target_panel": "host DUB-like or cysteine-protease sanity panel",
        "first_go_no_go": "PLpro signal with manageable host-like off-target risk",
    },
    "SARS-CoV-2 Mpro": {
        "first_assay": "cheap fluorogenic Mpro assay with orthogonal thermal or biochemical confirmation",
        "first_partner_type": "Moonshot-adjacent antiviral or fast protease-screening lab",
        "anti_target_panel": "host cysteine protease sanity panel",
        "first_go_no_go": "repeatable Mpro inhibition in a low-friction assay stack",
    },
    "Leishmania braziliensis DHODH": {
        "first_assay": "recombinant DHODH enzyme inhibition with orthogonal enzyme counterscreen",
        "first_partner_type": "DNDi leishmaniasis partner or neglected-disease enzyme lab",
        "anti_target_panel": "host DHODH or close-enzyme counterscreen",
        "first_go_no_go": "parasite-enzyme signal with early host-enzyme separation",
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


def build_payload(portfolio: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in portfolio.get("rows", []) or []:
        if row.get("wave") != "Wave 1":
            continue
        preset = CAMPAIGN_PRESETS[str(row["target_id"])]
        rows.append(
            {
                "target_id": row["target_id"],
                "partner_rail": row["partner_rail"],
                "outreach_track_id": TRACK_FOR_TARGET[str(row["target_id"])],
                "repurposing_lane_slots": 3,
                "novelty_lane_slots": 3,
                "first_assay": preset["first_assay"],
                "first_partner_type": preset["first_partner_type"],
                "anti_target_panel": preset["anti_target_panel"],
                "companion_panel_artifact": "runs/wetlab_validation_companion_panels_current.md",
                "first_go_no_go": preset["first_go_no_go"],
                "packet_stack": "one_page_brief + evidence_packet + wet_lab_packet",
                "base_requirement": "top_3_repurposing plus top_3_novelty plus one explicit negative/control lane",
            }
        )

    summary = {
        "status": "wetlab_wave1_campaign_blueprint_ready",
        "wave1_target_count": len(rows),
        "repurposing_lane_slots_per_target": 3,
        "novelty_lane_slots_per_target": 3,
        "packet_stack": "one_page_brief + evidence_packet + wet_lab_packet",
        "required_control_rule": "Every Wave 1 campaign should ship with at least one explicit anti-target or non-hit control lane before outbound outreach.",
        "next_required_step": "Fill the top-3 repurposing and top-3 novelty slots for each Wave 1 target, then export partner-specific outreach packets starting with DNDi/IPK, M4K, READDI, and the CA IX condition-aware oncology lane.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Wave 1 Campaign Blueprint",
        "",
        f"- status: `{s['status']}`",
        f"- wave1_target_count: `{s['wave1_target_count']}`",
        f"- repurposing_lane_slots_per_target: `{s['repurposing_lane_slots_per_target']}`",
        f"- novelty_lane_slots_per_target: `{s['novelty_lane_slots_per_target']}`",
        f"- packet_stack: `{s['packet_stack']}`",
        "",
        "## Wave 1 Targets",
        "",
        "| target_id | outreach_track_id | partner_rail | repurposing_slots | novelty_slots | first_assay | anti_target_panel | first_go_no_go |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['outreach_track_id']}` | `{row['partner_rail']}` | `{row['repurposing_lane_slots']}` | `{row['novelty_lane_slots']}` | {row['first_assay']} | {row['anti_target_panel']} | {row['first_go_no_go']} |"
        )
    lines.extend([
        "",
        "## Guardrail",
        "",
        f"- {s['required_control_rule']}",
        "- Every row in this blueprint should route through the shared validation companion panel artifact before outbound outreach.",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Wave 1 wet-lab campaign blueprint for outbound partner packaging.")
    parser.add_argument("--portfolio-json", default=DEFAULT_PORTFOLIO_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_load_json(args.portfolio_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
