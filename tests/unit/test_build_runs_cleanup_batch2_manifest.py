from __future__ import annotations

from pathlib import Path

from tools import build_runs_cleanup_batch2_manifest as mod


def test_build_runs_cleanup_batch2_manifest(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "archive_2026-03-29_external_validation_batch1").mkdir()
    (runs_dir / "archive_2026-03-29_external_validation_batch1" / "foo.txt").write_text("x" * 10, encoding="utf-8")
    (runs_dir / "idp_virtual_hbond_old.json").write_text("{}", encoding="utf-8")
    (runs_dir / "ligand_blind_gpcr_old.lock").write_text("", encoding="utf-8")

    payload = mod.build_payload(str(runs_dir), "2026-03-29")
    summary = payload["summary"]
    rows = {row["match_pattern"]: row for row in payload["rows"]}

    assert summary["status"] == "runs_cleanup_batch2_manifest_ready"
    assert summary["safe_apply_pattern_count"] >= 2
    assert rows["archive_2026-03-29_external_validation_batch1"]["apply_now"] is True
    assert rows["idp_virtual_hbond*"]["apply_now"] is True
    assert rows["ligand_blind_gpcr*"]["action"] == "review_only"
