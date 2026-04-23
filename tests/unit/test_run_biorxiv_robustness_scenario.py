from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from tools.run_biorxiv_robustness_scenario import main


def test_run_biorxiv_robustness_scenario_uses_current_package_meta(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    meta = runs / "biorxiv_external_validation_package_current.json"
    meta.write_text(json.dumps({"run_root": str(tmp_path / "accepted_run")}) + "\n", encoding="utf-8")

    calls: list[list[str]] = []

    class Result:
        def __init__(self, returncode: int = 0) -> None:
            self.returncode = returncode

    def fake_run(cmd: list[str], cwd: str | None = None) -> Result:
        calls.append(cmd)
        return Result(0)

    with patch("tools.run_biorxiv_robustness_scenario.ROOT", tmp_path), patch(
        "tools.run_biorxiv_robustness_scenario.subprocess.run",
        side_effect=fake_run,
    ):
        rc = main(
            [
                "--scenario",
                "embed_seed_shift1",
                "--set-spec-json",
                "config/external_validation_biorxiv_robustness_embed_seed_shift1.json",
                "--tag",
                "2026-03-22_embed_seed_shift1",
            ]
        )

    assert rc == 0
    assert calls[0][1].endswith("tools/run_biorxiv_external_validation_current.py")
    assert calls[1][1].endswith("tools/compare_biorxiv_external_validation_runs.py")
    assert "--candidate-run-root" in calls[1]
