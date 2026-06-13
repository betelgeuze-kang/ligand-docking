from __future__ import annotations

import os
from pathlib import Path

from tools.gpcr_replay.run_tier_alpha_adrb2_dispatch_smoke import (
    _configure_runtime,
    _runner_timeout_for_smoke,
)


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


def test_tier_alpha_smoke_reserves_parent_deadline_headroom() -> None:
    assert _runner_timeout_for_smoke(420) == 360
    assert _runner_timeout_for_smoke(90) == 30
