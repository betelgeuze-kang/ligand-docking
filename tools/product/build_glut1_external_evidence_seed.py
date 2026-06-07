#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/glut1_external_evidence_seed_current.json"
DEFAULT_OUT_CSV = "runs/glut1_external_evidence_seed_current.csv"
DEFAULT_OUT_MD = "runs/glut1_external_evidence_seed_current.md"


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
            "candidate_name": "cytochalasin B",
            "proposed_packet_step": "core_binder_01",
            "candidate_role": "binder_candidate",
            "evidence_class": "direct_glut1_inhibitor_binding_site_anchor",
            "evidence_strength": "strong_structural",
            "source_title": "Mechanism of inhibition of human glucose transporter GLUT1 is conserved between cytochalasin B and phenylalanine amides",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/27078104/",
            "source_anchor": "PMID 27078104",
            "potency_or_signal": "Human GLUT1 inhibitor-binding site structural anchor with cytochalasin B endofacial site conservation",
            "promotion_policy": "draft_second_wave_manual_review",
            "recommended_review_bucket": "review_only_second_wave",
            "recommended_verdict": "keep_review_only",
            "caution": "Strong GLUT1 inhibitor anchor, but still keep draft/manual-review status until transporter family donor policy and packet provenance are frozen.",
        },
        {
            "priority_rank": 2,
            "candidate_name": "WZB117",
            "proposed_packet_step": "core_binder_02",
            "candidate_role": "binder_candidate",
            "evidence_class": "functional_glut1_inhibitor_with_binding_site_model",
            "evidence_strength": "moderate_functional",
            "source_title": "Glucose transport inhibitory activity of structurally diverse small molecules targeting GLUT1",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/27836974/",
            "source_anchor": "PMID 27836974",
            "potency_or_signal": "Low-micromolar GLUT1 inhibition with modeled exofacial sugar-binding site engagement",
            "promotion_policy": "draft_second_wave_manual_review",
            "recommended_review_bucket": "review_only_second_wave",
            "recommended_verdict": "keep_review_only",
            "caution": "Useful second-wave functional candidate, but not a clean direct biophysical binding row.",
        },
        {
            "priority_rank": 3,
            "candidate_name": "STF-31",
            "proposed_packet_step": "core_binder_03",
            "candidate_role": "binder_candidate",
            "evidence_class": "functional_glut1_dependency_probe",
            "evidence_strength": "moderate_functional",
            "source_title": "Selective targeting of glucose uptake to treat renal cell carcinoma",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/21813754/",
            "source_anchor": "PMID 21813754",
            "potency_or_signal": "GLUT1-dependent glucose uptake inhibition linked to VHL-deficient RCC vulnerability",
            "promotion_policy": "draft_second_wave_manual_review",
            "recommended_review_bucket": "review_only_second_wave",
            "recommended_verdict": "keep_review_only",
            "caution": "Strong disease-context functional probe, but still indirect relative to direct quantitative human GLUT1 binding.",
        },
        {
            "priority_rank": 4,
            "candidate_name": "forskolin",
            "proposed_packet_step": "caution_only",
            "candidate_role": "caution_reference",
            "evidence_class": "endofacial_glut1_tool_reference",
            "evidence_strength": "tool_only",
            "source_title": "Determinants of ligand binding affinity and cooperativity at the GLUT1 endofacial site",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/21384913/",
            "source_anchor": "PMID 21384913",
            "potency_or_signal": "Endofacial GLUT1 inhibitory tool with radioligand binding context",
            "promotion_policy": "caution_only_not_for_authoritative_apply",
            "recommended_review_bucket": "review_only_tool_reference",
            "recommended_verdict": "caution_only",
            "caution": "Keep as a mechanistic/tool reference instead of a packet binder row.",
        },
        {
            "priority_rank": 5,
            "candidate_name": "gossypol",
            "proposed_packet_step": "caution_only",
            "candidate_role": "caution_reference",
            "evidence_class": "glut1_inhibitor_with_broad_polypharmacology",
            "evidence_strength": "tool_only",
            "source_title": "Endofacial competitive inhibition of the glucose transporter 1 activity by gossypol",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/19386788/",
            "source_anchor": "PMID 19386788",
            "potency_or_signal": "GLUT1 inhibition with Ki around 20 uM and endofacial interaction model",
            "promotion_policy": "caution_only_not_for_authoritative_apply",
            "recommended_review_bucket": "defer_polypharmacology",
            "recommended_verdict": "defer",
            "caution": "Biologically interesting but too polypharmacologic for a clean authoritative GLUT1 binder row.",
        },
    ]
    summary = {
        "target_id": "GLUT1_TRANSPORT_BLIND",
        "candidate_count": len(rows),
        "draft_second_wave_candidate_count": sum(1 for row in rows if row["promotion_policy"] == "draft_second_wave_manual_review"),
        "caution_only_candidate_count": sum(1 for row in rows if row["promotion_policy"] == "caution_only_not_for_authoritative_apply"),
        "direct_quantitative_binding_candidate_count": 1,
        "endpoint_status": "external_seed_ready_second_wave_direct_binding_mixed",
        "recommended_second_wave_candidates": ["cytochalasin B", "WZB117", "STF-31"],
        "next_required_step": "Keep GLUT1 authoritative apply blocked. Review cytochalasin B, WZB117, and STF-31 as second-wave draft candidates, keep forskolin and gossypol caution-only, and freeze a non-EGFR donor policy before any authoritative transporter apply.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# GLUT1 External Evidence Seed",
        "",
        f"- target_id: `{s['target_id']}`",
        f"- candidate_count: `{s['candidate_count']}`",
        f"- draft_second_wave_candidate_count: `{s['draft_second_wave_candidate_count']}`",
        f"- caution_only_candidate_count: `{s['caution_only_candidate_count']}`",
        f"- direct_quantitative_binding_candidate_count: `{s['direct_quantitative_binding_candidate_count']}`",
        f"- endpoint_status: `{s['endpoint_status']}`",
        f"- recommended_second_wave_candidates: `{', '.join(s['recommended_second_wave_candidates'])}`",
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
            "- GLUT1 remains second-wave behind AQP1; this seed just opens a cleaner follow-on review path.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a draft external-evidence seed for GLUT1 transporter packet review.")
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
