from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_massivefold_external_pool_intake as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_massivefold_external_pool_intake_separates_rerank_pool_from_internal_proof(tmp_path: Path) -> None:
    organizer = tmp_path / "organizer_notice.json"
    _write_json(
        organizer,
        {
            "summary": {"organizer_notice_status": "organizer_notice_intake_ready"},
            "massivefold_rows": [
                {
                    "model_set_id": "R2341",
                    "primary_target_id": "R2341",
                    "target_category": "rna_or_hybrid",
                    "bundle_format": "cif_bundle",
                    "massivefold_tarball_url": "ftp://files.plbs.fr:21211/CASP17-CAPRI/R2341_all_cifs_MassiveFold.tar.gz",
                    "ftp_filename": "R2341_all_cifs_MassiveFold.tar.gz",
                    "ftp_size_bytes": 667779936,
                    "ftp_modified_hint": "May 20 18:01",
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
                },
                {
                    "model_set_id": "H2335_T335",
                    "primary_target_id": "H2335",
                    "target_category": "protein_or_complex",
                    "bundle_format": "pdb_cif_bundle",
                    "massivefold_tarball_url": "ftp://files.plbs.fr:21211/CASP17-CAPRI/H2335_T335_all_pdbs_MassiveFold.tar.gz",
                    "ftp_filename": "H2335_T335_all_pdbs_MassiveFold.tar.gz",
                    "ftp_size_bytes": 4192785208,
                    "ftp_modified_hint": "May 29 17:10",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--organizer-notice-packet-json",
            str(organizer),
            "--out-dir",
            str(tmp_path / "external_pool"),
            "--out-json",
            str(tmp_path / "pool.json"),
            "--out-csv",
            str(tmp_path / "pool.csv"),
            "--out-md",
            str(tmp_path / "POOL.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_external_pool_intake_status"] == "massivefold_external_pool_intake_ready"
    assert summary["massivefold_pool_count"] == 3
    assert summary["ready_pool_count"] == 3
    assert summary["rna_hybrid_pool_count"] == 2
    assert summary["protein_complex_pool_count"] == 1
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["internal_prediction_blocked_count"] == 3
    assert summary["r2341_pool_present"] is True
    assert summary["r2345_pool_present"] is True
    assert summary["largest_model_set_id"] == "H2335_T335"
    assert summary["download_policy"] == "operator_explicit_download_required_no_automatic_tarball_fetch"

    rows = {row["model_set_id"]: row for row in payload["rows"]}
    assert rows["R2345"]["sequence_guard"] == (
        "ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only"
    )
    assert rows["R2345"]["competitive_proof_eligible"] == "False"
    assert rows["H2335_T335"]["internal_prediction_policy"] == "do_not_mark_as_internal_prediction"
    assert "downloads/H2335_T335_all_pdbs_MassiveFold.tar.gz" in rows["H2335_T335"]["download_path"]

    written_rows = _read_csv(tmp_path / "pool.csv")
    assert len(written_rows) == 3
    manifest = Path(rows["R2345"]["acquisition_manifest"])
    assert manifest.is_file()
    manifest_text = manifest.read_text(encoding="utf-8")
    assert "sha256sum" in manifest_text
    assert "competitive_proof_eligible: `False`" in manifest_text
    assert (tmp_path / "POOL.md").read_text(encoding="utf-8").startswith("# CASP17")


def test_massivefold_external_pool_intake_blocks_missing_organizer_notice(tmp_path: Path) -> None:
    args = mod.parse_args(
        [
            "--organizer-notice-packet-json",
            str(tmp_path / "missing_organizer.json"),
            "--out-dir",
            str(tmp_path / "external_pool"),
            "--out-json",
            str(tmp_path / "pool.json"),
            "--out-csv",
            str(tmp_path / "pool.csv"),
            "--out-md",
            str(tmp_path / "POOL.md"),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_external_pool_intake_status"] == (
        "blocked_organizer_notice_packet_missing"
    )
    assert payload["summary"]["massivefold_pool_count"] == 0
    assert payload["summary"]["competitive_proof_eligible_count"] == 0
