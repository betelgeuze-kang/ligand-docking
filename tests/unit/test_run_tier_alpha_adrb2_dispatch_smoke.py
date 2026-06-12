from __future__ import annotations

import os
from pathlib import Path

from tools.gpcr_replay.run_tier_alpha_adrb2_dispatch_smoke import _configure_runtime


def test_tier_alpha_smoke_configures_inner_validated_runner_timeout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("API_VALIDATED_RUNNER_TIMEOUT_SECONDS", raising=False)

    _configure_runtime(
        workspace=tmp_path,
        job_id="job",
        runner_enabled=True,
        runner_timeout_seconds=37,
    )

    assert os.environ["API_VALIDATED_RUNNER_ENABLED"] == "1"
    assert os.environ["API_VALIDATED_RUNNER_TIMEOUT_SECONDS"] == "37"
