import os
import subprocess
import sys
from pathlib import Path


def test_help_runs_without_pythonpath_when_invoked_by_script_path():
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "tools/run_ligand_backmapping_scoring.py", "--help"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert "run_ligand_backmapping_scoring.py" in result.stdout
