from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_and_apply_biorxiv_temporal_source_normalization(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    config_dir.mkdir()
    runs_dir.mkdir()

    ligand_csv = config_dir / "ligand.csv"
    ligand_csv.write_text(
        "\n".join(
            [
                "set_id,task_id,domain,profile_json,ligand_csv,eval_split_csv,target,ligand_id,role,is_binder,source_label,source_release,provenance_date,publication_year,release_date,provenance_granularity,provenance_url,curation_status,notes",
                "set1,gpcr_core_full,gpcr,a,b,c,ADRB2,L1,eval,1,chembl_blind_adrb2_v1:Ki:pchembl=10.0,,,,,,,pending,",
                "set1,gpcr_core_full,gpcr,a,b,c,EGFR,L2,fit,1,literature_proxy_v2,,,,,,,pending,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    norm_csv = config_dir / "norm.csv"
    norm_json = runs_dir / "norm.json"
    norm_md = runs_dir / "norm.md"
    sanity_md = runs_dir / "sanity.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_temporal_source_normalization.py"),
            "--ligand-csv",
            str(ligand_csv),
            "--out-csv",
            str(norm_csv),
            "--out-json",
            str(norm_json),
            "--out-md",
            str(norm_md),
            "--sanity-md",
            str(sanity_md),
        ],
        check=True,
    )

    rows = list(csv.DictReader(norm_csv.open(encoding="utf-8", newline="")))
    assert any(row["source_family"] == "chembl_blind_adrb2_v1" for row in rows)
    assert norm_md.exists()
    assert sanity_md.exists()

    out_csv = config_dir / "ligand_out.csv"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/apply_biorxiv_temporal_source_normalization.py"),
            "--ligand-csv",
            str(ligand_csv),
            "--normalization-csv",
            str(norm_csv),
            "--out-csv",
            str(out_csv),
        ],
        check=True,
    )

    out_rows = list(csv.DictReader(out_csv.open(encoding="utf-8", newline="")))
    chembl = out_rows[0]
    assert chembl["source_release"] == "chembl_blind_adrb2_v1"
    assert chembl["curation_status"] == "release_prefilled_pending_date"
    assert chembl["provenance_granularity"] == "source_family"
