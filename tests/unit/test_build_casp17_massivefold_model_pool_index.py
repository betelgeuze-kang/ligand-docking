from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_massivefold_model_pool_index as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_massivefold_model_pool_index_parses_protocols_and_extract_manifest(tmp_path: Path) -> None:
    listing = tmp_path / "pool/extracted_models/tarball_listing.txt"
    listing.parent.mkdir(parents=True, exist_ok=True)
    members = [
        "R2341_all_cifs/",
        "R2341_all_cifs/Model_1_af3_basic_af3_seed_101_sample_0_pred_10.cif",
        "R2341_all_cifs/Model_2_af3_woTemplates_af3_seed_102_sample_1_pred_11.cif",
        "R2341_all_cifs/Model_3_af3_woUnpaired_af3_seed_103_sample_2_pred_12.cif",
        "R2341_all_cifs/Model_4_af3_woPaired_af3_seed_104_sample_3_pred_13.cif",
        "R2341_all_cifs/Model_5_af3_woUnpaired_woPaired_af3_seed_105_sample_4_pred_14.cif",
        "R2341_all_cifs/Model_6_af3_woUnpaired_woTemplates_af3_seed_106_sample_0_pred_15.cif",
        "R2341_all_cifs/Model_7_af3_woPaired_woTemplates_af3_seed_107_sample_1_pred_16.cif",
        "R2341_all_cifs/Model_8_af3_woUnpaired_woPaired_woTemplates_af3_seed_108_sample_2_pred_17.cif",
        "R2341_all_cifs/notes.txt",
    ]
    listing.write_text("\n".join(members) + "\n", encoding="utf-8")
    extracted = listing.parent / "R2341_all_cifs/Model_1_af3_basic_af3_seed_101_sample_0_pred_10.cif"
    extracted.parent.mkdir(parents=True, exist_ok=True)
    extracted.write_text("data_model\n", encoding="utf-8")

    acquisition_json = tmp_path / "acquisition.json"
    _write_json(
        acquisition_json,
        {
            "summary": {
                "massivefold_acquisition_verification_status": (
                    "awaiting_massivefold_external_pool_acquisition"
                )
            },
            "rows": [
                {
                    "queue_rank": 1,
                    "primary_target_id": "R2341",
                    "model_set_id": "R2341",
                    "pool_verification_status": "verified_for_external_rerank_intake",
                    "download_path": str(tmp_path / "pool/downloads/R2341.tar.gz"),
                    "listing_path": str(listing),
                    "sha256_actual": "abc123",
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--acquisition-verification-json",
            str(acquisition_json),
            "--target-id",
            "R2341",
            "--extract-per-bucket",
            "1",
            "--out-dir",
            str(tmp_path / "index"),
            "--out-json",
            str(tmp_path / "index.json"),
            "--out-csv",
            str(tmp_path / "index.csv"),
            "--out-md",
            str(tmp_path / "INDEX.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["massivefold_model_pool_index_status"] == (
        "massivefold_model_pool_index_ready_extract_pending"
    )
    assert summary["model_count"] == 8
    assert summary["protocol_bucket_count"] == 8
    assert summary["selected_extract_count"] == 8
    assert summary["selected_extracted_count"] == 1
    assert summary["selected_extract_pending_count"] == 7
    assert summary["basic_count"] == 1
    assert summary["wo_templates_count"] == 1
    assert summary["wo_unpaired_wo_paired_wo_templates_count"] == 1
    assert summary["tarball_sha256"] == "abc123"

    rows = payload["rows"]
    assert rows[0]["rerank_bucket"] == "basic"
    assert rows[0]["selected_for_balanced_extract"] == "True"
    assert rows[0]["extraction_status"] == "extracted"
    assert rows[7]["rerank_bucket"] == "woUnpaired_woPaired_woTemplates"
    assert len(_read_csv(tmp_path / "index.csv")) == 8
    manifest = Path(summary["extraction_manifest"])
    assert manifest.is_file()
    assert len(manifest.read_text(encoding="utf-8").splitlines()) == 8
    assert "models/protocols: `8/8`" in (tmp_path / "INDEX.md").read_text(encoding="utf-8")


def test_massivefold_model_pool_index_parses_afm_and_cf_multimer_pdb_names(tmp_path: Path) -> None:
    listing = tmp_path / "pool/extracted_models/tarball_listing.txt"
    listing.parent.mkdir(parents=True, exist_ok=True)
    listing.write_text(
        "\n".join(
            [
                "H1311_all_pdbs/Model_644_afm_basic_model_1_multimer_v2_pred_34.pdb",
                "H1311_all_pdbs/Model_206_cf_woTemplates_model_5_multimer_v3_pred_58.pdb",
                "H1311_all_pdbs/Model_879_afm_dropout_full_model_5_multimer_v3_pred_47.pdb",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    acquisition_json = tmp_path / "acquisition.json"
    _write_json(
        acquisition_json,
        {
            "rows": [
                {
                    "queue_rank": 1,
                    "primary_target_id": "H1311",
                    "model_set_id": "H1311_T327",
                    "pool_verification_status": "verified_for_external_rerank_intake",
                    "download_path": str(tmp_path / "pool/downloads/H1311.tar.gz"),
                    "listing_path": str(listing),
                    "sha256_actual": "def456",
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--acquisition-verification-json",
            str(acquisition_json),
            "--target-id",
            "H1311",
            "--extract-per-bucket",
            "1",
            "--out-dir",
            str(tmp_path / "index"),
        ]
    )

    payload = mod.build_payload(args)

    rows = payload["rows"]
    assert payload["summary"]["model_count"] == 3
    assert payload["summary"]["protocol_bucket_count"] == 3
    assert payload["summary"]["selected_extract_count"] == 3
    assert rows[0]["model_serial"] == 644
    assert rows[0]["af_engine"] == "AFM"
    assert rows[0]["af_protocol"] == "afm_basic_multimer_v2"
    assert rows[0]["sample"] == 1
    assert rows[0]["pred"] == 34
    assert rows[0]["rerank_bucket"] == "afm_basic_v2"
    assert rows[1]["af_engine"] == "CF"
    assert rows[1]["rerank_bucket"] == "cf_woTemplates_v3"
    assert rows[2]["rerank_bucket"] == "afm_dropout_full_v3"


def test_massivefold_model_pool_index_blocks_unverified_pool(tmp_path: Path) -> None:
    acquisition_json = tmp_path / "acquisition.json"
    _write_json(
        acquisition_json,
        {
            "rows": [
                {
                    "primary_target_id": "R2341",
                    "model_set_id": "R2341",
                    "pool_verification_status": "open_tarball_download_required",
                }
            ]
        },
    )
    args = mod.parse_args(
        [
            "--acquisition-verification-json",
            str(acquisition_json),
            "--target-id",
            "R2341",
            "--out-dir",
            str(tmp_path / "index"),
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_model_pool_index_status"] == "blocked_target_pool_not_verified"
    assert payload["summary"]["model_count"] == 0
