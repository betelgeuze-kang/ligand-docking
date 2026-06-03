from __future__ import annotations

from pathlib import Path

from betelgeuze_product.lit_pcba_materialization import build_lit_pcba_materialization_manifest


def test_lit_pcba_materialization_blocks_missing_local_sources(tmp_path: Path) -> None:
    payload = build_lit_pcba_materialization_manifest(
        archive_path=tmp_path / "missing.tar.xz",
        extracted_dir=tmp_path / "missing",
        source_score_csv=tmp_path / "scores_source.csv",
        source_label_csv=tmp_path / "labels_source.csv",
        out_scores_csv=tmp_path / "scores.csv",
        out_labels_csv=tmp_path / "labels.csv",
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_lit_pcba_materialization"
    assert summary["materialized"] is False
    assert "zenodo_archive_missing" in summary["blockers"]
    assert "source_score_csv_missing" in summary["blockers"]
    assert summary["download_executed"] is False
    assert summary["external_state_mutated"] is False


def test_lit_pcba_materialization_standardizes_source_csvs(tmp_path: Path) -> None:
    archive = tmp_path / "LIT_PCBA_AVE_docked_released.tar.xz"
    archive.write_text("stub", encoding="utf-8")
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    source_scores = tmp_path / "source_scores.csv"
    source_labels = tmp_path / "source_labels.csv"
    source_scores.write_text("target,ligand_id,binding_score\nT1,L1,-9.0\nT1,L2,-1.0\n", encoding="utf-8")
    source_labels.write_text("target,ligand_id,is_binder\nT1,L1,1\nT1,L2,0\n", encoding="utf-8")
    out_scores = tmp_path / "scores.csv"
    out_labels = tmp_path / "labels.csv"

    payload = build_lit_pcba_materialization_manifest(
        archive_path=archive,
        extracted_dir=extracted,
        source_score_csv=source_scores,
        source_label_csv=source_labels,
        out_scores_csv=out_scores,
        out_labels_csv=out_labels,
    )

    summary = payload["summary"]
    assert summary["status"] == "lit_pcba_materialization_ready"
    assert summary["materialized"] is True
    assert summary["score_row_count"] == 2
    assert summary["label_row_count"] == 2
    assert out_scores.read_text(encoding="utf-8").startswith("target,ligand_id,binding_score")
    assert out_labels.read_text(encoding="utf-8").startswith("target,ligand_id,is_binder")
