from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_organic_ligand_slot_promotion_action_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _candidate(rank: int, target_id: str, dataset: str, affinity_ready: bool) -> dict:
    return {
        "candidate_rank": rank,
        "candidate_id": f"organic_ligand_slot_candidate_{rank:03d}",
        "target_id": target_id,
        "ligand_id": f"ligand_{rank}",
        "ligand_source_dataset": dataset,
        "ligand_authority_ref": f"{dataset.lower()}:{rank}",
        "native_authority_ref_candidate": "rcsb:3V94;homolog_seed_only",
        "standard_types": "Ki" if affinity_ready else "",
        "local_reference_pdb": f"casp17/reference/{target_id}/protein_ligand_complex.pdb",
        "prediction_pdb": f"casp17/reference/{target_id}/protein_ligand_complex_minimized.pdb",
        "ligand_mol2": f"casp17/reference/{target_id}/ligand.mol2",
        "ligand_template_xml": f"casp17/reference/{target_id}/ligand_template.xml",
        "local_reference_present": "True",
        "prediction_present": "True",
        "ligand_mol2_present": "True",
        "ligand_template_present": "True",
        "lane_decision_status": "strict_blind_replacement_or_authority_required",
        "strict_blind_promotion_status": "blocked_homolog_source_no_leak_and_chronology_required",
        "affinity_label_candidate": "True" if affinity_ready else "False",
        "metric_profile": "LDDT-PLI,BiSyRMSD,Kendall_tau_affinity",
        "candidate_manifest": f"casp17/candidates/{target_id}/CANDIDATE.md",
        "blockers": "operator_no_leak_chronology_native_authority_required",
    }


def test_organic_ligand_promotion_action_board_decomposes_strict_blind_actions(tmp_path: Path) -> None:
    candidate_packet = tmp_path / "candidate_packet.json"
    out_dir = tmp_path / "promotion_actions"
    out_json = tmp_path / "promotion.json"
    out_csv = tmp_path / "promotion.csv"
    out_md = tmp_path / "PROMOTION.md"
    _write_json(
        candidate_packet,
        {
            "summary": {
                "organic_ligand_slot_candidate_status": (
                    "organic_ligand_slot_candidates_ready_for_operator_review"
                ),
                "competitive_proof_eligible_count": 0,
                "strict_blind_promotion_blocked_count": 2,
            },
            "rows": [
                _candidate(
                    1,
                    "HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005",
                    "ChEMBL",
                    True,
                ),
                _candidate(
                    2,
                    "HIST_COMPLEX_07_TCRUZI_PDE_BINDINGDB_PDEB1_007_BDB50397079",
                    "BindingDB",
                    False,
                ),
            ],
        },
    )
    args = mod.parse_args(
        [
            "--candidate-packet-json",
            str(candidate_packet),
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["organic_ligand_slot_promotion_action_board_status"] == (
        "awaiting_organic_ligand_strict_blind_evidence"
    )
    assert summary["candidate_count"] == 2
    assert summary["action_count"] == 18
    assert summary["open_action_count"] == 16
    assert summary["reference_file_preflight_pass_count"] == 2
    assert summary["operator_evidence_required_count"] == 8
    assert summary["numeric_value_required_count"] == 1
    assert summary["affinity_source_required_count"] == 1
    assert summary["metric_input_required_count"] == 4
    assert summary["slot_mapping_required_count"] == 2
    assert summary["proof_ready_candidate_count"] == 0
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["strict_blind_promotion_blocked_count"] == 2
    assert summary["first_open_action_id"] == "organic_ligand_promotion_action_002"
    assert summary["first_open_action_type"] == "direct_native_or_source_authority"

    rows = payload["rows"]
    assert rows[0]["action_type"] == "reference_file_preflight"
    assert rows[0]["action_status"] == "reference_files_present_review_only"
    assert rows[1]["action_type"] == "direct_native_or_source_authority"
    assert rows[1]["action_status"] == "open_operator_evidence_required"
    assert rows[5]["action_type"] == "affinity_numeric_label"
    assert rows[5]["action_status"] == "open_numeric_value_required"
    assert rows[14]["action_type"] == "affinity_numeric_label"
    assert rows[14]["action_status"] == "open_affinity_source_required"

    assert len(_read_csv(out_csv)) == 18
    assert Path(rows[0]["action_md"]).is_file()
    first_candidate_actions = Path(rows[0]["action_folder"]).parent / "ACTIONS.md"
    assert first_candidate_actions.is_file()
    assert "Organic Ligand Promotion Action" in Path(rows[1]["action_md"]).read_text(encoding="utf-8")
    assert "reference-file preflight pass: `2`" in out_md.read_text(encoding="utf-8")


def test_organic_ligand_promotion_action_board_blocks_missing_candidate_packet(tmp_path: Path) -> None:
    args = mod.parse_args(
        [
            "--candidate-packet-json",
            str(tmp_path / "missing_candidate_packet.json"),
            "--out-dir",
            str(tmp_path / "out"),
            "--out-json",
            str(tmp_path / "promotion.json"),
            "--out-csv",
            str(tmp_path / "promotion.csv"),
            "--out-md",
            str(tmp_path / "PROMOTION.md"),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["organic_ligand_slot_promotion_action_board_status"] == (
        "blocked_organic_ligand_candidate_packet_missing"
    )
    assert payload["summary"]["candidate_count"] == 0
    assert payload["summary"]["action_count"] == 0
