from __future__ import annotations

import json

from tools.run_biorxiv_robustness_battery_current import main


def test_run_biorxiv_robustness_battery_current_dry_run(tmp_path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "battery.json").write_text(
        json.dumps(
            {
                "rows": [
                    {"scenario_id": "embed_seed_shift1", "spec_json": "config/spec1.json"},
                    {"scenario_id": "decoy_seed_shift1", "spec_json": "config/spec2.json"},
                ]
            }
        ),
        encoding="utf-8",
    )

    import tools.run_biorxiv_robustness_battery_current as mod

    mod.ROOT = tmp_path
    rc = main(
        [
            "--battery-json",
            "runs/battery.json",
            "--dry-run",
            "--out-json",
            "runs/out.json",
            "--out-md",
            "runs/out.md",
        ]
    )

    assert rc == 0
    data = json.loads((runs / "out.json").read_text(encoding="utf-8"))
    assert data["row_count"] == 2
    assert all(row["status"] == "dry_run" for row in data["rows"])
