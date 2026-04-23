from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def test_build_curated_candidate_source_seed_ca2(tmp_path: Path) -> None:
    replacement_csv = tmp_path / "runs" / "ca2_packet_replacement_workbook_current.csv"
    target_csv = tmp_path / "config" / "real_drug_targets_blind_ca2_zn_v1.csv"
    _write_csv(
        replacement_csv,
        [
            "packet",
            "packet_step",
            "current_ligand_id",
        ],
        [
            ["core", "core_binder_01", "ca2_placeholder_binder_01"],
            ["ood", "ood_non_binder_03", "ca2_ood_nonbinder_03"],
        ],
    )
    _write_csv(
        target_csv,
        ["target", "native_pdb_path", "pdb_id"],
        [["CARBONIC_ANHYDRASE_2_ZN_BLIND", "data/public_structures/1CA2.pdb", "1CA2"]],
    )
    out_json = tmp_path / "runs" / "ca2_curated_candidate_source_seed_current.json"
    out_csv = tmp_path / "runs" / "ca2_curated_candidate_source_seed_current.csv"
    out_md = tmp_path / "runs" / "ca2_curated_candidate_source_seed_current.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_curated_candidate_source_seed.py"),
            "--family",
            "ca2",
            "--replacement-csv",
            str(replacement_csv),
            "--target-csv",
            str(target_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=tmp_path,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["assigned_candidate_count"] == 2
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert rows[0]["candidate_ligand_name"] == "acetazolamide"
    assert rows[1]["candidate_ligand_name"] == "caffeine"
    assert rows[0]["target_anchor_pdb_id"] == "1CA2"


def test_build_curated_candidate_source_seed_pxr(tmp_path: Path) -> None:
    replacement_csv = tmp_path / "runs" / "pxr_packet_replacement_workbook_current.csv"
    target_csv = tmp_path / "config" / "real_drug_targets_blind_pxr_nr1i2_v1.csv"
    _write_csv(
        replacement_csv,
        [
            "packet",
            "packet_step",
            "current_ligand_id",
        ],
        [
            ["core", "core_fit_binder_01", "pxr_fit_ligand_01"],
            ["ood", "ood_eval_non_binder_02", "pxr_ood_decoy_02"],
        ],
    )
    _write_csv(
        target_csv,
        ["target", "native_pdb_path", "pdb_id"],
        [["PXR_NR1I2_BLIND", "data/native/o75469.pdb", "O75469"]],
    )
    out_json = tmp_path / "runs" / "pxr_curated_candidate_source_seed_current.json"
    out_csv = tmp_path / "runs" / "pxr_curated_candidate_source_seed_current.csv"
    out_md = tmp_path / "runs" / "pxr_curated_candidate_source_seed_current.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_curated_candidate_source_seed.py"),
            "--family",
            "pxr",
            "--replacement-csv",
            str(replacement_csv),
            "--target-csv",
            str(target_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=tmp_path,
    )
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["assigned_candidate_count"] == 2
    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert rows[0]["candidate_ligand_name"] == "hyperforin"
    assert rows[1]["candidate_ligand_name"] == "ibuprofen"
    assert rows[0]["target_anchor_pdb_id"] == "O75469"
