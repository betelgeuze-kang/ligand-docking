"""Check actual Docker COPY/ignore inputs without requiring a Docker daemon."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from tools.verify_product_docker_context import materialize_product_context


def test_product_context_contains_the_complete_docking_cli_import_path(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    context = tmp_path / "product-context"
    materialize_product_context(root, context)
    image = tmp_path / "image-app"
    image.mkdir()
    # Materializing a build context alone does not prove that Docker copies a
    # package into the image. Apply this Dockerfile's literal COPY instructions
    # to a separate application directory as well.
    for line in (context / "Dockerfile.product").read_text().splitlines():
        if not line.startswith("COPY "):
            continue
        fields = shlex.split(line)[1:]
        destination = image / fields[-1]
        assert destination.resolve().is_relative_to(image)
        for name in fields[:-1]:
            source = context / name
            if source.is_dir():
                assert len(fields) == 2
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                destination.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination / source.name)
    # A fresh isolated interpreter cannot accidentally use modules already
    # imported by pytest or a developer's working directory.
    probe = r'''
import contextlib
import io
import json
from pathlib import Path
import sys

context = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(context))
from betelgeuze_product.docking_cli import main
import betelgeuze_engine_v2
import betelgeuze_product
for module in (betelgeuze_engine_v2, betelgeuze_product):
    assert Path(module.__file__).resolve().is_relative_to(context)
checks = []
for arguments in (["--help"], ["prepared-refine", "--help"], ["prepared-jobs", "--help"]):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        try:
            code = main(arguments)
        except SystemExit as exc:
            code = exc.code
    assert code in (None, 0), (arguments, code)
    assert "usage:" in output.getvalue()
    checks.append(arguments)
assert not ({"openmm", "simtk", "gmxapi", "vina", "gnina"} & set(sys.modules))
print(json.dumps({"help_commands": checks, "scope": "source-context import and help only"}))
'''
    environment = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "CUDA_VISIBLE_DEVICES": "",
        "HIP_VISIBLE_DEVICES": "",
        "ROCR_VISIBLE_DEVICES": "",
    }
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", probe, str(image)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert len(json.loads(completed.stdout)["help_commands"]) == 3
