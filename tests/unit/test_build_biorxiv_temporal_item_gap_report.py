from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_temporal_item_gap_report(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    config_dir.mkdir()
    runs_dir.mkdir()

    ligand_csv = config_dir / "ligand.csv"
    ligand_csv.write_text(
        "\n".join(
            [
                "set_id,task_id,domain,profile_json,ligand_csv,eval_split_csv,target,ligand_id,role,is_binder,source_label,source_release,provenance_date,publication_year,release_date,provenance_granularity,provenance_url,curation_status,notes",
                "set1,gpcr_core_full,gpcr,config/p.json,config/l.csv,config/s.csv,ADRB2,CHEMBL1,eval,1,chembl,chembl_blind_adrb2_v1,2012,2012,,item_publication,https://example.org/doc/1,item_publication_chembl_api,ok",
                "set1,gpcr_core_full,gpcr,config/p.json,config/l.csv,config/s.csv,ADRB2,LIG2,eval,0,manual,gpcr_blind_proxy_v1,,,2026-03-10,dataset_release,https://example.org/dataset,dataset_release_locally_anchored,ok",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    idp_csv = config_dir / "idp.csv"
    idp_csv.write_text(
        "\n".join(
            [
                "referenced_by_sets,task_id,release_manifest_json,config_json,holdout_name,representative_target_name,source_kind,pdb_path,publication_year,benchmark_inclusion_date,corrected_label_freeze_date,provenance_source,curation_status,notes,provenance_granularity",
                "set1,idp_release_current,runs/m.json,config/c.json,alpha,alpha,pdb,data/native/a.pdb,,2026-03-21,2026-03-21,runs/m.json,dataset_release_locally_anchored,ok,dataset_release",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_json = runs_dir / "gap.json"
    out_csv = runs_dir / "gap.csv"
    out_md = runs_dir / "gap.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_temporal_item_gap_report.py"),
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

    summary = json.loads(out_json.read_text(encoding="utf-8"))
    assert summary["group_count"] == 2
    assert summary["ligand_group_count"] == 1
    assert summary["idp_group_count"] == 1

    with out_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["group_key"] == "gpcr_blind_proxy_v1"
    assert out_md.exists()
