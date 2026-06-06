#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORTFOLIO_JSON = "runs/wetlab_partner_target_portfolio_current.json"
DEFAULT_OUT_JSON = "runs/wetlab_validation_companion_panels_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_validation_companion_panels_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_validation_companion_panels_current.md"

COMPANION_PRESETS: dict[str, dict[str, str]] = {
    "T. cruzi PDE": {
        "primary_companion": "human PDE family mini-panel",
        "why": "The whole value proposition depends on parasite-vs-human PDE separation.",
    },
    "Cruzain": {
        "primary_companion": "host cysteine protease plus thiol-reactivity sanity set",
        "why": "Cheap protease hits are often reactive; the validation story needs a false-positive filter.",
    },
    "ALK2": {
        "primary_companion": "close-kinase mini-panel with mutant/wild-type comparison",
        "why": "Rare-disease kinase outreach will immediately ask whether the signal survives selective kinase triage.",
    },
    "LRRK2": {
        "primary_companion": "kinase selectivity and CNS-relevant liability panel",
        "why": "Large flexible kinase stories are weak without selectivity and translational sanity checks.",
    },
    "STK17B (DRAK2)": {
        "primary_companion": "open-probe positive/negative controls plus neighborhood kinase panel",
        "why": "The open-probe ecosystem makes benchmark controls part of the pitch, not optional extras.",
    },
    "CA IX": {
        "primary_companion": "CA II plus CA XII counterscreen",
        "why": "Condition-aware CA IX campaigns are only credible if selectivity over canonical carbonic anhydrases is shown.",
    },
    "DprE1": {
        "primary_companion": "host-enzyme and whole-cell orthogonal validation panel",
        "why": "Novel TB enzyme hits need both target engagement and a simple orthogonal sanity check before expensive expansion work.",
    },
    "Cathepsin K": {
        "primary_companion": "cathepsin-family / acidic-pH specificity panel",
        "why": "Acidic protease stories need class selectivity and condition specificity together.",
    },
    "SARS-CoV-2 PLpro": {
        "primary_companion": "host DUB-like or cysteine protease counterscreen",
        "why": "Host-like deubiquitinase liability is the first obvious objection for PLpro hits.",
    },
    "Dengue NS2B-NS3 protease": {
        "primary_companion": "flaviviral protease orthogonal panel plus shallow-pocket negative controls",
        "why": "Flat wet pockets need stronger discrimination against sticky false positives.",
    },
    "SARS-CoV-2 Mpro": {
        "primary_companion": "host cysteine protease sanity panel",
        "why": "Fast protease campaigns still need an immediate anti-reactivity and host-protease check.",
    },
    "Leishmania braziliensis DHODH": {
        "primary_companion": "host DHODH counterscreen",
        "why": "Neglected-disease enzyme wins are stronger when host-enzyme separation is visible from day one.",
    },
    "T. cruzi KRS1": {
        "primary_companion": "host aaRS selectivity panel",
        "why": "Aminoacyl-tRNA synthetase campaigns live or die on host-target separation.",
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
    rows = []
    for row in portfolio.get("rows", []) or []:
        target = str(row.get("target_id", ""))
        if target == "CA XII":
            continue
        preset = COMPANION_PRESETS[target]
        rows.append(
            {
                "target_id": target,
                "wave": row["wave"],
                "domain_family": row["domain_family"],
                "primary_companion_panel": preset["primary_companion"],
                "companion_why": preset["why"],
                "outbound_rule": "Ship this companion panel alongside the first validation packet, not later.",
            }
        )
    summary = {
        "status": "wetlab_validation_companion_panels_ready",
        "row_count": len(rows),
        "artifact_role": "per_target_selectivity_and_companion_panels",
        "global_companion_target": "CA XII remains the default CA IX selectivity companion.",
        "next_required_step": "Attach the listed companion panel to every first outbound packet so that external labs see an anti-target or specificity story immediately instead of as a follow-up apology.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Wet-Lab Validation Companion and Selectivity Panels",
        "",
        f"- status: `{s['status']}`",
        f"- row_count: `{s['row_count']}`",
        f"- artifact_role: `{s['artifact_role']}`",
        f"- global_companion_target: {s['global_companion_target']}",
        "",
        "| target_id | wave | domain_family | primary_companion_panel |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_id']}` | `{row['wave']}` | `{row['domain_family']}` | {row['primary_companion_panel']} |"
        )
    lines.extend(["", "## Notes", ""])
    for row in payload["rows"]:
        lines.extend([
            f"- `{row['target_id']}`: {row['companion_why']}",
            f"  Rule: {row['outbound_rule']}",
        ])
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the wet-lab validation companion and anti-target panel map.")
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
