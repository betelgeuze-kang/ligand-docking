#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CONFIG_JSON = "config/idp_3bead_benchmark_v7.json"
DEFAULT_PROVENANCE_CSV = "config/biorxiv_temporal_idp_provenance_v1.csv"
DEFAULT_PAGE4_PACKET_JSON = "runs/idp_page4_anchor_curation_packet_current.json"
DEFAULT_OUT_JSON = "runs/idp_page4_anchor_evidence_seed_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_anchor_evidence_seed_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_anchor_evidence_seed_current.md"


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


def _load_page4_target(config_payload: dict[str, Any]) -> dict[str, Any]:
    for row in config_payload.get("targets", []) or []:
        if str(row.get("name", "")).strip() == "page4":
            return dict(row)
    return {}


def _load_page4_provenance(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if str(row.get("holdout_name", "")).strip() == "page4":
                return dict(row)
    return {}


def build_payload(
    config_payload: dict[str, Any],
    provenance_row: dict[str, Any],
    page4_packet_payload: dict[str, Any],
) -> dict[str, Any]:
    page4_target = _load_page4_target(config_payload)
    packet_s = dict((page4_packet_payload.get("summary") if isinstance(page4_packet_payload.get("summary"), dict) else {}) or {})

    residue_count = int(page4_target.get("n_res", 0) or 0)
    source_kind = str(provenance_row.get("source_kind", "")).strip()
    provenance_source = str(provenance_row.get("provenance_source", "")).strip()
    publication_year = str(provenance_row.get("publication_year", "")).strip()

    rows = [
        {
            "seed_rank": 1,
            "seed_type": "construct_disorder_anchor",
            "target_name": "page4",
            "identity_candidate": "PAGE4",
            "construct_candidate": f"full_length_{residue_count}aa" if residue_count else "full_length_candidate",
            "condition_scope": "baseline_disorder_identity",
            "anchor_field_target": "identity_mapping, rg_mean_range, ensemble_disorder_support",
            "source_anchor": f"PMC3077599 ({publication_year})" if publication_year else "PMC3077599",
            "source_title": "The cancer/testis antigen prostate-associated gene 4 (PAGE4) is a highly intrinsically disordered protein",
            "source_url": provenance_source,
            "search_query": f'\"PAGE4\" intrinsically disordered protein {residue_count} aa',
            "why_this_seed": "Best local construct-level provenance anchor for mapping synthetic page4 to the PAGE4 literature identity hypothesis.",
            "construct_match_requirement": "full_length_only",
            "state_specificity_requirement": "unphosphorylated_or_state_explicit",
            "promotion_value_if_found": "high",
            "current_gap": "construct-matched citation not yet frozen into the packet",
            "reviewer_action": "confirm identity alias and capture construct mapping into replacement_anchor_provenance",
        },
        {
            "seed_rank": 2,
            "seed_type": "phosphorylation_compaction_anchor",
            "target_name": "page4",
            "identity_candidate": "PAGE4",
            "construct_candidate": f"full_length_{residue_count}aa" if residue_count else "full_length_candidate",
            "condition_scope": "compactness_or_helix_shift",
            "anchor_field_target": "rg_mean_range, transient_helicity_range, branch_state_support",
            "source_anchor": "PMID 26242913",
            "source_title": "Intramolecular tyrosine-oxygen interactions regulate phosphorylation-induced conformational dynamics of the disordered prostate-associated gene 4 protein",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/26242913/",
            "search_query": '\"PAGE4\" HIPK1 phosphorylation conformational dynamics',
            "why_this_seed": "Best follow-up seed for whether PAGE4 compactness and branch-state interpretation differ across explicit phosphorylation states.",
            "construct_match_requirement": "full_length_preferred",
            "state_specificity_requirement": "state_must_be_explicit",
            "promotion_value_if_found": "high",
            "current_gap": "state-conditioned compactness anchor is not yet packet-backed",
            "reviewer_action": "capture any construct-matched HIPK1-like compactness or helicity signal with state notes",
        },
        {
            "seed_rank": 3,
            "seed_type": "hyperphosphorylation_expansion_anchor",
            "target_name": "page4",
            "identity_candidate": "PAGE4",
            "construct_candidate": f"full_length_{residue_count}aa" if residue_count else "full_length_candidate",
            "condition_scope": "expanded_or_aggregation_negative",
            "anchor_field_target": "rg_mean_range, aggregation_negative_signal, state-specific branch support",
            "source_anchor": "PMID 28289210",
            "source_title": "Phosphorylation-induced conformational dynamics in an intrinsically disordered protein and potential role in phenotypic heterogeneity",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/28289210/",
            "search_query": '\"PAGE4\" CLK2 phosphorylation conformational dynamics',
            "why_this_seed": "Useful for distinguishing whether hyperphosphorylated PAGE4 should be treated as expanded rather than aggregation-prone under corrected-path interpretation.",
            "construct_match_requirement": "full_length_preferred",
            "state_specificity_requirement": "state_must_be_explicit",
            "promotion_value_if_found": "high",
            "current_gap": "aggregation-negative evidence is still provisional for page4",
            "reviewer_action": "record any construct-matched expansion or aggregation-negative evidence and keep state specificity explicit",
        },
        {
            "seed_rank": 4,
            "seed_type": "systems_level_followup",
            "target_name": "page4",
            "identity_candidate": "PAGE4",
            "construct_candidate": f"full_length_{residue_count}aa" if residue_count else "full_length_candidate",
            "condition_scope": "ensemble_switching_context",
            "anchor_field_target": "branch_state_support, ensemble_diversity_range",
            "source_anchor": "PMID 30813315",
            "source_title": "Structural and Dynamical Order of a Disordered Protein: Molecular Insights into Conformational Switching of PAGE4 at the Systems Level",
            "source_url": "https://pubmed.ncbi.nlm.nih.gov/30813315/",
            "search_query": '\"PAGE4\" systems level conformational switching',
            "why_this_seed": "Good follow-up context source if the first three papers do not provide enough construct-matched anchor detail.",
            "construct_match_requirement": "full_length_preferred",
            "state_specificity_requirement": "state_explicit_if_used",
            "promotion_value_if_found": "medium",
            "current_gap": "supportive systems-level context not yet translated into packet-safe anchor fields",
            "reviewer_action": "use only as supportive context unless a construct-matched anchor field can be extracted cleanly",
        },
    ]

    summary = {
        "status": "page4_anchor_evidence_seed_ready",
        "target_name": "page4",
        "identity_hypothesis": f"PAGE4_full_length_{residue_count}aa_human_candidate" if residue_count else "PAGE4_full_length_human_candidate",
        "identity_hypothesis_confidence": "moderate_local_provenance_supported",
        "benchmark_source_kind": source_kind,
        "residue_count": residue_count,
        "current_source_class": str(packet_s.get("source_class", "")).strip(),
        "current_provenance_kind": str(packet_s.get("provenance_kind", "")).strip(),
        "local_provenance_anchor": f"PMC3077599 ({publication_year})" if publication_year else "PMC3077599",
        "construct_match_required": True,
        "condition_match_required": True,
        "preferred_construct_scope": f"full_length_{residue_count}aa_state_explicit_if_available" if residue_count else "full_length_state_explicit_if_available",
        "preferred_evidence_modalities": "SAXS,NMR,ensemble_compaction,phosphorylation_state_mapping",
        "search_seed_count": len(rows),
        "top_search_target": f"PAGE4 full-length {residue_count} aa" if residue_count else "PAGE4 full-length",
        "first_open_source_anchor": rows[0]["source_anchor"],
        "first_open_source_url": rows[0]["source_url"],
        "do_not_promote_until": "explicit citation + construct mapping + condition relevance",
        "current_wrong_conditions": list(packet_s.get("current_wrong_conditions", []) or []),
        "next_required_step": (
            "Open the construct-level PAGE4 disorder anchor first, then review the phosphorylation-state papers before any packet replacement. "
            "Do not promote page4 into a broader roster until citation, construct mapping, and condition relevance are explicit."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Page4 Anchor Evidence Seed",
        "",
        f"- status: `{s['status']}`",
        f"- target_name: `{s['target_name']}`",
        f"- identity_hypothesis: `{s['identity_hypothesis']}`",
        f"- identity_hypothesis_confidence: `{s['identity_hypothesis_confidence']}`",
        f"- benchmark_source_kind: `{s['benchmark_source_kind']}`",
        f"- residue_count: `{s['residue_count']}`",
        f"- current_source_class: `{s['current_source_class']}`",
        f"- current_provenance_kind: `{s['current_provenance_kind']}`",
        f"- local_provenance_anchor: `{s['local_provenance_anchor']}`",
        f"- construct_match_required: `{s['construct_match_required']}`",
        f"- condition_match_required: `{s['condition_match_required']}`",
        f"- preferred_construct_scope: `{s['preferred_construct_scope']}`",
        f"- preferred_evidence_modalities: `{s['preferred_evidence_modalities']}`",
        f"- search_seed_count: `{s['search_seed_count']}`",
        f"- top_search_target: `{s['top_search_target']}`",
        f"- first_open_source_anchor: `{s['first_open_source_anchor']}`",
        f"- do_not_promote_until: `{s['do_not_promote_until']}`",
        "",
        "## Current Risk",
        "",
        f"- current_wrong_conditions: `{', '.join(s['current_wrong_conditions'])}`",
        f"- first_open_source_url: `{s['first_open_source_url']}`",
        "",
        "## Seed Ledger",
        "",
        "| rank | seed_type | source_anchor | condition_scope | anchor_field_target | reviewer_action |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['seed_rank']} | `{row['seed_type']}` | `{row['source_anchor']}` | "
            f"`{row['condition_scope']}` | `{row['anchor_field_target']}` | {row['reviewer_action']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a focused page4 literature/evidence seed sheet for first-wave IDP anchor curation.")
    parser.add_argument("--config-json", default=DEFAULT_CONFIG_JSON)
    parser.add_argument("--provenance-csv", default=DEFAULT_PROVENANCE_CSV)
    parser.add_argument("--page4-packet-json", default=DEFAULT_PAGE4_PACKET_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.config_json),
        _load_page4_provenance(args.provenance_csv),
        _load_json(args.page4_packet_json),
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
