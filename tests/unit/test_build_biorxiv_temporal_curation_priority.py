from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_temporal_curation_priority(tmp_path: Path) -> None:
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
                "set1,gpcr_chembl50_full,gpcr,a,b,c,ADRB2,L2,eval,1,chembl_blind_adrb2_v1:Ki:pchembl=9.7,,,,,,,pending,",
                "set1,gpcr_core_full,gpcr,a,b,c,EGFR,L3,fit,1,literature_proxy_v2,,,,,,,pending,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    idp_csv = config_dir / "idp.csv"
    idp_csv.write_text(
        "\n".join(
            [
                "referenced_by_sets,task_id,release_manifest_json,config_json,holdout_name,representative_target_name,source_kind,pdb_path,publication_year,benchmark_inclusion_date,corrected_label_freeze_date,provenance_source,curation_status,notes",
                "set_temporal_core_blind,idp_release_current,a,b,alpha,alpha,pdb,/tmp/a.pdb,,,,pending,",
                "set_temporal_core_blind,idp_release_current,a,b,beta,beta,synthetic,,,,,pending,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_json = runs_dir / "priority.json"
    out_csv = runs_dir / "priority.csv"
    out_md = runs_dir / "priority.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_temporal_curation_priority.py"),
            "--ligand-csv",
            str(ligand_csv),
            "--idp-csv",
            str(idp_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["group_count"] >= 3
    assert out_md.exists()
    with out_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    chembl_rows = [row for row in rows if row["source_family"] == "chembl_blind_adrb2_v1"]
    assert chembl_rows
