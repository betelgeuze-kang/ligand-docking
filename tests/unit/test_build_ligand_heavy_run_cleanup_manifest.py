from __future__ import annotations

import json
import os
from pathlib import Path

from tools.accounting import build_ligand_heavy_run_cleanup_manifest as mod


NOW = 1_800_000_000.0


def _write(path: Path, text: str = "x", *, age_days: int = 30) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    ts = NOW - (age_days * 86_400)
    os.utime(path, (ts, ts))
    os.utime(path.parent, (ts, ts))


def _mkdir(path: Path, *, age_days: int = 30) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _write(path / "payload.txt", "payload", age_days=age_days)
    ts = NOW - (age_days * 86_400)
    os.utime(path, (ts, ts))


def test_ligand_cleanup_manifest_keeps_top_rank_and_marks_old_raw_payloads(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    prefix = "ligand_htvs_nightly_2026-05-01_smoke"
    topk = runs / f"{prefix}_stage5_ranking_topk.csv"
    unique = runs / f"{prefix}_stage5_ranking_unique.csv"
    summary = runs / f"{prefix}_stage5_ranking_summary.json"
    raw_ligands = runs / f"{prefix}_stage1_ligands.json"
    raw_rows = runs / f"{prefix}_stage5_ranking_rows.csv"
    raw_dir = runs / f"{prefix}_stage2_traj_frames"
    current_named = runs / "ligand_htvs_nightly_current_stage2_traj_frames"
    no_top = runs / "ligand_htvs_nightly_2026-05-02_smoke_stage1_ligands.json"
    referenced = runs / "external_validation_2026-05-01_gpcr_full_p0_n100_r1_stage3_scores.csv"

    _write(topk, "top", age_days=30)
    _write(unique, "unique", age_days=30)
    _write(summary, "{}", age_days=30)
    _write(raw_ligands, "raw", age_days=30)
    _write(raw_rows, "all rows", age_days=30)
    _mkdir(raw_dir, age_days=30)
    _mkdir(current_named, age_days=30)
    _write(no_top, "raw no top", age_days=30)
    _write(referenced, "referenced", age_days=30)
    _write(
        runs / "product_release_source_of_truth_gate_current.json",
        json.dumps({"rows": [{"artifact_path": str(referenced.relative_to(tmp_path))}]}),
        age_days=1,
    )

    payload = mod.build_ligand_heavy_run_cleanup_manifest(root=tmp_path, now=NOW, older_than_days=7)
    rows = {row["path"]: row for row in payload["rows"]}
    summary_payload = payload["summary"]

    assert summary_payload["status"] == "ligand_heavy_run_cleanup_manifest_ready"
    assert rows[str(topk.relative_to(tmp_path))]["disposition"] == "keep_top_ranking_or_compact_evidence"
    assert rows[str(unique.relative_to(tmp_path))]["disposition"] == "keep_top_ranking_or_compact_evidence"
    assert rows[str(raw_ligands.relative_to(tmp_path))]["delete_recommended"] is True
    assert rows[str(raw_rows.relative_to(tmp_path))]["delete_recommended"] is True
    assert rows[str(raw_dir.relative_to(tmp_path))]["delete_recommended"] is True
    assert rows[str(current_named.relative_to(tmp_path))]["disposition"] == "review_current_named_ligand_payload"
    assert rows[str(no_top.relative_to(tmp_path))]["disposition"] == "review_missing_top_rank_evidence"
    assert rows[str(referenced.relative_to(tmp_path))]["disposition"] == "keep_referenced_current_evidence"
    assert summary_payload["delete_executed"] is False
    assert summary_payload["external_state_mutated"] is False


def test_ligand_cleanup_manifest_recent_raw_payload_requires_review(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    prefix = "external_validation_2026-06-12_ligand_smoke_p0_n64_r1"
    _write(runs / f"{prefix}_stage5_ranking_topk.csv", "top", age_days=1)
    raw = runs / f"{prefix}_stage1_ligands.json"
    _write(raw, "raw", age_days=1)

    payload = mod.build_ligand_heavy_run_cleanup_manifest(root=tmp_path, now=NOW, older_than_days=7)
    rows = {row["path"]: row for row in payload["rows"]}

    assert rows[str(raw.relative_to(tmp_path))]["delete_recommended"] is False
    assert rows[str(raw.relative_to(tmp_path))]["disposition"] == "review_recent_ligand_payload"
