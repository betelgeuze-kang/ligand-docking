import json
from pathlib import Path

from tools.casp17 import build_casp17_current_queue_rollover_hygiene_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_current_queue_rollover_hygiene_audit_reports_retained_stale_folders(tmp_path: Path) -> None:
    review_root = tmp_path / "review"
    decision_root = tmp_path / "decision"
    post_native_root = tmp_path / "post_native"
    for folder in [
        review_root / "01_h1001",
        review_root / "old_h0999",
        decision_root / "01_h1001",
        decision_root / "old_h0999",
        post_native_root / "01_h1001",
        post_native_root / "02_h1002",
        post_native_root / "old_h0999",
    ]:
        folder.mkdir(parents=True)

    review_json = tmp_path / "review.json"
    decision_json = tmp_path / "decision.json"
    post_native_json = tmp_path / "post_native.json"
    _write_json(
        review_json,
        {
            "summary": {"review_dir": str(review_root)},
            "rows": [{"target_id": "H1001", "packet_folder": str(review_root / "01_h1001")}],
        },
    )
    _write_json(
        decision_json,
        {
            "rows": [
                {
                    "target_id": "H1001",
                    "decision_packet_folder": str(decision_root / "01_h1001"),
                }
            ]
        },
    )
    _write_json(
        post_native_json,
        {
            "summary": {"scaffold_dir": str(post_native_root)},
            "target_rows": [
                {
                    "target_id": "H1001",
                    "post_native_scoring_md": str(post_native_root / "01_h1001" / "POST_NATIVE_SCORING.md"),
                },
                {
                    "target_id": "H1002",
                    "post_native_scoring_md": str(post_native_root / "02_h1002" / "POST_NATIVE_SCORING.md"),
                },
            ],
        },
    )

    args = mod.parse_args(
        [
            "--upload-review-packet-json",
            str(review_json),
            "--upload-operator-decision-kit-json",
            str(decision_json),
            "--post-native-scoring-scaffold-json",
            str(post_native_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "audit.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod._write_json(args.out_json, payload)
    mod._write_csv(args.out_csv, payload["rows"])
    mod._write_md(args.out_md, payload)

    assert payload["summary"]["status"] == "current_queue_rollover_hygiene_stale_generated_folders_retained"
    assert payload["summary"]["surface_count"] == 3
    assert payload["summary"]["surface_stale_count"] == 3
    assert payload["summary"]["missing_active_folder_count"] == 0
    assert payload["summary"]["stale_extra_folder_count"] == 3
    assert payload["summary"]["first_stale_surface_id"] == "current_upload_review_packet"
    assert "stale_generated_folders_retained" in Path(args.out_md).read_text(encoding="utf-8")


def test_current_queue_rollover_hygiene_audit_blocks_missing_active_folder(tmp_path: Path) -> None:
    review_root = tmp_path / "review"
    decision_root = tmp_path / "decision"
    post_native_root = tmp_path / "post_native"
    for folder in [review_root, decision_root, post_native_root]:
        folder.mkdir(parents=True)

    review_json = tmp_path / "review.json"
    decision_json = tmp_path / "decision.json"
    post_native_json = tmp_path / "post_native.json"
    _write_json(
        review_json,
        {
            "summary": {"review_dir": str(review_root)},
            "rows": [{"target_id": "H1001", "packet_folder": str(review_root / "missing_h1001")}],
        },
    )
    _write_json(decision_json, {"rows": []})
    _write_json(post_native_json, {"summary": {"scaffold_dir": str(post_native_root)}, "target_rows": []})

    args = mod.parse_args(
        [
            "--upload-review-packet-json",
            str(review_json),
            "--upload-operator-decision-kit-json",
            str(decision_json),
            "--post-native-scoring-scaffold-json",
            str(post_native_json),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["status"] == "blocked_missing_active_generated_folder"
    assert payload["summary"]["surface_blocked_count"] == 1
    assert payload["summary"]["missing_active_folder_count"] == 1
    assert payload["rows"][0]["surface_status"] == "blocked_missing_active_folder"
