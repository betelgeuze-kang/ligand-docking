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
    summary as _summary,
    write_json as _write_json,
)

DEFAULT_CHEMBL_TARGET_JSON = "runs/life_science_htr2a_evidence_current/chembl_target_CHEMBL224_raw.json"
DEFAULT_CHEMBL_MOLECULE_JSON = "runs/life_science_htr2a_evidence_current/chembl_molecule_CHEMBL83894_raw.json"
DEFAULT_CHEMBL_ACTIVITY_JSON = "runs/life_science_htr2a_evidence_current/chembl_activity_CHEMBL224_CHEMBL83894_raw.json"
DEFAULT_CHEMBL_MECHANISM_JSON = "runs/life_science_htr2a_evidence_current/chembl_mechanism_CHEMBL83894_raw.json"
DEFAULT_PUBCHEM_PROPERTIES_JSON = "runs/life_science_htr2a_evidence_current/pubchem_fananserin_properties_raw.json"
DEFAULT_RCSB_ENTRY_JSON = "runs/life_science_htr2a_evidence_current/rcsb_entry_6A93_raw.json"
DEFAULT_RCSB_NATIVE_LIGAND_JSON = "runs/life_science_htr2a_evidence_current/rcsb_6A93_nonpolymer_2_raw.json"
DEFAULT_UNIPROT_SEARCH_JSON = "runs/life_science_htr2a_evidence_current/uniprot_htr2a_search_raw.json"
DEFAULT_BINDINGDB_UNIPROT_JSON = "runs/life_science_htr2a_evidence_current/bindingdb_uniprot_P28223_raw.json"
DEFAULT_TOPOLOGY_PROBE_JSON = "runs/gpcr_htr2a_atom_typed_topology_probe_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_htr2a_life_science_evidence_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_htr2a_life_science_evidence_packet_current.md"


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


def _mechanisms(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("mechanisms", [])
    return rows if isinstance(rows, list) else []


def _pubchem_properties(payload: dict[str, Any]) -> dict[str, Any]:
    rows = ((payload.get("PropertyTable") or {}).get("Properties") or [])
    return rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}


def _reviewed_uniprot_entry(payload: dict[str, Any]) -> dict[str, Any]:
    for row in payload.get("results", []) or []:
        if "reviewed" in _text(row.get("entryType")).lower():
            return row
    return {}


def _pdb_refs(uniprot_entry: dict[str, Any]) -> list[dict[str, Any]]:
    refs = uniprot_entry.get("uniProtKBCrossReferences", [])
    return [row for row in refs if isinstance(row, dict) and row.get("database") == "PDB"]


def _pdb_ref_resolution(ref: dict[str, Any]) -> str:
    for prop in ref.get("properties", []) or []:
        if prop.get("key") == "Resolution":
            return _text(prop.get("value"))
    return ""


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
        "document_chembl_ids": sorted({_text(row.get("document_chembl_id")) for row in rows if row.get("document_chembl_id")}),
    }


def build_packet(
    *,
    chembl_target_json: str | Path = DEFAULT_CHEMBL_TARGET_JSON,
    chembl_molecule_json: str | Path = DEFAULT_CHEMBL_MOLECULE_JSON,
    chembl_activity_json: str | Path = DEFAULT_CHEMBL_ACTIVITY_JSON,
    chembl_mechanism_json: str | Path = DEFAULT_CHEMBL_MECHANISM_JSON,
    pubchem_properties_json: str | Path = DEFAULT_PUBCHEM_PROPERTIES_JSON,
    rcsb_entry_json: str | Path = DEFAULT_RCSB_ENTRY_JSON,
    rcsb_native_ligand_json: str | Path = DEFAULT_RCSB_NATIVE_LIGAND_JSON,
    uniprot_search_json: str | Path = DEFAULT_UNIPROT_SEARCH_JSON,
    bindingdb_uniprot_json: str | Path = DEFAULT_BINDINGDB_UNIPROT_JSON,
    topology_probe_json: str | Path = DEFAULT_TOPOLOGY_PROBE_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    chembl_target = _read_json(chembl_target_json)
    chembl_molecule = _read_json(chembl_molecule_json)
    chembl_activities = _activities(_read_json(chembl_activity_json))
    chembl_mechanisms = _mechanisms(_read_json(chembl_mechanism_json))
    pubchem_props = _pubchem_properties(_read_json(pubchem_properties_json))
    rcsb_entry = _read_json(rcsb_entry_json)
    rcsb_native_ligand = _read_json(rcsb_native_ligand_json)
    uniprot_entry = _reviewed_uniprot_entry(_read_json(uniprot_search_json))
    bindingdb_affinities = _bindingdb_affinities(_read_json(bindingdb_uniprot_json))
    topology_probe_summary = _summary(_read_json(topology_probe_json))

    target_components = chembl_target.get("target_components") or []
    target_accessions = sorted(
        {
            _text(component.get("accession"))
            for component in target_components
            if isinstance(component, dict) and component.get("accession")
        }
    )
    molecule_props = chembl_molecule.get("molecule_properties") or {}
    molecule_structures = chembl_molecule.get("molecule_structures") or {}
    activity_summary = _chembl_activity_summary(chembl_activities)
    pdb_refs = _pdb_refs(uniprot_entry)
    pdb_6a93 = next((row for row in pdb_refs if row.get("id") == "6A93"), {})
    bindingdb_min_ki = _min_numeric_affinity(bindingdb_affinities, "Ki")
    topology_status = _text(topology_probe_summary.get("status"))
    topology_separates_slice = topology_status == "htr2a_atom_typed_topology_probe_separates_current_slice_diagnostic_only"
    chembl_target_matches = (
        chembl_target.get("target_chembl_id") == "CHEMBL224"
        and _text(chembl_target.get("organism")) == "Homo sapiens"
        and "P28223" in target_accessions
    )
    molecule_matches_probe = (
        _text(chembl_molecule.get("molecule_chembl_id")) == "CHEMBL83894"
        and _text(chembl_molecule.get("pref_name")).upper() == "FANANSERIN"
        and int(molecule_props.get("heavy_atoms") or 0) == int(topology_probe_summary.get("positive_heavy_atom_count") or -1)
        and int(molecule_props.get("aromatic_rings") or 0)
        == int(topology_probe_summary.get("positive_aromatic_ring_count") or -1)
    )
    structure_matches = (
        _text((rcsb_entry.get("struct") or {}).get("title")).lower().find("5-ht2a") >= 0
        and _text((rcsb_native_ligand.get("pdbx_entity_nonpoly") or {}).get("comp_id")) == "8NU"
        and _text(pdb_6a93.get("id")) == "6A93"
    )
    pharmacology_support = (activity_summary["ki_activity_count"] or 0) > 0 and (
        activity_summary["min_ki_nM"] is not None and activity_summary["min_ki_nM"] <= 10.0
    )
    bindingdb_context_support = len(bindingdb_affinities) > 0 and (bindingdb_min_ki is None or bindingdb_min_ki <= 10.0)
    status = (
        "life_science_evidence_supports_claim_locked_htr2a_topology_probe"
        if chembl_target_matches
        and molecule_matches_probe
        and structure_matches
        and pharmacology_support
        and bindingdb_context_support
        and topology_separates_slice
        else "blocked_life_science_evidence_incomplete_for_htr2a_topology_probe"
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
        "uniprot_has_6A93": bool(pdb_6a93),
        "uniprot_6A93_resolution": _pdb_ref_resolution(pdb_6a93),
        "molecule_chembl_id": chembl_molecule.get("molecule_chembl_id"),
        "molecule_pref_name": chembl_molecule.get("pref_name"),
        "molecule_max_phase": chembl_molecule.get("max_phase"),
        "chembl_heavy_atoms": molecule_props.get("heavy_atoms"),
        "chembl_aromatic_rings": molecule_props.get("aromatic_rings"),
        "chembl_formula": molecule_props.get("full_molformula"),
        "chembl_mw": molecule_props.get("full_mwt"),
        "chembl_alogp": molecule_props.get("alogp"),
        "chembl_canonical_smiles": molecule_structures.get("canonical_smiles"),
        "chembl_standard_inchi_key": molecule_structures.get("standard_inchi_key"),
        "pubchem_cid": pubchem_props.get("CID"),
        "pubchem_molecular_formula": pubchem_props.get("MolecularFormula"),
        "pubchem_molecular_weight": pubchem_props.get("MolecularWeight"),
        "pubchem_xlogp": pubchem_props.get("XLogP"),
        "pubchem_tpsa": pubchem_props.get("TPSA"),
        "pubchem_heavy_atom_count": pubchem_props.get("HeavyAtomCount"),
        "chembl_activity_count": activity_summary["activity_count"],
        "chembl_ki_activity_count": activity_summary["ki_activity_count"],
        "chembl_min_ki_nM": activity_summary["min_ki_nM"],
        "chembl_max_pchembl_value": activity_summary["max_pchembl_value"],
        "chembl_mechanism_count": len(chembl_mechanisms),
        "bindingdb_htr2a_affinity_count": len(bindingdb_affinities),
        "bindingdb_min_ki_reported": bindingdb_min_ki,
        "rcsb_entry_id": "6A93",
        "rcsb_title": (rcsb_entry.get("struct") or {}).get("title"),
        "rcsb_method": _text(((rcsb_entry.get("exptl") or [{}])[0] or {}).get("method")),
        "rcsb_primary_pubmed_id": ((rcsb_entry.get("citation") or [{}])[0] or {}).get("pdbx_database_id_PubMed"),
        "rcsb_primary_doi": ((rcsb_entry.get("citation") or [{}])[0] or {}).get("pdbx_database_id_DOI"),
        "rcsb_native_ligand_comp_id": (rcsb_native_ligand.get("pdbx_entity_nonpoly") or {}).get("comp_id"),
        "rcsb_native_ligand_name": (rcsb_native_ligand.get("pdbx_entity_nonpoly") or {}).get("name"),
        "topology_probe_status": topology_status,
        "topology_probe_positive_support": topology_probe_summary.get("positive_topology_probe_support"),
        "topology_probe_max_decoy_support": topology_probe_summary.get("max_decoy_topology_probe_support"),
        "topology_probe_decoy_support_positive_or_higher_count": topology_probe_summary.get(
            "decoy_support_positive_or_higher_count"
        ),
        "next_action": "prototype_claim_locked_htr2a_topology_support_shadow_replay",
        "next_required_step": (
            "Use these external-source checks only to justify a claim-locked frozen shadow replay of the HTR2A "
            "topology-support feature. Do not apply the scorer or rerun guarded 100k until replay, leakage review, "
            "DRD2/OPRM1 regression checks, and OPRM1 support repair are complete."
        ),
    }
    return {
        "packet_type": "gpcr_htr2a_life_science_evidence_packet",
        "summary": summary,
        "source_artifacts": {
            "chembl_target": _artifact(chembl_target_json),
            "chembl_molecule": _artifact(chembl_molecule_json),
            "chembl_activity": _artifact(chembl_activity_json),
            "chembl_mechanism": _artifact(chembl_mechanism_json),
            "pubchem_properties": _artifact(pubchem_properties_json),
            "rcsb_entry": _artifact(rcsb_entry_json),
            "rcsb_native_ligand": _artifact(rcsb_native_ligand_json),
            "uniprot_search": _artifact(uniprot_search_json),
            "bindingdb_uniprot": _artifact(bindingdb_uniprot_json),
            "topology_probe": _artifact(topology_probe_json),
        },
        "source_urls": {
            "chembl_target": "https://www.ebi.ac.uk/chembl/api/data/target/CHEMBL224.json",
            "chembl_molecule": "https://www.ebi.ac.uk/chembl/api/data/molecule/CHEMBL83894.json",
            "chembl_activity": "https://www.ebi.ac.uk/chembl/api/data/activity.json?target_chembl_id=CHEMBL224&molecule_chembl_id=CHEMBL83894",
            "pubchem_compound": "https://pubchem.ncbi.nlm.nih.gov/compound/60785",
            "rcsb_entry": "https://data.rcsb.org/rest/v1/core/entry/6A93",
            "uniprot_htr2a": "https://rest.uniprot.org/uniprotkb/P28223",
            "bindingdb_uniprot": "https://bindingdb.org/rest/getLigandsByUniprots?uniprot=P28223&cutoff=100&response=application/json",
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
        "evidence_checks": {
            "chembl_target_matches": chembl_target_matches,
            "molecule_matches_probe": molecule_matches_probe,
            "structure_matches": structure_matches,
            "pharmacology_support": pharmacology_support,
            "bindingdb_context_support": bindingdb_context_support,
            "topology_separates_slice": topology_separates_slice,
        },
        "chembl_activity_evidence": activity_summary,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    checks = payload["evidence_checks"]
    lines = [
        "# GPCR HTR2A Life-Science Evidence Packet",
        "",
        f"- status: `{s['status']}`",
        f"- claim_promotion_allowed: `{str(s['claim_promotion_allowed']).lower()}`",
        f"- scorer_apply_allowed: `{str(s['scorer_apply_allowed']).lower()}`",
        f"- guarded_100k_rerun_allowed: `{str(s['guarded_100k_rerun_allowed']).lower()}`",
        f"- target: `{s['target_pref_name']}` / `{s['target_chembl_id']}` / `{s['uniprot_reviewed_accession']}`",
        f"- molecule: `{s['molecule_pref_name']}` / `{s['molecule_chembl_id']}` / PubChem CID `{s['pubchem_cid']}`",
        f"- ChEMBL Ki evidence: `{s['chembl_ki_activity_count']}` Ki rows, min Ki `{s['chembl_min_ki_nM']}` nM, max pChEMBL `{s['chembl_max_pchembl_value']}`",
        f"- RCSB structure: `{s['rcsb_entry_id']}` `{s['rcsb_title']}`; method `{s['rcsb_method']}`; native ligand `{s['rcsb_native_ligand_comp_id']}`",
        f"- UniProt PDB cross-reference: 6A93 present `{str(s['uniprot_has_6A93']).lower()}` at `{s['uniprot_6A93_resolution']}`",
        f"- BindingDB HTR2A affinity rows: `{s['bindingdb_htr2a_affinity_count']}`",
        f"- topology_probe_status: `{s['topology_probe_status']}`",
        f"- topology_probe_positive_support: `{s['topology_probe_positive_support']}`",
        f"- topology_probe_max_decoy_support: `{s['topology_probe_max_decoy_support']}`",
        "",
        "## Evidence Checks",
        "",
    ]
    for key, value in checks.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.extend(["", "## Source URLs", ""])
    for key, value in payload["source_urls"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Next Required Step", "", s["next_required_step"], ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build HTR2A life-science evidence packet.")
    parser.add_argument("--chembl-target-json", default=DEFAULT_CHEMBL_TARGET_JSON)
    parser.add_argument("--chembl-molecule-json", default=DEFAULT_CHEMBL_MOLECULE_JSON)
    parser.add_argument("--chembl-activity-json", default=DEFAULT_CHEMBL_ACTIVITY_JSON)
    parser.add_argument("--chembl-mechanism-json", default=DEFAULT_CHEMBL_MECHANISM_JSON)
    parser.add_argument("--pubchem-properties-json", default=DEFAULT_PUBCHEM_PROPERTIES_JSON)
    parser.add_argument("--rcsb-entry-json", default=DEFAULT_RCSB_ENTRY_JSON)
    parser.add_argument("--rcsb-native-ligand-json", default=DEFAULT_RCSB_NATIVE_LIGAND_JSON)
    parser.add_argument("--uniprot-search-json", default=DEFAULT_UNIPROT_SEARCH_JSON)
    parser.add_argument("--bindingdb-uniprot-json", default=DEFAULT_BINDINGDB_UNIPROT_JSON)
    parser.add_argument("--topology-probe-json", default=DEFAULT_TOPOLOGY_PROBE_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_packet(
        chembl_target_json=args.chembl_target_json,
        chembl_molecule_json=args.chembl_molecule_json,
        chembl_activity_json=args.chembl_activity_json,
        chembl_mechanism_json=args.chembl_mechanism_json,
        pubchem_properties_json=args.pubchem_properties_json,
        rcsb_entry_json=args.rcsb_entry_json,
        rcsb_native_ligand_json=args.rcsb_native_ligand_json,
        uniprot_search_json=args.uniprot_search_json,
        bindingdb_uniprot_json=args.bindingdb_uniprot_json,
        topology_probe_json=args.topology_probe_json,
    )
    _write_json(args.out_json, payload)
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
