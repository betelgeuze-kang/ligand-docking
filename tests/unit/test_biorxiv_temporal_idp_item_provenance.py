from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_and_apply_biorxiv_temporal_idp_item_provenance(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    data_dir = tmp_path / "data/native/idp_llps"
    config_dir.mkdir(parents=True)
    runs_dir.mkdir()
    data_dir.mkdir(parents=True)

    provenance_csv = config_dir / "idp_provenance.csv"
    provenance_csv.write_text(
        "\n".join(
            [
                "referenced_by_sets,task_id,release_manifest_json,config_json,holdout_name,representative_target_name,source_kind,pdb_path,publication_year,benchmark_inclusion_date,corrected_label_freeze_date,provenance_source,curation_status,notes,provenance_granularity",
                f"set1,idp_release_current,runs/release.json,config/c.json,alpha_synuclein_full,alpha_synuclein_full,pdb,{data_dir / 'alpha.pdb'},,2026-03-21,2026-03-21,runs/release.json,dataset_release_locally_anchored,seed,dataset_release",
                "set1,idp_release_current,runs/release.json,config/c.json,amyloid_beta_40,amyloid_beta_40,synthetic,,,2026-03-21,2026-03-21,runs/release.json,dataset_release_locally_anchored,seed,dataset_release",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (data_dir / "alpha.pdb").write_text(
        "\n".join(
            [
                "HEADER                                            01-AUG-25                     ",
                "TITLE     ALPHAFOLD MONOMER V2.0 PREDICTION FOR ALPHA-SYNUCLEIN",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    alpha_targets = runs_dir / "fold1_alpha_eval.csv"
    alpha_targets.write_text(
        "\n".join(
            [
                "target,source,observable_anchor",
                "\"alpha_synuclein_full\",pdb,\"{'source': 'literature_compilation_partial', 'provenance': {'citation': 'J. Chem. Inf. Model. 2024 review snippet reported experimental Rg range.', 'notes': 'broad range'}}\"",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ab40_targets = runs_dir / "fold2_ab40_eval.csv"
    ab40_targets.write_text(
        "\n".join(
            [
                "target,source,observable_anchor",
                "\"amyloid_beta_40\",synthetic,\"{'source': 'branch_family_provisional', 'provenance': {'citation': 'Generated from branch-conditioned family prior.', 'notes': 'auto-generated'}}\"",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_json = runs_dir / "release_manifest.json"
    manifest_json.write_text(
        json.dumps(
            {
                "fold_artifacts": [
                    {"holdout": "alpha_synuclein_full", "eval_corrected_csv": str(alpha_targets)},
                    {"holdout": "amyloid_beta_40", "eval_corrected_csv": str(ab40_targets)},
                ]
            }
        ),
        encoding="utf-8",
    )

    helper_csv = runs_dir / "idp_helper.csv"
    helper_json = runs_dir / "idp_helper.json"
    helper_md = runs_dir / "idp_helper.md"
    facts_csv = runs_dir / "idp_facts.csv"
    facts_json = runs_dir / "idp_facts.json"
    facts_md = runs_dir / "idp_facts.md"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_temporal_idp_item_helpers.py"),
            "--provenance-csv",
            str(provenance_csv),
            "--release-manifest-json",
            str(manifest_json),
            "--out-helper-csv",
            str(helper_csv),
            "--out-helper-json",
            str(helper_json),
            "--out-helper-md",
            str(helper_md),
            "--out-facts-csv",
            str(facts_csv),
            "--out-facts-json",
            str(facts_json),
            "--out-facts-md",
            str(facts_md),
        ],
        check=True,
    )

    with helper_csv.open(encoding="utf-8", newline="") as handle:
        helper_rows = list(csv.DictReader(handle))
    assert helper_rows[0]["holdout_name"] == "alpha_synuclein_full"
    assert helper_rows[0]["citation_publication_year"] == "2024"
    assert helper_rows[0]["pdb_header_date"] == "2025-08-01"
    assert helper_rows[1]["citation_publication_year"] == ""

    with facts_csv.open(encoding="utf-8", newline="") as handle:
        fact_rows = list(csv.DictReader(handle))
    assert len(fact_rows) == 1
    assert fact_rows[0]["holdout_name"] == "alpha_synuclein_full"
    assert fact_rows[0]["publication_year"] == "2024"
    assert fact_rows[0]["provenance_granularity"] == "item_publication"

    apply_json = runs_dir / "idp_apply.json"
    apply_md = runs_dir / "idp_apply.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/apply_biorxiv_temporal_idp_item_provenance_facts.py"),
            "--provenance-csv",
            str(provenance_csv),
            "--facts-csv",
            str(facts_csv),
            "--out-json",
            str(apply_json),
            "--out-md",
            str(apply_md),
        ],
        check=True,
    )

    with provenance_csv.open(encoding="utf-8", newline="") as handle:
        updated_rows = list(csv.DictReader(handle))
    assert updated_rows[0]["publication_year"] == "2024"
    assert updated_rows[0]["provenance_granularity"] == "item_publication"
    assert updated_rows[0]["curation_status"] == "item_publication_prefilled"
    assert updated_rows[1]["publication_year"] == ""

    summary = json.loads(apply_json.read_text(encoding="utf-8"))
    assert summary["fact_row_count"] == 1
    assert summary["matched_row_count"] == 1
    assert summary["updated_row_count"] == 1
    assert helper_md.exists()
    assert facts_md.exists()
    assert apply_md.exists()


def test_apply_biorxiv_temporal_idp_item_provenance_overrides_manual_pending(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    config_dir.mkdir()
    runs_dir.mkdir()

    provenance_csv = config_dir / "idp_provenance.csv"
    provenance_csv.write_text(
        "\n".join(
            [
                "referenced_by_sets,task_id,release_manifest_json,config_json,holdout_name,representative_target_name,source_kind,pdb_path,publication_year,benchmark_inclusion_date,corrected_label_freeze_date,provenance_source,curation_status,notes,provenance_granularity",
                "set1,idp_release_current,runs/release.json,config/c.json,cmyc_tad_fragment,cmyc_tad_fragment,synthetic,,,2026-03-21,2026-03-21,runs/release.json,manual_item_curation_pending,seed,dataset_release",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    facts_csv = runs_dir / "idp_facts.csv"
    facts_csv.write_text(
        "\n".join(
            [
                "holdout_name,publication_year,provenance_granularity,provenance_source,curation_status,notes",
                "cmyc_tad_fragment,2012,item_publication,https://pmc.ncbi.nlm.nih.gov/articles/PMC3401448/,item_publication_curated_web,curated",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    apply_json = runs_dir / "idp_apply.json"
    apply_md = runs_dir / "idp_apply.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/apply_biorxiv_temporal_idp_item_provenance_facts.py"),
            "--provenance-csv",
            str(provenance_csv),
            "--facts-csv",
            str(facts_csv),
            "--out-json",
            str(apply_json),
            "--out-md",
            str(apply_md),
        ],
        check=True,
    )

    with provenance_csv.open(encoding="utf-8", newline="") as handle:
        updated_rows = list(csv.DictReader(handle))
    assert updated_rows[0]["publication_year"] == "2012"
    assert updated_rows[0]["provenance_granularity"] == "item_publication"
    assert updated_rows[0]["provenance_source"] == "https://pmc.ncbi.nlm.nih.gov/articles/PMC3401448/"
    assert updated_rows[0]["curation_status"] == "item_publication_curated_web"
    assert "curated" in updated_rows[0]["notes"]
