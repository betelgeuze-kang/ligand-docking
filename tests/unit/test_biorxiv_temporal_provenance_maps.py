from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_and_check_biorxiv_temporal_provenance_maps(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    config_dir.mkdir()
    runs_dir.mkdir()

    (config_dir / "gpcr_profile.json").write_text(
        json.dumps(
            {
                "ligand_csv": str(config_dir / "gpcr_ligands.csv"),
                "eval_split_csv": str(config_dir / "gpcr_splits.csv"),
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "gpcr_ligands.csv").write_text(
        "target,ligand_id,reference_binding_kcal_mol,is_binder,source\nADRB2,L1,-8.0,1,chembl\n",
        encoding="utf-8",
    )
    (config_dir / "gpcr_splits.csv").write_text(
        "target,ligand_id,role\nADRB2,L1,eval\n",
        encoding="utf-8",
    )
    (config_dir / "idp_config.json").write_text(
        json.dumps(
            {
                "targets": [
                    {
                        "name": "alpha_synuclein_full",
                        "source": "pdb",
                        "pdb_path": "data/native/alpha.pdb",
                        "split_group": "alpha_synuclein_full",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (runs_dir / "idp_manifest.json").write_text(
        json.dumps({"config_json": str(config_dir / "idp_config.json")}),
        encoding="utf-8",
    )
    spec = {
        "frozen_references": {"idp_release_manifest_current": str(runs_dir / "idp_manifest.json")},
        "sets": [
            {
                "set_id": "set_temporal_core_blind",
                "tasks": [
                    {
                        "task_id": "gpcr_core_full",
                        "domain": "gpcr",
                        "profile_json": str(config_dir / "gpcr_profile.json"),
                    },
                    {
                        "task_id": "idp_release_current",
                        "kind": "idp_reference_current_full",
                    },
                ],
            }
        ],
    }
    (config_dir / "temporal_spec.json").write_text(json.dumps(spec), encoding="utf-8")

    ligand_csv = config_dir / "ligand_provenance.csv"
    idp_csv = config_dir / "idp_provenance.csv"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_biorxiv_temporal_provenance_templates.py"),
            "--set-spec-json",
            str(config_dir / "temporal_spec.json"),
            "--ligand-out-csv",
            str(ligand_csv),
            "--idp-out-csv",
            str(idp_csv),
        ],
        check=True,
    )

    with ligand_csv.open(encoding="utf-8", newline="") as handle:
        ligand_rows = list(csv.DictReader(handle))
    assert ligand_rows[0]["task_id"] == "gpcr_core_full"
    assert ligand_rows[0]["source_label"] == "chembl"
    assert ligand_rows[0]["curation_status"] == "pending"

    with idp_csv.open(encoding="utf-8", newline="") as handle:
        idp_rows = list(csv.DictReader(handle))
    assert idp_rows[0]["holdout_name"] == "alpha_synuclein_full"
    assert "provenance_granularity" in idp_rows[0]

    ligand_rows[0]["source_release"] = "ChEMBL_35"
    ligand_rows[0]["publication_year"] = "2024"
    ligand_rows[0]["provenance_granularity"] = "item_publication"
    with ligand_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ligand_rows[0].keys())
        writer.writeheader()
        writer.writerows(ligand_rows)

    coverage_json = runs_dir / "coverage.json"
    coverage_md = runs_dir / "coverage.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/check_biorxiv_temporal_provenance_maps.py"),
            "--ligand-csv",
            str(ligand_csv),
            "--idp-csv",
            str(idp_csv),
            "--out-json",
            str(coverage_json),
            "--out-md",
            str(coverage_md),
        ],
        check=True,
    )

    coverage = json.loads(coverage_json.read_text(encoding="utf-8"))
    assert coverage["ligand"]["ready_count"] == 1
    assert coverage["ligand"]["item_ready_count"] == 1
    assert coverage["ligand"]["dataset_ready_count"] == 0
    assert coverage["idp"]["missing_count"] == 1
    assert coverage["idp"]["item_ready_count"] == 0
    assert coverage["idp"]["dataset_ready_count"] == 0
    assert coverage_md.exists()
