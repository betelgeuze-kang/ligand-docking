from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_biorxiv_robustness_battery(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    profile = config_dir / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "description": "base profile",
                "csv_relax_embed_seed": 13,
                "hard_decoy_synth_random_seed": 13,
                "ranking_bootstrap_seed": 17,
                "hard_decoy_synth_total_decoys": 10000,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    base_spec = config_dir / "base_spec.json"
    base_spec.write_text(
        json.dumps(
            {
                "protocol_id": "base",
                "global_governance": {"claim_scope": ["base claim"]},
                "sets": [
                    {
                        "set_id": "set1",
                        "tasks": [
                            {
                                "task_id": "gpcr_core_full",
                                "profile_json": str(profile.relative_to(tmp_path)),
                            }
                        ],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out_json = tmp_path / "runs" / "battery.json"
    out_csv = tmp_path / "runs" / "battery.csv"
    out_md = tmp_path / "runs" / "battery.md"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_biorxiv_robustness_battery.py"),
            "--base-spec-json",
            str(base_spec),
            "--out-config-dir",
            str(config_dir),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=str(tmp_path),
        check=True,
    )

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["scenario_count"] == 4
    rows = {row["scenario_id"]: row for row in data["rows"]}
    assert "decoy_pressure_12k" in rows
    scenario_spec = tmp_path / rows["embed_seed_shift1"]["spec_json"]
    spec_payload = json.loads(scenario_spec.read_text(encoding="utf-8"))
    assert spec_payload["protocol_id"] == "external_validation_biorxiv_robustness_embed_seed_shift1"
    cloned_profile = tmp_path / spec_payload["sets"][0]["tasks"][0]["profile_json"]
    cloned_payload = json.loads(cloned_profile.read_text(encoding="utf-8"))
    assert cloned_payload["csv_relax_embed_seed"] == 29
