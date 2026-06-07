from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_transporter_local_crosscheck_triage_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _acquisition() -> dict[str, object]:
    return {
        "summary": {"unresolved_slot_count": 4},
        "rows": [
            {
                "target_id": "AQP1",
                "packet_step": "core_binder_01",
                "replacement_ligand_id": "AqB013",
                "current_ligand_id": "aqp1_placeholder_binder_01",
                "request_mode": "exact_target_pair_quantitative_binder_kcal_required",
                "required_missing_fields": "replacement_reference_binding_kcal_mol",
                "source_signal": "PMID 1",
            },
            {
                "target_id": "GLUT1_4PYP",
                "packet_step": "core_binder_02",
                "replacement_ligand_id": "",
                "current_ligand_id": "glut1_placeholder_binder_02",
                "request_mode": "direct_binding_kcal_or_keep_functional_review_only_required",
                "required_missing_fields": "replacement_reference_binding_kcal_mol",
                "source_signal": "PMID 2",
            },
            {
                "target_id": "GLUT1_4PYP",
                "packet_step": "core_non_binder_01",
                "replacement_ligand_id": "",
                "current_ligand_id": "glut1_placeholder_nonbinder_01",
                "request_mode": "exact_target_pair_quantitative_negative_evidence_required",
                "required_missing_fields": "replacement_ligand_id",
                "source_signal": "",
            },
        ],
    }


def _priority() -> dict[str, object]:
    return {
        "summary": {"queue_item_count": 3},
        "rows": [
            {
                "domain": "transporter",
                "priority": 1,
                "item_id": "AQP1.core_binder_01",
                "candidate_or_check": "AqB013",
                "local_crosscheck_path_count": 1,
            },
            {
                "domain": "transporter",
                "priority": 2,
                "item_id": "GLUT1_4PYP.core_binder_02",
                "candidate_or_check": "glut1_placeholder_binder_02",
                "local_crosscheck_path_count": 1,
            },
            {
                "domain": "transporter",
                "priority": 3,
                "item_id": "GLUT1_4PYP.core_non_binder_01",
                "candidate_or_check": "glut1_placeholder_nonbinder_01",
                "local_crosscheck_path_count": 1,
            },
        ],
    }


def test_transporter_local_crosscheck_triage_classifies_slot_level_blockers(tmp_path: Path) -> None:
    crosscheck = tmp_path / "crosscheck"
    crosscheck.mkdir()
    (crosscheck / "chembl_activity_aqp1_target_all_limit50.json").write_text(
        json.dumps(
            {
                "activities": [
                    {
                        "standard_type": "IC50",
                        "standard_value": "20000",
                        "standard_units": "nM",
                        "target_pref_name": "Aquaporin-1",
                        "target_organism": "Homo sapiens",
                        "molecule_chembl_id": "CHEMBL1",
                        "canonical_smiles": "CC",
                        "document_chembl_id": "CHEMBL_DOC_A",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (crosscheck / "chembl_activity_glut1_target_all_limit50.json").write_text(
        json.dumps(
            {
                "activities": [
                    {
                        "standard_type": "Kd",
                        "standard_value": "1000",
                        "standard_units": "nM",
                        "target_pref_name": "Solute carrier family 2, facilitated glucose transporter member 1",
                        "target_organism": "Homo sapiens",
                        "molecule_chembl_id": "CHEMBL2",
                        "canonical_smiles": "CCC",
                        "document_chembl_id": "CHEMBL_DOC_G",
                    },
                    {
                        "activity_comment": "Not Active",
                        "standard_type": "Inhibition",
                        "target_pref_name": "Solute carrier family 2, facilitated glucose transporter member 1",
                        "target_organism": "Homo sapiens",
                        "molecule_chembl_id": "CHEMBL3",
                        "canonical_smiles": "CCCC",
                        "document_chembl_id": "CHEMBL_DOC_G2",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(acquisition_payload=_acquisition(), priority_payload=_priority(), crosscheck_dir=crosscheck)

    rows = {row["item_id"]: row for row in payload["rows"]}
    summary = payload["summary"]
    assert summary["triage_row_count"] == 3
    assert summary["operator_review_evidence_matrix_ready"] is True
    assert summary["claim_safe_local_evidence_ready_count"] == 0
    assert summary["claim_safe_local_evidence_blocked_count"] == 3
    assert summary["direct_binding_claim_blocked_count"] == 2
    assert summary["negative_value_claim_blocked_count"] == 0
    assert summary["top_claim_safe_blocker"] == "functional_assay_quantitative_but_not_direct_binding_claim_safe"
    assert summary["candidate_assignment_required_count"] == 1
    assert summary["functional_quantitative_only_direct_gap_open_count"] == 1
    assert summary["review_only_direct_binding_gap_count"] == 1
    assert summary["authoritative_apply_allowed"] is False
    assert rows["AQP1.core_binder_01"]["slot_triage_bucket"] == "functional_quantitative_only_direct_gap_open"
    assert rows["AQP1.core_binder_01"]["claim_safe_local_evidence_ready"] is False
    assert rows["AQP1.core_binder_01"]["claim_safe_blocker"] == (
        "functional_assay_quantitative_but_not_direct_binding_claim_safe"
    )
    assert rows["AQP1.core_binder_01"]["operator_next_verdict"] == (
        "keep_functional_surrogate_review_only_until_direct_binding_source"
    )
    assert rows["AQP1.core_binder_01"]["best_evidence_activity_type"] == "IC50"
    assert rows["GLUT1_4PYP.core_binder_02"]["slot_triage_bucket"] == "keep_review_only_direct_binding_gap"
    assert rows["GLUT1_4PYP.core_binder_02"]["claim_safe_blocker"] == (
        "review_only_guardrail_requires_explicit_direct_binding_source"
    )
    assert rows["GLUT1_4PYP.core_non_binder_01"]["slot_triage_bucket"] == "candidate_assignment_required_from_local_pool"
    assert rows["GLUT1_4PYP.core_non_binder_01"]["claim_safe_blocker"] == (
        "local_pool_exists_but_slot_ligand_source_smiles_scaffold_not_assigned"
    )
    assert rows["GLUT1_4PYP.core_non_binder_01"]["not_active_nonquantitative_record_count"] == 1


def test_transporter_local_crosscheck_triage_cli_writes_outputs(tmp_path: Path) -> None:
    acquisition = tmp_path / "acquisition.json"
    priority = tmp_path / "priority.json"
    crosscheck = tmp_path / "crosscheck"
    out_json = tmp_path / "triage.json"
    out_csv = tmp_path / "triage.csv"
    out_md = tmp_path / "triage.md"
    crosscheck.mkdir()
    (crosscheck / "bindingdb_glut1_p11166.json").write_text(
        json.dumps(
            {
                "getLindsByUniprotsResponse": {
                    "affinities": [
                        {
                            "query": "Solute carrier family 2, facilitated glucose transporter member 1",
                            "monomerid": "M1",
                            "smile": "CC",
                            "affinity_type": "Kd",
                            "affinity": "100",
                            "pmid": "123",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    acquisition.write_text(json.dumps(_acquisition()), encoding="utf-8")
    priority.write_text(json.dumps(_priority()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_local_crosscheck_triage_packet.py",
            "--acquisition-json",
            str(acquisition),
            "--priority-json",
            str(priority),
            "--crosscheck-dir",
            str(crosscheck),
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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["triage_packet_ready"] is True
    assert "slot_triage_bucket" in out_csv.read_text(encoding="utf-8")
    assert "Transporter Local Crosscheck Triage Packet" in out_md.read_text(encoding="utf-8")
