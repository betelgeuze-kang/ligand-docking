from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_apply_biorxiv_temporal_idp_local_release_facts(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    config_dir.mkdir()
    runs_dir.mkdir()

    provenance_csv = config_dir / "idp_provenance.csv"
    provenance_csv.write_text(
        "\n".join(
            [
                "referenced_by_sets,task_id,release_manifest_json,config_json,holdout_name,representative_target_name,source_kind,pdb_path,publication_year,benchmark_inclusion_date,corrected_label_freeze_date,provenance_granularity,provenance_source,curation_status,notes",
                    "set1,idp_release_current,runs/m.json,config/c.json,alpha_synuclein_full,alpha_synuclein_full,pdb,data/native/a.pdb,,,,,,pending,seed",
                    "set1,idp_release_current,runs/m.json,config/c.json,amyloid_beta_40,amyloid_beta_40,synthetic,,,,,,,pending,seed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    facts_csv = config_dir / "idp_local_release_facts.csv"
    facts_csv.write_text(
        "\n".join(
            [
                "source_kind,publication_year,benchmark_inclusion_date,corrected_label_freeze_date,provenance_granularity,provenance_source,curation_status,notes",
                "pdb,,2026-03-21,2026-03-21,dataset_release,runs/release_manifest.json,dataset_release_locally_anchored,pdb anchor",
                "synthetic,,2026-03-21,2026-03-21,dataset_release,runs/release_manifest.json,dataset_release_locally_anchored,synthetic anchor",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_json = runs_dir / "idp_apply.json"
    out_md = runs_dir / "idp_apply.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/apply_biorxiv_temporal_idp_local_release_facts.py"),
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
    assert rows[0]["benchmark_inclusion_date"] == "2026-03-21"
    assert rows[0]["corrected_label_freeze_date"] == "2026-03-21"
    assert rows[0]["provenance_granularity"] == "dataset_release"
    assert rows[0]["provenance_source"] == "runs/release_manifest.json"
    assert rows[0]["curation_status"] == "dataset_release_locally_anchored"
    assert "pdb anchor" in rows[0]["notes"]
    assert rows[1]["provenance_source"] == "runs/release_manifest.json"

    summary = json.loads(out_json.read_text(encoding="utf-8"))
    assert summary["matched_key_count"] == 2
    assert summary["matched_row_count"] == 2
    assert summary["updated_row_count"] == 2
    assert out_md.exists()
