import hashlib
import json
from pathlib import Path

from tools import build_casp17_current_prospective_strict_blind_escrow as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_current_prospective_strict_blind_escrow_preserves_verified_candidates(tmp_path):
    ready_model = tmp_path / "H2319TS.pdb"
    expired_model = tmp_path / "H1335TS.pdb"
    mismatch_model = tmp_path / "R2350TS.pdb"
    ready_model.write_text("ATOM      1  CA  GLY A   1       0.000   0.000   0.000\n", encoding="utf-8")
    expired_model.write_text("ATOM      1  CA  ALA A   1       1.000   0.000   0.000\n", encoding="utf-8")
    mismatch_model.write_text("ATOM      1  CA  SER A   1       2.000   0.000   0.000\n", encoding="utf-8")

    preflight_json = tmp_path / "preflight.json"
    upload_queue_json = tmp_path / "queue.json"
    review_json = tmp_path / "review.json"
    out_json = tmp_path / "escrow.json"
    out_csv = tmp_path / "escrow.csv"
    out_md = tmp_path / "ESCROW.md"
    escrow_dir = tmp_path / "escrow_targets"

    _write_json(
        preflight_json,
        {
            "summary": {"package_preflight_status": "ready"},
            "rows": [
                {
                    "target_id": "H2319",
                    "protein_name": "astrovirus antibody complex",
                    "candidate_pdb": str(ready_model),
                    "candidate_sha256": _sha256(ready_model),
                    "package_preflight_status": "ready",
                },
                {
                    "target_id": "H1335",
                    "protein_name": "HCMV Fab complex",
                    "candidate_pdb": str(expired_model),
                    "candidate_sha256": _sha256(expired_model),
                    "package_preflight_status": "ready",
                },
                {
                    "target_id": "R2350",
                    "protein_name": "RNA hybrid",
                    "candidate_pdb": str(mismatch_model),
                    "candidate_sha256": "badsha",
                    "package_preflight_status": "ready",
                },
            ],
        },
    )
    _write_json(
        upload_queue_json,
        {
            "summary": {"upload_queue_status": "official_verified_current_upload_queue_partial"},
            "rows": [
                {
                    "target_id": "H2319",
                    "official_target_id": "H2319",
                    "upload_queue_status": "upload_ready_expiring_today",
                    "queue_rank": 1,
                    "official_human_expiration": "2026-06-02",
                },
                {
                    "target_id": "H1335",
                    "official_target_id": "H1335",
                    "upload_queue_status": "upload_blocked_deadline_expired",
                    "queue_rank": 0,
                    "blockers": "human_submission_deadline_expired",
                },
                {
                    "target_id": "R2350",
                    "official_target_id": "R2350",
                    "upload_queue_status": "upload_ready_future",
                    "queue_rank": 2,
                },
            ],
        },
    )
    _write_json(
        review_json,
        {
            "summary": {"review_packet_status": "current_upload_review_packet_ready"},
            "rows": [
                {
                    "target_id": "H2319",
                    "urgency": "today",
                    "review_md": "casp17/current_upload_review_packet/H2319/UPLOAD_REVIEW.md",
                    "first_viewer_html_path": "casp17/targets_current/H2319/objects/chain_A/viewer.html",
                }
            ],
        },
    )

    args = mod.parse_args(
        [
            "--package-preflight-json",
            str(preflight_json),
            "--upload-queue-json",
            str(upload_queue_json),
            "--upload-review-packet-json",
            str(review_json),
            "--escrow-dir",
            str(escrow_dir),
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
    rows = {row["target_id"]: row for row in payload["rows"]}
    assert summary["prospective_escrow_status"] == "current_prospective_strict_blind_escrow_partial"
    assert summary["target_count"] == 3
    assert summary["escrow_ready_count"] == 2
    assert summary["escrow_blocked_count"] == 1
    assert summary["upload_ready_count"] == 2
    assert summary["upload_blocked_count"] == 1
    assert summary["sha256_match_count"] == 2
    assert summary["review_link_count"] == 1
    assert summary["native_pending_count"] == 3
    assert summary["external_timestamp_required_count"] == 3
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert summary["first_upload_ready_target_id"] == "H2319"
    assert summary["first_upload_blocked_target_id"] == "H1335"

    assert rows["H1335"]["escrow_status"] == "prospective_escrow_ready_native_pending"
    assert "upload_queue_blocked:human_submission_deadline_expired" in rows["H1335"]["blockers"]
    assert "upload_review_packet_missing" in rows["H1335"]["blockers"]
    assert rows["R2350"]["escrow_status"] == "prospective_escrow_blocked"
    assert "candidate_sha256_mismatch" in rows["R2350"]["blockers"]
    assert rows["H2319"]["competitive_proof_eligible"] == "false"

    assert out_json.exists()
    assert out_csv.exists()
    assert out_md.exists()
    assert (escrow_dir / "h2319" / "ESCROW.md").exists()
    serialized = out_json.read_text(encoding="utf-8") + out_md.read_text(encoding="utf-8")
    assert "AUTHOR " not in serialized
