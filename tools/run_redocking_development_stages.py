#!/usr/bin/env python3
"""Bounded development execution around the unchanged public redocking runner."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "config/redocking_development_stages_20261103.json"
ENGINES = ("engine_v2", "vina", "gnina")
ROLES = ("receptor", "reference", "native", "seed")


class ProcessCleanupError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest_json(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    os.replace(temp, path)


def read_json(path):
    def invalid(value):
        raise ValueError("nonfinite JSON: " + value)
    return json.loads(Path(path).read_text(), parse_constant=invalid)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def contract():
    from betelgeuze_engine_v2.benchmark import public_redocking_benchmark
    return public_redocking_benchmark


def manifest():
    m = read_json(MANIFEST_PATH)
    c = contract()
    require(m["case_ids"] == list(c.FROZEN_PUBLIC_REDOCKING_CASE_IDS[:34]),
            "development case order changed")
    require(not set(m["case_ids"]) & set(c.FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS),
            "development selection overlaps fresh case metadata")
    require(len(set(m["case_ids"])) == 34, "duplicate case")
    require(m["analysis_scope"] == "contaminated_development" and not m["claim_safe"],
            "scope must remain development only")
    return m


def source_record(m):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    numerical_paths = ("betelgeuze_engine_v2", "tools/run_engine_v2_public_redocking_300.py",
                       "benchmarks/oracles", "rust_engine_v2", "rust/betelgeuze-docking-search")
    require(git("rev-parse", m["baseline_commit"] + "^{tree}") == m["baseline_tree"],
            "baseline tree mismatch")
    require(not git("diff", "--name-only", m["baseline_commit"], "--", *numerical_paths),
            "numerical implementation differs from frozen baseline")
    return {"commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
            "baseline_commit": m["baseline_commit"], "baseline_tree": m["baseline_tree"],
            "wrapper_sha256": digest_file(__file__),
            "manifest_sha256": digest_file(MANIFEST_PATH),
            "runner_sha256": digest_file(ROOT / "tools/run_engine_v2_public_redocking_300.py"),
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT")}


def verify_input(path, spec):
    require(path.is_file() and not path.is_symlink(), "input missing or symlink: " + str(path))
    require(path.stat().st_size == spec["size"], "input size mismatch: " + str(path))
    require(digest_file(path) == spec["sha256"], "input hash mismatch: " + str(path))


def download_inputs(input_root, m):
    input_root.mkdir(parents=True, exist_ok=True)
    for key, spec in m["inputs"].items():
        path = input_root / spec["filename"]
        if not path.exists():
            temporary = path.with_suffix(path.suffix + ".part")
            print("Downloading " + key, flush=True)
            request = urllib.request.Request(spec["url"], headers={"User-Agent": "ligand-docking-development/1.0"})
            try:
                with urllib.request.urlopen(request, timeout=60) as response, temporary.open("xb") as output:
                    total = 0
                    while data := response.read(1024 * 1024):
                        total += len(data)
                        require(total <= spec["size"], "download exceeds declared size")
                        output.write(data)
                verify_input(temporary, spec)
                temporary.replace(path)
            finally:
                if temporary.exists():
                    temporary.unlink()
        verify_input(path, spec)
        path.chmod(0o500 if key == "gnina" else 0o444)


def rmsd_contract_test():
    from rdkit import Chem
    from posebusters.modules.rmsd import check_rmsd
    reference = Chem.MolFromSmiles("CCO")
    conf = Chem.Conformer(reference.GetNumAtoms())
    for i, xyz in enumerate(((0., 0., 0.), (1.5, 0., 0.), (2.1, 1.2, .4))):
        conf.SetAtomPosition(i, xyz)
    reference.AddConformer(conf)
    shifted = Chem.Mol(reference)
    for i in range(shifted.GetNumAtoms()):
        p = shifted.GetConformer().GetAtomPosition(i)
        shifted.GetConformer().SetAtomPosition(i, (p.x + 3., p.y, p.z))
    result = check_rmsd(shifted, reference)["results"]
    require(abs(result["rmsd"] - 3.0) < 1.e-9, "RMSD silently aligned ligand")
    require(result["kabsch_rmsd"] < 1.e-6, "shape RMSD test inconsistent")
    return {k: float(v) for k, v in result.items()}


def prepare(input_root, output_root):
    from importlib import metadata
    import rdkit
    import torch
    from tools import run_engine_v2_public_redocking_300 as runner
    m = manifest()
    output_root.mkdir(parents=True, exist_ok=True)
    record = {"status": "preparing", "started_at": utc_now(), "source": source_record(m)}
    write_json(output_root / "preflight.json", record)
    try:
        try:
            metadata.distribution("rdkit")
        except metadata.PackageNotFoundError:
            pass
        else:
            raise RuntimeError("both RDKit distribution names must not be installed")
        record["evaluator_versions"] = runner._evaluator_environment_versions()
        require(rdkit.__version__ == "2022.09.5", "loaded RDKit module version differs")
        record["rdkit_origin"] = rdkit.__file__
        record["rdkit_module_sha256"] = digest_file(rdkit.__file__)
        record["evaluator_payload_sha256s"] = runner._evaluator_distribution_payload_sha256s()
        record["torch_version"] = str(torch.__version__)
        record["python"] = sys.version
        record["platform"] = platform.platform()
        record["host_cpu_count"] = os.cpu_count()
        record["runner_image"] = {k: os.environ.get(k) for k in ("ImageOS", "ImageVersion", "RUNNER_OS", "RUNNER_ARCH")}
        record["loader_library_path"] = os.environ.get("LD_LIBRARY_PATH")
        record["engine_source_sha256"] = runner._engine_source_sha256(ROOT)
        record["evaluation_pipeline_sha256"] = runner._evaluation_pipeline_sha256(ROOT)
        record["rmsd_semantics_test"] = rmsd_contract_test()
        check = subprocess.run([sys.executable, "-m", "pip", "check"], text=True,
                               capture_output=True, timeout=60)
        record["pip_check"] = {"returncode": check.returncode, "stdout": check.stdout, "stderr": check.stderr}
        expected = "posebusters 0.3.1 requires rdkit, which is not installed."
        if check.returncode:
            lines = [x.strip().lower() for x in check.stdout.splitlines() if x.strip()]
            require(lines == [expected], "pip check has an unexpected dependency failure")
        download_inputs(input_root, m)
        binary = input_root / m["inputs"]["gnina"]["filename"]
        linkage = subprocess.run(["ldd", str(binary)], text=True, capture_output=True, timeout=30)
        record["gnina_ldd"] = {"returncode": linkage.returncode, "stdout": linkage.stdout, "stderr": linkage.stderr}
        linked = {}
        for line in linkage.stdout.splitlines():
            tokens = line.split()
            if "=>" in tokens:
                target = tokens[tokens.index("=>") + 1]
                if target.startswith("/") and Path(target).is_file():
                    linked[target] = digest_file(target)
        record["gnina_linked_library_sha256s"] = linked
        probe = subprocess.run([str(binary), "--version"], text=True, capture_output=True, timeout=30)
        record["gnina_version_probe"] = {"returncode": probe.returncode,
                                        "stdout": probe.stdout, "stderr": probe.stderr}
        require(probe.returncode == 0, "GNINA loader/version probe failed: " + probe.stderr)
        record["input_specs"] = m["inputs"]
        record["status"] = "ready"
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        record["finished_at"] = utc_now()
        write_json(output_root / "preflight.json", record)
    print(json.dumps({"preflight": "ready", "rmsd_translation": record["rmsd_semantics_test"]["rmsd"]}), flush=True)


def proc_snapshot():
    result = {}
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            text = path.read_text()
            fields = text[text.rfind(")") + 2:].split()
            result[int(path.parent.name)] = {
                "ppid": int(fields[1]), "pgrp": int(fields[2]), "start": int(fields[19]),
                "rss": max(0, int(fields[21])) * os.sysconf("SC_PAGE_SIZE"), "state": fields[0]}
        except (OSError, ValueError, IndexError):
            continue
    return result


def descendants(snapshot, root_pid, tracked):
    ids = {root_pid} | {pid for pid, start in tracked.items()
                       if pid in snapshot and snapshot[pid]["start"] == start}
    changed = True
    while changed:
        new = {pid for pid, info in snapshot.items() if info["ppid"] in ids}
        changed = not new <= ids
        ids |= new
    return {pid: snapshot[pid] for pid in ids if pid in snapshot}


def _stop_tree_impl(process, tracked):
    # External oracle processes create their own sessions; kill all observed descendant groups.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        snapshot = proc_snapshot()
        active = descendants(snapshot, process.pid, tracked)
        tracked.update({pid: info["start"] for pid, info in active.items()})
        groups = {info["pgrp"] for info in active.values() if info["state"] != "Z"}
        for group in groups:
            if group > 1 and group != os.getpgrp():
                try:
                    os.killpg(group, sig)
                except ProcessLookupError:
                    pass
        if sig == signal.SIGTERM:
            time.sleep(1)
    process.wait(timeout=10)
    deadline = time.monotonic() + 3.0
    while True:
        active = descendants(proc_snapshot(), process.pid, tracked)
        live = [pid for pid, info in active.items() if info["state"] != "Z"]
        if not live:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("descendants survived cleanup: " + repr(live))
        time.sleep(.05)


def stop_tree(process, tracked):
    try:
        _stop_tree_impl(process, tracked)
    except Exception as exc:
        raise ProcessCleanupError("process cleanup failed: " + str(exc)) from exc


def invoke_case(command, log_path, m):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    tracked = {}
    peak = 0
    reason = "exited"
    with log_path.open("xb") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        while process.poll() is None:
            active = descendants(proc_snapshot(), process.pid, tracked)
            tracked.update({pid: info["start"] for pid, info in active.items()})
            peak = max(peak, sum(info["rss"] for info in active.values()))
            if time.monotonic() - started > m["case_wall_seconds"]:
                reason = "wall_timeout"
                stop_tree(process, tracked)
                break
            if peak > m["process_tree_rss_limit_bytes"]:
                reason = "sampled_process_tree_rss_limit"
                stop_tree(process, tracked)
                break
            time.sleep(m["sampling_seconds"])
        returncode = process.wait()
        remaining = descendants(proc_snapshot(), process.pid, tracked)
        if any(info["state"] != "Z" for info in remaining.values()):
            stop_tree(process, tracked)
            reason = "remaining_descendants_terminated"
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"returncode": returncode, "termination": reason, "cleanup_complete": True,
            "supervision_scope": "observed descendants; sampled RSS, not cgroup containment",
            "wall_seconds": time.monotonic() - started,
            "child_cpu_seconds": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
            "sampled_peak_process_tree_rss_bytes": peak,
            "rss_measurement": "sum of observed descendant RSS; shared pages may be counted multiple times",
            "rss_sampling_seconds": m["sampling_seconds"]}


def verify_receipt(path, expected_case, engine, m, preflight, materialization):
    payload = read_json(path)
    require(payload["schema_id"] == contract().PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID,
            "execution schema mismatch")
    require(payload["runner_id"] == contract().PUBLIC_REDOCKING_RUNNER_ID, "runner identity mismatch")
    stored = payload.pop("receipt_sha256")
    require(digest_json(payload) == stored, "receipt digest mismatch")
    require(payload["archive_sha256"] == m["inputs"]["archive"]["sha256"], "archive identity mismatch")
    require(payload["source_ids_sha256"] == m["inputs"]["source_identifiers"]["sha256"], "identifier mismatch")
    require(payload["fresh_execution"] is True and payload["cache_read_allowed"] is False, "cached receipt")
    require(payload["materialization_receipt_sha256"] == materialization["receipt_sha256"], "materialization mismatch")
    expected_impl = preflight["engine_source_sha256"] if engine == "engine_v2" else m["inputs"]["gnina"]["sha256"]
    require(payload["implementation_sha256"] == expected_impl, "implementation identity mismatch")
    require(payload["evaluation_pipeline_sha256"] == preflight["evaluation_pipeline_sha256"], "evaluator identity mismatch")
    row = payload["result"]
    require((row["case_id"], row["engine_id"]) == (expected_case, engine), "result identity mismatch")
    command = payload["command"]
    require(int(command[command.index("--seed") + 1]) == m["seed_base"] + m["case_ids"].index(expected_case),
            "case seed changed")
    expected_files = ("protein.pdb", "ligands.sdf", "ligand.sdf", "ligand_start_conf.sdf")
    for role, filename in zip(ROLES, expected_files):
        require(row[role + "_artifact_sha256"] == materialization["artifact_sha256s"][filename],
                "input artifact cross-wired")
    if row["status"] == "success":
        for key in ("rmsd_angstroms", "geometric_valid", "chemical_valid", "pose_artifact_sha256s"):
            require(len(row[key]) == 5, "successful row must retain five ranked poses")
        require(all(type(x) is bool for x in row["geometric_valid"] + row["chemical_valid"]),
                "invalid validity values")
        require(all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in row["rmsd_angstroms"]),
                "invalid RMSD")
        require(not row["failure_code"], "successful row has failure")
    else:
        require(row["status"] == "failure" and bool(row["failure_code"]), "untyped failure")
        require(all(not row[key] for key in ("rmsd_angstroms", "geometric_valid", "chemical_valid",
                                             "pose_artifact_sha256s")), "failed row has outcomes")
    if engine == "engine_v2":
        diag = row["engine_v2_diagnostics"]
        require(isinstance(diag, dict), "missing Engine V2 diagnostics")
        if diag["preparation_status"] == "success":
            candidates = diag["candidates"]
            require(len(candidates) == 64 and {x["proposal_index"] for x in candidates} == set(range(64)),
                    "candidate slot denominator changed")
            ranked = sorted((x for x in candidates if x["status"] == "success"
                             and isinstance(x["score"], (int, float)) and math.isfinite(x["score"])),
                            key=lambda x: (x["score"], x["proposal_index"]))
            if row["status"] == "success":
                require(len(ranked) >= 5, "successful row lacks five scored candidates")
                for i, candidate in enumerate(ranked[:5]):
                    require(candidate["rmsd_angstrom"] == row["rmsd_angstroms"][i]
                            and candidate["geometric_valid"] == row["geometric_valid"][i]
                            and candidate["chemical_valid"] == row["chemical_valid"][i]
                            and candidate["pose_artifact_sha256"] == row["pose_artifact_sha256s"][i],
                            "reported Top5 differs from score-ranked candidates")
    return row


def recoveries(row):
    if row is None or row["status"] != "success":
        return {name + str(k): 0 for name in ("top", "valid_top") for k in (1, 3, 5)}
    result = {}
    for k in (1, 3, 5):
        result["top" + str(k)] = int(any(r <= 2.0 for r in row["rmsd_angstroms"][:k]))
        result["valid_top" + str(k)] = int(any(r <= 2.0 and g and c for r, g, c in zip(
            row["rmsd_angstroms"][:k], row["geometric_valid"][:k], row["chemical_valid"][:k])))
    return result


def row_metrics(row):
    result = recoveries(row)
    if row is None:
        result.update(status="unobserved", failure_code="missing_engine_receipt")
        return result
    result.update(status=row["status"], failure_code=row["failure_code"],
                  runtime_seconds=row["runtime_seconds"])
    diag = row.get("engine_v2_diagnostics")
    if diag:
        candidates = [x for x in diag["candidates"] if x["status"] == "success"]
        result["oracle"] = int(any(x["rmsd_angstrom"] <= 2.0 for x in candidates))
        result["valid_oracle"] = int(any(x["rmsd_angstrom"] <= 2.0 and x["geometric_valid"]
                                       and x["chemical_valid"] for x in candidates))
        result["candidate_slots"] = len(diag["candidates"])
        result["successful_candidate_count"] = len(candidates)
        result["preparation_status"] = diag["preparation_status"]
        result["diagnostic_evaluation_seconds"] = diag["diagnostic_evaluation_seconds"]
        require(result["valid_top5"] <= result["valid_oracle"] <= result["oracle"],
                "oracle/ranking invariant violated")
    return result


def summarize_attempts(attempts, expected_indices, m):
    by_index = {x["global_index"]: x for x in attempts}
    require(len(by_index) == len(attempts), "duplicate case attempt")
    require(set(by_index) <= set(expected_indices), "unexpected case")
    rows = []
    for index in expected_indices:
        attempt = by_index.get(index)
        for engine in ENGINES:
            row = attempt.get("rows", {}).get(engine) if attempt else None
            metrics = row_metrics(row)
            rows.append({"global_index": index, "case_id": m["case_ids"][index], "engine_id": engine,
                         "case_termination": attempt["execution"]["termination"] if attempt else "not_executed",
                         **metrics})
    metrics = {}
    for engine in ENGINES:
        selected = [x for x in rows if x["engine_id"] == engine]
        names = ["top1", "top3", "top5", "valid_top1", "valid_top3", "valid_top5"]
        values = {name: sum(x[name] for x in selected) / len(selected) for name in names}
        values["case_count"] = len(selected)
        values["observed_rows"] = sum(x["status"] != "unobserved" for x in selected)
        values["success_rows"] = sum(x["status"] == "success" for x in selected)
        values["failure_rows"] = sum(x["status"] == "failure" for x in selected)
        values["unobserved_rows"] = sum(x["status"] == "unobserved" for x in selected)
        runtime = [x["runtime_seconds"] for x in selected if "runtime_seconds" in x]
        values["median_observed_engine_runtime_seconds"] = statistics.median(runtime) if runtime else None
        if engine == "engine_v2":
            for name in ("oracle", "valid_oracle"):
                values[name + "_operational_rate"] = sum(x.get(name, 0) for x in selected) / len(selected)
        metrics[engine] = values
    return {"schema_id": "betelgeuze.redocking_development_summary/1.0.0",
            "analysis_scope": "contaminated_development", "claim_safe": False,
            "primary_claim_eligible": False, "manifest_sha256": digest_file(MANIFEST_PATH),
            "expected_indices": list(expected_indices), "attempted_cases": len(attempts),
            "unobserved_policy": "Count as operational non-recovery; retain missing observations separately.",
            "scientific_accuracy_complete": all(x["status"] != "unobserved" for x in rows),
            "physical_energy_force_calls": None,
            "physical_energy_force_calls_reason": "V7/ScorerV1 lane; no physical E/F count inferred.",
            "metrics": metrics, "case_metrics": rows}


def publish_summary(output_root, attempts, indices, m):
    summary = summarize_attempts(attempts, indices, m)
    summary["source"] = source_record(m)
    write_json(output_root / "summary.json", summary)
    with (output_root / "case-metrics.csv").open("w", newline="") as f:
        fields = sorted({k for row in summary["case_metrics"] for k in row})
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary["case_metrics"])
    print(json.dumps({"summary": summary["metrics"]}, sort_keys=True), flush=True)
    return summary


def run_stage(stage, start, count, input_root, output_root):
    m = manifest()
    indices = list(range(start, start + count))
    require((stage == "smoke" and indices == [0, 1]) or
            (stage == "development" and start in (2, 10, 18, 26) and count == 8),
            "only the frozen 2-case or four 8-case shards may execute")
    require(not list(output_root.glob("attempt-*.json")), "attempt directory is not fresh")
    preflight = read_json(output_root / "preflight.json")
    require(preflight["status"] == "ready", "preflight has not passed")
    for spec in m["inputs"].values():
        verify_input(input_root / spec["filename"], spec)
    attempts = []
    raw_root = output_root / "raw"
    raw_root.mkdir(exist_ok=True)
    write_json(output_root / "run-manifest.json", {**m, "active_indices": indices,
               "stage": stage, "source": source_record(m), "started_at": utc_now()})
    for index in indices:
        case_id = m["case_ids"][index]
        case_root = raw_root / case_id
        require(not case_root.exists(), "case directory already exists")
        command = [sys.executable, "-m", "tools.run_engine_v2_public_redocking_300",
                   "--archive", str(input_root / m["inputs"]["archive"]["filename"]),
                   "--source-identifiers", str(input_root / m["inputs"]["source_identifiers"]["filename"]),
                   "--gnina", str(input_root / m["inputs"]["gnina"]["filename"]),
                   "--output-root", str(case_root), "--case-subset", "all",
                   "--start-index", str(index), "--limit", "1",
                   "--seed", str(m["seed_base"]), "--timeout-seconds", "300",
                   "--bootstrap-samples", "2000", "--engine-v2-scorer-backend", "python_reference"]
        record = {"global_index": index, "case_id": case_id, "stage": stage, "command": command,
                  "started_at": utc_now(), "rows": {}, "verification_errors": [],
                  "execution": {"termination": "started"}}
        record_path = output_root / ("attempt-%02d.json" % index)
        write_json(record_path, record)
        print("START %s index=%d seed=%d" % (case_id, index, m["seed_base"] + index), flush=True)
        try:
            record["execution"] = invoke_case(command, output_root / (case_id + ".log"), m)
            mat_path = case_root / "receipts/materializations" / (case_id + ".json")
            if mat_path.is_file():
                materialization = read_json(mat_path)
                require(materialization["case_id"] == case_id and
                        materialization["frozen_case_seed"] == m["seed_base"] + index and
                        materialization["source_archive_sha256"] == m["inputs"]["archive"]["sha256"],
                        "materialization case/seed/archive mismatch")
                projection = {k: v for k, v in materialization.items() if k != "receipt_sha256"}
                require(digest_json(projection) == materialization["receipt_sha256"], "materialization digest mismatch")
                for engine in ENGINES:
                    path = case_root / "receipts" / engine / (case_id + ".json")
                    if path.is_file():
                        try:
                            record["rows"][engine] = verify_receipt(path, case_id, engine, m, preflight, materialization)
                        except Exception as exc:
                            record["verification_errors"].append(engine + ": " + str(exc))
            record["raw_scopes"] = [read_json(p).get("analysis_scope") for p in case_root.glob("*partial*.json")]
        except Exception as exc:
            record["verification_errors"].append(type(exc).__name__ + ": " + str(exc))
            record["execution"].setdefault("error", str(exc))
            if isinstance(exc, ProcessCleanupError):
                record["execution"]["termination"] = "cleanup_failed"
        finally:
            record["finished_at"] = utc_now()
            # Only the disposable per-case binary copy is removed; all numerical evidence stays.
            staged = case_root / "private-external-binary"
            if staged.is_dir() and not staged.is_symlink():
                shutil.rmtree(staged)
            write_json(record_path, record)
            attempts.append(record)
            publish_summary(output_root, attempts, indices, m)
        print("END %s rows=%d termination=%s" % (case_id, len(record["rows"]),
                                               record["execution"]["termination"]), flush=True)
        if record["execution"]["termination"] == "cleanup_failed":
            break
    summary = publish_summary(output_root, attempts, indices, m)
    complete = (summary["scientific_accuracy_complete"] and all(
        not x["verification_errors"] and x["execution"].get("returncode") == 0
        and x["execution"].get("termination") == "exited"
        and x["execution"].get("cleanup_complete") is True for x in attempts))
    searched = any(x.get("rows", {}).get("engine_v2", {}).get("engine_v2_diagnostics", {}).get(
        "preparation_status") == "success" for x in attempts)
    gate = bool(complete and searched)
    write_json(output_root / "stage-status.json", {"stage": stage, "complete": complete,
               "prepared_case_observed": searched, "next_stage_ready": gate,
               "accuracy_threshold_used_for_admission": False})
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("next_stage_ready=" + str(gate).lower() + "\n")
    return 0 if complete else 1


def collect_inventory(output_root):
    rows = []
    total = 0
    for path in sorted(output_root.rglob("*")):
        if path.is_file() and not path.is_symlink() and path.name != "artifact-inventory.json":
            require("private-external-binary" not in path.parts, "binary staged in evidence")
            size = path.stat().st_size
            total += size
            rows.append({"path": str(path.relative_to(output_root)), "size": size, "sha256": digest_file(path)})
    require(total < 512 * 1024 * 1024, "evidence exceeds 512 MiB")
    write_json(output_root / "artifact-inventory.json", {"bytes": total, "files": rows})


def self_test():
    m = manifest()
    row = {"status": "success", "rmsd_angstroms": [1.0, 3.0, 1.5, 4.0, 5.0],
           "geometric_valid": [False, True, True, True, True], "chemical_valid": [True] * 5}
    require(recoveries(row) == {"top1": 1, "valid_top1": 0, "top3": 1, "valid_top3": 1,
                                "top5": 1, "valid_top5": 1}, "validity/rank semantics changed")
    empty = summarize_attempts([], [0, 1], m)
    require(empty["metrics"]["engine_v2"]["case_count"] == 2 and
            empty["metrics"]["engine_v2"]["unobserved_rows"] == 2, "missing denominator dropped")
    rmsd = rmsd_contract_test()
    with tempfile.TemporaryDirectory() as directory:
        limited = {**m, "case_wall_seconds": .3, "sampling_seconds": .05}
        probe = invoke_case([sys.executable, "-c", "import time; time.sleep(30)"],
                            Path(directory) / "timeout.log", limited)
        require(probe["termination"] == "wall_timeout" and probe["returncode"] != 0,
                "case timeout is not enforced")
        for early_exit in (False, True):
            child_marker = Path(directory) / ("child-%s.pid" % early_exit)
            child_code = ("import os, signal, time; from pathlib import Path; "
                          "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                          "p=Path(%r); p.with_suffix('.tmp').write_text(str(os.getpid())); "
                          "os.replace(p.with_suffix('.tmp'), p); time.sleep(30)" % str(child_marker))
            parent_code = ("import subprocess, sys, time; "
                           "subprocess.Popen([sys.executable, '-c', %r], start_new_session=True); "
                           "time.sleep(%s)" % (child_code, ".25" if early_exit else "30"))
            limits = {**m, "case_wall_seconds": .6, "sampling_seconds": .025}
            observed = invoke_case([sys.executable, "-c", parent_code],
                                   Path(directory) / ("tree-%s.log" % early_exit), limits)
            require(child_marker.exists(), "separate-session control did not start")
            child_pid = int(child_marker.read_text())
            require(proc_snapshot().get(child_pid, {"state": "Z"})["state"] == "Z",
                    "separate-session child survived")
            expected = "remaining_descendants_terminated" if early_exit else "wall_timeout"
            require(observed["termination"] == expected, "process tree cleanup reason changed")
        marker = Path(directory) / "previously-untracked.pid"
        child_code = ("import os, signal, time; from pathlib import Path; "
                      "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                      "p=Path(%r); p.with_suffix('.tmp').write_text(str(os.getpid())); "
                          "os.replace(p.with_suffix('.tmp'), p); time.sleep(30)" % str(marker))
        parent_code = ("import subprocess, sys, time; "
                       "subprocess.Popen([sys.executable, '-c', %r], start_new_session=True); "
                       "time.sleep(30)" % child_code)
        process = subprocess.Popen([sys.executable, "-c", parent_code], start_new_session=True)
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.025)
        try:
            require(marker.exists(), "untracked-descendant control did not start")
            child_pid = int(marker.read_text())
            stop_tree(process, {})
            require(proc_snapshot().get(child_pid, {"state": "Z"})["state"] == "Z",
                    "child discovered during TERM survived KILL")
        finally:
            if process.poll() is None:
                stop_tree(process, {})
    print(json.dumps({"tests": 7, "passed": 7, "synthetic_only": True, "rmsd": rmsd}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("self-test", "prepare", "run", "inventory", "aggregate"))
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--stage", choices=("smoke", "development"))
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--artifact-root", type=Path)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    if args.action == "self-test":
        self_test()
    elif args.action == "prepare":
        prepare(args.input_root.resolve(), args.output_root.resolve())
    elif args.action == "run":
        return run_stage(args.stage, args.start, args.count, args.input_root.resolve(), args.output_root.resolve())
    elif args.action == "inventory":
        collect_inventory(args.output_root)
    else:
        m = read_json(MANIFEST_PATH)
        attempts = [read_json(path) for path in args.artifact_root.rglob("attempt-*.json")]
        for stage, indices in (("smoke", [0, 1]), ("development", list(range(2, 34)))):
            destination = args.output_root / stage
            destination.mkdir(exist_ok=True)
            selected = [x for x in attempts if x["stage"] == stage]
            summary = publish_summary(destination, selected, indices, m)
            for metric in summary["case_metrics"]:
                print(json.dumps({"case_metric": metric}, sort_keys=True), flush=True)
            for attempt in selected:
                for engine, row in attempt["rows"].items():
                    detail = {"stage": stage, "case_id": row["case_id"], "engine_id": engine,
                              "status": row["status"], "failure_code": row["failure_code"],
                              "runtime_seconds": row["runtime_seconds"], "rmsd_angstroms": row["rmsd_angstroms"],
                              "geometric_valid": row["geometric_valid"], "chemical_valid": row["chemical_valid"],
                              "execution": attempt["execution"]}
                    diag = row.get("engine_v2_diagnostics")
                    if diag:
                        detail["preparation_failure_code"] = diag["preparation_failure_code"]
                        candidates = [x for x in diag["candidates"] if x["status"] == "success"]
                        if candidates:
                            picks = {"score_top1": min(candidates, key=lambda x: (x["score"], x["proposal_index"])),
                                     "rmsd_oracle": min(candidates, key=lambda x: (x["rmsd_angstrom"], x["proposal_index"]))}
                            for label, candidate in picks.items():
                                keys = ("proposal_index", "proposal_mode", "score", "rmsd_angstrom",
                                        "geometric_valid", "chemical_valid", "posebusters_failed_check_ids",
                                        "score_term_binary64_hex")
                                detail[label] = {key: candidate.get(key) for key in keys}
                    print(json.dumps({"case_detail": detail}, sort_keys=True), flush=True)
        collect_inventory(args.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
