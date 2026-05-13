from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_transporter_negative_candidate_curation_queue as mod


ROOT = Path(__file__).resolve().parents[2]


def _candidate(molecule: str, rank: int) -> dict[str, object]:
    return {
        "target_id": "GLUT1",
        "target_chembl_id": "CHEMBL2535",
        "molecule_chembl_id": molecule,
        "canonical_smiles": "CCO",
        "document_chembl_id": "CHEMBL1125913",
        "document_year": "1991",
        "assay_chembl_id": "CHEMBL684234",
        "assay_description": "Inhibition of [125I]7-IHPP-Fsk binding to glucose transporter of human erythrocyte membrane",
        "standard_type": "Kd",
        "standard_relation": ">",
        "standard_value": "100000.0",
        "standard_units": "nM",
        "evidence_class": "chembl_quantitative_weak_or_no_binding_lower_bound",
        "target_candidate_rank": rank,
        "global_candidate_rank": rank + 2,
    }


def _negative_queue() -> dict[str, object]:
    return {
        "summary": {"top_target_id": "AQP1"},
        "rows": [
            {"queue_rank": 1, "queue_id": "AQP1__core_non_binder_01", "target_id": "AQP1", "packet_step": "core_non_binder_01"},
            {"queue_rank": 2, "queue_id": "AQP1__core_non_binder_02", "target_id": "AQP1", "packet_step": "core_non_binder_02"},
            {"queue_rank": 3, "queue_id": "AQP1__core_non_binder_03", "target_id": "AQP1", "packet_step": "core_non_binder_03"},
            {"queue_rank": 4, "queue_id": "GLUT1__core_non_binder_01", "target_id": "GLUT1", "packet_step": "core_non_binder_01"},
            {"queue_rank": 5, "queue_id": "GLUT1__core_non_binder_02", "target_id": "GLUT1", "packet_step": "core_non_binder_02"},
            {"queue_rank": 6, "queue_id": "GLUT1__core_non_binder_03", "target_id": "GLUT1", "packet_step": "core_non_binder_03"},
        ],
    }


def test_build_transporter_negative_candidate_curation_queue_maps_top_glut1_candidates_to_slots() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "packet_artifact": "runs/transporter_negative_candidate_harvest_current.md",
                "aqp1_quantitative_lower_bound_candidate_count": 0,
            },
            "rows": [_candidate("CHEMBL322952", 1), _candidate("CHEMBL324463", 2), _candidate("CHEMBL326703", 3), _candidate("CHEMBL328561", 4)],
        },
        _negative_queue(),
    )

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["curation_queue_ready"] is True
    assert summary["target_id"] == "GLUT1"
    assert summary["available_quantitative_lower_bound_candidate_count"] == 4
    assert summary["target_negative_slot_count"] == 3
    assert summary["queue_row_count"] == 3
    assert summary["slot_cover_ready_count"] == 3
    assert summary["unused_candidate_count"] == 1
    assert summary["aqp1_first_blocker_open"] is True
    assert summary["candidate_apply_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert summary["queue_status"] == "glut1_curation_queue_ready_aqp1_first_blocker_still_open"
    assert [row["slot_queue_id"] for row in rows] == [
        "GLUT1__core_non_binder_01",
        "GLUT1__core_non_binder_02",
        "GLUT1__core_non_binder_03",
    ]
    assert [row["molecule_chembl_id"] for row in rows] == ["CHEMBL322952", "CHEMBL324463", "CHEMBL326703"]
    assert all(row["candidate_apply_allowed"] is False for row in rows)
    assert all(row["authoritative_negative_apply_allowed"] is False for row in rows)


def test_build_transporter_negative_candidate_curation_queue_cli(tmp_path: Path) -> None:
    harvest_json = tmp_path / "harvest.json"
    negative_queue_json = tmp_path / "negative_queue.json"
    out_json = tmp_path / "curation_queue.json"
    out_csv = tmp_path / "curation_queue.csv"
    out_md = tmp_path / "curation_queue.md"
    harvest_json.write_text(
        json.dumps(
            {
                "summary": {
                    "packet_artifact": "runs/transporter_negative_candidate_harvest_current.md",
                    "aqp1_quantitative_lower_bound_candidate_count": 0,
                },
                "rows": [_candidate("CHEMBL322952", 1), _candidate("CHEMBL324463", 2), _candidate("CHEMBL326703", 3)],
            }
        ),
        encoding="utf-8",
    )
    negative_queue_json.write_text(json.dumps(_negative_queue()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_transporter_negative_candidate_curation_queue.py",
            "--candidate-harvest-json",
            str(harvest_json),
            "--negative-queue-json",
            str(negative_queue_json),
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
    assert payload["summary"]["curation_queue_ready"] is True
    assert payload["summary"]["queue_row_count"] == 3
    assert out_csv.exists()
    assert out_md.read_text(encoding="utf-8").startswith("# Transporter Negative Candidate Curation Queue")
