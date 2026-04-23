from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_apply_biorxiv_temporal_item_provenance_facts(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    config_dir.mkdir()
    runs_dir.mkdir()

    provenance_csv = config_dir / "ligand_provenance.csv"
    provenance_csv.write_text(
        "\n".join(
            [
                "set_id,task_id,domain,profile_json,ligand_csv,eval_split_csv,target,ligand_id,role,is_binder,source_label,source_release,provenance_date,publication_year,release_date,provenance_granularity,provenance_url,curation_status,notes",
                "set1,gpcr_chembl50_full,gpcr,config/p.json,config/l.csv,config/s.csv,ADRB2,CHEMBL1,eval,1,chembl_blind_adrb2_v1:Ki,chembl_blind_adrb2_v1,,,2026-03-11,dataset_release,runs/dataset.json,dataset_release_locally_anchored,seed",
                "set1,gpcr_chembl50_full,gpcr,config/p.json,config/l.csv,config/s.csv,ADRB2,LIG2,eval,0,other,other,,,2026-03-11,dataset_release,runs/dataset.json,dataset_release_locally_anchored,seed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    facts_csv = runs_dir / "chembl_item_facts.csv"
    facts_csv.write_text(
        "\n".join(
            [
                "source_release,ligand_id,publication_year,provenance_date,release_date,provenance_granularity,provenance_url,curation_status,notes",
                "chembl_blind_adrb2_v1,CHEMBL1,2012,2012,,item_publication,https://example.org/doc/1,item_publication_chembl_api,chembl item anchor",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_json = runs_dir / "item_apply.json"
    out_md = runs_dir / "item_apply.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/apply_biorxiv_temporal_item_provenance_facts.py"),
            "--provenance-csv",
            str(provenance_csv),
            "--facts-csv",
            str(facts_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
    )

    with provenance_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["publication_year"] == "2012"
    assert rows[0]["provenance_date"] == "2012"
    assert rows[0]["provenance_granularity"] == "item_publication"
    assert rows[0]["provenance_url"] == "https://example.org/doc/1"
    assert rows[0]["curation_status"] == "item_publication_chembl_api"
    assert "chembl item anchor" in rows[0]["notes"]
    assert rows[1]["publication_year"] == ""

    summary = json.loads(out_json.read_text(encoding="utf-8"))
    assert summary["fact_row_count"] == 1
    assert summary["matched_row_count"] == 1
    assert summary["updated_row_count"] == 1
    assert out_md.exists()
