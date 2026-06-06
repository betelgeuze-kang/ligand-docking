from __future__ import annotations

from tools.wetlab import build_wetlab_broad_screen_result_rows as mod


def test_build_wetlab_broad_screen_result_rows_payload() -> None:
    payload = mod.build_payload(
        target_id="CA IX",
        shard_id="05_of_20",
        compound_name="Acetazolamide",
        bulk_rank=1,
        bulk_score=93.2,
        seed_status="broad_screen_runtime_validation_result",
        first_contact_use_mode="benchmark_control",
        vendor_check_required=False,
        cost_check_required=False,
        selectivity_note="Keep CA II / CA XII counterscreens attached.",
        usage_rationale="Example row for a later CA IX shard.",
        must_not_do="Do not treat this runtime-validation row as a wet-lab measurement claim.",
        source_anchor="caix_broad_screen_shard_05_runtime_validation",
        source_url="runs/caix_broad_screen_shard_05_result_rows_current.md",
    )
    assert payload["summary"]["status"] == "wetlab_broad_screen_result_rows_ready"
    row = payload["rows"][0]
    assert row["target_id"] == "CA IX"
    assert row["shard_id"] == "05_of_20"
    assert row["compound_name"] == "Acetazolamide"
    assert payload["structured"]["merge_command"].endswith(
        "runs/caix_broad_screen_shard_05_result_rows_current.json"
    )
