from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_negative_evidence_gap_matrix as mod


ROOT = Path(__file__).resolve().parents[2]


def _external_crosscheck() -> dict[str, object]:
    return {
        "summary": {
            "aqp1_uniprot_accession": "P29972",
            "aqp1_chembl_target_id": "CHEMBL4523210",
            "aqp1_bindingdb_affinity_count": 0,
        },
        "rows": [
            {
                "target_id": "AQP1",
                "target_accession": "P29972",
                "target_chembl_id": "CHEMBL4523210",
                "candidate": "sodium nitroprusside",
                "evidence_role": "negative_candidate_probe",
            }
        ],
    }


def _direct_audit() -> dict[str, object]:
    return {
        "summary": {
            "primary_candidate": "sodium nitroprusside",
            "target_chembl_id": "CHEMBL4523210",
            "pubmed_exact_ligand_target_hit_count": 8,
            "chembl_exact_target_pair_activity_count": 0,
            "direct_negative_quantitative_row_found_count": 0,
        }
    }


def _exact_source() -> dict[str, object]:
    return {
        "summary": {
            "source_endpoint": "hemolysis_at_200_mpa",
            "row_count": 4,
            "direct_negative_quantitative_row_found_count": 0,
            "promotion_gate_failed_reason": "not_a_direct_transporter_specific_quantitative_negative_binding_or_flux_row",
        },
        "rows": [
            {
                "candidate_name": "sodium nitroprusside",
                "hemolysis_outcome": "almost_unaffected_at_200_mpa",
            }
        ],
    }


def _harvest() -> dict[str, object]:
    return {
        "summary": {
            "aqp1_candidate_review_row_count": 2,
            "aqp1_quantitative_lower_bound_candidate_count": 0,
        }
    }


def _negative_queue() -> dict[str, object]:
    return {"summary": {"aqp1_negative_slot_count": 3}}


def _primary_functional_evidence() -> dict[str, object]:
    return {
        "summary": {
            "packet_artifact": "runs/aqp1_negative_primary_functional_evidence_current.md",
            "endpoint": "pressure_induced_hemolysis_percent_at_200_mpa",
            "direct_negative_quantitative_row_found_count": 3,
            "authoritative_negative_apply_allowed_count": 3,
        }
    }


def test_build_aqp1_negative_evidence_gap_matrix_summarizes_blocked_routes() -> None:
    payload = mod.build_payload(_external_crosscheck(), _direct_audit(), _exact_source(), _harvest(), _negative_queue())

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["gap_matrix_ready"] is True
    assert summary["target_id"] == "AQP1"
    assert summary["target_uniprot_accession"] == "P29972"
    assert summary["target_chembl_id"] == "CHEMBL4523210"
    assert summary["negative_slot_count"] == 3
    assert summary["evidence_route_count"] == 5
    assert summary["blocked_route_count"] == 5
    assert summary["review_context_route_count"] == 3
    assert summary["direct_negative_quantitative_row_found_count"] == 0
    assert summary["authoritative_negative_apply_allowed_count"] == 0
    assert summary["negative_slot_cover_ready_count"] == 0
    assert summary["negative_slot_cover_missing_count"] == 3
    assert summary["claim_promotion_allowed"] is False
    assert summary["gap_status"] == "aqp1_direct_negative_quantitative_evidence_absent"
    assert rows[0]["evidence_route"] == "chembl_exact_target_pair_primary_probe"
    assert rows[0]["route_status"] == "exhausted_no_structured_exact_pair_row"
    assert rows[4]["evidence_route"] == "chembl_target_level_candidate_harvest"
    assert all(row["authoritative_negative_apply_allowed"] is False for row in rows)


def test_build_aqp1_negative_evidence_gap_matrix_cli(tmp_path: Path) -> None:
    external_json = tmp_path / "external.json"
    direct_json = tmp_path / "direct.json"
    exact_json = tmp_path / "exact.json"
    harvest_json = tmp_path / "harvest.json"
    queue_json = tmp_path / "queue.json"
    out_json = tmp_path / "gap_matrix.json"
    out_csv = tmp_path / "gap_matrix.csv"
    out_md = tmp_path / "gap_matrix.md"
    external_json.write_text(json.dumps(_external_crosscheck()), encoding="utf-8")
    direct_json.write_text(json.dumps(_direct_audit()), encoding="utf-8")
    exact_json.write_text(json.dumps(_exact_source()), encoding="utf-8")
    harvest_json.write_text(json.dumps(_harvest()), encoding="utf-8")
    queue_json.write_text(json.dumps(_negative_queue()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_negative_evidence_gap_matrix.py",
            "--external-crosscheck-json",
            str(external_json),
            "--negative-direct-audit-json",
            str(direct_json),
            "--negative-exact-source-json",
            str(exact_json),
            "--negative-candidate-harvest-json",
            str(harvest_json),
            "--negative-queue-json",
            str(queue_json),
            "--primary-functional-evidence-json",
            str(tmp_path / "missing_primary_functional.json"),
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
    assert payload["summary"]["gap_matrix_ready"] is True
    assert payload["summary"]["negative_slot_cover_missing_count"] == 3
    assert out_csv.exists()
    assert out_md.read_text(encoding="utf-8").startswith("# AQP1 Negative Evidence Gap Matrix")


def test_build_aqp1_negative_evidence_gap_matrix_accepts_primary_functional_closure() -> None:
    payload = mod.build_payload(
        _external_crosscheck(),
        _direct_audit(),
        _exact_source(),
        _harvest(),
        _negative_queue(),
        _primary_functional_evidence(),
    )

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["direct_negative_quantitative_row_found_count"] == 3
    assert summary["authoritative_negative_apply_allowed_count"] == 3
    assert summary["negative_slot_cover_ready_count"] == 3
    assert summary["negative_slot_cover_missing_count"] == 0
    assert summary["negative_evidence_closure_allowed"] is True
    assert summary["gap_status"] == "aqp1_primary_functional_negative_evidence_curated"
    assert summary["commercialization_blocker"] == ""
    assert rows[3]["evidence_route"] == "pressure_hemolysis_exact_source_anchor"
    assert rows[3]["route_status"] == "primary_functional_no_effect_rows_curated"
