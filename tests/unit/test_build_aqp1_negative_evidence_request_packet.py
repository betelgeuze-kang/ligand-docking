from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_aqp1_negative_evidence_request_packet as mod


ROOT = Path(__file__).resolve().parents[2]


def _gap_matrix() -> dict[str, object]:
    return {
        "summary": {
            "packet_artifact": "runs/aqp1_negative_evidence_gap_matrix_current.md",
            "target_uniprot_accession": "P29972",
            "target_chembl_id": "CHEMBL4523210",
            "negative_slot_count": 3,
            "blocked_route_count": 5,
            "review_context_route_count": 3,
            "direct_negative_quantitative_row_found_count": 0,
        }
    }


def _negative_queue() -> dict[str, object]:
    return {
        "rows": [
            {"queue_rank": 1, "queue_id": "AQP1__core_non_binder_01", "target_id": "AQP1", "packet_step": "core_non_binder_01"},
            {"queue_rank": 2, "queue_id": "AQP1__core_non_binder_02", "target_id": "AQP1", "packet_step": "core_non_binder_02"},
            {"queue_rank": 3, "queue_id": "AQP1__core_non_binder_03", "target_id": "AQP1", "packet_step": "core_non_binder_03"},
            {"queue_rank": 4, "queue_id": "GLUT1__core_non_binder_01", "target_id": "GLUT1", "packet_step": "core_non_binder_01"},
        ]
    }


def _exact_source() -> dict[str, object]:
    return {
        "summary": {
            "primary_negative_probe_candidate": "sodium nitroprusside",
            "source_pmid": "23123479",
        }
    }


def test_build_aqp1_negative_evidence_request_packet_defines_three_exact_evidence_rows() -> None:
    payload = mod.build_payload(_gap_matrix(), _negative_queue(), _exact_source())

    summary = payload["summary"]
    rows = payload["rows"]
    assert summary["evidence_request_ready"] is True
    assert summary["target_id"] == "AQP1"
    assert summary["target_uniprot_accession"] == "P29972"
    assert summary["target_chembl_id"] == "CHEMBL4523210"
    assert summary["request_row_count"] == 3
    assert summary["required_assignable_negative_row_count"] == 3
    assert summary["current_direct_negative_quantitative_row_found_count"] == 0
    assert summary["negative_slot_cover_ready_count"] == 0
    assert summary["negative_slot_cover_missing_count"] == 3
    assert summary["blocked_gap_route_count"] == 5
    assert summary["review_context_route_count"] == 3
    assert summary["public_reinterpretation_exhausted"] is True
    assert summary["internal_wetlab_or_primary_source_required"] is True
    assert summary["authoritative_negative_apply_allowed_count"] == 0
    assert summary["negative_evidence_closure_allowed"] is False
    assert summary["claim_promotion_allowed"] is False
    assert rows[0]["candidate_scope"] == "sodium nitroprusside"
    assert rows[0]["candidate_source_context"] == "PMID:23123479 review-only context"
    assert rows[1]["candidate_scope"] == "independent_exact_aqp1_nonbinder_candidate_01"
    assert all(row["authoritative_negative_apply_allowed"] is False for row in rows)
    assert all("molecule_identity" in row["minimum_required_fields"] for row in rows)


def test_build_aqp1_negative_evidence_request_packet_cli(tmp_path: Path) -> None:
    gap_json = tmp_path / "gap.json"
    queue_json = tmp_path / "queue.json"
    exact_json = tmp_path / "exact.json"
    out_json = tmp_path / "request.json"
    out_csv = tmp_path / "request.csv"
    out_md = tmp_path / "request.md"
    gap_json.write_text(json.dumps(_gap_matrix()), encoding="utf-8")
    queue_json.write_text(json.dumps(_negative_queue()), encoding="utf-8")
    exact_json.write_text(json.dumps(_exact_source()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "tools/build_aqp1_negative_evidence_request_packet.py",
            "--gap-matrix-json",
            str(gap_json),
            "--negative-queue-json",
            str(queue_json),
            "--exact-source-json",
            str(exact_json),
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
    assert payload["summary"]["evidence_request_ready"] is True
    assert payload["summary"]["request_row_count"] == 3
    assert out_csv.exists()
    assert out_md.read_text(encoding="utf-8").startswith("# AQP1 Negative Evidence Request Packet")
