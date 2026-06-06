from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_glut1_claim_safe_binding_kcal_packet as mod


def _source_payload() -> dict[str, object]:
    return {
        "rows": [
            {
                "packet_step": "core_binder_01",
                "candidate_name": "cytochalasin B",
                "source_anchor": "PMID 1716731",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/1716731/",
                "chembl_activity_url": "https://www.ebi.ac.uk/chembl/api/data/activity.json?molecule_chembl_id=CHEMBL411729&target_chembl_id=CHEMBL2535",
                "direct_binding_measure": "Kd=190 nM",
            }
        ]
    }


def _pubchem_payload() -> dict[str, object]:
    return {
        "PropertyTable": {
            "Properties": [
                {
                    "MolecularWeight": "479.6",
                    "ConnectivitySMILES": "CC1CCCC(C=CC(=O)OC23C(C=CC1)C(C(=C)C(C2C(NC3=O)CC4=CC=CC=C4)C)O)O",
                }
            ]
        }
    }


def _chembl_payload() -> dict[str, object]:
    return {
        "activities": [
            {
                "canonical_smiles": "C=C1[C@@H](C)[C@H]2[C@H](Cc3ccccc3)NC(=O)[C@]23OC(=O)/C=C/[C@H](O)CCC[C@@H](C)C/C=C/[C@H]3[C@@H]1O"
            }
        ]
    }


def test_build_glut1_claim_safe_binding_kcal_packet_computes_delta_g() -> None:
    payload = mod.build_payload(
        source_payload=_source_payload(),
        pubchem_payload=_pubchem_payload(),
        chembl_activity_payload=_chembl_payload(),
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "glut1_claim_safe_binding_kcal_packet_ready"
    assert summary["claim_safe_binding_kcal_ready_count"] == 1
    assert row["replacement_ligand_id"] == "cytochalasin_b"
    assert row["replacement_reference_binding_kcal_mol"] == "-9.1694"
    assert row["claim_safe_binding_kcal_ready"] == "yes"
    assert row["manual_verdict"] == "promote_authoritative_apply"
    assert "Kd_190_nM" in row["replacement_source"]


def test_build_glut1_claim_safe_binding_kcal_packet_cli_writes_outputs(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    pubchem = tmp_path / "pubchem.json"
    chembl = tmp_path / "chembl.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    source.write_text(json.dumps(_source_payload()) + "\n", encoding="utf-8")
    pubchem.write_text(json.dumps(_pubchem_payload()) + "\n", encoding="utf-8")
    chembl.write_text(json.dumps(_chembl_payload()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--source-json",
            str(source),
            "--pubchem-json",
            str(pubchem),
            "--chembl-activity-json",
            str(chembl),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["claim_safe_row_count"] == 1
    assert "cytochalasin_b" in out_csv.read_text(encoding="utf-8")
    assert "GLUT1 Claim-Safe Binding Kcal Packet" in out_md.read_text(encoding="utf-8")
