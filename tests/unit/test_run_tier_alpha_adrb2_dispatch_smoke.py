from __future__ import annotations

import os
import sys
from pathlib import Path

from tools.product import run_tier_alpha_adrb2_dispatch_smoke as product_smoke
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


def test_tier_alpha_smoke_prefers_repo_sources_over_installed_wheel() -> None:
    assert sys.path[0] == str(product_smoke.ROOT)
