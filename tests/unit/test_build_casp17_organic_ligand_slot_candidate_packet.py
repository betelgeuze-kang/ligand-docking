from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_organic_ligand_slot_candidate_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _candidate_files(base: Path) -> tuple[str, str]:
    base.mkdir(parents=True, exist_ok=True)
    for name in (
        "protein_ligand_complex.pdb",
        "protein_ligand_complex_minimized.pdb",
        "ligand.mol2",
        "ligand_LIG_conect.pdb",
        "ligand_template.xml",
    ):
        (base / name).write_text("MODEL\nEND\n", encoding="utf-8")
    return str(base / "protein_ligand_complex.pdb"), str(base / "protein_ligand_complex_minimized.pdb")


def test_organic_ligand_slot_candidate_packet_keeps_candidates_fail_closed(tmp_path: Path) -> None:
    chembl_native, chembl_prediction = _candidate_files(tmp_path / "chembl")
    bindingdb_native, bindingdb_prediction = _candidate_files(tmp_path / "bindingdb")
    source_json = tmp_path / "source.json"
    lane_json = tmp_path / "lane.json"
    metric_json = tmp_path / "metric.json"
    _write_json(
        source_json,
        {
            "summary": {
                "complex_source_authority_candidate_status": (
                    "complex_homolog_source_authority_candidates_ready_claim_limited"
                )
            },
            "rows": [
                {
                    "target_id": "HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005",
                    "benchmark_id": "hist_seed_01",
                    "ligand_id": "lig_chembl",
                    "ligand_source_dataset": "ChEMBL",
                    "molecule_or_monomer_id": "CHEMBL4453005",
                    "ligand_authority_ref": "chembl_molecule:CHEMBL4453005",
                    "protein_authority_ref": "rcsb:3V94;chain:B",
                    "native_authority_ref_candidate": "rcsb:3V94;chembl_molecule:CHEMBL4453005",
                    "standard_types": "Ki",
                    "best_document_year": "2020",
                    "best_assay_description": "PDEB1 assay",
                    "complex_pdb": chembl_native,
                    "minimized_complex_pdb": chembl_prediction,
                    "candidate_status": "operator_homolog_source_authority_review_ready",
                    "direct_tcruzi_pde_evidence": False,
                    "homolog_seed_only": True,
                    "blockers": "direct_tcruzi_pde_evidence_absent_homolog_seed_only",
                },
                {
                    "target_id": "HIST_COMPLEX_07_TCRUZI_PDE_BINDINGDB_PDEB1_007_BDB50397079",
                    "benchmark_id": "hist_seed_07",
                    "ligand_id": "lig_bindingdb",
                    "ligand_source_dataset": "BindingDB",
                    "molecule_or_monomer_id": "50397079",
                    "ligand_authority_ref": "bindingdb_monomer:50397079",
                    "protein_authority_ref": "rcsb:3V94;chain:B",
                    "native_authority_ref_candidate": "rcsb:3V94;bindingdb_monomer:50397079",
                    "standard_types": "",
                    "complex_pdb": bindingdb_native,
                    "minimized_complex_pdb": bindingdb_prediction,
                    "candidate_status": "operator_homolog_source_authority_review_ready",
                    "direct_tcruzi_pde_evidence": False,
                    "homolog_seed_only": True,
                    "blockers": "direct_tcruzi_pde_evidence_absent_homolog_seed_only",
                },
            ],
        },
    )
    _write_json(
        lane_json,
        {
            "summary": {"lane_decision_status": "strict_blind_replacement_required"},
            "rows": [
                {
                    "target_id": "HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005",
                    "lane_decision_status": "strict_blind_replacement_or_authority_required",
                    "strict_blind_eligible": False,
                    "competitive_proof_allowed": False,
                },
                {
                    "target_id": "HIST_COMPLEX_07_TCRUZI_PDE_BINDINGDB_PDEB1_007_BDB50397079",
                    "lane_decision_status": "strict_blind_replacement_or_authority_required",
                    "strict_blind_eligible": False,
                    "competitive_proof_allowed": False,
                },
            ],
        },
    )
    _write_json(
        metric_json,
        {
            "summary": {
                "metric_surface_contract_status": (
                    "awaiting_strict_blind_evidence_files_and_ligand_category_slots"
                ),
                "organic_ligand_slot_count": 0,
            }
        },
    )
    args = mod.parse_args(
        [
            "--complex-source-authority-json",
            str(source_json),
            "--lane-decision-packet-json",
            str(lane_json),
            "--win-tier-metric-surface-contract-json",
            str(metric_json),
            "--out-dir",
            str(tmp_path / "out"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "PACKET.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["organic_ligand_slot_candidate_status"] == (
        "organic_ligand_slot_candidates_ready_for_operator_review"
    )
    assert summary["candidate_count"] == 2
    assert summary["chembl_candidate_count"] == 1
    assert summary["bindingdb_candidate_count"] == 1
    assert summary["review_ready_candidate_count"] == 2
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["strict_blind_promotion_blocked_count"] == 2
    assert summary["local_reference_present_count"] == 2
    assert summary["prediction_present_count"] == 2
    assert summary["ligand_mol2_present_count"] == 2
    assert summary["lddt_pli_required_count"] == 2
    assert summary["bisyrmsd_required_count"] == 2
    assert summary["affinity_label_candidate_count"] == 1
    assert summary["metric_contract_ligand_slot_gap_count"] == 0

    rows = payload["rows"]
    assert rows[0]["competitive_proof_eligible"] == "False"
    assert rows[0]["review_ready"] == "True"
    assert rows[0]["strict_blind_promotion_status"] == "blocked_homolog_source_no_leak_and_chronology_required"
    assert rows[0]["metric_profile"] == "LDDT-PLI,BiSyRMSD,Kendall_tau_affinity"
    assert "strict_blind_not_eligible" in rows[0]["blockers"]
    assert rows[1]["ligand_source_dataset"] == "BindingDB"
    assert rows[1]["affinity_label_candidate"] == "False"

    assert len(_read_csv(tmp_path / "packet.csv")) == 2
    manifest = Path(rows[0]["candidate_manifest"])
    assert manifest.is_file()
    manifest_text = manifest.read_text(encoding="utf-8")
    assert "competitive_proof_eligible: `False`" in manifest_text
    assert "LDDT-PLI,BiSyRMSD,Kendall_tau_affinity" in manifest_text
    assert (tmp_path / "PACKET.md").read_text(encoding="utf-8").startswith("# CASP17 Organic")


def test_organic_ligand_slot_candidate_packet_blocks_missing_source(tmp_path: Path) -> None:
    args = mod.parse_args(
        [
            "--complex-source-authority-json",
            str(tmp_path / "missing_source.json"),
            "--out-dir",
            str(tmp_path / "out"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "PACKET.md"),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["organic_ligand_slot_candidate_status"] == (
        "blocked_complex_source_authority_candidates_missing"
    )
    assert payload["summary"]["candidate_count"] == 0
