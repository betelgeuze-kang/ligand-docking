import json
from pathlib import Path

from tools import build_casp17_current_upload_review_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_current_upload_review_packet_links_ready_queue_to_3d_objects(tmp_path: Path) -> None:
    upload_queue_json = tmp_path / "upload_queue.json"
    package_json = tmp_path / "package.json"
    navigation_json = tmp_path / "navigation.json"
    object_review_json = tmp_path / "object_review.json"

    _write_json(
        upload_queue_json,
        {
            "summary": {
                "upload_queue_status": "official_verified_current_upload_queue_partial",
                "upload_ready_count": 1,
                "blocked_count": 1,
                "target_count": 2,
            },
            "rows": [
                {
                    "queue_rank": 1,
                    "target_id": "T9001",
                    "official_target_id": "T9001",
                    "upload_queue_status": "upload_ready_expiring_today",
                    "protein_name": "Ready protein",
                    "official_human_expiration": "2026-06-02",
                    "days_to_official_human_expiration": 0,
                    "candidate_pdb": "runs/predictions/T9001TS.pdb",
                    "candidate_sha256": "sha-t9001",
                },
                {
                    "queue_rank": 0,
                    "target_id": "T9002",
                    "official_target_id": "T9002",
                    "upload_queue_status": "blocked_official_deadline_expired",
                    "protein_name": "Blocked protein",
                    "official_human_expiration": "2026-06-01",
                    "days_to_official_human_expiration": -1,
                    "candidate_pdb": "runs/predictions/T9002TS.pdb",
                    "candidate_sha256": "sha-t9002",
                },
            ],
        },
    )
    _write_json(
        package_json,
        {
            "rows": [
                {
                    "target_id": "T9001",
                    "package_preflight_status": "ready",
                    "candidate_pdb": "runs/predictions/T9001TS.pdb",
                    "candidate_sha256": "sha-t9001",
                }
            ]
        },
    )
    _write_json(
        navigation_json,
        {
            "rows": [
                {
                    "target_id": "T9001",
                    "catalog_status": "pass",
                    "object_count": 2,
                    "chain_ids": "A,B",
                    "library_protein_folder": "casp17/protein_object_library_current/T9001_Ready",
                    "protein_readme": "casp17/protein_object_library_current/T9001_Ready/README.md",
                    "protein_manifest": "casp17/protein_object_library_current/T9001_Ready/protein_manifest.json",
                    "first_viewer_html_path": "casp17/targets_current/T9001/objects/chain_A/viewer.html",
                }
            ]
        },
    )
    _write_json(
        object_review_json,
        {
            "rows": [
                {"target_id": "T9001", "object_id": "chain_A"},
                {"target_id": "T9001", "object_id": "chain_B"},
            ]
        },
    )

    args = mod.parse_args(
        [
            "--upload-queue-json",
            str(upload_queue_json),
            "--package-preflight-json",
            str(package_json),
            "--protein-object-navigation-json",
            str(navigation_json),
            "--target-object-review-json",
            str(object_review_json),
            "--review-dir",
            str(tmp_path / "review_packet"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_packet(args, payload)

    assert payload["summary"]["review_packet_status"] == "current_upload_review_packet_ready"
    assert payload["summary"]["review_target_count"] == 1
    assert payload["summary"]["review_ready_count"] == 1
    assert payload["summary"]["review_blocked_count"] == 0
    assert payload["summary"]["urgency_today_count"] == 1
    assert payload["summary"]["candidate_present_count"] == 1
    assert payload["summary"]["object_catalog_pass_count"] == 1
    assert payload["summary"]["viewer_link_count"] == 1
    row = payload["rows"][0]
    assert row["target_id"] == "T9001"
    assert row["review_status"] == "ready"
    assert row["object_count"] == 2
    assert row["chain_ids"] == "A,B"
    assert row["first_viewer_html_path"].endswith("viewer.html")
    review_md = Path(row["review_md"])
    assert review_md.exists()
    assert "candidate_sha256: `sha-t9001`" in review_md.read_text(encoding="utf-8")
    assert "reviews ready/blocked/total: `1/0/1`" in Path(args.out_md).read_text(encoding="utf-8")
