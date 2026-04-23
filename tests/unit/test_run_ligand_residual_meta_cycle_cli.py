from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_run_ligand_residual_meta_cycle_help_runs_as_direct_script() -> None:
    proc = subprocess.run(
        [sys.executable, "tools/run_ligand_residual_meta_cycle.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert "ligand-queue-csv" in proc.stdout
