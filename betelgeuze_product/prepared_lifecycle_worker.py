"""Fixed installed Fourier child; no public command, path or test-hook interface."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import resource
import sys

from .prepared_lifecycle import (PreparedLifecycle, admission_document, digest,
    json_bytes, private_root, regular_bytes, require, write_absent)
from .prepared_lifecycle_owner import implementation_sources


def tree_bytes(root):
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlink in owned output")
        if path.is_file():
            total += path.stat().st_size
    return total


def execute_binding(binding_path, owner_token):
    require(sys.flags.isolated == 1 and sys.dont_write_bytecode,
            "RUNTIME_UNQUALIFIED", "Isolated installed execution is required", 503)
    path = Path(binding_path)
    private_root(path.parent)
    binding = json_bytes(regular_bytes(path, path.parent))
    require(binding["schema_version"] == "prepared_lifecycle_invocation/1.0.0"
            and hashlib.sha256(owner_token.encode()).hexdigest() == binding["owner_token_sha256"],
            "OWNER_FENCE_LOST", "Invocation owner token differs", 409)
    require(binding["implementation_sources"] == implementation_sources(),
            "SOURCE_OR_MODEL_MISMATCH", "Installed implementation bytes changed", 409)
    service = PreparedLifecycle(binding["state_root"], binding["input_root"], tenant_id=binding["tenant"])
    with service._connect() as connection:
        row = service._row(connection, binding["execution_id"])
    require(row["owner_token"] == owner_token and row["generation"] == binding["generation"]
            and row["status"] in ("running", "cancel_requested"), "OWNER_FENCE_LOST", "Invocation is no longer owned", 409)
    if row["cancel_requested"]:
        return 2
    admission = admission_document(service.input_root, binding["admission"]["admission_id"], tenant_id=service.tenant_id)
    require(admission == binding["admission"], "SOURCE_OR_MODEL_MISMATCH", "Registered model changed", 409)
    limits = binding["limits"]
    require(sorted(os.sched_getaffinity(0)) == limits["cpu_affinity"], "RUNTIME_UNQUALIFIED", "CPU affinity envelope was not applied", 503)
    for kind, key in ((resource.RLIMIT_CPU, "cpu_seconds"), (resource.RLIMIT_AS, "address_space_bytes"),
                      (resource.RLIMIT_FSIZE, "file_bytes")):
        require(resource.getrlimit(kind) == (limits[key], limits[key]),
                "RESOURCE_CONTAINMENT_UNAVAILABLE", "Worker resource envelope was not applied", 503)
    import torch
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    from .cpu_refinement_fourier_v1 import workflow
    from .prepared_refinement_cli import report
    require(not any(n.split(".")[0] in ("tools", "tests", "pytest") for n in sys.modules),
            "RUNTIME_UNQUALIFIED", "Test or tool imports are forbidden", 503)
    prefix = Path(sys.prefix).resolve()
    require(all(Path(m.__file__).resolve().is_relative_to(prefix)
                for name, m in tuple(sys.modules.items()) if name.startswith(("betelgeuze_product", "betelgeuze_engine_v2"))
                and getattr(m, "__file__", None)), "RUNTIME_UNQUALIFIED", "Installed package origins required", 503)
    job, attempt = Path(binding["job_root"]), Path(binding["attempt_root"])
    require(job == service.root / "jobs" / binding["execution_id"] and attempt.parent == job / "attempts",
            "OWNER_FENCE_LOST", "Owned output binding differs", 409)
    original_publish = workflow._publish

    def guarded_publish(destination, document):
        # This guard changes publication admission only, never force arithmetic.
        size = len((workflow.canonical(document) + "\n").encode())
        require(Path(destination).is_relative_to(job) and tree_bytes(job) + 2 * size <= binding["policy"]["output_bytes"],
                "BUDGET_EXHAUSTED", "Retained publication budget exhausted", 409)
        return original_publish(destination, document)

    workflow._publish = guarded_publish
    try:
        result = workflow.run(admission["protocol"], job / "numerical", resume=binding["resume"],
            pause_after_accepted_iterations=None if binding["resume"] else admission["initial_pause"])
        document = report(admission["protocol"], job / "numerical")
    finally:
        workflow._publish = original_publish
    require(document["work"]["total_force_evaluation_calls"] is None or
            document["work"]["total_force_evaluation_calls"] <= binding["policy"]["force_call_ceiling"],
            "BUDGET_EXHAUSTED", "Force census exceeds reserved total", 409)
    envelope = {"schema_version": "prepared_lifecycle_numerical_result/1.0.0",
        "execution_id": binding["execution_id"], "generation": binding["generation"],
        "status": result["status"], "numerical_state": result["status"],
        "known_force_calls": document["work"]["known_force_evaluation_calls"],
        "total_work_known": document["work"]["total_work_known"],
        "unknown_stage": result["unknown_stage"], "backend_binding": result["binding"],
        "report_sha256": digest(document), "research_only": True, "qualified": False}
    for name, value in (("report.json", document), ("result.json", envelope)):
        size = len((workflow.canonical(value) + "\n").encode())
        require(tree_bytes(job) + size <= binding["policy"]["output_bytes"], "BUDGET_EXHAUSTED", "Retained publication budget exhausted", 409)
        write_absent(attempt / name, value)
    # Transport success means the numerical outcome was durably published.
    # A known numerical failure remains explicit in result.status, not rc.
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--owner-token", required=True)
    args = parser.parse_args(argv)
    return execute_binding(args.binding, args.owner_token)


if __name__ == "__main__":
    raise SystemExit(main())
