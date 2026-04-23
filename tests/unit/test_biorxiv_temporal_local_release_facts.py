from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_apply_biorxiv_temporal_local_release_facts(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    config_dir.mkdir()
    runs_dir.mkdir()

    provenance_csv = config_dir / "ligand_provenance.csv"
    provenance_csv.write_text(
        "\n".join(
            [
                "set_id,task_id,domain,profile_json,ligand_csv,eval_split_csv,target,ligand_id,role,is_binder,source_label,source_release,provenance_date,publication_year,release_date,provenance_granularity,provenance_url,curation_status,notes",
                "set1,gpcr_core_full,gpcr,config/p.json,config/l.csv,config/s.csv,ADRB2,L1,eval,1,gpcr_blind_proxy_v1,gpcr_blind_proxy_v1,,,,dataset_release,,release_prefilled_pending_date,seed",
                "set1,gpcr_core_full,gpcr,config/p.json,config/l.csv,config/s.csv,ADRB2,L2,eval,0,other,other,,,,dataset_release,,release_prefilled_pending_date,seed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    facts_csv = config_dir / "local_release_facts.csv"
    facts_csv.write_text(
        "\n".join(
            [
                "source_release,provenance_date,publication_year,release_date,provenance_granularity,provenance_url,curation_status,notes",
                "gpcr_blind_proxy_v1,,,2026-03-10,dataset_release,runs/example_summary.json,dataset_release_locally_anchored,local anchor",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_json = runs_dir / "apply.json"
    out_md = runs_dir / "apply.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/apply_biorxiv_temporal_local_release_facts.py"),
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
    assert rows[0]["release_date"] == "2026-03-10"
    assert rows[0]["provenance_url"] == "runs/example_summary.json"
    assert rows[0]["curation_status"] == "dataset_release_locally_anchored"
    assert "local anchor" in rows[0]["notes"]
    assert rows[1]["release_date"] == ""

    summary = json.loads(out_json.read_text(encoding="utf-8"))
    assert summary["matched_source_count"] == 1
    assert summary["matched_row_count"] == 1
    assert summary["updated_row_count"] == 1
    assert out_md.exists()
