import json
from pathlib import Path

from tools import build_casp17_strict_blind_internal_like_source_review as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "HEADER    FIXTURE",
                "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 10.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_internal_like_source_review_separates_pre_native_post_native_and_unmapped(tmp_path: Path) -> None:
    internal = tmp_path / "data" / "internal_structures"
    refined = tmp_path / "data" / "internal_structures_refined"
    _write_pdb(internal / "nightly" / "2026-05-01-run" / "internal_post_alpha_sample000_step00020.pdb")
    _write_pdb(refined / "nightly" / "2026-06-01-run" / "visual_post_internal_post_beta_sample000_step00020.pdb")
    _write_pdb(internal / "nightly" / "undated" / "internal_post_gamma_sample000_step00020.pdb")
    _write_pdb(internal / "nightly" / "2026-05-01-run" / "internal_post_delta_sample000_step00020.pdb")
    _write_json(
        tmp_path / "source_requests.json",
        {
            "summary": {"source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement"},
            "rows": [
                {
                    "candidate_scope": "monomer",
                    "candidate_target_id": "HIST_ALPHA",
                    "request_id": "source_request_001",
                    "native_release_date": "2026-05-20",
                    "current_prediction_pdb": "data/internal_structures_refined/alpha.pdb",
                    "current_native_pdb": "native_alpha.pdb",
                    "native_authority_ref": "fixture:alpha",
                },
                {
                    "candidate_scope": "monomer",
                    "candidate_target_id": "HIST_BETA",
                    "request_id": "source_request_002",
                    "native_release_date": "2026-05-01",
                    "current_prediction_pdb": "data/internal_structures_refined/beta.pdb",
                    "current_native_pdb": "native_beta.pdb",
                    "native_authority_ref": "fixture:beta",
                },
                {
                    "candidate_scope": "monomer",
                    "candidate_target_id": "HIST_GAMMA",
                    "request_id": "source_request_003",
                    "native_release_date": "2026-05-01",
                    "current_prediction_pdb": "data/internal_structures_refined/gamma.pdb",
                    "current_native_pdb": "native_gamma.pdb",
                    "native_authority_ref": "fixture:gamma",
                },
            ],
        },
    )
    _write_json(tmp_path / "triage.json", {"summary": {"internal_like_review_count": 4}})
    args = mod.parse_args(
        [
            "--scan-roots",
            f"{internal},{refined}",
            "--source-request-packet-json",
            str(tmp_path / "source_requests.json"),
            "--unknown-triage-json",
            str(tmp_path / "triage.json"),
            "--out-json",
            str(tmp_path / "review.json"),
            "--out-csv",
            str(tmp_path / "review.csv"),
            "--target-csv",
            str(tmp_path / "targets.csv"),
            "--out-md",
            str(tmp_path / "review.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)
    by_label = {row["target_label"]: row for row in payload["rows"]}

    assert payload["summary"]["internal_like_source_review_status"] == (
        "strict_blind_internal_like_source_review_pre_native_candidates_need_no_leak_review"
    )
    assert payload["summary"]["internal_like_candidate_count"] == 4
    assert payload["summary"]["triage_count_match"] == "True"
    assert payload["summary"]["mapped_candidate_count"] == 3
    assert payload["summary"]["pre_native_candidate_count"] == 1
    assert payload["summary"]["post_native_blocked_count"] == 1
    assert payload["summary"]["prediction_date_missing_count"] == 1
    assert payload["summary"]["unmapped_candidate_count"] == 1
    assert by_label["alpha"]["review_status"] == "pre_native_candidate_operator_review_required"
    assert by_label["alpha"]["prediction_before_native"] == "true"
    assert by_label["beta"]["review_status"] == "blocked_post_native_internal_candidate"
    assert by_label["gamma"]["review_status"] == "blocked_chronology_date_missing"
    assert by_label["delta"]["review_status"] == "blocked_source_request_target_mapping_missing"
    assert "pre-native | post-native" in Path(args.out_md).read_text(encoding="utf-8")
