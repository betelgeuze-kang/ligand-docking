from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_rna_hybrid_massivefold_priority_queue as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_rna_hybrid_massivefold_priority_queue_promotes_r2341_and_guards_r2345(
    tmp_path: Path,
) -> None:
    organizer = tmp_path / "organizer_notice.json"
    intake = tmp_path / "external_pool.json"
    _write_json(
        organizer,
        {
            "summary": {"organizer_notice_status": "organizer_notice_intake_ready"},
            "notice_rows": [
                {
                    "target_id": "R2345",
                    "request_status": "ignored_invalid_dna_t_in_rna_sequence",
                    "request_time_pacific": "09:30",
                },
                {
                    "target_id": "R2345",
                    "request_status": "accepted_second_request_only",
                    "request_time_pacific": "11:30",
                },
            ],
        },
    )
    _write_json(
        intake,
        {
            "summary": {"massivefold_external_pool_intake_status": "massivefold_external_pool_intake_ready"},
            "rows": [
                {
                    "model_set_id": "R2350",
                    "primary_target_id": "R2350",
                    "target_category": "rna_or_hybrid",
                    "bundle_format": "cif_bundle",
                    "massivefold_tarball_url": "ftp://files.plbs.fr:21211/CASP17-CAPRI/R2350_all_cifs_MassiveFold.tar.gz",
                    "ftp_filename": "R2350_all_cifs_MassiveFold.tar.gz",
                    "ftp_size_bytes": 1362175616,
                    "ftp_modified_hint": "May 26 09:37",
                    "pool_folder": "casp17/massivefold_external_pool_intake/r2350",
                    "acquisition_manifest": "casp17/massivefold_external_pool_intake/r2350/ACQUISITION_MANIFEST.md",
                    "sequence_guard": "",
                },
                {
                    "model_set_id": "R2345",
                    "primary_target_id": "R2345",
                    "target_category": "rna_or_hybrid",
                    "bundle_format": "cif_bundle",
                    "massivefold_tarball_url": "ftp://files.plbs.fr:21211/CASP17-CAPRI/R2345_all_cifs_MassiveFold.tar.gz",
                    "ftp_filename": "R2345_all_cifs_MassiveFold.tar.gz",
                    "ftp_size_bytes": 245903877,
                    "ftp_modified_hint": "May 22 14:25",
                    "pool_folder": "casp17/massivefold_external_pool_intake/r2345",
                    "acquisition_manifest": "casp17/massivefold_external_pool_intake/r2345/ACQUISITION_MANIFEST.md",
                    "sequence_guard": "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only",
                },
                {
                    "model_set_id": "H2335_T335",
                    "primary_target_id": "H2335",
                    "target_category": "protein_or_complex",
                    "bundle_format": "pdb_cif_bundle",
                    "massivefold_tarball_url": "ftp://files.plbs.fr:21211/CASP17-CAPRI/H2335_T335_all_pdbs_MassiveFold.tar.gz",
                    "ftp_filename": "H2335_T335_all_pdbs_MassiveFold.tar.gz",
                    "ftp_size_bytes": 4192785208,
                },
                {
                    "model_set_id": "R2341",
                    "primary_target_id": "R2341",
                    "target_category": "rna_or_hybrid",
                    "bundle_format": "cif_bundle",
                    "massivefold_tarball_url": "ftp://files.plbs.fr:21211/CASP17-CAPRI/R2341_all_cifs_MassiveFold.tar.gz",
                    "ftp_filename": "R2341_all_cifs_MassiveFold.tar.gz",
                    "ftp_size_bytes": 667779936,
                    "ftp_modified_hint": "May 20 18:01",
                    "pool_folder": "casp17/massivefold_external_pool_intake/r2341",
                    "acquisition_manifest": "casp17/massivefold_external_pool_intake/r2341/ACQUISITION_MANIFEST.md",
                    "sequence_guard": "",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--organizer-notice-packet-json",
            str(organizer),
            "--massivefold-external-pool-intake-json",
            str(intake),
            "--out-dir",
            str(tmp_path / "priority"),
            "--out-json",
            str(tmp_path / "priority.json"),
            "--out-csv",
            str(tmp_path / "priority.csv"),
            "--out-md",
            str(tmp_path / "PRIORITY.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["rna_hybrid_massivefold_priority_queue_status"] == (
        "rna_hybrid_massivefold_priority_queue_ready"
    )
    assert summary["queue_row_count"] == 3
    assert summary["ready_queue_row_count"] == 3
    assert summary["blocked_queue_row_count"] == 0
    assert summary["first_priority_target_id"] == "R2341"
    assert summary["r2341_queue_rank"] == 1
    assert summary["r2345_queue_rank"] == 2
    assert summary["r2345_invalid_request_quarantined"] is True
    assert summary["r2345_invalid_request_status"] == "ignored_invalid_dna_t_in_rna_sequence"
    assert summary["r2345_active_request_status"] == "accepted_second_request_only"
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["internal_prediction_blocked_count"] == 3

    rows = payload["rows"]
    assert [row["primary_target_id"] for row in rows] == ["R2341", "R2345", "R2350"]
    assert rows[1]["sequence_guard"] == "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"
    assert rows[1]["row_status"] == "ready_for_rule_checked_external_pool_acquisition"
    assert "organizer_notice_first_rna_massivefold_set_available" in rows[0]["priority_reason"]
    assert "corrected_1130_pacific_request_only" in rows[1]["priority_reason"]

    written_rows = _read_csv(tmp_path / "priority.csv")
    assert len(written_rows) == 3
    assert Path(rows[0]["priority_action_md"]).is_file()
    action_text = Path(rows[1]["priority_action_md"]).read_text(encoding="utf-8")
    assert "ignored_invalid_dna_t_in_rna_sequence" in action_text
    assert "competitive_proof_eligible: `False`" in action_text
    assert (tmp_path / "PRIORITY.md").read_text(encoding="utf-8").startswith("# CASP17 RNA")


def test_rna_hybrid_massivefold_priority_queue_blocks_missing_intake(tmp_path: Path) -> None:
    organizer = tmp_path / "organizer_notice.json"
    _write_json(organizer, {"summary": {"organizer_notice_status": "organizer_notice_intake_ready"}})
    args = mod.parse_args(
        [
            "--organizer-notice-packet-json",
            str(organizer),
            "--massivefold-external-pool-intake-json",
            str(tmp_path / "missing_intake.json"),
            "--out-dir",
            str(tmp_path / "priority"),
            "--out-json",
            str(tmp_path / "priority.json"),
            "--out-csv",
            str(tmp_path / "priority.csv"),
            "--out-md",
            str(tmp_path / "PRIORITY.md"),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["rna_hybrid_massivefold_priority_queue_status"] == (
        "blocked_massivefold_external_pool_intake_missing"
    )
    assert payload["summary"]["queue_row_count"] == 0


def test_rna_hybrid_massivefold_priority_queue_blocks_r2345_without_sequence_guard(
    tmp_path: Path,
) -> None:
    organizer = tmp_path / "organizer_notice.json"
    intake = tmp_path / "external_pool.json"
    _write_json(
        organizer,
        {
            "notice_rows": [
                {"target_id": "R2345", "request_status": "ignored_invalid_dna_t_in_rna_sequence"},
                {"target_id": "R2345", "request_status": "accepted_second_request_only"},
            ]
        },
    )
    _write_json(
        intake,
        {
            "rows": [
                {
                    "model_set_id": "R2345",
                    "primary_target_id": "R2345",
                    "target_category": "rna_or_hybrid",
                    "bundle_format": "cif_bundle",
                    "massivefold_tarball_url": "ftp://files.plbs.fr:21211/CASP17-CAPRI/R2345_all_cifs_MassiveFold.tar.gz",
                    "ftp_filename": "R2345_all_cifs_MassiveFold.tar.gz",
                    "ftp_size_bytes": 245903877,
                    "sequence_guard": "",
                }
            ]
        },
    )
    args = mod.parse_args(
        [
            "--organizer-notice-packet-json",
            str(organizer),
            "--massivefold-external-pool-intake-json",
            str(intake),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["rna_hybrid_massivefold_priority_queue_status"] == (
        "blocked_rna_hybrid_massivefold_priority_queue"
    )
    assert payload["summary"]["first_blocked_target_id"] == "R2345"
    assert payload["summary"]["first_blocked_status"] == "blocked_r2345_sequence_guard_missing"
