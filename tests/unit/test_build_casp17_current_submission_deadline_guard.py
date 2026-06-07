import json
from pathlib import Path

from tools.casp17 import build_casp17_current_submission_deadline_guard as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_current_submission_deadline_guard_recomputes_open_and_expired_windows(tmp_path: Path) -> None:
    target_json = tmp_path / "target_model_folders.json"
    package_json = tmp_path / "package_preflight.json"
    watchlist_json = tmp_path / "watchlist.json"

    _write_json(
        target_json,
        {
            "rows": [
                {
                    "target_id": "T9001",
                    "protein_name": "Today target",
                    "lane": "difficult_protein_complexes",
                    "human_expiration": "2026-06-02",
                    "qa_expiration": "2026-06-05",
                },
                {
                    "target_id": "T9002",
                    "protein_name": "Expired target",
                    "lane": "difficult_protein_complexes",
                    "human_expiration": "2026-06-01",
                    "qa_expiration": "2026-06-04",
                },
                {
                    "target_id": "T9003",
                    "protein_name": "Package blocked target",
                    "lane": "difficult_protein_complexes",
                    "human_expiration": "2026-06-04",
                    "qa_expiration": "2026-06-07",
                },
            ]
        },
    )
    _write_json(
        package_json,
        {
            "summary": {
                "package_preflight_status": "blocked",
                "ready_count": 2,
                "blocked_count": 1,
                "target_count": 3,
            },
            "rows": [
                {
                    "target_id": "T9001",
                    "package_preflight_status": "ready",
                    "candidate_pdb": "runs/predictions/T9001TS.pdb",
                },
                {
                    "target_id": "T9002",
                    "package_preflight_status": "ready",
                    "candidate_pdb": "runs/predictions/T9002TS.pdb",
                },
                {
                    "target_id": "T9003",
                    "package_preflight_status": "blocked",
                    "candidate_pdb": "runs/predictions/T9003TS.pdb",
                },
            ],
        },
    )
    _write_json(watchlist_json, {"summary": {"today": "2026-05-26"}})

    args = mod.parse_args(
        [
            "--target-model-folders-json",
            str(target_json),
            "--package-preflight-json",
            str(package_json),
            "--target-watchlist-json",
            str(watchlist_json),
            "--current-date",
            "2026-06-02",
            "--out-md",
            str(tmp_path / "deadline.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod._write_md(args.out_md, payload)
    by_target = {row["target_id"]: row for row in payload["rows"]}

    assert payload["summary"]["deadline_guard_status"] == "partial_current_upload_window_ready"
    assert payload["summary"]["upload_window_ready_count"] == 1
    assert payload["summary"]["deadline_blocked_count"] == 2
    assert payload["summary"]["human_expired_count"] == 1
    assert payload["summary"]["human_expiring_today_count"] == 1
    assert payload["summary"]["human_future_count"] == 1
    assert payload["summary"]["watchlist_stale"] is True
    assert payload["summary"]["watchlist_stale_days"] == 7
    assert payload["summary"]["first_blocked_target_id"] == "T9002"
    assert payload["summary"]["first_blocked_reason"] == "human_submission_deadline_expired"
    assert payload["summary"]["nearest_open_target_id"] == "T9001"
    assert by_target["T9001"]["deadline_guard_status"] == "ready_expiring_today"
    assert by_target["T9001"]["human_deadline_open"] is True
    assert by_target["T9001"]["blockers"] == ""
    assert by_target["T9002"]["deadline_guard_status"] == "blocked_human_deadline_expired"
    assert "human_submission_deadline_expired" in by_target["T9002"]["blockers"]
    assert by_target["T9003"]["deadline_guard_status"] == "blocked_package_preflight"
    assert "package_preflight_not_ready" in by_target["T9003"]["blockers"]
    assert "upload-window ready/blocked/total: `1/2/3`" in Path(args.out_md).read_text(encoding="utf-8")
