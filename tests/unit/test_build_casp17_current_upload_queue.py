import json
from pathlib import Path

from tools.casp17 import build_casp17_current_upload_queue as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_current_upload_queue_merges_package_deadlines_and_official_targetlist(
    tmp_path: Path,
) -> None:
    package_json = tmp_path / "package_preflight.json"
    deadline_json = tmp_path / "deadline_guard.json"
    official_csv = tmp_path / "official_targetlist.csv"

    _write_json(
        package_json,
        {
            "summary": {
                "package_preflight_status": "ready",
                "ready_count": 3,
                "blocked_count": 1,
                "target_count": 4,
            },
            "rows": [
                {
                    "target_id": "T9001",
                    "package_preflight_status": "ready",
                    "candidate_pdb": "runs/predictions/T9001TS.pdb",
                    "candidate_sha256": "sha-t9001",
                },
                {
                    "target_id": "T9002",
                    "package_preflight_status": "ready",
                    "candidate_pdb": "runs/predictions/T9002TS.pdb",
                    "candidate_sha256": "sha-t9002",
                },
                {
                    "target_id": "H2903",
                    "package_preflight_status": "ready",
                    "candidate_pdb": "runs/predictions/H2903TS.pdb",
                    "candidate_sha256": "sha-h2903",
                },
                {
                    "target_id": "T9004",
                    "package_preflight_status": "blocked",
                    "candidate_pdb": "runs/predictions/T9004TS.pdb",
                    "candidate_sha256": "",
                },
            ],
        },
    )
    _write_json(
        deadline_json,
        {
            "summary": {
                "deadline_guard_status": "partial_current_upload_window_ready",
                "upload_window_ready_count": 3,
                "deadline_blocked_count": 1,
                "target_count": 4,
            },
            "rows": [
                {
                    "target_id": "T9001",
                    "protein_name": "Ready today",
                    "deadline_guard_status": "ready_expiring_today",
                    "human_expiration": "2026-06-02",
                    "qa_expiration": "2026-06-05",
                    "days_to_human_expiration": 0,
                },
                {
                    "target_id": "T9002",
                    "protein_name": "Expired official target",
                    "deadline_guard_status": "blocked_human_deadline_expired",
                    "human_expiration": "2026-06-01",
                    "qa_expiration": "2026-06-04",
                    "days_to_human_expiration": -1,
                    "blockers": "human_submission_deadline_expired",
                },
                {
                    "target_id": "H2903",
                    "protein_name": "Phase mapped cancelled target",
                    "deadline_guard_status": "ready_future_window",
                    "human_expiration": "2026-06-04",
                    "qa_expiration": "2026-06-07",
                    "days_to_human_expiration": 2,
                },
                {
                    "target_id": "T9004",
                    "protein_name": "Package blocked target",
                    "deadline_guard_status": "ready_future_window",
                    "human_expiration": "2026-06-05",
                    "qa_expiration": "2026-06-08",
                    "days_to_human_expiration": 3,
                },
            ],
        },
    )
    official_csv.write_text(
        "\n".join(
            [
                "Target;Type;Res;Oligo.State;Entry Date; Server Exp.;Human Exp.;QA Exp.;Cancellation Date;Description",
                "T9001;protein;100;monomer;2026-05-28;2026-06-01;2026-06-02;2026-06-05;;Today fixture",
                "T9002;protein;100;monomer;2026-05-28;2026-05-31;2026-06-01;2026-06-04;;Expired fixture",
                "H1903;complex;200;heteromer;2026-05-28;2026-06-03;2026-06-04;2026-06-07;;<em><font color=red>Canceled - preprint.</font></em>",
                "T9004;protein;100;monomer;2026-05-28;2026-06-04;2026-06-05;2026-06-08;;Package fixture",
                "",
            ]
        ),
        encoding="utf-8",
    )

    args = mod.parse_args(
        [
            "--package-preflight-json",
            str(package_json),
            "--deadline-guard-json",
            str(deadline_json),
            "--official-targetlist-csv",
            str(official_csv),
            "--current-date",
            "2026-06-02",
            "--out-json",
            str(tmp_path / "queue.json"),
            "--out-csv",
            str(tmp_path / "queue.csv"),
            "--out-md",
            str(tmp_path / "queue.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod._write_json(args.out_json, payload)
    mod._write_csv(args.out_csv, payload["rows"])
    mod._write_md(args.out_md, payload)
    by_target = {row["target_id"]: row for row in payload["rows"]}

    assert payload["summary"]["upload_queue_status"] == "official_verified_current_upload_queue_partial"
    assert payload["summary"]["upload_ready_count"] == 1
    assert payload["summary"]["blocked_count"] == 3
    assert payload["summary"]["ready_today_count"] == 1
    assert payload["summary"]["ready_soon_count"] == 0
    assert payload["summary"]["ready_future_count"] == 0
    assert payload["summary"]["official_direct_match_count"] == 3
    assert payload["summary"]["official_phase_mapped_count"] == 1
    assert payload["summary"]["official_missing_count"] == 0
    assert payload["summary"]["official_cancelled_count"] == 1
    assert payload["summary"]["official_expired_count"] == 1
    assert payload["summary"]["first_upload_target_id"] == "T9001"
    assert payload["summary"]["first_blocked_target_id"] == "H2903"
    assert payload["summary"]["first_blocked_reason"] == "official_target_cancelled"
    assert by_target["T9001"]["upload_queue_status"] == "upload_ready_expiring_today"
    assert by_target["T9001"]["queue_rank"] == 1
    assert by_target["T9002"]["upload_queue_status"] == "blocked_official_deadline_expired"
    assert "official_human_deadline_expired" in by_target["T9002"]["blockers"]
    assert by_target["H2903"]["official_target_id"] == "H1903"
    assert by_target["H2903"]["official_match_status"] == "phase_mapped_to_primary_target"
    assert by_target["H2903"]["upload_queue_status"] == "blocked_official_cancelled"
    assert "official_target_cancelled" in by_target["H2903"]["blockers"]
    assert by_target["H2903"]["official_description"] == "Canceled - preprint."
    assert by_target["T9004"]["upload_queue_status"] == "blocked_package_preflight"
    assert "package_preflight_not_ready" in by_target["T9004"]["blockers"]
    assert "upload ready/blocked/total: `1/3/4`" in Path(args.out_md).read_text(encoding="utf-8")


def test_official_targetlist_csv_normalization_strips_trailing_spaces() -> None:
    assert mod._normalize_official_csv_text("Target;Description   \nT1;Name   \n\n  \n") == (
        "Target;Description\nT1;Name\n"
    )
