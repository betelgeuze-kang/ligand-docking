import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_current_upload_active_manifest_lock as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_operator_row(folder: Path, target_id: str, decision: str = "") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "operator_decision_row.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "target_id",
                "operator_decision",
                "operator_id",
                "operator_decision_ref",
                "author_serialization_status",
                "final_upload_filename",
                "operator_notes",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(
            {
                "target_id": target_id,
                "operator_decision": decision,
                "operator_id": "",
                "operator_decision_ref": "",
                "author_serialization_status": "",
                "final_upload_filename": "",
                "operator_notes": "",
            }
        )


def _args(tmp_path: Path, review_json: Path, decision_json: Path, hygiene_json: Path):
    return mod.parse_args(
        [
            "--upload-review-packet-json",
            str(review_json),
            "--upload-operator-decision-kit-json",
            str(decision_json),
            "--queue-rollover-hygiene-audit-json",
            str(hygiene_json),
            "--out-json",
            str(tmp_path / "lock.json"),
            "--out-csv",
            str(tmp_path / "lock.csv"),
            "--out-md",
            str(tmp_path / "lock.md"),
        ]
    )


def test_active_manifest_lock_passes_with_stale_readonly_folders(tmp_path: Path) -> None:
    review_folder = tmp_path / "review" / "01_h1001"
    decision_folder = tmp_path / "decision" / "01_h1001"
    stale_decision_folder = tmp_path / "decision" / "old_h0999"
    review_folder.mkdir(parents=True)
    decision_folder.mkdir(parents=True)
    _write_operator_row(stale_decision_folder, "H0999")

    review_json = tmp_path / "review.json"
    decision_json = tmp_path / "decision.json"
    hygiene_json = tmp_path / "hygiene.json"
    _write_json(
        review_json,
        {
            "summary": {"review_packet_status": "current_upload_review_packet_ready"},
            "rows": [
                {
                    "target_id": "H1001",
                    "queue_rank": 1,
                    "packet_folder": str(review_folder),
                }
            ],
        },
    )
    _write_json(
        decision_json,
        {
            "summary": {"decision_kit_status": "current_upload_operator_decision_kit_awaiting_operator_decisions"},
            "rows": [
                {
                    "target_id": "H1001",
                    "queue_rank": 1,
                    "decision_packet_folder": str(decision_folder),
                    "operator_decision": "",
                }
            ],
        },
    )
    _write_json(
        hygiene_json,
        {
            "summary": {"status": "current_queue_rollover_hygiene_stale_generated_folders_retained"},
            "rows": [
                {
                    "surface_id": "current_upload_operator_decision_kit",
                    "stale_extra_folders": [str(stale_decision_folder)],
                }
            ],
        },
    )

    args = _args(tmp_path, review_json, decision_json, hygiene_json)
    payload = mod.build_payload(args)
    mod._write_json(args.out_json, payload)
    mod._write_csv(args.out_csv, payload["rows"])
    mod._write_md(args.out_md, payload)

    assert payload["summary"]["active_manifest_lock_status"] == (
        "current_upload_active_manifest_lock_pass_stale_readonly"
    )
    assert payload["summary"]["active_locked_count"] == 1
    assert payload["summary"]["stale_readonly_count"] == 1
    assert payload["summary"]["stale_operator_value_folder_count"] == 0
    assert "stale_folder_readonly_no_operator_values" in Path(args.out_md).read_text(encoding="utf-8")


def test_active_manifest_lock_blocks_stale_operator_decision_values(tmp_path: Path) -> None:
    review_folder = tmp_path / "review" / "01_h1001"
    decision_folder = tmp_path / "decision" / "01_h1001"
    stale_decision_folder = tmp_path / "decision" / "old_h0999"
    review_folder.mkdir(parents=True)
    decision_folder.mkdir(parents=True)
    _write_operator_row(stale_decision_folder, "H0999", decision="approve")

    review_json = tmp_path / "review.json"
    decision_json = tmp_path / "decision.json"
    hygiene_json = tmp_path / "hygiene.json"
    _write_json(
        review_json,
        {"rows": [{"target_id": "H1001", "queue_rank": 1, "packet_folder": str(review_folder)}]},
    )
    _write_json(
        decision_json,
        {"rows": [{"target_id": "H1001", "queue_rank": 1, "decision_packet_folder": str(decision_folder)}]},
    )
    _write_json(
        hygiene_json,
        {
            "rows": [
                {
                    "surface_id": "current_upload_operator_decision_kit",
                    "stale_extra_folders": [str(stale_decision_folder)],
                }
            ]
        },
    )

    payload = mod.build_payload(_args(tmp_path, review_json, decision_json, hygiene_json))

    assert payload["summary"]["active_manifest_lock_status"] == "blocked_stale_operator_decision_values_present"
    assert payload["summary"]["stale_operator_value_folder_count"] == 1
    assert payload["summary"]["first_blocker"] == "stale_operator_value_present"


def test_active_manifest_lock_blocks_missing_active_decision_row(tmp_path: Path) -> None:
    review_folder = tmp_path / "review" / "01_h1001"
    review_folder.mkdir(parents=True)
    review_json = tmp_path / "review.json"
    decision_json = tmp_path / "decision.json"
    hygiene_json = tmp_path / "hygiene.json"
    _write_json(
        review_json,
        {"rows": [{"target_id": "H1001", "queue_rank": 1, "packet_folder": str(review_folder)}]},
    )
    _write_json(decision_json, {"rows": []})
    _write_json(hygiene_json, {"rows": []})

    payload = mod.build_payload(_args(tmp_path, review_json, decision_json, hygiene_json))

    assert payload["summary"]["active_manifest_lock_status"] == "blocked_active_manifest_mismatch"
    assert payload["summary"]["active_blocked_count"] == 1
    assert payload["summary"]["first_blocked_target_id"] == "H1001"
