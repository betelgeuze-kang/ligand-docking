#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/aqp1_binding_source_modality_triage_current.json"
DEFAULT_OUT_CSV = "runs/aqp1_binding_source_modality_triage_current.csv"
DEFAULT_OUT_MD = "runs/aqp1_binding_source_modality_triage_current.md"

CLAIM_BOUNDARY = (
    "AQP1 binding source-modality triage only; classifies public Bacopaside II/AQP1 evidence for transporter "
    "scope-gate use. It does not promote scope, fill operator placeholders, apply rows, run docking, or mutate "
    "external state."
)

EVIDENCE_ROWS: list[dict[str, Any]] = [
    {
        "evidence_id": "aqp1_bacopaside_ii_functional_ic50_pm27474162",
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "candidate_ligand_id": "aqp1_bacopaside_ii_review_seed",
        "candidate_name": "bacopaside II",
        "source_modality": "functional_quantitative_surrogate",
        "source_title": (
            "Differential Inhibition of Water and Ion Channel Activities of Mammalian Aquaporin-1 by Two "
            "Structurally Related Bacopaside Compounds Derived from the Medicinal Plant Bacopa monnieri"
        ),
        "source_url_or_doi": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
        "source_pmid_or_document_id": "PMID 27474162",
        "assay_type": "AQP1 water-channel functional inhibition",
        "quantitative_value": "18",
        "quantitative_units": "uM IC50",
        "reference_binding_kcal_mol": "",
        "computed_binding_energy_kcal_mol": "",
        "functional_delta_g_surrogate_kcal_mol": "-6.47",
        "direct_experimental_binding_evidence": False,
        "claim_safe_binding_kcal_ready": False,
        "accepted_for_scope_promotion": False,
        "rejection_reason": "functional_ic50_surrogate_not_direct_or_claim_safe_binding_kcal",
    },
    {
        "evidence_id": "aqp1_bacopaside_ii_computational_mmgbsa_jmgm_2026",
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "candidate_ligand_id": "aqp1_bacopaside_ii_review_seed",
        "candidate_name": "bacopaside II",
        "source_modality": "computational_docking_md_mmgbsa",
        "source_title": (
            "Molecular mechanisms of aquaporin 1 inhibition by Bacopaside I and Bacopaside II: Insights from "
            "molecular dynamics simulations"
        ),
        "source_url_or_doi": "https://doi.org/10.1016/j.jmgm.2026.109302",
        "source_pmid_or_document_id": "DOI 10.1016/j.jmgm.2026.109302",
        "assay_type": "computational docking, MD, GaMD, and MM/GBSA",
        "quantitative_value": "-34.48",
        "quantitative_units": "kcal/mol MMGBSA",
        "reference_binding_kcal_mol": "",
        "computed_binding_energy_kcal_mol": "-34.48",
        "functional_delta_g_surrogate_kcal_mol": "",
        "direct_experimental_binding_evidence": False,
        "claim_safe_binding_kcal_ready": False,
        "accepted_for_scope_promotion": False,
        "rejection_reason": "computational_binding_energy_is_supportive_but_not_operator_verified_direct_binding",
    },
    {
        "evidence_id": "aqp1_bacopaside_ii_mechanistic_cell_context_pmc6718670",
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "candidate_ligand_id": "aqp1_bacopaside_ii_review_seed",
        "candidate_name": "bacopaside II",
        "source_modality": "mechanistic_cellular_support",
        "source_title": (
            "Combined pharmacological administration of AQP1 ion channel blocker AqB011 and water channel blocker "
            "Bacopaside II amplifies inhibition of colon cancer cell migration"
        ),
        "source_url_or_doi": "https://pmc.ncbi.nlm.nih.gov/articles/PMC6718670/",
        "source_pmid_or_document_id": "PMCID PMC6718670",
        "assay_type": "cell migration and mechanistic AQP1 blocker context",
        "quantitative_value": "",
        "quantitative_units": "",
        "reference_binding_kcal_mol": "",
        "computed_binding_energy_kcal_mol": "",
        "functional_delta_g_surrogate_kcal_mol": "",
        "direct_experimental_binding_evidence": False,
        "claim_safe_binding_kcal_ready": False,
        "accepted_for_scope_promotion": False,
        "rejection_reason": "mechanistic_cell_context_not_quantitative_binding_kcal",
    },
    {
        "evidence_id": "aqp1_bacopaside_ii_chembl_aqp1_absence_current",
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "candidate_ligand_id": "aqp1_bacopaside_ii_review_seed",
        "candidate_name": "bacopaside II",
        "source_modality": "public_database_recheck",
        "source_title": "ChEMBL activity query for human AQP1 CHEMBL4523210 and bacopaside II CHEMBL390758",
        "source_url_or_doi": (
            "https://www.ebi.ac.uk/chembl/api/data/activity.json?"
            "target_chembl_id=CHEMBL4523210&molecule_chembl_id=CHEMBL390758"
        ),
        "source_pmid_or_document_id": "ChEMBL CHEMBL4523210/CHEMBL390758 current recheck",
        "assay_type": "public database target-ligand activity lookup",
        "quantitative_value": "0",
        "quantitative_units": "activity rows",
        "reference_binding_kcal_mol": "",
        "computed_binding_energy_kcal_mol": "",
        "functional_delta_g_surrogate_kcal_mol": "",
        "direct_experimental_binding_evidence": False,
        "claim_safe_binding_kcal_ready": False,
        "accepted_for_scope_promotion": False,
        "rejection_reason": "no_chembl_aqp1_activity_or_binding_rows_for_bacopaside_ii",
    },
    {
        "evidence_id": "aqp1_bacopaside_ii_bindingdb_p29972_empty_current",
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "candidate_ligand_id": "aqp1_bacopaside_ii_review_seed",
        "candidate_name": "bacopaside II",
        "source_modality": "public_database_recheck",
        "source_title": "BindingDB UniProt P29972 ligand affinity lookup",
        "source_url_or_doi": (
            "https://bindingdb.org/rest/getLigandsByUniprots?"
            "uniprot=P29972&cutoff=100&response=application/json"
        ),
        "source_pmid_or_document_id": "BindingDB P29972 current recheck",
        "assay_type": "public database UniProt ligand affinity lookup",
        "quantitative_value": "0",
        "quantitative_units": "affinity rows",
        "reference_binding_kcal_mol": "",
        "computed_binding_energy_kcal_mol": "",
        "functional_delta_g_surrogate_kcal_mol": "",
        "direct_experimental_binding_evidence": False,
        "claim_safe_binding_kcal_ready": False,
        "accepted_for_scope_promotion": False,
        "rejection_reason": "bindingdb_has_no_p29972_affinity_rows",
    },
    {
        "evidence_id": "aqp1_functional_ic50_chembl195380_identity_mismatch",
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "candidate_ligand_id": "aqp1_bacopaside_ii_review_seed",
        "candidate_name": "bacopaside II",
        "source_modality": "ligand_identity_crosscheck",
        "source_title": "ChEMBL AQP1 functional IC50 row identity crosscheck",
        "source_url_or_doi": (
            "https://www.ebi.ac.uk/chembl/api/data/activity.json?"
            "target_chembl_id=CHEMBL4523210"
        ),
        "source_pmid_or_document_id": "ChEMBL CHEMBL4523210 activity current recheck",
        "assay_type": "functional AQP1 IC50 row belongs to CHEMBL195380, not bacopaside II CHEMBL390758",
        "quantitative_value": "2700",
        "quantitative_units": "nM IC50 for CHEMBL195380",
        "reference_binding_kcal_mol": "",
        "computed_binding_energy_kcal_mol": "",
        "functional_delta_g_surrogate_kcal_mol": "",
        "direct_experimental_binding_evidence": False,
        "claim_safe_binding_kcal_ready": False,
        "accepted_for_scope_promotion": False,
        "rejection_reason": "functional_ic50_row_is_not_bacopaside_ii_identity_mismatch",
    },
    {
        "evidence_id": "aqp1_chembl20_kd_direct_like_operator_validation_candidate",
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "candidate_ligand_id": "chembl20_acetazolamide_review_candidate",
        "candidate_name": "acetazolamide",
        "source_modality": "direct_like_binding_candidate_requires_operator_validation",
        "source_title": "ChEMBL AQP1 CHEMBL20 Kd row from RSC Med Chem 2025",
        "source_url_or_doi": (
            "https://www.ebi.ac.uk/chembl/api/data/activity.json?"
            "target_chembl_id=CHEMBL4523210&molecule_chembl_id=CHEMBL20"
        ),
        "source_pmid_or_document_id": "ChEMBL activity 29308926 / document CHEMBL6182835",
        "assay_type": (
            "Binding affinity to AQP1 (unknown origin) expressed in HEK cells assessed as dissociation constant"
        ),
        "quantitative_value": "174000",
        "quantitative_units": "nM Kd",
        "reference_binding_kcal_mol": "-5.13",
        "computed_binding_energy_kcal_mol": "",
        "functional_delta_g_surrogate_kcal_mol": "",
        "direct_experimental_binding_evidence": False,
        "claim_safe_binding_kcal_ready": False,
        "accepted_for_scope_promotion": False,
        "rejection_reason": "direct_like_kd_candidate_requires_operator_validation_data_validity_outside_typical_range_and_assay_origin_unknown",
    },
    {
        "evidence_id": "aqp1_bindingdb_p29972_expanded_functional_affinity_rows",
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "candidate_ligand_id": "aqp1_expanded_functional_candidate_pool",
        "candidate_name": "AQP1 BindingDB expanded candidate pool",
        "source_modality": "public_database_recheck",
        "source_title": "BindingDB UniProt P29972 expanded cutoff ligand affinity lookup",
        "source_url_or_doi": (
            "https://bindingdb.org/rest/getLigandsByUniprots?"
            "uniprot=P29972&cutoff=1000000&response=application/json"
        ),
        "source_pmid_or_document_id": "BindingDB P29972 expanded cutoff current recheck",
        "assay_type": "public database UniProt ligand affinity lookup; returned rows are functional IC50 rows, not Kd/Ki",
        "quantitative_value": "17",
        "quantitative_units": "expanded affinity rows",
        "reference_binding_kcal_mol": "",
        "computed_binding_energy_kcal_mol": "",
        "functional_delta_g_surrogate_kcal_mol": "",
        "direct_experimental_binding_evidence": False,
        "claim_safe_binding_kcal_ready": False,
        "accepted_for_scope_promotion": False,
        "rejection_reason": "bindingdb_expanded_rows_are_functional_ic50_not_direct_binding_kcal",
    },
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _float_text(value: Any) -> float:
    try:
        return float(str(value or "").strip())
    except ValueError:
        return 0.0


def build_payload() -> dict[str, Any]:
    rows = [dict(row) for row in EVIDENCE_ROWS]
    direct_count = sum(1 for row in rows if row["direct_experimental_binding_evidence"] is True)
    claim_safe_count = sum(1 for row in rows if row["claim_safe_binding_kcal_ready"] is True)
    computational_rows = [row for row in rows if row["source_modality"] == "computational_docking_md_mmgbsa"]
    functional_rows = [row for row in rows if row["source_modality"] == "functional_quantitative_surrogate"]
    public_database_recheck_rows = [row for row in rows if row["source_modality"] == "public_database_recheck"]
    identity_mismatch_rows = [
        row for row in rows if "identity_mismatch" in str(row.get("rejection_reason", ""))
    ]
    direct_like_candidate_rows = [
        row for row in rows if row["source_modality"] == "direct_like_binding_candidate_requires_operator_validation"
    ]
    best_computed = ""
    if computational_rows:
        best = min(computational_rows, key=lambda row: _float_text(row["computed_binding_energy_kcal_mol"]))
        best_computed = str(best["computed_binding_energy_kcal_mol"])
    summary = {
        "packet_type": "aqp1_binding_source_modality_triage",
        "status": "blocked_aqp1_binding_source_modality_triage",
        "target_id": "AQP1",
        "target_uniprot": "P29972",
        "candidate_ligand_id": "aqp1_bacopaside_ii_review_seed",
        "candidate_name": "bacopaside II",
        "row_count": len(rows),
        "source_modality_guard_ready": True,
        "source_modalities": sorted({str(row["source_modality"]) for row in rows}),
        "functional_surrogate_row_count": len(functional_rows),
        "computational_binding_energy_row_count": len(computational_rows),
        "public_database_recheck_row_count": len(public_database_recheck_rows),
        "ligand_identity_mismatch_row_count": len(identity_mismatch_rows),
        "direct_like_binding_candidate_row_count": len(direct_like_candidate_rows),
        "direct_like_binding_candidate_claim_safe_ready_count": 0,
        "chembl_aqp1_direct_like_binding_row_count": 1,
        "chembl_aqp1_direct_like_binding_claim_safe_row_count": 0,
        "chembl_aqp1_direct_like_binding_candidate_chembl_id": "CHEMBL20",
        "chembl_aqp1_direct_like_binding_candidate_name": "acetazolamide",
        "chembl_aqp1_direct_like_binding_candidate_activity_id": "29308926",
        "chembl_aqp1_direct_like_binding_candidate_standard_type": "Kd",
        "chembl_aqp1_direct_like_binding_candidate_standard_value_nM": "174000.0",
        "chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol": "-5.13",
        "chembl_aqp1_direct_like_binding_candidate_blocker": (
            "data_validity_outside_typical_range_and_assay_origin_unknown"
        ),
        "bindingdb_aqp1_expanded_cutoff_affinity_row_count": 17,
        "bindingdb_aqp1_expanded_cutoff_direct_like_affinity_row_count": 0,
        "bindingdb_aqp1_expanded_cutoff_best_functional_ic50_nM": "2700",
        "bacopaside_ii_pubchem_cid": "9876264",
        "bacopaside_ii_chembl_id": "CHEMBL390758",
        "aqp1_chembl_target_id": "CHEMBL4523210",
        "aqp1_bindingdb_uniprot_affinity_row_count": 0,
        "bacopaside_ii_chembl_aqp1_activity_row_count": 0,
        "functional_ic50_identity_mismatch_detail": (
            "AQP1 functional IC50 2700 nM row is CHEMBL195380, while bacopaside II is CHEMBL390758."
        ),
        "direct_experimental_binding_row_count": direct_count,
        "claim_safe_binding_kcal_ready_count": claim_safe_count,
        "public_direct_binding_recheck_ready": True,
        "public_direct_binding_recheck_source_count": len(rows),
        "public_direct_binding_recheck_sources": [
            str(row["source_url_or_doi"]) for row in rows if row.get("source_url_or_doi")
        ],
        "public_direct_binding_recheck_result": (
            "no_public_direct_experimental_or_claim_safe_binding_kcal_for_aqp1_bacopaside_ii;"
            "chembl_aqp1_bacopaside_ii_rows=0;bindingdb_p29972_cutoff100_affinities=0;"
            "functional_ic50_identity_mismatch=CHEMBL195380_not_CHEMBL390758;"
            "chembl20_kd_candidate_delta_g=-5.13_requires_operator_validation;"
            "bindingdb_p29972_expanded_cutoff_rows=17_direct_like_rows=0"
        ),
        "replacement_reference_binding_kcal_mol_action": (
            "keep_blank_until_direct_binding_or_operator_verified_claim_safe_kcal"
        ),
        "accepted_for_scope_promotion_count": sum(
            1 for row in rows if row["accepted_for_scope_promotion"] is True
        ),
        "best_computational_binding_energy_kcal_mol": best_computed,
        "best_functional_delta_g_surrogate_kcal_mol": "-6.47",
        "triage_decision": "keep_blocked_until_direct_experimental_or_operator_verified_claim_safe_binding_kcal",
        "triage_artifact": DEFAULT_OUT_JSON,
        "next_required_step": (
            "Keep AQP1.core_binder_01 blocked for transporter promotion: public evidence currently contains "
            "functional IC50 support and computational MM/GBSA support, but no operator-verified direct experimental "
            "or claim-safe binding kcal row. Current public database recheck also shows no ChEMBL AQP1 rows for "
            "bacopaside II itself and flags the CHEMBL195380 functional IC50 row as a ligand-identity mismatch. "
            "A ChEMBL20 Kd row now gives a direct-like -5.13 kcal/mol candidate, but it remains blocked until "
            "operator verification because ChEMBL marks the value outside the typical range and the assay origin is unknown."
        ),
        "execution_enabled": False,
        "external_state_mutated": False,
        "scope_promotion_allowed": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# AQP1 Binding Source-Modality Triage",
        "",
        f"- status: `{s['status']}`",
        f"- target_id: `{s['target_id']}`",
        f"- candidate_name: `{s['candidate_name']}`",
        f"- row_count: `{s['row_count']}`",
        f"- direct_experimental_binding_row_count: `{s['direct_experimental_binding_row_count']}`",
        f"- claim_safe_binding_kcal_ready_count: `{s['claim_safe_binding_kcal_ready_count']}`",
        f"- public_direct_binding_recheck_ready: `{s['public_direct_binding_recheck_ready']}`",
        f"- public_direct_binding_recheck_source_count: `{s['public_direct_binding_recheck_source_count']}`",
        f"- public_direct_binding_recheck_result: `{s['public_direct_binding_recheck_result']}`",
        f"- public_database_recheck_row_count: `{s['public_database_recheck_row_count']}`",
        f"- ligand_identity_mismatch_row_count: `{s['ligand_identity_mismatch_row_count']}`",
        f"- direct_like_binding_candidate_row_count: `{s['direct_like_binding_candidate_row_count']}`",
        f"- chembl_aqp1_direct_like_binding_candidate_chembl_id: `{s['chembl_aqp1_direct_like_binding_candidate_chembl_id']}`",
        f"- chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol: `{s['chembl_aqp1_direct_like_binding_candidate_delta_g_kcal_mol']}`",
        f"- chembl_aqp1_direct_like_binding_candidate_blocker: `{s['chembl_aqp1_direct_like_binding_candidate_blocker']}`",
        f"- bindingdb_aqp1_expanded_cutoff_affinity_row_count: `{s['bindingdb_aqp1_expanded_cutoff_affinity_row_count']}`",
        f"- bacopaside_ii_chembl_id: `{s['bacopaside_ii_chembl_id']}`",
        f"- aqp1_chembl_target_id: `{s['aqp1_chembl_target_id']}`",
        f"- functional_ic50_identity_mismatch_detail: `{s['functional_ic50_identity_mismatch_detail']}`",
        f"- replacement_reference_binding_kcal_mol_action: `{s['replacement_reference_binding_kcal_mol_action']}`",
        f"- computational_binding_energy_row_count: `{s['computational_binding_energy_row_count']}`",
        f"- best_computational_binding_energy_kcal_mol: `{s['best_computational_binding_energy_kcal_mol']}`",
        f"- triage_decision: `{s['triage_decision']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Evidence Rows",
        "",
        "| evidence_id | source_modality | quantitative_value | accepted_for_scope_promotion | rejection_reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['evidence_id']}` | `{row['source_modality']}` | "
            f"`{row['quantitative_value']} {row['quantitative_units']}` | "
            f"`{row['accepted_for_scope_promotion']}` | `{row['rejection_reason']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AQP1 Bacopaside II source-modality triage packet.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload()
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_md(args.out_md, payload)


if __name__ == "__main__":
    main()
