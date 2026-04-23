from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_temporal_idp_remaining_policy(tmp_path: Path) -> None:
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
                "set1,idp_release_current,runs/m.json,config/c.json,tau_2n4r_fragment,tau_2n4r_fragment,synthetic,,,2026-03-21,2026-03-21,runs/m.json,manual_item_curation_fragment_anchor_missing,frag,dataset_release",
                "set1,idp_release_current,runs/m.json,config/c.json,prion_like_polyq_control,prion_like_polyq_control,synthetic,,,2026-03-21,2026-03-21,runs/m.json,dataset_control_policy_current,control,dataset_release",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_json = runs_dir / "remaining.json"
    out_csv = runs_dir / "remaining.csv"
    out_md = runs_dir / "remaining.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_temporal_idp_remaining_policy.py"),
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
    assert summary["remaining_count"] == 2
    assert summary["policy_counts"]["fragment_anchor_missing"] == 1
    assert summary["policy_counts"]["intentional_dataset_control"] == 1

    with out_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["holdout_name"] == "tau_2n4r_fragment"
    assert rows[1]["policy_label"] == "intentional_dataset_control"
    assert out_md.exists()
