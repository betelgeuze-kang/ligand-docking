from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_oprm1_life_science_evidence_packet as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, Path, Path, Path]:
    chembl_target = tmp_path / "chembl_target.json"
    chembl_molecule = tmp_path / "chembl_molecule.json"
    chembl_activity = tmp_path / "chembl_activity.json"
    pubchem = tmp_path / "pubchem.json"
    rcsb_entry = tmp_path / "rcsb_entry.json"
    rcsb_ligand = tmp_path / "rcsb_ligand.json"
    uniprot = tmp_path / "uniprot.json"
    bindingdb = tmp_path / "bindingdb.json"
    _write_json(
        chembl_target,
        {
            "target_chembl_id": "CHEMBL233",
            "pref_name": "Mu-type opioid receptor",
            "organism": "Homo sapiens",
            "target_components": [{"accession": "P35372"}],
        },
    )
    _write_json(
        chembl_molecule,
        {
            "molecule_chembl_id": "CHEMBL331883",
            "molecule_structures": {
                "canonical_smiles": "CCC(=O)N(c1ccccc1)[C@H]1CCN(C[C@H](O)c2ccccc2)C[C@H]1C",
                "standard_inchi_key": "FRPRNNRJTCONEC-COPCDDAFSA-N",
            },
            "molecule_properties": {
                "heavy_atoms": 27,
                "full_molformula": "C23H30N2O2",
                "full_mwt": "366.51",
                "alogp": "3.87",
            },
        },
    )
    _write_json(
        chembl_activity,
        {
            "activities": [
                {
                    "standard_type": "Ki",
                    "standard_value": "0.013",
                    "pchembl_value": "10.89",
                    "assay_description": "Binding affinity against Opioid receptor mu 1",
                }
            ]
        },
    )
    _write_json(
        pubchem,
        {
            "PropertyTable": {
                "Properties": [
                    {
                        "CID": 10021831,
                        "MolecularFormula": "C23H30N2O2",
                        "MolecularWeight": "366.5",
                        "XLogP": 3.6,
                        "HBondDonorCount": 1,
                        "HBondAcceptorCount": 3,
                        "RotatableBondCount": 6,
                    }
                ]
            }
        },
    )
    _write_json(
        rcsb_entry,
        {
            "struct": {"title": "Morphine-bound mu-opioid receptor-Gi complex"},
            "exptl": [{"method": "ELECTRON MICROSCOPY"}],
            "rcsb_entry_info": {"resolution_combined": [3.2]},
        },
    )
    _write_json(
        rcsb_ligand,
        {
            "pdbx_entity_nonpoly": {
                "comp_id": "MOI",
                "name": "(7R,7AS,12BS)-3-METHYL-2,3,4,4A,7,7A-HEXAHYDRO-1H-4,12-METHANO[1]BENZOFURO[3,2-E]ISOQUINOLINE-7,9-DIOL",
            }
        },
    )
    _write_json(
        uniprot,
        {
            "primaryAccession": "P35372",
            "uniProtkbId": "OPRM_HUMAN",
            "uniProtKBCrossReferences": [{"database": "PDB", "id": "8EF6"}],
        },
    )
    _write_json(
        bindingdb,
        {"getLindsByUniprotsResponse": {"affinities": [{"affinity_type": "Ki", "affinity": "0.0013"}]}},
    )
    return chembl_target, chembl_molecule, chembl_activity, pubchem, rcsb_entry, rcsb_ligand, uniprot, bindingdb


def test_build_packet_supports_claim_locked_oprm1_probe(tmp_path: Path) -> None:
    inputs = _fixture_inputs(tmp_path)

    payload = mod.build_packet(
        chembl_target_json=inputs[0],
        chembl_molecule_json=inputs[1],
        chembl_activity_json=inputs[2],
        pubchem_properties_json=inputs[3],
        rcsb_entry_json=inputs[4],
        rcsb_native_ligand_json=inputs[5],
        uniprot_json=inputs[6],
        bindingdb_uniprot_json=inputs[7],
        generated_at_local="2026-05-09T01:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "life_science_evidence_supports_claim_locked_oprm1_topology_pose_probe"
    assert summary["target_chembl_id"] == "CHEMBL233"
    assert summary["uniprot_reviewed_accession"] == "P35372"
    assert summary["pubchem_cid"] == 10021831
    assert summary["chembl_min_ki_nM"] == 0.013
    assert summary["rcsb_entry_id"] == "8EF6"
    assert payload["evidence_checks"]["structure_matches"] is True
    assert payload["claim_boundary"]["scorer_apply_allowed"] is False


def test_cli_writes_evidence_packet(tmp_path: Path) -> None:
    inputs = _fixture_inputs(tmp_path)
    out_json = tmp_path / "out.json"
    out_md = tmp_path / "out.md"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_oprm1_life_science_evidence_packet.py"),
            "--chembl-target-json",
            str(inputs[0]),
            "--chembl-molecule-json",
            str(inputs[1]),
            "--chembl-activity-json",
            str(inputs[2]),
            "--pubchem-properties-json",
            str(inputs[3]),
            "--rcsb-entry-json",
            str(inputs[4]),
            "--rcsb-native-ligand-json",
            str(inputs[5]),
            "--uniprot-json",
            str(inputs[6]),
            "--bindingdb-uniprot-json",
            str(inputs[7]),
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
    assert payload["summary"]["status"] == "life_science_evidence_supports_claim_locked_oprm1_topology_pose_probe"
    assert "GPCR OPRM1 Life-Science Evidence Packet" in out_md.read_text(encoding="utf-8")
