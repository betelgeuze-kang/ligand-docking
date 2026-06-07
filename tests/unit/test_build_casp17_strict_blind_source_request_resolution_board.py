import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_source_request_resolution_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_source_request_resolution_board_propagates_internal_like_chronology(tmp_path: Path) -> None:
    source_request_json = tmp_path / "source_requests.json"
    review_json = tmp_path / "internal_like_review.json"
    _write_json(
        source_request_json,
        {
            "summary": {"source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement"},
            "rows": [
                {
                    "request_id": "source_request_001",
                    "candidate_target_id": "HIST_ALPHA",
                    "candidate_scope": "monomer",
                    "request_kind": "pre_native_prediction_source_required",
                    "request_status": "awaiting_pre_native_source_or_replacement",
                    "first_blocker": "prediction_not_before_native",
                    "native_release_date": "2026-05-01",
                    "current_prediction_pdb": "alpha.pdb",
                },
                {
                    "request_id": "source_request_002",
                    "candidate_target_id": "HIST_BETA",
                    "candidate_scope": "monomer",
                    "request_kind": "pre_native_prediction_source_required",
                    "request_status": "awaiting_pre_native_source_or_replacement",
                    "first_blocker": "prediction_not_before_native",
                    "native_release_date": "2026-05-20",
                    "current_prediction_pdb": "beta.pdb",
                },
                {
                    "request_id": "source_request_003",
                    "candidate_target_id": "HIST_COMPLEX_GAMMA",
                    "candidate_scope": "complex",
                    "request_kind": "candidate_replacement_required",
                    "request_status": "out_of_scope_replace_candidate",
                    "first_blocker": "native_authority_missing",
                    "native_release_date": "",
                    "current_prediction_pdb": "complex.pdb",
                },
            ],
        },
    )
    _write_json(
        review_json,
        {
            "summary": {
                "internal_like_source_review_status": "strict_blind_internal_like_source_review_operator_review_required",
                "internal_like_candidate_count": 3,
                "post_native_blocked_count": 2,
                "pre_native_candidate_count": 1,
            },
            "target_rows": [
                {
                    "mapped_target_id": "HIST_ALPHA",
                    "target_review_status": "target_all_internal_like_candidates_post_native",
                    "candidate_count": 2,
                    "pre_native_count": 0,
                    "post_native_count": 2,
                },
                {
                    "mapped_target_id": "HIST_BETA",
                    "target_review_status": "target_has_pre_native_candidates_requiring_no_leak_review",
                    "candidate_count": 1,
                    "pre_native_count": 1,
                    "post_native_count": 0,
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--source-request-packet-json",
            str(source_request_json),
            "--internal-like-source-review-json",
            str(review_json),
            "--out-json",
            str(tmp_path / "resolution.json"),
            "--out-csv",
            str(tmp_path / "resolution.csv"),
            "--out-md",
            str(tmp_path / "resolution.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)
    by_target = {row["candidate_target_id"]: row for row in payload["rows"]}

    assert payload["summary"]["source_request_resolution_board_status"] == (
        "source_request_resolution_operator_review_required"
    )
    assert payload["summary"]["request_count"] == 3
    assert payload["summary"]["ready_for_source_gate_count"] == 0
    assert payload["summary"]["all_post_native_monomer_request_count"] == 1
    assert payload["summary"]["pre_native_review_possible_count"] == 1
    assert payload["summary"]["candidate_replacement_required_count"] == 1
    assert by_target["HIST_ALPHA"]["resolution_status"] == "requires_new_pre_native_internal_source"
    assert by_target["HIST_BETA"]["resolution_status"] == "pre_native_candidate_requires_no_leak_review"
    assert by_target["HIST_COMPLEX_GAMMA"]["resolution_status"] == (
        "requires_authoritative_native_or_replacement_candidate"
    )
    assert "all-post-native monomer/replacement/pre-native-review/missing-review" in Path(
        args.out_md
    ).read_text(encoding="utf-8")
