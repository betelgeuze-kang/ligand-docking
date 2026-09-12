"""Exercise a wheel in an isolated interpreter with a fresh synthetic request.

Run with that environment's Python and -I. This checks installation and receipt
integrity only; the caller supplies a fresh synthetic two-pose workflow request.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys


def verify(request: Path, evidence: Path) -> dict:
    if not sys.flags.isolated or sys.prefix == sys.base_prefix:
        raise ValueError("requires_isolated_virtual_environment")
    evidence.mkdir(parents=True, exist_ok=False)
    prefix = Path(sys.prefix).resolve()
    # Import real consumers before recording the transitive installed modules.
    importlib.import_module("betelgeuze_engine.product.prepared_rigid_poses")
    importlib.import_module("betelgeuze_product.local_research_workflow")
    import numpy
    import rdkit
    import torch

    # Torch registers these two dynamic namespaces with placeholder __file__
    # strings. Their implementation modules torch._ops/_classes are audited.
    dynamic = {"torch.ops": torch.ops, "torch.classes": torch.classes}
    roots = ("betelgeuze_", "core", "tools", "torch", "numpy", "rdkit")
    imported = {name: str(Path(module.__file__).resolve())
                for name, module in list(sys.modules.items())
                if name.startswith(roots) and getattr(module, "__file__", None)
                and dynamic.get(name) is not module}
    outside = {name: path for name, path in imported.items()
               if not Path(path).is_relative_to(prefix)}
    if outside or any(name == "tools" or name.startswith("tools.") for name in imported):
        raise ValueError("project_or_numerical_import_outside_install")
    if torch.version.hip is not None or torch.version.cuda is not None:
        raise ValueError("requires_cpu_torch_distribution")
    run = evidence / "run"
    common = [sys.executable, "-I", "-B", "-m", "betelgeuze_product.local_research_workflow"]
    stages = [
        ("run", ["--request", str(request.resolve()), "--run-dir", str(run.resolve())]),
        ("resume", ["--request", str(request.resolve()), "--run-dir", str(run.resolve()), "--resume"]),
        ("verify", ["--run-dir", str(run.resolve()), "--verify-run"]),
    ]
    commands = []
    for name, arguments in stages:
        command = common + arguments
        proc = subprocess.run(command, cwd=evidence, capture_output=True, text=True,
                              timeout=120, env=dict(os.environ, PYTHONPATH=""))
        (evidence / (name + ".stdout")).write_text(proc.stdout)
        (evidence / (name + ".stderr")).write_text(proc.stderr)
        commands.append({"stage": name, "command": command, "exit_code": proc.returncode})
        (evidence / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if proc.returncode:
            raise ValueError("installed_workflow_stage_failed_" + name)
    first = json.loads((run / "attempt-000001/physics.json").read_text())
    second = json.loads((run / "attempt-000002/physics.json").read_text())
    summary = json.loads((run / "attempt-000002/report.json").read_text())
    checked = json.loads((evidence / "verify.stdout").read_text())
    if (first["denominator"] != {"requested": 2, "evaluated": 2, "failed": 0, "skipped": 0}
            or first["rows"] != second["rows"]
            or second["resume_observation"]["restored_rows"] != 2
            or summary["backend_executed"] is not None
            or checked["status"] != "intact" or checked["execution_performed"] is not False
            or checked["scientifically_validated"] is not False):
        raise ValueError("installed_workflow_verification_mismatch")
    result = {"status": "verified", "scope": "synthetic_installed_cpu_run_resume_receipts",
              "request_sha256": hashlib.sha256(request.read_bytes()).hexdigest(),
              "interpreter": sys.executable, "prefix": str(prefix), "imports": imported,
              "numpy": numpy.__version__, "rdkit": rdkit.__version__, "torch": torch.__version__,
              "distributions": sorted((d.metadata["Name"], d.version)
                                      for d in importlib.metadata.distributions()),
              "commands": commands, "dynamic_namespaces": sorted(dynamic), "restored_rows": 2, "scientifically_validated": False}
    (evidence / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.request, args.evidence)
    print(json.dumps({key: result[key] for key in ("status", "scope", "restored_rows")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
