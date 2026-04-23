from __future__ import annotations

import csv
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_temporal_family_helpers(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    config_dir.mkdir()
    runs_dir.mkdir()

    ligand_csv = config_dir / "ligand.csv"
    ligand_csv.write_text(
        "\n".join(
            [
                "set_id,task_id,domain,profile_json,ligand_csv,eval_split_csv,target,ligand_id,role,is_binder,source_label,source_release,provenance_date,publication_year,release_date,provenance_granularity,provenance_url,curation_status,notes",
                "set1,gpcr_core_full,gpcr,a,b,c,EGFR,erlotinib,fit,1,literature_proxy_v2,literature_proxy_v2,,,,dataset_release,,release_prefilled_pending_date,",
                "set1,ion_trpv1_chembl20_full,ion_channel,a,b,c,EGFR,erlotinib,fit,1,literature_proxy_v2,literature_proxy_v2,,,,dataset_release,,release_prefilled_pending_date,",
                "set1,gpcr_core_full,gpcr,a,b,c,ADRB2,carazolol,eval,1,gpcr_blind_proxy_v1,gpcr_blind_proxy_v1,,,,dataset_release,,release_prefilled_pending_date,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = runs_dir / "helpers"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_temporal_family_helpers.py"),
            "--ligand-csv",
            str(ligand_csv),
            "--out-dir",
            str(out_dir),
        ],
        check=True,
    )

    literature_unique = out_dir / "biorxiv_temporal_helper_literature_proxy_v2_unique_ligands_current.csv"
    gpcr_rowmap = out_dir / "biorxiv_temporal_helper_gpcr_blind_proxy_v1_rowmap_current.csv"
    readme = out_dir / "README.md"
    assert literature_unique.exists()
    assert gpcr_rowmap.exists()
    assert readme.exists()

    rows = list(csv.DictReader(literature_unique.open(encoding="utf-8", newline="")))
    assert rows[0]["ligand_id"] == "erlotinib"
    assert "gpcr_core_full" in rows[0]["tasks"]
