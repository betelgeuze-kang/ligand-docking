from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_temporal_idp_synthetic_progress(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    config_dir.mkdir()
    runs_dir.mkdir()

    idp_csv = config_dir / "idp.csv"
    idp_csv.write_text(
        "\n".join(
            [
                "referenced_by_sets,task_id,release_manifest_json,config_json,holdout_name,representative_target_name,source_kind,pdb_path,publication_year,benchmark_inclusion_date,corrected_label_freeze_date,provenance_source,curation_status,notes,provenance_granularity",
                "set1,idp_release_current,runs/m.json,config/c.json,ddx4_n1,ddx4_n1,synthetic,,2015,2026-03-21,2026-03-21,https://example.org/ddx4,item_publication_curated_web,ok,item_publication",
                "set1,idp_release_current,runs/m.json,config/c.json,ash1_idr_fragment,ash1_idr_fragment,synthetic,,,2026-03-21,2026-03-21,runs/m.json,dataset_release_locally_anchored,ok,dataset_release",
                "set1,idp_release_current,runs/m.json,config/c.json,fus_lcd,fus_lcd,pdb,/tmp/fus.pdb,2019,2026-03-21,2026-03-21,https://example.org/fus,item_publication_curated_web,ok,item_publication",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_json = runs_dir / "synthetic.json"
    out_csv = runs_dir / "synthetic.csv"
    out_md = runs_dir / "synthetic.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_temporal_idp_synthetic_progress.py"),
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
    assert summary["synthetic_row_count"] == 2
    assert summary["item_ready_count"] == 1
    assert summary["dataset_ready_count"] == 1

    with out_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["holdout_name"] == "ddx4_n1"
    assert rows[1]["status"] == "dataset_ready"
    assert out_md.exists()
