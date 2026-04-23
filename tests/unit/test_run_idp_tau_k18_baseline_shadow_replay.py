import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/betelgeuze/분자동역학")


def test_run_idp_tau_k18_baseline_shadow_replay_help() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_idp_tau_k18_baseline_shadow_replay.py"), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "--kalman-shadow-feature-mask" in proc.stdout
    assert "--baseline-gate-json" in proc.stdout
