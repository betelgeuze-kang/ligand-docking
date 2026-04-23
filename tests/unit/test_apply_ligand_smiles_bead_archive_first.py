from __future__ import annotations

from pathlib import Path

from tools.apply_ligand_smiles_bead_archive_first import apply_manifest


def test_apply_ligand_smiles_bead_archive_first_moves_target_specific_caches(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    archive_root = runs / "archive" / "ligand_smiles"

    (runs / "ligand_smiles_bead_cache.json").write_text("{}", encoding="utf-8")
    target_cache = runs / "ligand_smiles_bead_cache_blind_gpcr_adrb2_v1.json"
    target_cache.write_text("{}", encoding="utf-8")

    manifest = {
        "rows": [
            {
                "filename": "ligand_smiles_bead_cache.json",
                "classification": "shared_default_cache",
                "recommended_disposition": "keep_in_active_root",
                "size_mb": 0.01,
            },
            {
                "filename": target_cache.name,
                "classification": "target_specific_cache",
                "recommended_disposition": "archive_first",
                "size_mb": 0.01,
            },
        ]
    }

    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        payload = apply_manifest(manifest, archive_root=str(archive_root))
    finally:
        os.chdir(cwd)

    assert payload["summary"]["status"] == "ligand_smiles_bead_archive_first_apply_report_ready"
    assert payload["summary"]["applied_row_count"] == 1
    assert (runs / "ligand_smiles_bead_cache.json").exists()
    assert not target_cache.exists()
    assert (archive_root / target_cache.name).exists()

