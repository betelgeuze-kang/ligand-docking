from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_htr2a_life_science_evidence_packet as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _fixtures(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "target": tmp_path / "chembl_target.json",
        "molecule": tmp_path / "chembl_molecule.json",
        "activity": tmp_path / "chembl_activity.json",
        "mechanism": tmp_path / "chembl_mechanism.json",
        "pubchem": tmp_path / "pubchem.json",
        "rcsb": tmp_path / "rcsb.json",
        "native": tmp_path / "native.json",
        "uniprot": tmp_path / "uniprot.json",
        "bindingdb": tmp_path / "bindingdb.json",
        "topology": tmp_path / "topology.json",
    }
    _write_json(
        paths["target"],
        {
            "target_chembl_id": "CHEMBL224",
            "pref_name": "5-hydroxytryptamine receptor 2A",
            "organism": "Homo sapiens",
            "target_components": [{"accession": "P28223"}],
        },
    )
    _write_json(
        paths["molecule"],
        {
            "molecule_chembl_id": "CHEMBL83894",
            "pref_name": "FANANSERIN",
            "max_phase": "2.0",
            "molecule_properties": {
                "heavy_atoms": 30,
                "aromatic_rings": 3,
                "full_molformula": "C23H24FN3O2S",
                "full_mwt": "425.53",
                "alogp": "3.70",
            },
            "molecule_structures": {
                "canonical_smiles": "O=S1(=O)c2cccc3cccc(c23)N1CCCN1CCN(c2ccc(F)cc2)CC1",
                "standard_inchi_key": "VGIGHGMPMUCLIQ-UHFFFAOYSA-N",
            },
        },
    )
    _write_json(
        paths["activity"],
        {
            "activities": [
                {
                    "standard_type": "Ki",
                    "standard_value": "0.04",
                    "standard_units": "nM",
                    "pchembl_value": "10.40",
                    "assay_description": "Binding affinity for human HTR2A",
                    "document_chembl_id": "CHEMBL1",
                }
            ]
        },
    )
    _write_json(paths["mechanism"], {"mechanisms": []})
    _write_json(
        paths["pubchem"],
        {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 60785,
                        "MolecularFormula": "C23H24FN3O2S",
                        "MolecularWeight": "425.5",
                        "XLogP": 3.7,
                        "TPSA": 43.86,
                        "HeavyAtomCount": 30,
                    }
                ]
            }
        },
    )
    _write_json(
        paths["rcsb"],
        {
            "struct": {"title": "Crystal structure of 5-HT2AR in complex with risperidone"},
            "exptl": [{"method": "X-RAY DIFFRACTION"}],
            "citation": [{"pdbx_database_id_PubMed": 30723326, "pdbx_database_id_DOI": "10.1038/x"}],
        },
    )
    _write_json(
        paths["native"],
        {"pdbx_entity_nonpoly": {"comp_id": "8NU", "name": "risperidone analog"}},
    )
    _write_json(
        paths["uniprot"],
        {
            "results": [
                {
                    "entryType": "UniProtKB reviewed (Swiss-Prot)",
                    "primaryAccession": "P28223",
                    "uniProtkbId": "5HT2A_HUMAN",
                    "uniProtKBCrossReferences": [
                        {
                            "database": "PDB",
                            "id": "6A93",
                            "properties": [{"key": "Resolution", "value": "3.00 A"}],
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        paths["bindingdb"],
        {
            "getLindsByUniprotsResponse": {
                "affinities": [
                    {"query": "5-hydroxytryptamine receptor 2A", "affinity_type": "Ki", "affinity": "4"}
                ]
            }
        },
    )
    _write_json(
        paths["topology"],
        {
            "summary": {
                "status": "htr2a_atom_typed_topology_probe_separates_current_slice_diagnostic_only",
                "positive_topology_probe_support": 1.0,
                "max_decoy_topology_probe_support": 0.0,
                "decoy_support_positive_or_higher_count": 0,
                "positive_heavy_atom_count": 30,
                "positive_aromatic_ring_count": 3,
            }
        },
    )
    return paths


def test_build_packet_supports_claim_locked_htr2a_probe(tmp_path: Path) -> None:
    paths = _fixtures(tmp_path)
    payload = mod.build_packet(
        chembl_target_json=paths["target"],
        chembl_molecule_json=paths["molecule"],
        chembl_activity_json=paths["activity"],
        chembl_mechanism_json=paths["mechanism"],
        pubchem_properties_json=paths["pubchem"],
        rcsb_entry_json=paths["rcsb"],
        rcsb_native_ligand_json=paths["native"],
        uniprot_search_json=paths["uniprot"],
        bindingdb_uniprot_json=paths["bindingdb"],
        topology_probe_json=paths["topology"],
        generated_at_local="2026-05-09T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "life_science_evidence_supports_claim_locked_htr2a_topology_probe"
    assert summary["target_uniprot_accessions"] == ["P28223"]
    assert summary["chembl_min_ki_nM"] == 0.04
    assert summary["uniprot_has_6A93"] is True
    assert payload["evidence_checks"] == {
        "chembl_target_matches": True,
        "molecule_matches_probe": True,
        "structure_matches": True,
        "pharmacology_support": True,
        "bindingdb_context_support": True,
        "topology_separates_slice": True,
    }
    assert payload["claim_boundary"]["scorer_apply_allowed"] is False


def test_build_packet_cli_writes_outputs(tmp_path: Path) -> None:
    paths = _fixtures(tmp_path)
    out_json = tmp_path / "packet.json"
    out_md = tmp_path / "packet.md"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_htr2a_life_science_evidence_packet.py"),
            "--chembl-target-json",
            str(paths["target"]),
            "--chembl-molecule-json",
            str(paths["molecule"]),
            "--chembl-activity-json",
            str(paths["activity"]),
            "--chembl-mechanism-json",
            str(paths["mechanism"]),
            "--pubchem-properties-json",
            str(paths["pubchem"]),
            "--rcsb-entry-json",
            str(paths["rcsb"]),
            "--rcsb-native-ligand-json",
            str(paths["native"]),
            "--uniprot-search-json",
            str(paths["uniprot"]),
            "--bindingdb-uniprot-json",
            str(paths["bindingdb"]),
            "--topology-probe-json",
            str(paths["topology"]),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert payload["summary"]["molecule_pref_name"] == "FANANSERIN"
    assert "GPCR HTR2A Life-Science Evidence Packet" in out_md.read_text(encoding="utf-8")
