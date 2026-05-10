from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_positive_coverage_expansion_packet as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_raw_fixture(raw_dir: Path) -> None:
    for spec in mod.TARGET_SPECS:
        activity_name = str(spec["activity_raw"])
        molecule_name = str(spec["molecule_raw"])
        ligand = molecule_name.replace("chembl_molecule_", "").replace("_raw.json", "")
        _write_json(
            raw_dir / activity_name,
            {
                "activities": [
                    {
                        "molecule_chembl_id": ligand,
                        "activity_id": 123,
                        "document_chembl_id": "CHEMBL_DOC",
                        "standard_type": "Ki",
                        "standard_relation": "=",
                        "standard_value": "0.05",
                        "standard_units": "nM",
                        "pchembl_value": "10.30",
                        "assay_type": "B",
                        "assay_description": "human GPCR radioligand binding assay",
                    }
                ]
            },
        )
        _write_json(
            raw_dir / molecule_name,
            {
                "molecule_chembl_id": ligand,
                "pref_name": ligand,
                "max_phase": 0,
                "molecule_structures": {
                    "canonical_smiles": "CCN",
                    "standard_inchi_key": f"{ligand}_KEY",
                },
                "molecule_properties": {
                    "full_mwt": "45.0",
                    "alogp": "0.1",
                    "hba": "1",
                    "hbd": "1",
                },
            },
        )
        _write_json(
            raw_dir / str(spec["uniprot_raw"]),
            {
                "entryType": "UniProtKB reviewed (Swiss-Prot)",
                "primaryAccession": spec["uniprot_accession"],
                "uniProtkbId": f"{spec['target_chembl_id']}_HUMAN",
            },
        )
        _write_json(raw_dir / str(spec["alphafold_raw"]), {"$": [{"modelEntityId": "AF-TEST-F1"}]})
        _write_json(raw_dir / str(spec["rcsb_search_raw"]), {"result_set": [{"identifier": "1ABC", "score": 1.0}]})
        _write_json(
            raw_dir / str(spec["pubchem_raw"]),
            {
                "PropertyTable": {
                    "Properties": [
                        {
                            "CID": 123,
                            "MolecularFormula": "C2H7N",
                            "MolecularWeight": "45.0",
                            "XLogP": "0.1",
                            "HBondDonorCount": "1",
                            "HBondAcceptorCount": "1",
                            "RotatableBondCount": "1",
                        }
                    ]
                }
            },
        )


def test_build_packet_stages_four_positive_candidates(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    _write_raw_fixture(raw_dir)

    payload, rows = mod.build_packet(raw_dir=raw_dir, generated_at_local="2026-05-09T00:00:00+09:00")

    summary = payload["summary"]
    assert summary["status"] == "gpcr_positive_coverage_expansion_candidates_ready_for_materialization"
    assert summary["ready_positive_candidate_count"] == 4
    assert summary["staged_positive_candidate_count"] == 4
    assert summary["projected_positive_count_after_staging"] == 7
    assert summary["reviewed_uniprot_candidate_count"] == 4
    assert summary["rcsb_experimental_candidate_count"] == 4
    assert summary["alphafold_candidate_count"] == 4
    assert summary["pubchem_property_candidate_count"] == 4
    assert summary["claim_promotion_allowed"] is False
    assert summary["missing_artifacts"] == []
    assert {row["target_chembl_id"] for row in rows} == {"CHEMBL234", "CHEMBL251", "CHEMBL231", "CHEMBL236"}
    assert all(row["inclusion_decision"] == "ready_for_frozen_pipeline_materialization" for row in rows)
    assert rows[0]["uniprot_accession"] == "P35462"
    assert rows[0]["uniprot_reviewed"] is True
    assert rows[0]["rcsb_first_hit"] == "1ABC"


def test_cli_writes_positive_coverage_artifacts(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    out_json = tmp_path / "packet.json"
    out_md = tmp_path / "packet.md"
    out_csv = tmp_path / "packet.csv"
    _write_raw_fixture(raw_dir)

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_positive_coverage_expansion_packet.py"),
            "--raw-dir",
            str(raw_dir),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--out-csv",
            str(out_csv),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["packet_type"] == "gpcr_positive_coverage_expansion_packet"
    assert "GPCR Positive Coverage Expansion Packet" in out_md.read_text(encoding="utf-8")
    assert "CHEMBL234_DRD3_HUMAN" in out_csv.read_text(encoding="utf-8")
