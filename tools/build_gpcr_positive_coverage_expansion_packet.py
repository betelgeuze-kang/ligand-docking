#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
from pathlib import Path
from typing import Any

from tools.lib.artifacts import artifact as _artifact
from tools.lib.artifacts import resolve as _resolve
from tools.lib.artifacts import write_csv as _write_csv
from tools.lib.artifacts import write_json as _write_json

DEFAULT_RAW_DIR = "runs/life_science_gpcr_coverage_expansion_current"
DEFAULT_OUT_JSON = "runs/gpcr_positive_coverage_expansion_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_positive_coverage_expansion_packet_current.md"
DEFAULT_OUT_CSV = "runs/gpcr_positive_coverage_expansion_candidates_current.csv"

TARGET_SPECS = [
    {
        "target": "CHEMBL234_DRD3_HUMAN",
        "target_chembl_id": "CHEMBL234",
        "pref_name": "D(3) dopamine receptor",
        "uniprot_accession": "P35462",
        "activity_raw": "chembl_activity_CHEMBL234_high_ki_raw.json",
        "molecule_raw": "chembl_molecule_CHEMBL5841759_raw.json",
        "uniprot_raw": "uniprot_P35462_raw.json",
        "alphafold_raw": "alphafold_prediction_P35462_raw.json",
        "rcsb_search_raw": "rcsb_search_P35462_raw.json",
        "pubchem_raw": "pubchem_CHEMBL5841759_properties_raw.json",
    },
    {
        "target": "CHEMBL251_ADORA2A_HUMAN",
        "target_chembl_id": "CHEMBL251",
        "pref_name": "Adenosine receptor A2a",
        "uniprot_accession": "P29274",
        "activity_raw": "chembl_activity_CHEMBL251_high_ki_raw.json",
        "molecule_raw": "chembl_molecule_CHEMBL2419139_raw.json",
        "uniprot_raw": "uniprot_P29274_raw.json",
        "alphafold_raw": "alphafold_prediction_P29274_raw.json",
        "rcsb_search_raw": "rcsb_search_P29274_raw.json",
        "pubchem_raw": "pubchem_CHEMBL2419139_properties_raw.json",
    },
    {
        "target": "CHEMBL231_HRH1_HUMAN",
        "target_chembl_id": "CHEMBL231",
        "pref_name": "Histamine H1 receptor",
        "uniprot_accession": "P35367",
        "activity_raw": "chembl_activity_CHEMBL231_high_ki_raw.json",
        "molecule_raw": "chembl_molecule_CHEMBL1626_raw.json",
        "uniprot_raw": "uniprot_P35367_raw.json",
        "alphafold_raw": "alphafold_prediction_P35367_raw.json",
        "rcsb_search_raw": "rcsb_search_P35367_raw.json",
        "pubchem_raw": "pubchem_CHEMBL1626_properties_raw.json",
    },
    {
        "target": "CHEMBL236_OPRD1_HUMAN",
        "target_chembl_id": "CHEMBL236",
        "pref_name": "Delta-type opioid receptor",
        "uniprot_accession": "P41143",
        "activity_raw": "chembl_activity_CHEMBL236_high_ki_raw.json",
        "molecule_raw": "chembl_molecule_CHEMBL67192_raw.json",
        "uniprot_raw": "uniprot_P41143_raw.json",
        "alphafold_raw": "alphafold_prediction_P41143_raw.json",
        "rcsb_search_raw": "rcsb_search_P41143_raw.json",
        "pubchem_raw": "pubchem_CHEMBL67192_properties_raw.json",
    },
]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(payload, list):
        return {"$": payload}
    return payload if isinstance(payload, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _top_activity(activity_payload: dict[str, Any]) -> dict[str, Any]:
    rows = activity_payload.get("activities", [])
    if not isinstance(rows, list):
        rows = []
    candidates = [row for row in rows if isinstance(row, dict) and _text(row.get("molecule_chembl_id"))]
    candidates.sort(
        key=lambda row: (
            -(_float(row.get("pchembl_value")) or -1.0),
            _float(row.get("standard_value")) if _float(row.get("standard_value")) is not None else 10**9,
            _text(row.get("molecule_chembl_id")),
        )
    )
    return candidates[0] if candidates else {}


def _molecule_summary(molecule_payload: dict[str, Any]) -> dict[str, Any]:
    structures = molecule_payload.get("molecule_structures", {})
    if not isinstance(structures, dict):
        structures = {}
    props = molecule_payload.get("molecule_properties", {})
    if not isinstance(props, dict):
        props = {}
    return {
        "pref_name": molecule_payload.get("pref_name"),
        "canonical_smiles": structures.get("canonical_smiles"),
        "standard_inchi_key": structures.get("standard_inchi_key"),
        "full_mwt": _float(props.get("full_mwt")),
        "alogp": _float(props.get("alogp")),
        "hba": _float(props.get("hba")),
        "hbd": _float(props.get("hbd")),
        "max_phase": molecule_payload.get("max_phase"),
    }


def _uniprot_summary(uniprot_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_type": uniprot_payload.get("entryType"),
        "primary_accession": uniprot_payload.get("primaryAccession"),
        "uniprot_id": uniprot_payload.get("uniProtkbId"),
        "reviewed": _text(uniprot_payload.get("entryType")).startswith("UniProtKB reviewed"),
    }


def _record_count(payload: dict[str, Any], key: str) -> int:
    rows = payload.get(key, [])
    return len(rows) if isinstance(rows, list) else 0


def _rcsb_hits(payload: dict[str, Any]) -> list[str]:
    rows = payload.get("result_set", [])
    if not isinstance(rows, list):
        return []
    return [_text(row.get("identifier")) for row in rows if isinstance(row, dict) and _text(row.get("identifier"))]


def _pubchem_summary(payload: dict[str, Any]) -> dict[str, Any]:
    rows = (((payload.get("PropertyTable") or {}) if isinstance(payload.get("PropertyTable"), dict) else {}).get("Properties") or [])
    row = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}
    return {
        "cid": row.get("CID"),
        "molecular_formula": row.get("MolecularFormula"),
        "molecular_weight": _float(row.get("MolecularWeight")),
        "xlogp": _float(row.get("XLogP")),
        "hbd": _float(row.get("HBondDonorCount")),
        "hba": _float(row.get("HBondAcceptorCount")),
        "rotatable_bond_count": _float(row.get("RotatableBondCount")),
    }


def build_packet(
    *,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    generated_at_local: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw_path = _resolve(raw_dir)
    rows: list[dict[str, Any]] = []
    missing_artifacts: list[str] = []
    for priority, spec in enumerate(TARGET_SPECS, start=1):
        activity_path = raw_path / str(spec["activity_raw"])
        molecule_path = raw_path / str(spec["molecule_raw"])
        uniprot_path = raw_path / str(spec["uniprot_raw"])
        alphafold_path = raw_path / str(spec["alphafold_raw"])
        rcsb_path = raw_path / str(spec["rcsb_search_raw"])
        pubchem_path = raw_path / str(spec["pubchem_raw"])
        activity_payload = _read_json(activity_path)
        molecule_payload = _read_json(molecule_path)
        uniprot_payload = _read_json(uniprot_path)
        alphafold_payload = _read_json(alphafold_path)
        rcsb_payload = _read_json(rcsb_path)
        pubchem_payload = _read_json(pubchem_path)
        if not activity_payload:
            missing_artifacts.append(_artifact(activity_path))
        if not molecule_payload:
            missing_artifacts.append(_artifact(molecule_path))
        if not uniprot_payload:
            missing_artifacts.append(_artifact(uniprot_path))
        if not alphafold_payload:
            missing_artifacts.append(_artifact(alphafold_path))
        if not rcsb_payload:
            missing_artifacts.append(_artifact(rcsb_path))
        activity = _top_activity(activity_payload)
        molecule = _molecule_summary(molecule_payload)
        uniprot = _uniprot_summary(uniprot_payload)
        pubchem = _pubchem_summary(pubchem_payload)
        rcsb_hit_ids = _rcsb_hits(rcsb_payload)
        alphafold_model_count = _record_count(alphafold_payload, "$") or (
            len(alphafold_payload) if isinstance(alphafold_payload, list) else 0
        )
        molecule_id = _text(activity.get("molecule_chembl_id")) or Path(str(spec["molecule_raw"])).stem.replace(
            "chembl_molecule_", ""
        ).replace("_raw", "")
        pchembl = _float(activity.get("pchembl_value"))
        standard_value = _float(activity.get("standard_value"))
        has_activity = pchembl is not None and pchembl >= 8.0
        has_smiles = bool(molecule.get("canonical_smiles"))
        has_reviewed_uniprot = bool(uniprot.get("reviewed")) and uniprot.get("primary_accession") == spec["uniprot_accession"]
        has_structure_source = bool(rcsb_hit_ids or alphafold_model_count > 0)
        inclusion_decision = (
            "ready_for_frozen_pipeline_materialization"
            if has_activity and has_smiles and has_reviewed_uniprot and has_structure_source
            else "hold_until_activity_smiles_target_or_structure_complete"
        )
        structure_source_priority = (
            "rcsb_experimental_first"
            if rcsb_hit_ids
            else "alphafold_model_fallback"
            if alphafold_model_count > 0
            else "missing_structure_source"
        )
        rows.append(
            {
                "priority": priority,
                "target": spec["target"],
                "target_chembl_id": spec["target_chembl_id"],
                "target_pref_name": spec["pref_name"],
                "uniprot_accession": spec["uniprot_accession"],
                "candidate_ligand_id": molecule_id,
                "candidate_ligand_pref_name": molecule.get("pref_name"),
                "canonical_smiles": molecule.get("canonical_smiles"),
                "standard_inchi_key": molecule.get("standard_inchi_key"),
                "pubchem_cid": pubchem.get("cid"),
                "pubchem_molecular_formula": pubchem.get("molecular_formula"),
                "uniprot_reviewed": has_reviewed_uniprot,
                "uniprot_id": uniprot.get("uniprot_id"),
                "rcsb_hit_count": len(rcsb_hit_ids),
                "rcsb_first_hit": rcsb_hit_ids[0] if rcsb_hit_ids else None,
                "alphafold_model_count": alphafold_model_count,
                "structure_source_priority": structure_source_priority,
                "chembl_activity_id": activity.get("activity_id"),
                "chembl_document_id": activity.get("document_chembl_id"),
                "standard_type": activity.get("standard_type"),
                "standard_relation": activity.get("standard_relation"),
                "standard_value_nM": standard_value,
                "pchembl_value": pchembl,
                "assay_type": activity.get("assay_type"),
                "assay_description": activity.get("assay_description"),
                "activity_raw_artifact": _artifact(activity_path),
                "molecule_raw_artifact": _artifact(molecule_path),
                "uniprot_raw_artifact": _artifact(uniprot_path),
                "alphafold_raw_artifact": _artifact(alphafold_path),
                "rcsb_search_raw_artifact": _artifact(rcsb_path),
                "pubchem_raw_artifact": _artifact(pubchem_path) if pubchem_payload else None,
                "inclusion_decision": inclusion_decision,
                "required_before_guarded_100k": (
                    "Generate non-leaky candidate/decoy rows, protein structure or homology input, trajectory/cache "
                    "features, and split metadata before this row can affect PR-AUC CI-low."
                ),
            }
        )
    staged = [row for row in rows if row["inclusion_decision"] == "ready_for_frozen_pipeline_materialization"]
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "gpcr_positive_coverage_expansion_candidates_ready_for_materialization",
        "raw_dir": _artifact(raw_path),
        "candidate_target_count": len(rows),
        "ready_positive_candidate_count": len(staged),
        "staged_positive_candidate_count": len(staged),
        "observed_positive_count": 6,
        "base_adrb2_positive_count": 6,
        "current_shadow_positive_count": 3,
        "current_non_adrb2_shadow_positive_count": 3,
        "projected_positive_count_after_staging": 3 + len(staged),
        "projected_total_positive_count_after_staging": 6 + 3 + len(staged),
        "reviewed_uniprot_candidate_count": sum(1 for row in rows if row["uniprot_reviewed"]),
        "rcsb_experimental_candidate_count": sum(1 for row in rows if int(row["rcsb_hit_count"] or 0) > 0),
        "alphafold_candidate_count": sum(1 for row in rows if int(row["alphafold_model_count"] or 0) > 0),
        "pubchem_property_candidate_count": sum(1 for row in rows if row.get("pubchem_cid")),
        "current_guarded_shadow_pr_auc_ci_low": 0.325,
        "required_pr_auc_ci_low": 0.45,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "missing_artifacts": missing_artifacts,
        "raw_artifact_count": len(glob.glob(str(raw_path / "*.json"))),
        "next_required_step": (
            "Materialize these ready positives into the frozen GPCR candidate/decoy pipeline, then rerun the full "
            "guarded 100k review; do not count this packet as accuracy evidence until trajectories and split metadata exist."
        ),
    }
    payload = {
        "packet_type": "gpcr_positive_coverage_expansion_packet",
        "summary": summary,
        "rows": rows,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "target_identity_feature_allowed": False,
            "threshold_relaxation_allowed": False,
            "staging_only_not_accuracy_evidence": True,
        },
    }
    return payload, rows


def _fmt(value: Any) -> str:
    return "None" if value is None else str(value)


def _render_md(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# GPCR Positive Coverage Expansion Packet",
        "",
        f"- status: `{s['status']}`",
        f"- ready_positive_candidate_count: `{s['ready_positive_candidate_count']}`",
        f"- projected_positive_count_after_staging: `{s['projected_positive_count_after_staging']}`",
        f"- rcsb_experimental_candidate_count: `{s['rcsb_experimental_candidate_count']}`",
        f"- alphafold_candidate_count: `{s['alphafold_candidate_count']}`",
        f"- pubchem_property_candidate_count: `{s['pubchem_property_candidate_count']}`",
        f"- current_guarded_shadow_pr_auc_ci_low: `{s['current_guarded_shadow_pr_auc_ci_low']}`",
        f"- required_pr_auc_ci_low: `{s['required_pr_auc_ci_low']}`",
        f"- claim_promotion_allowed: `{str(s['claim_promotion_allowed']).lower()}`",
        "",
        "## Candidates",
        "",
        "| Priority | Target | UniProt | Ligand | pChEMBL | Ki nM | RCSB | AF | Decision |",
        "|---:|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['target']}` | `{row['uniprot_accession']}` | "
            f"`{row['candidate_ligand_id']}` | {_fmt(row['pchembl_value'])} | "
            f"{_fmt(row['standard_value_nM'])} | {row['rcsb_hit_count']} | {row['alphafold_model_count']} | "
            f"`{row['inclusion_decision']}` |"
        )
    lines.extend(["", "## Next Required Step", "", s["next_required_step"], ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build staged GPCR positive coverage expansion candidates.")
    parser.add_argument("--raw-dir", default=DEFAULT_RAW_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload, rows = build_packet(raw_dir=args.raw_dir)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, rows)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
