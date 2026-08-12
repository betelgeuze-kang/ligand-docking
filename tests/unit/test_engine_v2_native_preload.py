from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_installed_native_preload_oserror_is_fatal_and_not_retried(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "import-count"
    (tmp_path / "betelgeuze_engine_v2_native.py").write_text(
        "from pathlib import Path\n"
        f"marker = Path({str(marker)!r})\n"
        "count = int(marker.read_text()) + 1 if marker.exists() else 1\n"
        "marker.write_text(str(count))\n"
        "raise OSError('synthetic qualified HIP preload failure')\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join((str(tmp_path), str(Path.cwd())))

    completed = subprocess.run(
        [sys.executable, "-c", "import betelgeuze_engine_v2"],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "synthetic qualified HIP preload failure" in completed.stderr
    assert marker.read_text(encoding="utf-8") == "1"
