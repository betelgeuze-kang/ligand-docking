from __future__ import annotations

from pathlib import Path

from tools.build_idp_3bead_release_cleanup_review_manifest import build_payload


def test_build_idp_3bead_release_cleanup_review_manifest(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "idp_3bead_release_manifest_current.json").write_text("{}", encoding="utf-8")
    (runs / "idp_3bead_release_smoke_manifest_current.md").write_text(
        "see `runs/idp_3bead_release_smoke_current_2026-03-20_speedopt3full_summary.json`",
        encoding="utf-8",
    )
    (runs / "idp_3bead_release_smoke_runner_current.md").write_text(
        "baseline `runs/idp_3bead_release_smoke_current_2026-03-20_r3_baseline_manifest.json`",
        encoding="utf-8",
    )
    (runs / "idp_3bead_global_aggregation_dashboard_current.json").write_text(
        '{"manifest":"runs/idp_3bead_release_manifest_2026-03-16_r9_physfix1.json"}',
        encoding="utf-8",
    )
    (runs / "idp_3bead_release_smoke_current_2026-03-20_speedopt3full_summary.json").write_text("{}", encoding="utf-8")
    (runs / "idp_3bead_release_smoke_current_2026-03-20_r3_baseline_manifest.json").write_text("{}", encoding="utf-8")
    (runs / "idp_3bead_release_manifest_2026-03-16_r9_physfix1.json").write_text("{}", encoding="utf-8")
    (runs / "idp_3bead_release_smoke_current_2026-03-22_external-foo_fold1_eval.json").write_text("{}", encoding="utf-8")

    payload = build_payload(str(runs))
    rows = {row["prefix"]: row for row in payload["rows"]}

    assert payload["summary"]["status"] == "idp_3bead_release_cleanup_review_manifest_ready"
    assert rows["idp_3bead_release_smoke_current_2026-03-20_speedopt3full"]["classification"] == "review_hold_current_reference"
    assert rows["idp_3bead_release_smoke_current_2026-03-20_r3"]["classification"] == "review_hold_current_reference"
    assert rows["idp_3bead_release_manifest_2026-03-16_r9_physfix1"]["classification"] == "review_hold_current_reference"
    assert rows["idp_3bead_release_smoke_current_2026-03-22_external-foo"]["recommended_disposition"] == "review_for_archive_after_prefix_signoff"

