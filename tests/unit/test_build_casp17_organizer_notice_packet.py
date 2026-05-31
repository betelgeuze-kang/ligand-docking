from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_casp17_organizer_notice_packet_guards_r2345_and_massivefold(tmp_path: Path) -> None:
    links_csv = tmp_path / "CASP17-CAPRI_MF_links.csv"
    links_csv.write_text(
        "\n".join(
            [
                "R2341,ftp://files.plbs.fr:21211/CASP17-CAPRI/R2341_all_cifs_MassiveFold.tar.gz",
                "R2345,ftp://files.plbs.fr:21211/CASP17-CAPRI/R2345_all_cifs_MassiveFold.tar.gz",
                "H2335_T335,ftp://files.plbs.fr:21211/CASP17-CAPRI/H2335_T335_all_pdbs_MassiveFold.tar.gz",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    listing = tmp_path / "listing.txt"
    listing.write_text(
        "\n".join(
            [
                "-rw-r--r-- 1 ftp ftp 667779936 May 20 18:01 R2341_all_cifs_MassiveFold.tar.gz",
                "-rw-r--r-- 1 ftp ftp 245903877 May 22 14:25 R2345_all_cifs_MassiveFold.tar.gz",
                "-rw-r--r-- 1 ftp ftp 4192785208 May 29 17:10 H2335_T335_all_pdbs_MassiveFold.tar.gz",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "casp17/notice.json"
    out_csv = tmp_path / "casp17/notice.csv"
    out_md = tmp_path / "casp17/NOTICE.md"
    out_dir = tmp_path / "casp17/notices"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_organizer_notice_packet.py"),
            "--massivefold-links-csv",
            str(links_csv),
            "--ftp-listing-file",
            str(listing),
            "--no-network",
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    summary = payload["summary"]
    assert summary["organizer_notice_status"] == "organizer_notice_intake_ready"
    assert summary["r2345_first_request_status"] == "ignored_invalid_dna_t_in_rna_sequence"
    assert summary["r2345_replacement_request_status"] == "accepted_second_request_only"
    assert summary["massivefold_link_count"] == 3
    assert summary["massivefold_rna_hybrid_link_count"] == 2
    assert summary["massivefold_protein_complex_link_count"] == 1
    assert summary["massivefold_r2341_link_present"] is True
    assert summary["massivefold_r2345_link_present"] is True
    assert summary["massivefold_internal_prediction_policy"] == "do_not_mark_as_internal_prediction"
    assert summary["large_download_policy"] == "tarballs_not_downloaded_by_notice_packet"

    rows = {row["notice_id"]: row for row in payload["notice_rows"]}
    assert rows["organizer_notice_001"]["target_id"] == "R2345"
    assert rows["organizer_notice_001"]["action"] == "do_not_use_first_request_for_modeling_or_scoring"
    assert rows["organizer_notice_002"]["request_time_pacific"] == "11:30"

    model_rows = {row["model_set_id"]: row for row in payload["massivefold_rows"]}
    assert model_rows["R2341"]["bundle_format"] == "cif_bundle"
    assert model_rows["R2341"]["ftp_size_bytes"] == 667779936
    assert model_rows["H2335_T335"]["bundle_format"] == "pdb_cif_bundle"
    assert (out_dir / "R2345" / "NOTICE.md").exists()

    with out_csv.open("r", encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert {row["row_type"] for row in csv_rows} == {"organizer_notice", "massivefold_model_set"}
    md_text = out_md.read_text(encoding="utf-8")
    assert "R2345 first request" in md_text
    assert "MassiveFold Links" in md_text
