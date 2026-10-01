"""Exercise a built product wheel outside the checkout, without PYTHONPATH.

Run from a full source checkout AFTER installing the wheel into --python's venv.
Synthetic prepared inputs are generated here; the installed child process imports
no test fixtures and is launched with -I. No downloaded scientific data is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from tests.unit.test_cpu_refinement_v1_2_workflow import extended_request_fixture
from tests.unit.test_cpu_fixed_receptor_pipeline import request_fixture as fixed_request_fixture


def verify(python: Path, output: Path) -> dict:
    source = Path(__file__).resolve().parents[1]
    executable = str(python.absolute())
    output.mkdir(parents=True, exist_ok=False)
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    with tempfile.TemporaryDirectory(prefix="cpu-installed-1-2-") as directory:
        outside = Path(directory)
        request = extended_request_fixture(outside)
        request_path = outside / "request.json"
        request_path.write_text(json.dumps(request))
        commands = [
            [executable, "-I", "-c", "import json,sys; from pathlib import Path; "
             "import betelgeuze_product.cpu_refinement_v1_2.workflow as w; "
             "p=Path(w.__file__).resolve(); "
             f"assert not p.is_relative_to(Path({str(source)!r})); "
             "assert p.is_relative_to(Path(sys.prefix)); "
             "print(json.dumps({'module':str(p),'prefix':sys.prefix,'python':sys.version}))"],
            [executable, "-I", "-m", "betelgeuze_product.cpu_refinement_v1_2", "run", str(request_path),
             "--output", str(outside / "run")],
            [executable, "-I", "-m", "betelgeuze_product.cpu_refinement_v1_2", "verify", str(outside / "run")],
        ]
        fixed_inputs = outside / "fixed-inputs"
        fixed_inputs.mkdir()
        fixed_request = fixed_request_fixture(fixed_inputs)
        fixed_path = fixed_inputs / "request.json"
        fixed_path.write_text(json.dumps(fixed_request))
        commands.extend([
            [executable, "-I", "-m", "betelgeuze_product.cpu_refinement_v1_2", "run",
             str(fixed_path), "--output", str(outside / "fixed-run")],
            [executable, "-I", "-m", "betelgeuze_product.cpu_refinement_v1_2", "verify",
             str(outside / "fixed-run")],
        ])
        records = []
        for command in commands:
            run = subprocess.run(command, cwd=outside, env=env, capture_output=True, text=True, timeout=180)
            records.append({"command": command, "returncode": run.returncode,
                            "stdout": run.stdout, "stderr": run.stderr})
            (output / "commands.json").write_text(json.dumps(records, indent=2))
            if run.returncode:
                raise RuntimeError("installed CPU CLI failed; see retained command output")
        for name in ("request.json", "report.json", "complete.json"):
            (output / name).write_bytes((outside / "run" / name).read_bytes())
        report = json.loads((outside / "run" / "report.json").read_bytes())
        expected = {"betelgeuze_product/cpu_refinement_v1_2/" + path.name:
                    hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (source / "betelgeuze_product/cpu_refinement_v1_2").glob("*.py")}
        installed = {key: value for key, value in report["implementation_sources"].items()
                     if key.startswith("betelgeuze_product/cpu_refinement_v1_2/")}
        if installed != expected:
            raise RuntimeError("installed implementation differs from checkout bytes")
        if report["result"]["arms"]["refined"]["failure_count"]:
            raise RuntimeError("installed synthetic refinement did not succeed")
        fixed_report = json.loads((outside / "fixed-run" / "report.json").read_bytes())
        if fixed_report["result"]["arms"]["refined"]["failure_count"]:
            raise RuntimeError("installed fixed-receptor refinement failed")
        if fixed_report["result"]["schema_id"] != "cpu_fixed_receptor_comparison/1.0.0":
            raise RuntimeError("installed CLI did not use fixed-receptor model")
        (output / "fixed-run").mkdir()
        for name in ("request.json", "report.json", "complete.json"):
            (output / "fixed-run" / name).write_bytes((outside / "fixed-run" / name).read_bytes())
        result = {"fixed_receptor_cli_verified": True, "installed_cli_verified": True, "outside_checkout": True,
                  "pythonpath_removed": True, "isolated_python_flag": True,
                  "new_source_hashes": installed, "scientifically_validated": False}
        (output / "verification.json").write_text(json.dumps(result, indent=2))
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.python, args.output)))


if __name__ == "__main__":
    main()
