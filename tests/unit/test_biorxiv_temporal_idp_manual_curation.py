from __future__ import annotations

import csv
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_temporal_idp_manual_curation(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    config_dir.mkdir()
    runs_dir.mkdir()

    provenance_csv = config_dir / "idp_provenance.csv"
    provenance_csv.write_text(
        "\n".join(
            [
                "referenced_by_sets,task_id,release_manifest_json,config_json,holdout_name,representative_target_name,source_kind,pdb_path,publication_year,benchmark_inclusion_date,corrected_label_freeze_date,provenance_source,curation_status,notes,provenance_granularity",
                "set1,idp_release_current,runs/release.json,config/c.json,alpha_synuclein_full,alpha_synuclein_full,pdb,data/a.pdb,2024,2026-03-21,2026-03-21,runs/release.json,item_publication,item ready,item_publication",
                "set1,idp_release_current,runs/release.json,config/c.json,fus_lcd,fus_lcd,pdb,data/fus.pdb,,2026-03-21,2026-03-21,runs/release.json,dataset_release_locally_anchored,dataset only,dataset_release",
                "set1,idp_release_current,runs/release.json,config/c.json,amyloid_beta_40,amyloid_beta_40,synthetic,,,2026-03-21,2026-03-21,runs/release.json,dataset_release_locally_anchored,dataset only,dataset_release",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    helper_csv = runs_dir / "idp_helper.csv"
    helper_csv.write_text(
        "\n".join(
            [
                "holdout_name,source_kind,pdb_path,eval_corrected_csv,anchor_source,citation_publication_year,pdb_header_date,auto_item_ready_candidate,citation,notes",
                "fus_lcd,pdb,data/fus.pdb,runs/fus_eval.csv,literature_inferred_partial,,2025-08-01,no,FUS citation,fus note",
                "amyloid_beta_40,synthetic,,runs/ab40_eval.csv,branch_family_provisional,, ,no,Generated from branch-conditioned family prior.,ab40 note",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = runs_dir / "idp_manual"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_temporal_idp_manual_curation.py"),
            "--provenance-csv",
            str(provenance_csv),
            "--helper-csv",
            str(helper_csv),
            "--out-dir",
            str(out_dir),
        ],
        check=True,
    )

    pdb_csv = out_dir / "biorxiv_temporal_idp_pdb_manual_facts_current.csv"
    synthetic_csv = out_dir / "biorxiv_temporal_idp_synthetic_manual_facts_current.csv"
    readme = out_dir / "README.md"
    assert pdb_csv.exists()
    assert synthetic_csv.exists()
    assert readme.exists()

    pdb_rows = list(csv.DictReader(pdb_csv.open(encoding="utf-8", newline="")))
    synthetic_rows = list(csv.DictReader(synthetic_csv.open(encoding="utf-8", newline="")))
    assert len(pdb_rows) == 1
    assert pdb_rows[0]["holdout_name"] == "fus_lcd"
    assert pdb_rows[0]["manual_status"] == "pending"
    assert pdb_rows[0]["citation_hint"] == "FUS citation"
    assert len(synthetic_rows) == 1
    assert synthetic_rows[0]["holdout_name"] == "amyloid_beta_40"
