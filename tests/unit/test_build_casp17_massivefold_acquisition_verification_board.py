from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from tools.casp17 import build_casp17_massivefold_acquisition_verification_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _queue_row(rank: int, target_id: str, pool_folder: Path, size: int) -> dict:
    filename = f"{target_id}_all_cifs_MassiveFold.tar.gz"
    return {
        "queue_rank": rank,
        "model_set_id": target_id,
        "primary_target_id": target_id,
        "target_category": "rna_or_hybrid",
        "ftp_filename": filename,
        "ftp_size_bytes": size,
        "massivefold_tarball_url": f"ftp://files.plbs.fr:21211/CASP17-CAPRI/{filename}",
        "pool_folder": str(pool_folder),
    }


def test_massivefold_acquisition_verification_board_tracks_open_and_verified_pools(tmp_path: Path) -> None:
    r2341_pool = tmp_path / "casp17/massivefold_external_pool_intake/r2341"
    r2345_pool = tmp_path / "casp17/massivefold_external_pool_intake/r2345"
    tarball = r2341_pool / "downloads/R2341_all_cifs_MassiveFold.tar.gz"
    tarball.parent.mkdir(parents=True, exist_ok=True)
    tarball.write_bytes(b"massivefold-test")
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    sha_path = r2341_pool / "hashes/R2341_all_cifs_MassiveFold.tar.gz.sha256"
    sha_path.parent.mkdir(parents=True, exist_ok=True)
    sha_path.write_text(f"{digest}  {tarball}\n", encoding="utf-8")
    listing = r2341_pool / "extracted_models/tarball_listing.txt"
    listing.parent.mkdir(parents=True, exist_ok=True)
    listing.write_text("R2341/model_1.cif\nR2341/model_2.cif\nREADME.txt\n", encoding="utf-8")

    priority_json = tmp_path / "priority.json"
    _write_json(
        priority_json,
        {
            "summary": {
                "rna_hybrid_massivefold_priority_queue_status": (
                    "rna_hybrid_massivefold_priority_queue_ready"
                )
            },
            "rows": [
                _queue_row(1, "R2341", r2341_pool, tarball.stat().st_size),
                _queue_row(2, "R2345", r2345_pool, 245903877),
            ],
        },
    )
    args = mod.parse_args(
        [
            "--priority-queue-json",
            str(priority_json),
            "--out-dir",
            str(tmp_path / "board"),
            "--out-json",
            str(tmp_path / "board.json"),
            "--out-csv",
            str(tmp_path / "board.csv"),
            "--out-md",
            str(tmp_path / "BOARD.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_acquisition_verification_status"] == (
        "awaiting_massivefold_external_pool_acquisition"
    )
    assert summary["acquisition_pool_count"] == 2
    assert summary["verified_pool_count"] == 1
    assert summary["open_acquisition_action_count"] == 1
    assert summary["tarball_present_count"] == 1
    assert summary["size_match_count"] == 1
    assert summary["sha256_record_present_count"] == 1
    assert summary["sha256_verified_count"] == 1
    assert summary["listing_present_count"] == 1
    assert summary["listing_entry_count"] == 2
    assert summary["r2341_verification_status"] == "verified_for_external_rerank_intake"
    assert summary["r2345_verification_status"] == "open_tarball_download_required"

    rows = {row["primary_target_id"]: row for row in payload["rows"]}
    assert rows["R2341"]["pool_verification_status"] == "verified_for_external_rerank_intake"
    assert rows["R2341"]["sha256_actual"] == digest
    assert rows["R2345"]["pool_verification_status"] == "open_tarball_download_required"
    assert rows["R2345"]["next_action"].startswith("download the tarball")
    assert len(_read_csv(tmp_path / "board.csv")) == 2
    assert Path(rows["R2341"]["action_md"]).is_file()
    assert "R2341 MassiveFold Acquisition Verification" in Path(
        rows["R2341"]["action_md"]
    ).read_text(encoding="utf-8")
    assert "pools verified/open/total: `1/1/2`" in (tmp_path / "BOARD.md").read_text(encoding="utf-8")


def test_massivefold_acquisition_verification_board_blocks_missing_priority_queue(tmp_path: Path) -> None:
    args = mod.parse_args(
        [
            "--priority-queue-json",
            str(tmp_path / "missing_priority.json"),
            "--out-dir",
            str(tmp_path / "board"),
            "--out-json",
            str(tmp_path / "board.json"),
            "--out-csv",
            str(tmp_path / "board.csv"),
            "--out-md",
            str(tmp_path / "BOARD.md"),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_acquisition_verification_status"] == (
        "blocked_massivefold_priority_queue_missing"
    )
    assert payload["summary"]["acquisition_pool_count"] == 0


def test_massivefold_acquisition_verification_board_accepts_protein_complex_priority_status(
    tmp_path: Path,
) -> None:
    h1311_pool = tmp_path / "casp17/massivefold_external_pool_intake/h1311_t327"
    priority_json = tmp_path / "protein_priority.json"
    _write_json(
        priority_json,
        {
            "summary": {
                "protein_complex_massivefold_priority_queue_status": (
                    "protein_complex_massivefold_priority_queue_ready"
                )
            },
            "rows": [
                {
                    **_queue_row(1, "H1311", h1311_pool, 1934629344),
                    "model_set_id": "H1311_T327",
                    "target_category": "protein_or_complex",
                    "ftp_filename": "H1311_T327_all_pdbs_MassiveFold.tar.gz",
                    "massivefold_tarball_url": (
                        "ftp://files.plbs.fr:21211/CASP17-CAPRI/"
                        "H1311_T327_all_pdbs_MassiveFold.tar.gz"
                    ),
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--priority-queue-json",
            str(priority_json),
            "--out-dir",
            str(tmp_path / "board"),
            "--out-json",
            str(tmp_path / "board.json"),
            "--out-csv",
            str(tmp_path / "board.csv"),
            "--out-md",
            str(tmp_path / "BOARD.md"),
        ]
    )

    payload = mod.build_payload(args)

    summary = payload["summary"]
    assert summary["priority_queue_status"] == "protein_complex_massivefold_priority_queue_ready"
    assert summary["first_priority_target_id"] == "H1311"
    assert summary["first_open_status"] == "open_tarball_download_required"
