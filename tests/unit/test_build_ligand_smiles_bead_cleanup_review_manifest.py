from __future__ import annotations

from pathlib import Path

from tools.build_ligand_smiles_bead_cleanup_review_manifest import build_payload


def test_build_ligand_smiles_bead_cleanup_review_manifest(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    config = tmp_path / "config"
    runs.mkdir()
    config.mkdir()
    (runs / "ligand_smiles_bead_cache.json").write_text("{}", encoding="utf-8")
    (runs / "ligand_smiles_bead_cache_blind_gpcr_adrb2_v1.json").write_text("{}", encoding="utf-8")
    (config / "ligand_htvs_blind_gpcr_adrb2_v4_scorefix3.json").write_text(
        '{"csv_smiles_cache_json": "runs/ligand_smiles_bead_cache_blind_gpcr_adrb2_v1.json"}',
        encoding="utf-8",
    )

    payload = build_payload(str(runs))
    rows = {row["filename"]: row for row in payload["rows"]}

    assert payload["summary"]["status"] == "ligand_smiles_bead_cleanup_review_manifest_ready"
    assert rows["ligand_smiles_bead_cache.json"]["recommended_disposition"] == "keep_in_active_root"
    assert rows["ligand_smiles_bead_cache_blind_gpcr_adrb2_v1.json"]["recommended_disposition"] == "keep_in_active_root"
