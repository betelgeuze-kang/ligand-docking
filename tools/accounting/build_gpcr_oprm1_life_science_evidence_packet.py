#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

from tools.lib.artifacts import (
    artifact as _artifact,
    read_json as _read_json,
    resolve as _resolve,
    write_json as _write_json,
)

DEFAULT_CHEMBL_TARGET_JSON = "runs/life_science_oprm1_evidence_current/chembl_target_CHEMBL233_raw.json"
DEFAULT_CHEMBL_MOLECULE_JSON = "runs/life_science_oprm1_evidence_current/chembl_molecule_CHEMBL331883_raw.json"
DEFAULT_CHEMBL_ACTIVITY_JSON = "runs/life_science_oprm1_evidence_current/chembl_activity_CHEMBL233_CHEMBL331883_raw.json"
DEFAULT_PUBCHEM_PROPERTIES_JSON = "runs/life_science_oprm1_evidence_current/pubchem_CHEMBL331883_properties_raw.json"
DEFAULT_RCSB_ENTRY_JSON = "runs/life_science_oprm1_evidence_current/rcsb_entry_8EF6_raw.json"
DEFAULT_RCSB_NATIVE_LIGAND_JSON = "runs/life_science_oprm1_evidence_current/rcsb_8EF6_nonpolymer_6_raw.json"
DEFAULT_UNIPROT_JSON = "runs/life_science_oprm1_evidence_current/uniprot_P35372_raw.json"
DEFAULT_BINDINGDB_UNIPROT_JSON = "runs/life_science_oprm1_evidence_current/bindingdb_uniprot_P35372_raw.json"
DEFAULT_OUT_JSON = "runs/gpcr_oprm1_life_science_evidence_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_oprm1_life_science_evidence_packet_current.md"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _activities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("activities", [])
    return rows if isinstance(rows, list) else []


def _pubchem_properties(payload: dict[str, Any]) -> dict[str, Any]:
    rows = ((payload.get("PropertyTable") or {}).get("Properties") or [])
    return rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}


def _pdb_refs(uniprot_entry: dict[str, Any]) -> list[dict[str, Any]]:
    refs = uniprot_entry.get("uniProtKBCrossReferences", [])
    return [row for row in refs if isinstance(row, dict) and row.get("database") == "PDB"]


def _bindingdb_affinities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    response = payload.get("getLindsByUniprotsResponse") or {}
    rows = response.get("affinities") or []
    return rows if isinstance(rows, list) else []


def _min_numeric_affinity(rows: list[dict[str, Any]], affinity_type: str = "Ki") -> float | None:
    values: list[float] = []
    for row in rows:
        if _text(row.get("affinity_type")).lower() != affinity_type.lower():
            continue
        value = _float(row.get("affinity"))
        if value is not None:
            values.append(value)
    return min(values) if values else None


def _chembl_activity_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ki_rows = [row for row in rows if _text(row.get("standard_type")).lower() == "ki"]
    ki_values = [_float(row.get("standard_value")) for row in ki_rows]
    pchembl_values = [_float(row.get("pchembl_value")) for row in rows]
    real_ki = [value for value in ki_values if value is not None]
    real_pchembl = [value for value in pchembl_values if value is not None]
    return {
        "activity_count": len(rows),
        "ki_activity_count": len(ki_rows),
        "min_ki_nM": min(real_ki) if real_ki else None,
        "max_pchembl_value": max(real_pchembl) if real_pchembl else None,
        "assay_descriptions": [_text(row.get("assay_description")) for row in rows[:5]],
    }


def build_packet(
    *,
    chembl_target_json: str | Path = DEFAULT_CHEMBL_TARGET_JSON,
    chembl_molecule_json: str | Path = DEFAULT_CHEMBL_MOLECULE_JSON,
    chembl_activity_json: str | Path = DEFAULT_CHEMBL_ACTIVITY_JSON,
    pubchem_properties_json: str | Path = DEFAULT_PUBCHEM_PROPERTIES_JSON,
    rcsb_entry_json: str | Path = DEFAULT_RCSB_ENTRY_JSON,
    rcsb_native_ligand_json: str | Path = DEFAULT_RCSB_NATIVE_LIGAND_JSON,
    uniprot_json: str | Path = DEFAULT_UNIPROT_JSON,
    bindingdb_uniprot_json: str | Path = DEFAULT_BINDINGDB_UNIPROT_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    chembl_target = _read_json(chembl_target_json)
    chembl_molecule = _read_json(chembl_molecule_json)
    chembl_activities = _activities(_read_json(chembl_activity_json))
    pubchem_props = _pubchem_properties(_read_json(pubchem_properties_json))
    rcsb_entry = _read_json(rcsb_entry_json)
    rcsb_native_ligand = _read_json(rcsb_native_ligand_json)
    uniprot_entry = _read_json(uniprot_json)
    bindingdb_affinities = _bindingdb_affinities(_read_json(bindingdb_uniprot_json))

    target_components = chembl_target.get("target_components") or []
    target_accessions = sorted(
        {
            _text(component.get("accession"))
            for component in target_components
            if isinstance(component, dict) and component.get("accession")
        }
    )
    molecule_structures = chembl_molecule.get("molecule_structures") or {}
    molecule_props = chembl_molecule.get("molecule_properties") or {}
    activity_summary = _chembl_activity_summary(chembl_activities)
    pdb_refs = _pdb_refs(uniprot_entry)
    bindingdb_min_ki = _min_numeric_affinity(bindingdb_affinities, "Ki")

    chembl_target_matches = (
        chembl_target.get("target_chembl_id") == "CHEMBL233"
        and _text(chembl_target.get("organism")) == "Homo sapiens"
        and "P35372" in target_accessions
    )
    molecule_matches = (
        _text(chembl_molecule.get("molecule_chembl_id")) == "CHEMBL331883"
        and _text(molecule_structures.get("standard_inchi_key")) == "FRPRNNRJTCONEC-COPCDDAFSA-N"
    )
    structure_matches = (
        "mu-opioid receptor" in _text((rcsb_entry.get("struct") or {}).get("title")).lower()
        and _text((rcsb_native_ligand.get("pdbx_entity_nonpoly") or {}).get("comp_id")) == "MOI"
    )
    pharmacology_support = (activity_summary["ki_activity_count"] or 0) > 0 and (
        activity_summary["min_ki_nM"] is not None and activity_summary["min_ki_nM"] <= 10.0
    )
    bindingdb_context_support = len(bindingdb_affinities) > 0 and (bindingdb_min_ki is None or bindingdb_min_ki <= 10.0)
    status = (
        "life_science_evidence_supports_claim_locked_oprm1_topology_pose_probe"
        if chembl_target_matches
        and molecule_matches
        and structure_matches
        and pharmacology_support
        and bindingdb_context_support
        else "blocked_life_science_evidence_incomplete_for_oprm1_topology_pose_probe"
    )
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "guarded_100k_rerun_allowed": False,
        "target_chembl_id": chembl_target.get("target_chembl_id"),
        "target_pref_name": chembl_target.get("pref_name"),
        "target_organism": chembl_target.get("organism"),
        "target_uniprot_accessions": target_accessions,
        "uniprot_reviewed_accession": uniprot_entry.get("primaryAccession"),
        "uniprot_id": uniprot_entry.get("uniProtkbId"),
        "uniprot_pdb_ref_count": len(pdb_refs),
        "uniprot_has_8EF6": any(row.get("id") == "8EF6" for row in pdb_refs),
        "molecule_chembl_id": chembl_molecule.get("molecule_chembl_id"),
        "chembl_canonical_smiles": molecule_structures.get("canonical_smiles"),
        "chembl_standard_inchi_key": molecule_structures.get("standard_inchi_key"),
        "chembl_heavy_atoms": molecule_props.get("heavy_atoms"),
        "chembl_formula": molecule_props.get("full_molformula"),
        "chembl_mw": molecule_props.get("full_mwt"),
        "chembl_alogp": molecule_props.get("alogp"),
        "pubchem_cid": pubchem_props.get("CID"),
        "pubchem_molecular_formula": pubchem_props.get("MolecularFormula"),
        "pubchem_molecular_weight": pubchem_props.get("MolecularWeight"),
        "pubchem_xlogp": pubchem_props.get("XLogP"),
        "pubchem_hbond_donor_count": pubchem_props.get("HBondDonorCount"),
        "pubchem_hbond_acceptor_count": pubchem_props.get("HBondAcceptorCount"),
        "pubchem_rotatable_bond_count": pubchem_props.get("RotatableBondCount"),
        "chembl_activity_count": activity_summary["activity_count"],
        "chembl_ki_activity_count": activity_summary["ki_activity_count"],
        "chembl_min_ki_nM": activity_summary["min_ki_nM"],
        "chembl_max_pchembl_value": activity_summary["max_pchembl_value"],
        "bindingdb_oprm1_affinity_count": len(bindingdb_affinities),
        "bindingdb_min_ki_reported": bindingdb_min_ki,
        "rcsb_entry_id": "8EF6",
        "rcsb_title": (rcsb_entry.get("struct") or {}).get("title"),
        "rcsb_method": _text(((rcsb_entry.get("exptl") or [{}])[0] or {}).get("method")),
        "rcsb_resolution_A": ((rcsb_entry.get("rcsb_entry_info") or {}).get("resolution_combined") or [None])[0],
        "rcsb_native_ligand_comp_id": (rcsb_native_ligand.get("pdbx_entity_nonpoly") or {}).get("comp_id"),
        "rcsb_native_ligand_name": (rcsb_native_ligand.get("pdbx_entity_nonpoly") or {}).get("name"),
        "next_action": "prototype_claim_locked_oprm1_topology_pose_shadow_replay",
        "next_required_step": (
            "Use these external-source checks only to justify a claim-locked frozen shadow replay of an OPRM1 "
            "topology/pose support feature. Do not apply the scorer or rerun guarded 100k until replay and "
            "CI/top20 gates clear without target identity, labels, or threshold relaxation."
        ),
    }
    return {
        "packet_type": "gpcr_oprm1_life_science_evidence_packet",
        "summary": summary,
        "source_artifacts": {
            "chembl_target": _artifact(chembl_target_json),
            "chembl_molecule": _artifact(chembl_molecule_json),
            "chembl_activity": _artifact(chembl_activity_json),
            "pubchem_properties": _artifact(pubchem_properties_json),
            "rcsb_entry": _artifact(rcsb_entry_json),
            "rcsb_native_ligand": _artifact(rcsb_native_ligand_json),
            "uniprot": _artifact(uniprot_json),
            "bindingdb_uniprot": _artifact(bindingdb_uniprot_json),
        },
        "evidence_checks": {
            "chembl_target_matches": chembl_target_matches,
            "molecule_matches": molecule_matches,
            "structure_matches": structure_matches,
            "pharmacology_support": pharmacology_support,
            "bindingdb_context_support": bindingdb_context_support,
        },
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "guarded_100k_rerun_allowed": False,
            "threshold_relaxation_allowed": False,
            "target_identity_feature_allowed": False,
            "label_feature_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# GPCR OPRM1 Life-Science Evidence Packet",
        "",
        f"- status: `{s['status']}`",
        f"- claim_promotion_allowed: `{str(s['claim_promotion_allowed']).lower()}`",
        f"- scorer_apply_allowed: `{str(s['scorer_apply_allowed']).lower()}`",
        f"- guarded_100k_rerun_allowed: `{str(s['guarded_100k_rerun_allowed']).lower()}`",
        f"- target: `{s['target_pref_name']}` / `{s['target_chembl_id']}` / `{s['uniprot_reviewed_accession']}`",
        f"- molecule: `{s['molecule_chembl_id']}` / PubChem CID `{s['pubchem_cid']}` / InChIKey `{s['chembl_standard_inchi_key']}`",
        f"- ChEMBL Ki evidence: `{s['chembl_ki_activity_count']}` Ki rows, min Ki `{s['chembl_min_ki_nM']}` nM, max pChEMBL `{s['chembl_max_pchembl_value']}`",
        f"- RCSB structure: `{s['rcsb_entry_id']}` `{s['rcsb_title']}`; method `{s['rcsb_method']}`; native ligand `{s['rcsb_native_ligand_comp_id']}`",
        f"- BindingDB OPRM1 affinity rows: `{s['bindingdb_oprm1_affinity_count']}`",
        "",
        "## Evidence Checks",
        "",
    ]
    for key, value in payload["evidence_checks"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Next Required Step", "", s["next_required_step"], ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build OPRM1 life-science evidence packet.")
    parser.add_argument("--chembl-target-json", default=DEFAULT_CHEMBL_TARGET_JSON)
    parser.add_argument("--chembl-molecule-json", default=DEFAULT_CHEMBL_MOLECULE_JSON)
    parser.add_argument("--chembl-activity-json", default=DEFAULT_CHEMBL_ACTIVITY_JSON)
    parser.add_argument("--pubchem-properties-json", default=DEFAULT_PUBCHEM_PROPERTIES_JSON)
    parser.add_argument("--rcsb-entry-json", default=DEFAULT_RCSB_ENTRY_JSON)
    parser.add_argument("--rcsb-native-ligand-json", default=DEFAULT_RCSB_NATIVE_LIGAND_JSON)
    parser.add_argument("--uniprot-json", default=DEFAULT_UNIPROT_JSON)
    parser.add_argument("--bindingdb-uniprot-json", default=DEFAULT_BINDINGDB_UNIPROT_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_packet(
        chembl_target_json=args.chembl_target_json,
        chembl_molecule_json=args.chembl_molecule_json,
        chembl_activity_json=args.chembl_activity_json,
        pubchem_properties_json=args.pubchem_properties_json,
        rcsb_entry_json=args.rcsb_entry_json,
        rcsb_native_ligand_json=args.rcsb_native_ligand_json,
        uniprot_json=args.uniprot_json,
        bindingdb_uniprot_json=args.bindingdb_uniprot_json,
    )
    _write_json(args.out_json, payload)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
