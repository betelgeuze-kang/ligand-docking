from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_transporter_slot_assignment_candidate_workbook as mod


ROOT = Path(__file__).resolve().parents[2]


def _triage() -> dict[str, object]:
    return {
        "summary": {"triage_row_count": 3},
        "rows": [
            {
                "priority": "1",
                "target_id": "AQP1",
                "item_id": "AQP1.core_binder_01",
                "packet_step": "core_binder_01",
                "candidate_or_check": "AqB013",
                "slot_triage_bucket": "functional_quantitative_only_direct_gap_open",
            },
            {
                "priority": "2",
                "target_id": "GLUT1_4PYP",
                "item_id": "GLUT1_4PYP.core_binder_03",
                "packet_step": "core_binder_03",
                "candidate_or_check": "glut1_placeholder_binder_03",
                "slot_triage_bucket": "candidate_assignment_required_from_local_pool",
            },
            {
                "priority": "3",
                "target_id": "GLUT1_4PYP",
                "item_id": "GLUT1_4PYP.core_non_binder_01",
                "packet_step": "core_non_binder_01",
                "candidate_or_check": "glut1_placeholder_nonbinder_01",
                "slot_triage_bucket": "candidate_assignment_required_from_local_pool",
            },
        ],
    }


def test_transporter_slot_assignment_candidate_workbook_builds_manual_candidates(tmp_path: Path) -> None:
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
                        "molecule_chembl_id": "CHEMBL_A",
                        "canonical_smiles": "CC",
                        "document_chembl_id": "DOC_A",
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
                        "target_pref_name": "GLUT1",
                        "molecule_chembl_id": "CHEMBL_G",
                        "canonical_smiles": "CCC",
                        "document_chembl_id": "DOC_G",
                    },
                    {
                        "activity_comment": "Not Active",
                        "standard_type": "Inhibition",
                        "target_pref_name": "GLUT1",
                        "molecule_chembl_id": "CHEMBL_NEG",
                        "canonical_smiles": "CCCC",
                        "document_chembl_id": "DOC_NEG",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(triage_payload=_triage(), crosscheck_dir=crosscheck)

    rows = {row["item_id"]: row for row in payload["rows"]}
    summary = payload["summary"]
    assert summary["candidate_row_count"] == 3
    assert summary["candidate_ready_for_manual_review_count"] == 3
    assert summary["candidate_ready_for_apply_count"] == 0
    assert summary["blocked_review_only_count"] == 1
    assert summary["scaffold_suggestion_count"] == 3
    assert summary["negative_value_review_required_count"] == 1
    assert rows["AQP1.core_binder_01"]["candidate_mode"] == "functional_quantitative_surrogate_review_only"
    assert rows["AQP1.core_binder_01"]["candidate_ready_for_apply"] is False
    assert rows["AQP1.core_binder_01"]["replacement_scaffold"] == "heuristic::acyclic_2c"
    assert rows["GLUT1_4PYP.core_binder_03"]["replacement_reference_binding_kcal_mol"] == "-8.1855"
    assert rows["GLUT1_4PYP.core_binder_03"]["replacement_scaffold"] == "heuristic::acyclic_3c"
    assert rows["GLUT1_4PYP.core_binder_03"]["required_missing_fields"] == ""
    assert rows["GLUT1_4PYP.core_binder_03"]["candidate_ready_for_apply"] is False
    assert rows["GLUT1_4PYP.core_non_binder_01"]["candidate_mode"].startswith("inactive_nonquantitative")
    assert rows["GLUT1_4PYP.core_non_binder_01"]["replacement_scaffold"] == "heuristic::acyclic_4c"
    assert "replacement_reference_binding_kcal_mol" in rows["GLUT1_4PYP.core_non_binder_01"]["required_missing_fields"]
    assert "manual_ligand_identity" in rows["GLUT1_4PYP.core_non_binder_01"]["manual_review_blockers"]


def test_transporter_slot_assignment_candidate_workbook_cli_writes_outputs(tmp_path: Path) -> None:
    triage = tmp_path / "triage.json"
    crosscheck = tmp_path / "crosscheck"
    out_json = tmp_path / "workbook.json"
    out_csv = tmp_path / "workbook.csv"
    out_md = tmp_path / "workbook.md"
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
    triage.write_text(json.dumps(_triage()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_slot_assignment_candidate_workbook.py",
            "--triage-json",
            str(triage),
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

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["candidate_workbook_ready"] is True
    assert "candidate_mode" in out_csv.read_text(encoding="utf-8")
    assert "Transporter Slot Assignment Candidate Workbook" in out_md.read_text(encoding="utf-8")
