from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_temporal_provenance_inventory(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    runs_dir = tmp_path / "runs"
    config_dir.mkdir()
    runs_dir.mkdir()

    (config_dir / "ligand_profile.json").write_text(
        json.dumps(
            {
                "ligand_csv": str(config_dir / "ligands.csv"),
                "eval_split_csv": str(config_dir / "splits.csv"),
                "leakage_ligand_meta_csv": str(config_dir / "ligand_meta.csv"),
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "ligands.csv").write_text(
        "target,ligand_id,source,publication_year\nA,L1,chembl,2024\n",
        encoding="utf-8",
    )
    (config_dir / "splits.csv").write_text("target,ligand_id,role\nA,L1,eval\n", encoding="utf-8")
    (config_dir / "ligand_meta.csv").write_text("ligand_id,smiles\nL1,CCO\n", encoding="utf-8")
    (runs_dir / "idp_manifest.json").write_text(
        json.dumps(
            {
                "generated_at_local": "2026-03-22T14:00:00+09:00",
                "config_json": str(config_dir / "idp_config.json"),
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "idp_config.json").write_text(
        json.dumps({"targets": [{"name": "alpha", "split_group": "alpha"}]}),
        encoding="utf-8",
    )
    spec = {
        "temporal_governance": {
            "dataset_level_freeze_sources": {
                "gpcr_core_full": str(config_dir / "ligand_profile.json"),
                "idp_release_current": str(runs_dir / "idp_manifest.json"),
            }
        }
    }
    (config_dir / "temporal_spec.json").write_text(json.dumps(spec), encoding="utf-8")

    out_json = runs_dir / "inventory.json"
    out_csv = runs_dir / "inventory.csv"
    out_md = runs_dir / "inventory.md"
    cmd = [
        "python3",
        str(ROOT / "tools/build_biorxiv_temporal_provenance_inventory.py"),
        "--set-spec-json",
        str(config_dir / "temporal_spec.json"),
        "--out-json",
        str(out_json),
        "--out-csv",
        str(out_csv),
        "--out-md",
        str(out_md),
    ]
    subprocess.run(cmd, check=True)

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["inspected_file_count"] >= 4
    assert payload["summary"]["item_level_ready_count"] >= 1
    assert payload["summary"]["dataset_level_only_count"] >= 1
    assert out_md.exists()

    with out_csv.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    ready_paths = {row["path"] for row in rows if row["readiness"] == "item_level_ready"}
    assert any("ligands.csv" in path for path in ready_paths)
