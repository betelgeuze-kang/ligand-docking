"""Fixed isolated read-only worker; no numerical execution entry point.

The parent supplies only internally derived bindings. This worker's resource
envelope is independent of numerical execution budgets and is not a namespace
or RSS/RAM containment claim.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import sys
import time

REQUEST_SCHEMA = "prepared_lifecycle_readonly_request/1.0.0"
RESPONSE_SCHEMA = "prepared_lifecycle_readonly_response/1.0.0"
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024
WALL_SECONDS = 120
CPU_SECONDS = 90
ADDRESS_SPACE_BYTES = 4 * 1024**3
FILE_BYTES = 1024 * 1024
OWNING_SCOPE = "bound_bytes_structural_receipts_no_force_reexecution"
_MODULE_STARTED = time.monotonic()


def _require(condition):
    if not condition:
        raise ValueError("read-only worker binding rejected")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _file_hash(path):
    _require(path.is_absolute() and not path.is_symlink() and path.resolve(strict=True) == path)
    info = path.stat()
    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= MAX_REQUEST_BYTES)
    return _sha(path.read_bytes())


def _bootstrap():
    """Check trusted installed origins and our bytes before reading JSON."""
    _require(sys.flags.isolated == 1 and sys.dont_write_bytecode and "torch" not in sys.modules)
    root = Path(os.environ["BETELGEUZE_READONLY_INSTALLED_ROOT"])
    _require(root.is_absolute() and root.resolve(strict=True) == root
             and root.is_relative_to(Path(sys.prefix).resolve()))
    own = Path(__file__).resolve()
    _require(own == root / "betelgeuze_product/prepared_lifecycle_readonly_worker.py")
    _require(_file_hash(own) == os.environ["BETELGEUZE_READONLY_WORKER_SHA256"])
    _require(_file_hash(root / "betelgeuze_product/prepared_lifecycle.py")
             == os.environ["BETELGEUZE_READONLY_CORE_SHA256"])
    return root


def _apply_resources(cpu):
    if signal.getitimer(signal.ITIMER_REAL)[0] <= 0:
        _arm_wall_timer()
    _require(type(cpu) is int and cpu in os.sched_getaffinity(0))
    for kind, value in ((resource.RLIMIT_CPU, CPU_SECONDS),
                        (resource.RLIMIT_AS, ADDRESS_SPACE_BYTES),
                        (resource.RLIMIT_FSIZE, FILE_BYTES)):
        resource.setrlimit(kind, (value, value))
    os.sched_setaffinity(0, {cpu})
    applied = {"RLIMIT_CPU": list(resource.getrlimit(resource.RLIMIT_CPU)),
               "RLIMIT_AS": list(resource.getrlimit(resource.RLIMIT_AS)),
               "RLIMIT_FSIZE": list(resource.getrlimit(resource.RLIMIT_FSIZE)),
               "cpu_affinity": sorted(os.sched_getaffinity(0))}
    _require(applied == {"RLIMIT_CPU": [CPU_SECONDS, CPU_SECONDS],
                         "RLIMIT_AS": [ADDRESS_SPACE_BYTES, ADDRESS_SPACE_BYTES],
                         "RLIMIT_FSIZE": [FILE_BYTES, FILE_BYTES], "cpu_affinity": [cpu]})
    remaining = signal.getitimer(signal.ITIMER_REAL)[0]
    _require(0 < remaining <= WALL_SECONDS)
    return {**applied, "self_wall_limit_seconds": WALL_SECONDS,
            "self_wall_timer_remaining_seconds_at_admission": remaining}


def _arm_wall_timer():
    # Continues to bound waits even if the HTTP/CLI controller disappears.
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL, WALL_SECONDS)


def _pairs(items):
    value = {}
    for key, item in items:
        _require(key not in value)
        value[key] = item
    return value


def _reject_constant(_):
    raise ValueError("nonfinite JSON rejected")


def _request(raw):
    _require(0 < len(raw) <= MAX_REQUEST_BYTES)
    value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    _require(type(value) is dict and set(value) == {
        "schema_version", "nonce", "protocol", "protocol_sha256", "directory",
        "implementation_sources", "runtime_identity", "with_report"})
    _require(value["schema_version"] == REQUEST_SCHEMA and type(value["protocol"]) is dict
             and type(value["with_report"]) is bool and type(value["nonce"]) is str
             and len(value["nonce"]) == 64 and all(c in "0123456789abcdef" for c in value["nonce"])
             and _sha(_canonical(value["protocol"])) == value["protocol_sha256"])
    directory = Path(value["directory"])
    _require(directory.is_absolute() and not directory.is_symlink()
             and directory.resolve(strict=True) == directory and directory.is_dir())
    return value


def _origin(module, root):
    _require(Path(module.__file__).resolve().is_relative_to(root))


def _initialize_torch():
    _require("torch" not in sys.modules)
    import torch

    _origin(torch, Path(sys.prefix).resolve())
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    _require(torch.get_num_threads() == 1 and torch.get_num_interop_threads() == 1)


def _count(value):
    _require(type(value) is int and value >= 0)
    return value


def _read_owning(protocol, directory, *, with_report):
    """Only owning reads; no direct run/evaluate/graph/minimizer dispatch."""
    from .cpu_refinement_fourier_v1 import workflow
    from .cpu_refinement_v1_2 import provenance

    root = Path(__file__).resolve().parent.parent
    _origin(workflow, root)
    _origin(provenance, root)
    if with_report:
        from . import prepared_refinement_cli

        _origin(prepared_refinement_cli, root)
        document = prepared_refinement_cli.report(protocol, directory)
        _require(document.get("verification_scope") == OWNING_SCOPE
                 and document.get("work", {}).get("report_force_evaluation_calls") == 0)
        result = {"binding": document["binding"], "status": document["execution_status"],
                  "known_force_calls": _count(document["work"]["known_force_evaluation_calls"]),
                  "total_work_known": document["work"]["total_work_known"], "report": document}
    else:
        checked = workflow.verify(protocol, directory)
        _require(checked.get("verification_scope") == OWNING_SCOPE)
        rows = ([] if checked["baseline"] is None else [checked["baseline"]]) + checked["invocations"]
        result = {"binding": checked["binding"], "status": checked["status"],
                  "known_force_calls": sum(_count(r["work"]["force_evaluation_calls"]) for r in rows),
                  "total_work_known": checked["unknown_stage"] is None, "report": None}
    _require(type(result["total_work_known"]) is bool)
    result["evaluator"] = workflow._committed(directory / "frozen.json")["payload"]["evaluator"]
    result["read_only_environment"] = provenance.environment()
    return result


def main():
    stage = "bootstrap"
    try:
        _arm_wall_timer()
        root = _bootstrap()
        applied = _apply_resources(int(os.environ["BETELGEUZE_READONLY_CPU"]))
        stage = "request"
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        request = _request(raw)
        from . import prepared_lifecycle as core

        _origin(core, root)
        _require(core.implementation_sources() == request["implementation_sources"]
                 and core.runtime_identity() == request["runtime_identity"])
        stage = "owning_read"
        _initialize_torch()
        result = _read_owning(request["protocol"], Path(request["directory"]), with_report=request["with_report"])
        _require(core.implementation_sources() == request["implementation_sources"]
                 and core.runtime_identity() == request["runtime_identity"])
        usage = resource.getrusage(resource.RUSAGE_SELF)
        cost = {"CPU_seconds": usage.ru_utime + usage.ru_stime,
                "worker_module_wall_seconds": time.monotonic()-_MODULE_STARTED,
                "peak_RSS_bytes": usage.ru_maxrss * 1024,
                "CPU_scope": "this isolated worker own CPU through measurement, including imports/read; excludes response serialization/emission",
                "wall_scope": "worker module entry through measurement; interpreter startup and response serialization/emission excluded",
                "peak_RSS_scope": "this worker high-water RSS through measurement; observed, not a RAM limit",
                "applied_resources": applied, "new_force_calls": 0,
                "execution_budget_charged": False}
        response = {"schema_version": RESPONSE_SCHEMA, "nonce": request["nonce"],
                    "request_sha256": _sha(raw), "implementation_sources": request["implementation_sources"],
                    "runtime_identity": request["runtime_identity"], "result": result, "read_only_child_cost": cost}
        encoded = _canonical(response) + b"\n"
        _require(len(encoded) <= MAX_RESPONSE_BYTES)
        sys.stdout.buffer.write(encoded)
        sys.stdout.buffer.flush()
        return 0
    except BaseException:
        # Never echo bound private paths, raw protocol contents, or credentials.
        sys.stderr.write(json.dumps({"code": "READ_VERIFICATION_FAILED", "stage": stage}) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
