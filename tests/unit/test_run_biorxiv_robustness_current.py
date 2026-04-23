from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from tools.run_biorxiv_robustness_current import main


def test_run_biorxiv_robustness_current_uses_current_package_meta(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    tools_dir = tmp_path / "tools"
    runs.mkdir()
    tools_dir.mkdir()

    current_meta = {
        "run_root": str((runs / "external_validation_blind_runs_current").resolve()),
    }
    (runs / "biorxiv_external_validation_package_current.json").write_text(
        json.dumps(current_meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    calls: list[list[str]] = []

    class _Done:
        def __init__(self, returncode: int = 0) -> None:
            self.returncode = returncode

    def fake_run(cmd: list[str], cwd: str | None = None):  # type: ignore[override]
        calls.append(cmd)
        return _Done(0)

    with patch("tools.run_biorxiv_robustness_current.ROOT", tmp_path), patch(
        "tools.run_biorxiv_robustness_current.subprocess.run",
        side_effect=fake_run,
    ):
        rc = main(
            [
                "--tag",
                "robust_test",
                "--out-root",
                "runs",
                "--current-package-meta-json",
                "runs/biorxiv_external_validation_package_current.json",
            ]
        )

    assert rc == 0
    assert len(calls) == 2
    assert calls[0][1].endswith("tools/run_biorxiv_external_validation_current.py")
    assert calls[1][1].endswith("tools/compare_biorxiv_external_validation_runs.py")
    assert str((runs / "external_validation_blind_runs_current").resolve()) in calls[1]
    assert str((runs / "external_validation_blind_runs_robust_test").resolve()) in calls[1]
