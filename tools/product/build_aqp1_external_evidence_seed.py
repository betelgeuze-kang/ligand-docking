#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/aqp1_external_evidence_seed_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_external_evidence_seed_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_external_evidence_seed_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload() -> dict[str, Any]:
    rows = [
        {
            "priority_rank": 1,
            "candidate_name": "bacopaside II",
            "proposed_packet_step": "core_binder_01",
            "candidate_role": "binder_candidate",
            "evidence_class": "functional_aqp1_water_channel_inhibitor",
            "evidence_strength": "moderate_functional",
            "source_title": "Differential Inhibition of Water and Ion Channel Activities of Mammalian Aquaporin-1 by Two Structurally Related Bacopaside Compounds Derived from the Medicinal Plant Bacopa monnieri",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
            "source_anchor": "PMID 27474162",
            "potency_or_signal": "AQP1 water-channel IC50 18 uM in Xenopus oocyte assay",
            "promotion_policy": "draft_first_wave_manual_review",
            "recommended_review_bucket": "review_only_first_wave",
            "recommended_verdict": "keep_review_only",
            "caution": "Functional AQP1 inhibition is shown, but this is not a direct human target-binding row and still needs transporter-specific packet provenance before any apply.",
        },
        {
            "priority_rank": 2,
            "candidate_name": "AqB013",
            "proposed_packet_step": "core_binder_02",
            "candidate_role": "binder_candidate",
            "evidence_class": "functional_aqp1_antagonist_tool",
            "evidence_strength": "moderate_functional",
            "source_title": "Stimulation of aquaporin-mediated fluid transport by cyclic GMP in human retinal pigment epithelium in vitro",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/22427546/",
            "source_anchor": "PMID 22427546",
            "potency_or_signal": "20 uM AqB013 blocked cGMP-stimulated AQP1-dependent fluid flux in human RPE culture",
            "promotion_policy": "draft_first_wave_manual_review",
            "recommended_review_bucket": "review_only_first_wave",
            "recommended_verdict": "keep_review_only",
            "caution": "Useful transporter-like functional anchor, but still a tool-compound style functional result rather than direct quantitative binding evidence.",
        },
        {
            "priority_rank": 3,
            "candidate_name": "AqB011",
            "proposed_packet_step": "core_binder_03",
            "candidate_role": "binder_candidate",
            "evidence_class": "functional_aqp1_ion_conductance_modulator",
            "evidence_strength": "moderate_functional",
            "source_title": "Bumetanide Derivatives AqB007 and AqB011 Selectively Block the Aquaporin-1 Ion Channel Conductance and Slow Cancer Cell Migration",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/26467039/",
            "source_anchor": "PMID 26467039",
            "potency_or_signal": "AqB011 blocked AQP1 ion conductance with IC50 14 uM and slowed migration in AQP1-positive HT29 cells",
            "promotion_policy": "draft_first_wave_manual_review",
            "recommended_review_bucket": "review_only_first_wave",
            "recommended_verdict": "keep_review_only",
            "caution": "This is stronger than TEA as a first-wave functional AQP1 modulator, but it still reflects ion-conductance modulation rather than direct quantitative target binding.",
        },
        {
            "priority_rank": 4,
            "candidate_name": "tetraethylammonium",
            "proposed_packet_step": "caution_only",
            "candidate_role": "caution_reference",
            "evidence_class": "native_function_blocker_nonselective_tool",
            "evidence_strength": "weak_tool_only",
            "source_title": "Tetraethylammonium block of water flux in Aquaporin-1 channels expressed in kidney thin limbs of Henle's loop and a kidney-derived cell line",
            "source_url": "https://link.springer.com/article/10.1186/1472-6793-2-4",
            "source_anchor": "BMC Physiol 2002",
            "potency_or_signal": "1-10 mM partial AQP1 water-flux block in MDCK/native kidney models",
            "promotion_policy": "caution_only_not_for_authoritative_apply",
            "recommended_review_bucket": "review_only_tool_reference",
            "recommended_verdict": "caution_only",
            "caution": "Native-cell validation exists, but concentration is high and specificity is poor; keep as a tool reference, not an authoritative binder packet row.",
        },
        {
            "priority_rank": 5,
            "candidate_name": "acetazolamide",
            "proposed_packet_step": "caution_only",
            "candidate_role": "caution_reference",
            "evidence_class": "aqp1_modulation_system_effect_contested",
            "evidence_strength": "contested_system_level",
            "source_title": "Aquaporin-1 Translocation and Degradation Mediates the Water Transportation Mechanism of Acetazolamide",
            "source_url": "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0045976",
            "source_anchor": "PLOS One 2012",
            "potency_or_signal": "Kidney/HK-2 system evidence for AQP1 downregulation rather than direct target binding",
            "promotion_policy": "caution_only_not_for_authoritative_apply",
            "recommended_review_bucket": "defer_contested_system_effect",
            "recommended_verdict": "defer",
            "caution": "Keep as a controversy/system-effect reference only. Do not use as an authoritative AQP1 binder replacement row.",
        },
    ]
    summary = {
        "target_id": "AQP1_TRANSPORT_BLIND",
        "candidate_count": len(rows),
        "draft_first_wave_candidate_count": sum(1 for row in rows if row["promotion_policy"] == "draft_first_wave_manual_review"),
        "caution_only_candidate_count": sum(1 for row in rows if row["promotion_policy"] == "caution_only_not_for_authoritative_apply"),
        "direct_quantitative_binding_candidate_count": 0,
        "functional_candidate_count": 4,
        "endpoint_status": "external_seed_ready_direct_binding_absent",
        "recommended_first_wave_candidates": ["bacopaside II", "AqB013", "AqB011"],
        "next_required_step": (
            "Keep AQP1 authoritative apply blocked. Review bacopaside II, AqB013, and AqB011 first as draft functional candidates, "
            "keep tetraethylammonium and acetazolamide caution-only, and do not freeze transporter donor policy until a target-specific packet row becomes non-placeholder."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# AQP1 External Evidence Seed",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- draft_first_wave_candidate_count: `{s['draft_first_wave_candidate_count']}`",
        f"- caution_only_candidate_count: `{s['caution_only_candidate_count']}`",
        f"- direct_quantitative_binding_candidate_count: `{s['direct_quantitative_binding_candidate_count']}`",
        f"- endpoint_status: `{s['endpoint_status']}`",
        f"- recommended_first_wave_candidates: `{', '.join(s['recommended_first_wave_candidates'])}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Candidate Rows",
        "",
        "| priority | candidate_name | proposed_packet_step | evidence_class | promotion_policy | review_bucket | verdict | source_anchor |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority_rank']} | `{row['candidate_name']}` | `{row['proposed_packet_step']}` | "
            f"{row['evidence_class']} | `{row['promotion_policy']}` | `{row['recommended_review_bucket']}` | `{row['recommended_verdict']}` | `{row['source_anchor']}` |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- These rows are draft/manual-review seeds only. They are not authoritative replacement rows.",
            "- No direct quantitative human AQP1 binding packet is being claimed here.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a draft external-evidence seed for AQP1 transporter packet review.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload()
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
