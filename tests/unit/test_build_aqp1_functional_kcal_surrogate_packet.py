from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_functional_kcal_surrogate_packet as mod

ROOT = Path(__file__).resolve().parents[2]


def _capture_payload() -> dict:
    return {
        "summary": {
            "binder_row_count": 3,
            "supportive_direct_quantitative_binding_count": 0,
            "kcal_overlay_ready_count": 0,
        },
        "rows": [
            {
                "packet_step": "core_binder_01",
                "candidate_name": "bacopaside II",
                "replacement_ligand_id": "aqp1_bacopaside_ii_review_seed",
                "source_anchor": "PMID 27474162",
                "source_title": "Bacopaside source",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                "current_signal": "AQP1 water-channel IC50 18 uM in Xenopus oocyte assay",
                "quantitative_measure_kind": "IC50",
                "quantitative_measure_value": "18",
                "quantitative_measure_units": "uM",
            },
            {
                "packet_step": "core_binder_02",
                "candidate_name": "AqB013",
                "replacement_ligand_id": "AqB013",
                "source_anchor": "PMID 22427546",
                "source_title": "AqB013 source",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/22427546/",
                "current_signal": "20 uM AqB013 blocked cGMP-stimulated AQP1-dependent fluid flux",
                "quantitative_measure_kind": "functional_single_concentration_effect",
                "quantitative_measure_value": "20",
                "quantitative_measure_units": "uM",
            },
            {
                "packet_step": "core_binder_03",
                "candidate_name": "AqB011",
                "replacement_ligand_id": "AqB011",
                "source_anchor": "PMID 26467039",
                "source_title": "AqB011 source",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/26467039/",
                "current_signal": "AqB011 blocked AQP1 ion conductance with IC50 14 uM",
                "quantitative_measure_kind": "IC50",
                "quantitative_measure_value": "14",
                "quantitative_measure_units": "uM",
            },
        ],
    }


def _provenance_payload() -> dict:
    return {
        "summary": {
            "exact_human_aqp1_activity_count": 1,
            "claim_safe_kcal_ready_count": 0,
        },
        "rows": [
            {
                "packet_step": "core_binder_01",
                "pubchem_cid": "9876264",
                "pubchem_canonical_smiles": "CC",
                "chembl_activity_record_count": "0",
                "target_chembl_id": "CHEMBL4523210",
                "target_uniprot": "P29972",
            },
            {
                "packet_step": "core_binder_02",
                "pubchem_cid": "25026841",
                "pubchem_canonical_smiles": "CCC",
                "chembl_molecule_chembl_id": "CHEMBL5280895",
                "chembl_best_activity_type": "IC50",
                "chembl_best_activity_value": "20000.0",
                "chembl_best_activity_units": "nM",
                "chembl_activity_record_count": "1",
                "target_chembl_id": "CHEMBL4523210",
                "target_uniprot": "P29972",
            },
            {
                "packet_step": "core_binder_03",
                "pubchem_cid": "25026839",
                "pubchem_canonical_smiles": "CCCC",
                "chembl_activity_record_count": "0",
                "target_chembl_id": "CHEMBL4523210",
                "target_uniprot": "P29972",
            },
        ],
    }


def test_build_payload_creates_claim_safe_functional_surrogates_without_direct_binding_claims() -> None:
    payload = mod.build_payload(_capture_payload(), _provenance_payload(), as_of_date="2026-05-13")

    summary = payload["summary"]
    rows = {row["packet_step"]: row for row in payload["rows"]}

    assert summary["row_count"] == 3
    assert summary["functional_kcal_surrogate_ready_count"] == 3
    assert summary["claim_safe_functional_kcal_ready_count"] == 3
    assert summary["direct_binding_claim_allowed_count"] == 0
    assert summary["functional_kcal_surrogate_closure_allowed"] is True
    assert summary["direct_binding_gap_still_open"] is True

    assert rows["core_binder_01"]["functional_delta_g_surrogate_kcal_mol"] == "-6.47"
    assert rows["core_binder_02"]["functional_measure_basis"] == "chembl_exact_target_functional_ic50"
    assert rows["core_binder_02"]["functional_delta_g_surrogate_kcal_mol"] == "-6.41"
    assert rows["core_binder_03"]["functional_delta_g_surrogate_kcal_mol"] == "-6.62"
    assert {row["direct_binding_claim_allowed"] for row in payload["rows"]} == {"no"}
    assert {row["replacement_reference_binding_kcal_mol_must_remain_blank"] for row in payload["rows"]} == {"yes"}


def test_build_payload_blocks_rows_without_identity_support() -> None:
    provenance = _provenance_payload()
    provenance["rows"][2]["pubchem_cid"] = ""
    provenance["rows"][2]["pubchem_canonical_smiles"] = ""

    payload = mod.build_payload(_capture_payload(), provenance, as_of_date="2026-05-13")

    summary = payload["summary"]
    row = next(row for row in payload["rows"] if row["packet_step"] == "core_binder_03")
    assert summary["functional_kcal_surrogate_ready_count"] == 2
    assert summary["functional_kcal_surrogate_closure_allowed"] is False
    assert row["row_ready_for_apply"] == "no"


def test_cli_writes_packet(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    provenance = tmp_path / "provenance.json"
    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"
    capture.write_text(json.dumps(_capture_payload()), encoding="utf-8")
    provenance.write_text(json.dumps(_provenance_payload()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_functional_kcal_surrogate_packet.py",
            "--capture-sheet-json",
            str(capture),
            "--provenance-json",
            str(provenance),
            "--as-of-date",
            "2026-05-13",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["packet_artifact"] == "runs/aqp1_functional_kcal_surrogate_packet_current.md"
    assert out_csv.exists()
    assert out_md.exists()
