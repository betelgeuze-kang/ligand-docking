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
import shutil
import subprocess
import sys


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _check_attempt(run: Path, attempt: int, checked: dict, binding_sha256: str) -> dict:
    directory = run / f"attempt-{attempt:06d}"
    report_path = directory / "report.json"
    report = json.loads(report_path.read_bytes())
    completion = json.loads((directory / "complete.json").read_bytes())
    report_sha256 = _sha256(report_path)
    if (
        report["status"] != "completed"
        or report["exit_code"] != 0
        or report["attempt"] != attempt
        or report["publication_policy"] != "final_report_digest_v1"
        or report["artifact_integrity_policy"] != "referenced_artifacts_including_html_sha256_v1"
        or report["scientifically_validated"] is not False
        or set(report["artifacts"]) != {"physics", "html"}
        or completion != {
            "schema_version": "local_research_attempt_completion_v1",
            "attempt": attempt,
            "report_sha256": report_sha256,
            "request_binding_sha256": binding_sha256,
        }
        or checked["status"] != "intact"
        or checked["attempt"] != attempt
        or checked["workflow_status"] != "completed"
        or checked["workflow_exit_code"] != 0
        or checked["report_sha256"] != report_sha256
        or checked["summary_receipt_verified"] is not True
        or checked["html_verified"] is not True
        or set(checked["artifacts_verified"]) != {"physics.json", "report.html"}
        or checked["execution_performed"] is not False
        or checked["scientifically_validated"] is not False
    ):
        raise ValueError("installed_attempt_receipt_mismatch")
    for key, name in (("physics", "physics.json"), ("html", "report.html")):
        path = directory / name
        artifact = report["artifacts"][key]
        if (artifact["name"] != name or artifact["bytes"] != path.stat().st_size
                or artifact["sha256"] != _sha256(path)):
            raise ValueError("installed_artifact_receipt_mismatch")
    return {
        "attempt": attempt,
        "report_sha256": report_sha256,
        "physics_sha256": report["artifacts"]["physics"]["sha256"],
        "html_sha256": report["artifacts"]["html"]["sha256"],
        "summary_receipt_verified": True,
        "html_verified": True,
    }


def _check_run_receipts(run: Path, first_checked: dict, latest_checked: dict) -> dict:
    binding_sha256 = _sha256(run / "request.json")
    first = json.loads((run / "attempt-000001/physics.json").read_bytes())
    second = json.loads((run / "attempt-000002/physics.json").read_bytes())
    first_summary = json.loads((run / "attempt-000001/report.json").read_bytes())
    second_summary = json.loads((run / "attempt-000002/report.json").read_bytes())
    if (
        first["denominator"] != {"requested": 2, "evaluated": 2, "failed": 0, "skipped": 0}
        or first["rows"] != second["rows"]
        or second["resume_observation"]["restored_rows"] != 2
        or second["resume_observation"]["newly_completed_rows"] != 0
        or second["resume_observation"]["completed_rows"] != 2
        or first_summary["resume_requested"] is not False
        or first_summary["backend_executed"] != "cpu"
        or second_summary["resume_requested"] is not True
        or second_summary["backend_executed"] is not None
    ):
        raise ValueError("installed_workflow_resume_mismatch")
    return {
        "binding_sha256": binding_sha256,
        "attempts": [
            _check_attempt(run, 1, first_checked, binding_sha256),
            _check_attempt(run, 2, latest_checked, binding_sha256),
        ],
        "restored_rows": 2,
        "newly_completed_rows": 0,
    }


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
        ("verify-first", ["--run-dir", str(run.resolve()), "--verify-run", "--attempt", "1"]),
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
    receipt = _check_run_receipts(
        run,
        json.loads((evidence / "verify-first.stdout").read_text()),
        json.loads((evidence / "verify.stdout").read_text()),
    )
    # Corrupt only a private copy: the original run remains a valid receipt.
    tampered = evidence / "tampered-run"
    tampered.mkdir(mode=0o700)
    for name in ("request.json", ".workflow.lock"):
        shutil.copy2(run / name, tampered / name)
    shutil.copytree(run / "attempt-000002", tampered / "attempt-000002")
    html = tampered / "attempt-000002/report.html"
    raw = html.read_bytes()
    html.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    command = common + ["--run-dir", str(tampered.resolve()), "--verify-run"]
    rejected = subprocess.run(command, cwd=evidence, capture_output=True, text=True,
                              timeout=120, env=dict(os.environ, PYTHONPATH=""))
    (evidence / "verify-tampered.stdout").write_text(rejected.stdout)
    (evidence / "verify-tampered.stderr").write_text(rejected.stderr)
    commands.append({"stage": "verify-tampered", "command": command,
                     "exit_code": rejected.returncode})
    (evidence / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
    outcome = json.loads(rejected.stdout)
    if (rejected.returncode != 2 or outcome["status"] != "invalid"
            or outcome.get("reason") != "artifact_digest_mismatch"
            or outcome["execution_performed"] is not False
            or _sha256(run / "attempt-000002/report.html")
            != receipt["attempts"][1]["html_sha256"]):
        raise ValueError("installed_tampered_copy_not_rejected")
    result = {"status": "verified", "scope": "synthetic_installed_cpu_run_resume_receipts",
              "request_sha256": hashlib.sha256(request.read_bytes()).hexdigest(),
              "interpreter": sys.executable, "prefix": str(prefix), "imports": imported,
              "numpy": numpy.__version__, "rdkit": rdkit.__version__, "torch": torch.__version__,
              "distributions": sorted((d.metadata["Name"], d.version)
                                      for d in importlib.metadata.distributions()),
              "commands": commands, "dynamic_namespaces": sorted(dynamic),
              "receipt": receipt, "tampered_copy_rejected": True,
              "restored_rows": 2, "scientifically_validated": False}
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
