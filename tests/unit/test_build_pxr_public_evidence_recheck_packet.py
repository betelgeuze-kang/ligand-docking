from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_pxr_public_evidence_recheck_packet as mod


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_pxr_public_evidence_recheck_blocks_functional_proxy_and_no_public_rows(tmp_path: Path) -> None:
    exact_review_packet = {
        "rows": [
            {
                "review_row_id": "pxr_review_a",
                "candidate_name": "acetaminophen",
                "packet_step": "core_eval_non_binder_01",
            },
            {
                "review_row_id": "pxr_review_b",
                "candidate_name": "bexarotene",
                "packet_step": "ood_fit_binder_01",
            },
        ]
    }
    _write(
        tmp_path / "chembl_activity_acetaminophen_CHEMBL112_CHEMBL3401.json",
        {
            "activities": [
                {
                    "activity_id": 1,
                    "assay_type": "F",
                    "standard_type": "AC50",
                    "standard_relation": "=",
                    "standard_value": "23999.9",
                    "standard_units": "nM",
                    "assay_chembl_id": "CHEMBL5291845",
                    "document_chembl_id": "CHEMBL5291721",
                }
            ]
        },
    )
    _write(
        tmp_path / "bindingdb_target_acetaminophen.json",
        {"getLindsByUniprotResponse": {"bdb.hit": "2", "bdb.affinities": [{"UniProt": "P12345"}]}},
    )
    _write(tmp_path / "chembl_activity_bexarotene_CHEMBL1023_CHEMBL3401.json", {"activities": []})
    _write(
        tmp_path / "bindingdb_target_bexarotene.json",
        {"getLindsByUniprotResponse": {"bdb.hit": "1", "bdb.affinities": [{"UniProt": "P19793"}]}},
    )

    payload = mod.build_payload(exact_review_packet=exact_review_packet, source_dir=tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "blocked_pxr_public_evidence_recheck_no_direct_candidates"
    assert summary["public_evidence_recheck_ready"] is True
    assert summary["candidate_count"] == 2
    assert summary["chembl_direct_binding_total_record_count"] == 0
    assert summary["chembl_functional_activity_total_record_count"] == 1
    assert summary["bindingdb_pxr_like_total_record_count"] == 0
    assert summary["public_direct_or_claim_safe_binding_kcal_ready_count"] == 0
    assert summary["functional_activity_proxy_only_count"] == 1
    assert summary["no_public_target_pair_quantitative_binding_evidence_count"] == 1
    assert summary["all_candidates_remain_blocked"] is True
    rows = {row["candidate_name"]: row for row in payload["rows"]}
    assert rows["acetaminophen"]["public_recheck_blocker"] == "functional_activity_proxy_only"
    assert rows["acetaminophen"]["public_direct_or_claim_safe_binding_kcal_ready"] is False
    assert rows["bexarotene"]["public_recheck_blocker"] == (
        "no_public_target_pair_quantitative_binding_evidence"
    )


def test_pxr_public_evidence_recheck_marks_direct_binding_candidate_for_operator_verify(tmp_path: Path) -> None:
    exact_review_packet = {
        "rows": [
            {
                "review_row_id": "pxr_review_a",
                "candidate_name": "acetaminophen",
                "packet_step": "core_eval_non_binder_01",
            }
        ]
    }
    _write(
        tmp_path / "chembl_activity_acetaminophen_CHEMBL112_CHEMBL3401.json",
        {
            "activities": [
                {
                    "activity_id": 1,
                    "assay_type": "B",
                    "standard_type": "Ki",
                    "standard_relation": "=",
                    "standard_value": "100",
                    "standard_units": "nM",
                }
            ]
        },
    )
    _write(
        tmp_path / "bindingdb_target_acetaminophen.json",
        {"getLindsByUniprotResponse": {"bdb.hit": "0", "bdb.affinities": []}},
    )

    payload = mod.build_payload(exact_review_packet=exact_review_packet, source_dir=tmp_path)

    assert payload["summary"]["status"] == "pxr_public_evidence_recheck_has_direct_candidates"
    assert payload["summary"]["public_direct_or_claim_safe_binding_kcal_ready_count"] == 1
    assert payload["rows"][0]["public_recheck_decision"] == "operator_verify_direct_binding_before_fill"
    assert payload["rows"][0]["scope_promotion_allowed"] is False
