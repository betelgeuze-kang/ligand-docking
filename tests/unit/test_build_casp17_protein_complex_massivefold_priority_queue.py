from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_protein_complex_massivefold_priority_queue as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _intake_row(
    pool_id: str,
    model_set_id: str,
    target_id: str,
    category: str,
    size: int,
    *,
    tarball_url: str | None = None,
) -> dict:
    filename = f"{model_set_id}_all_pdbs_MassiveFold.tar.gz"
    if category == "rna_or_hybrid":
        filename = f"{model_set_id}_all_cifs_MassiveFold.tar.gz"
    return {
        "pool_id": pool_id,
        "model_set_id": model_set_id,
        "primary_target_id": target_id,
        "target_category": category,
        "bundle_format": "pdb_cif_bundle" if category == "protein_or_complex" else "cif_bundle",
        "ftp_filename": filename,
        "ftp_size_bytes": size,
        "ftp_modified_hint": "May 2 10:06",
        "massivefold_tarball_url": (
            tarball_url
            if tarball_url is not None
            else f"ftp://files.plbs.fr:21211/CASP17-CAPRI/{filename}"
        ),
        "pool_folder": f"casp17/massivefold_external_pool_intake/{model_set_id.lower()}",
        "acquisition_manifest": (
            f"casp17/massivefold_external_pool_intake/{model_set_id.lower()}/ACQUISITION_MANIFEST.md"
        ),
    }


def test_protein_complex_massivefold_priority_queue_filters_and_ranks_rows(tmp_path: Path) -> None:
    organizer_json = tmp_path / "organizer.json"
    intake_json = tmp_path / "intake.json"
    _write_json(
        organizer_json,
        {"summary": {"organizer_notice_status": "organizer_notice_intake_ready"}},
    )
    _write_json(
        intake_json,
        {
            "summary": {
                "massivefold_external_pool_intake_status": "massivefold_external_pool_intake_ready"
            },
            "rows": [
                _intake_row("massivefold_external_pool_010", "R2345", "R2345", "rna_or_hybrid", 245),
                _intake_row("massivefold_external_pool_002", "H2324_T328", "H2324", "protein_or_complex", 200),
                _intake_row("massivefold_external_pool_001", "H1311_T327", "H1311", "protein_or_complex", 100),
            ],
        },
    )
    args = mod.parse_args(
        [
            "--organizer-notice-packet-json",
            str(organizer_json),
            "--massivefold-external-pool-intake-json",
            str(intake_json),
            "--out-dir",
            str(tmp_path / "queue"),
            "--out-json",
            str(tmp_path / "queue.json"),
            "--out-csv",
            str(tmp_path / "queue.csv"),
            "--out-md",
            str(tmp_path / "QUEUE.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["protein_complex_massivefold_priority_queue_status"] == (
        "protein_complex_massivefold_priority_queue_ready"
    )
    assert summary["queue_row_count"] == 2
    assert summary["ready_queue_row_count"] == 2
    assert summary["blocked_queue_row_count"] == 0
    assert summary["first_priority_target_id"] == "H1311"
    assert summary["first_priority_model_set_id"] == "H1311_T327"
    assert summary["largest_model_set_id"] == "H2324_T328"
    assert summary["largest_pool_size_bytes"] == 200
    assert summary["total_declared_size_bytes"] == 300
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["internal_prediction_blocked_count"] == 2

    rows = payload["rows"]
    assert [row["model_set_id"] for row in rows] == ["H1311_T327", "H2324_T328"]
    assert [row["queue_rank"] for row in rows] == [1, 2]
    assert rows[0]["row_status"] == "ready_for_rule_checked_external_pool_acquisition"
    assert len(_read_csv(tmp_path / "queue.csv")) == 2
    assert Path(rows[0]["priority_action_md"]).is_file()
    assert "Protein/Complex MassiveFold Priority Action" in Path(
        rows[0]["priority_action_md"]
    ).read_text(encoding="utf-8")
    assert "queue rows ready/blocked/total: `2/0/2`" in (tmp_path / "QUEUE.md").read_text(
        encoding="utf-8"
    )


def test_protein_complex_massivefold_priority_queue_blocks_missing_intake(tmp_path: Path) -> None:
    organizer_json = tmp_path / "organizer.json"
    _write_json(
        organizer_json,
        {"summary": {"organizer_notice_status": "organizer_notice_intake_ready"}},
    )
    args = mod.parse_args(
        [
            "--organizer-notice-packet-json",
            str(organizer_json),
            "--massivefold-external-pool-intake-json",
            str(tmp_path / "missing_intake.json"),
            "--out-dir",
            str(tmp_path / "queue"),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["protein_complex_massivefold_priority_queue_status"] == (
        "blocked_massivefold_external_pool_intake_missing"
    )
    assert payload["summary"]["queue_row_count"] == 0


def test_protein_complex_massivefold_priority_queue_blocks_missing_tarball_url(tmp_path: Path) -> None:
    organizer_json = tmp_path / "organizer.json"
    intake_json = tmp_path / "intake.json"
    _write_json(
        organizer_json,
        {"summary": {"organizer_notice_status": "organizer_notice_intake_ready"}},
    )
    _write_json(
        intake_json,
        {
            "summary": {
                "massivefold_external_pool_intake_status": "massivefold_external_pool_intake_ready"
            },
            "rows": [
                _intake_row(
                    "massivefold_external_pool_001",
                    "H1311_T327",
                    "H1311",
                    "protein_or_complex",
                    100,
                    tarball_url="",
                )
            ],
        },
    )
    args = mod.parse_args(
        [
            "--organizer-notice-packet-json",
            str(organizer_json),
            "--massivefold-external-pool-intake-json",
            str(intake_json),
            "--out-dir",
            str(tmp_path / "queue"),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["protein_complex_massivefold_priority_queue_status"] == (
        "blocked_protein_complex_massivefold_priority_queue"
    )
    assert payload["summary"]["ready_queue_row_count"] == 0
    assert payload["summary"]["blocked_queue_row_count"] == 1
    assert payload["rows"][0]["row_status"] == "blocked_missing_tarball_url"
