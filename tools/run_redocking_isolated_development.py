"""Explicit-profile, per-engine development processes; no invented science rows."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
from tools.redocking_isolation import (AtomicJournal, CleanupError, IsolationError,
    Limits, atomic_json, digest_file, digest_json, read_checkpoint, supervise)

ROOT = Path(__file__).resolve().parents[1]
ENGINES = ("engine_v2", "vina", "gnina")
PROFILES = ("legacy_v7", "development_observation_v1")
ROLES = {"receptor": "protein.pdb", "reference": "ligands.sdf",
         "native": "ligand.sdf", "seed": "ligand_start_conf.sdf"}
SCHEMA = "betelgeuze.redocking_isolated_development_stages/1.0.0"


def require(condition, message):
    if not condition:
        raise IsolationError(message)


def read_json(path):
    def pairs(values):
        out = {}
        for k, v in values:
            require(k not in out, "duplicate JSON key")
            out[k] = v
        return out
    def invalid(value):
        raise IsolationError("nonfinite JSON: " + value)
    raw = path if isinstance(path, bytes) else Path(path).read_bytes()
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def now():
    return datetime.now(timezone.utc).isoformat()


def task_limits(m, kind):
    b = m["isolation"]
    wall = b["materialization_wall_seconds"] if kind == "materialize" else b["engine_wall_seconds"][kind]
    return Limits(wall, rss_bytes=b["rss_limit_bytes"], poll_seconds=b["poll_seconds"], log_bytes=b["log_bytes"])


def load_manifest(path):
    m = read_json(path)
    require(m["schema_id"] == SCHEMA, "unsupported isolated manifest")
    require(m["analysis_scope"] == "contaminated_development" and m["claim_safe"] is False
            and m["primary_claim_eligible"] is False, "development boundary changed")
    require(len(m["case_ids"]) == len(set(m["case_ids"])) == 34
            and all(re.fullmatch(r"[0-9][A-Z0-9]{3}_[A-Z0-9]{3}", c) for c in m["case_ids"]),
            "expected frozen 34-case selection")
    require(m["smoke_indices"] == [0, 1] and m["development_indices"] == list(range(2, 34)),
            "stage selection changed")
    for k, v in {"seed_base": 2026072700, "candidate_count": 64, "output_pose_count": 5,
                 "repetitions": 1, "rmsd_threshold_angstrom": 2,
                 "external_timeout_seconds": 300, "scorer_backend": "python_reference"}.items():
        require(m[k] == v, "frozen execution policy changed: " + k)
    require(set(m["profiles"]) == set(PROFILES), "explicit development profiles required")
    require(set(m["inputs"]) == {"archive", "source_identifiers", "gnina"}, "input set changed")
    for spec in m["inputs"].values():
        require(Path(spec["filename"]).name == spec["filename"] and type(spec["size"]) is int
                and spec["size"] > 0 and re.fullmatch(r"[0-9a-f]{64}", spec["sha256"]), "invalid input spec")
    for kind in ("materialize", *ENGINES):
        task_limits(m, kind)
    return m


def source_identity(manifest):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    require(not git("status", "--porcelain", "--untracked-files=no"), "tracked source is modified")
    files = ("tools/run_redocking_isolated_development.py", "tools/redocking_isolation.py",
             "tools/run_engine_v2_public_redocking_300.py", "tools/redocking_development_p1.py")
    return {"commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
            "manifest_sha256": digest_file(manifest),
            "entrypoint_sha256s": {n: digest_file(ROOT / n) for n in files},
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT")}


def verify_input(path, spec):
    require(path.is_file() and not path.is_symlink(), "input must be a regular nonsymlink file")
    require(path.stat().st_size == spec["size"] and digest_file(path) == spec["sha256"], "input bytes changed")


def verify_self_hash(record):
    require(digest_json({k: v for k, v in record.items() if k != "receipt_sha256"}) == record["receipt_sha256"],
            "canonical receipt mismatch")


def validate_job_preflight(request, worker_preflight=None):
    reference = request.get("job_preflight")
    if reference is None:
        return None
    path = Path(reference["path"])
    require(path.is_file() and not path.is_symlink(), "job preflight missing or symlinked")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == reference["sha256"], "job preflight changed")
    job = read_json(raw)
    source = request["source"]
    require(job["status"] == "ready" and job["commit"] == source["commit"]
        and job["manifest_sha256"] == source["manifest_sha256"]
        and job.get("workflow_run_id") == source.get("workflow_run_id")
        and job.get("workflow_run_attempt") == source.get("workflow_run_attempt"),
        "job preflight status/source mismatch")
    if worker_preflight is not None:
        for key in ("evaluation_pipeline_sha256", "engine_source_sha256", "evaluator_versions",
                    "evaluator_payload_sha256s"):
            require(job[key] == worker_preflight[key], "job/worker preflight mismatch: " + key)
    return {"path": str(path), "sha256": reference["sha256"], "status": "verified",
            "worker_environment_compared": worker_preflight is not None,
            "environment_content_identity_sha256": job.get("environment_content_identity_sha256")}


def common_inputs(directory, cid, index, m):
    mat = read_json(directory / "materialization.json")
    verify_self_hash(mat)
    require(mat["case_id"] == cid and mat["frozen_case_seed"] == m["seed_base"] + index
            and mat["source_archive_sha256"] == m["inputs"]["archive"]["sha256"]
            and mat["hash_verified_archive"] is True, "materialization binding mismatch")
    require(set(mat["artifact_sha256s"]) == set(ROLES.values()), "materialization role set changed")
    require(all(mat["archive_members"][f] == f"posebusters_benchmark_set/{cid}/{cid}_{f}"
                for f in ROLES.values()), "materialization member names changed")
    paths = {role: directory / "inputs" / cid / f"{cid}_{filename}" for role, filename in ROLES.items()}
    for role, path in paths.items():
        require(path.is_file() and not path.is_symlink()
                and digest_file(path) == mat["artifact_sha256s"][ROLES[role]], "materialized input changed")
    paths["directory"] = directory / "inputs" / cid
    return mat, paths


def cpu_environment():
    env = os.environ.copy()
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
        env[key] = "1"
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1")
    return env


def _materialize_worker(request, m, r, journal, destination):
    cid, index = request["case_id"], request["global_index"]
    inputs = Path(request["input_root"])
    with journal.stage("public_input_identity"):
        for key in ("archive", "source_identifiers"):
            verify_input(inputs / m["inputs"][key]["filename"], m["inputs"][key])
        r.verify_public_redocking_source_identifiers((inputs / m["inputs"]["source_identifiers"]["filename"]).read_bytes())
        require(m["case_ids"] == list(r.FROZEN_PUBLIC_REDOCKING_CASE_IDS[:34]), "frozen case order changed")
    with journal.stage("materialization"):
        with r.VerifiedPublicRedockingArchive.open(inputs / m["inputs"]["archive"]["filename"]) as archive:
            paths, receipt = r._materialize_case_inputs(archive, cid, destination / "inputs")
        atomic_json(destination / "materialization.json", receipt.to_dict(), replace=False)
        common_inputs(destination, cid, index, m)
    return {"status": "completed", "materialization_receipt_sha256": receipt.receipt_sha256,
            "profile_validation": "deferred_to_independent_engine_worker",
            "input_sha256s": receipt.input_artifact_sha256s_by_role}


def _engine_worker(request, m, r, journal, destination):
    cid, index, engine = request["case_id"], request["global_index"], request["task"]
    with journal.stage("input_identity"):
        mat, paths = common_inputs(Path(request["materialization_root"]), cid, index, m)
        inputs = {role: mat["artifact_sha256s"][filename] for role, filename in ROLES.items()}
    with journal.stage("evaluator_initialization"):
        r._configure_engine_v2_cpu()
        r._load_rdkit_modules()
        r._load_posebusters()
        versions = r._evaluator_environment_versions()
        preflight = {"status": "ready", "source": request["source"], "profile": request["profile"],
            "case_id": cid, "engine_id": engine, "seed": m["seed_base"] + index,
            "input_sha256s": inputs, "materialization_receipt_sha256": mat["receipt_sha256"],
            "evaluator_versions": versions,
            "evaluator_payload_sha256s": r._evaluator_distribution_payload_sha256s(),
            "evaluation_pipeline_sha256": r._evaluation_pipeline_sha256(ROOT, evaluator_versions=versions),
            "engine_source_sha256": r._engine_source_sha256(ROOT),
            "execution_environment_sha256": r._execution_environment_identity().sha256}
        try:
            preflight["job_preflight_binding"] = validate_job_preflight(request, preflight)
        except Exception as exc:
            preflight.update(status="failed", job_preflight_error=type(exc).__name__ + ": " + str(exc))
            raise
        finally:
            atomic_json(destination / "preflight.json", preflight, replace=False)
    observer = None
    if request["profile"] == "development_observation_v1":
        from tools.redocking_development_p1 import DevelopmentObservation
        observer = DevelopmentObservation(cid, event_sink=journal.emit,
                    evaluator_identity=preflight["evaluation_pipeline_sha256"], reuse_evaluations=True)
    observation = {"development_observation": observer} if observer is not None else {}
    profiles = {p.case_id: p for p in r.frozen_public_redocking_profiles()}
    output = destination / "poses" / engine / (cid + ".sdf")
    seed, scorer = m["seed_base"] + index, r.ScorerBackend.PYTHON_REFERENCE
    with r.PinnedCaseInputs(paths, inputs) as pinned:
        with journal.stage("profile_validation"), pinned.verified_window():
            profile = r._profile(cid, pinned.execution_paths, profiles[cid], **observation)
            atomic_json(destination / "profile-observation.json", {
                "case_id": profile.case_id, "heavy_atom_count": profile.heavy_atom_count,
                "rotor_count": profile.rotor_count, "ring_count": profile.ring_count,
                "ligand_artifact_sha256": profile.ligand_artifact_sha256}, replace=False)
        if engine == "engine_v2":
            with journal.stage("engine_v2_result"), pinned.verified_window():
                row = r._engine_v2_result(cid, pinned.execution_paths, logical_paths=paths,
                    input_sha256s=inputs, output=output, seed=seed, scorer_backend=scorer, **observation)
            command = r._engine_v2_command(cid, paths, output=output, seed=seed, scorer_backend=scorer)
            policy, implementation = r._engine_v2_execution_policy(scorer), preflight["engine_source_sha256"]
        else:
            binary_path = Path(request["input_root"]) / m["inputs"]["gnina"]["filename"]
            with journal.stage("external_binary_stage"):
                verify_input(binary_path, m["inputs"]["gnina"])
                binary = r._stage_external_binary(binary_path, output_root=destination)
            with binary:
                with journal.stage("external_result", engine=engine), pinned.verified_window():
                    row, command = r._external_result(cid, engine, pinned.execution_paths, binary=binary,
                        input_descriptors=pinned.descriptors, input_sha256s=inputs,
                        external_paths=pinned.external_execution_paths, logical_paths=paths,
                        output=output, seed=seed, timeout_seconds=m["external_timeout_seconds"],
                        development_stdio=(sys.stdout.fileno(), sys.stderr.fileno()))
                implementation = binary.sha256
            policy = r._external_execution_policy(m["external_timeout_seconds"], "")
        pinned.verify()
    if observer is not None:
        observer.assert_healthy()
        atomic_json(destination / "observation-summary.json", observer.summary(), replace=False)
    with journal.stage("scientific_receipt_commit"):
        payload = r._row_payload(row, command=command, execution_policy=policy, input_sha256s=inputs,
            materialization_receipt_sha256=mat["receipt_sha256"], implementation_sha256=implementation,
            evaluation_pipeline_sha256=preflight["evaluation_pipeline_sha256"],
            execution_environment_sha256=preflight["execution_environment_sha256"])
        atomic_json(destination / "receipt.json", payload, replace=False)
    return {"status": "completed", "scientific_status": payload["result"]["status"],
            "receipt_sha256": payload["receipt_sha256"]}


def worker(request_path, expected_sha):
    require(not request_path.is_symlink() and digest_file(request_path) == expected_sha, "request bytes changed")
    request = read_json(request_path)
    destination = Path(request["task_root"])
    require(destination == request_path.parent and destination.is_absolute(), "request/task directory mismatch")
    manifest = Path(request["manifest_path"])
    m = load_manifest(manifest)
    require(request["profile"] in PROFILES and request["task"] in ("materialize", *ENGINES), "unknown worker profile/task")
    require(type(request["global_index"]) is int and 0 <= request["global_index"] < 34
            and request["case_id"] == m["case_ids"][request["global_index"]], "request case/index mismatch")
    require(source_identity(manifest) == request["source"], "worker source differs from controller")
    validate_job_preflight(request)
    journal = AtomicJournal(destination / "journal", {"request_sha256": expected_sha,
        "source": request["source"], "profile": request["profile"], "case_id": request["case_id"],
        "seed": m["seed_base"] + request["global_index"], "task": request["task"]},
        max_bytes=m["isolation"]["journal_bytes"], max_events=m["isolation"]["journal_events"])
    status = {"schema_id": "betelgeuze.redocking_isolated_worker/1.0.0", "started_at": now(),
              "request_sha256": expected_sha, "source": request["source"], "status": "running"}
    atomic_json(destination / "worker-status.json", status)
    try:
        with journal.stage("runner_import"):
            from tools import run_engine_v2_public_redocking_300 as r
        require(m["case_ids"] == list(r.FROZEN_PUBLIC_REDOCKING_CASE_IDS[:34]), "case selection is not historical prefix")
        result = (_materialize_worker if request["task"] == "materialize" else _engine_worker)(
                  request, m, r, journal, destination)
        require(source_identity(manifest) == request["source"], "source changed during worker execution")
        status.update(result)
        journal.emit({"stage": "worker", "phase": "complete", "details": result})
        returncode = 0
    except Exception as exc:
        status.update(status="failed", error={"exception_type": type(exc).__name__, "message": str(exc)[:4096]})
        traceback.print_exc()
        returncode = 1
    finally:
        status["finished_at"] = now()
        atomic_json(destination / "worker-status.json", status)
    return returncode


def observe_science(destination, common, cid, index, engine, m, source, *, profile,
                    recorded_task_root=None):
    """Verify retained bytes, preserving the original execution path binding.

    The controller validates against its actual task directory. Offline analysis
    may supply the task root from the separately hash-verified worker request;
    moving an evidence archive must not rewrite the scientific command receipt.
    """
    destination, common = destination.resolve(), common.resolve()
    execution_root = destination if recorded_task_root is None else Path(recorded_task_root)
    require(execution_root.is_absolute() and ".." not in execution_root.parts,
            "recorded task root is not a canonical absolute path")
    receipt_path = destination / "receipt.json"
    if not receipt_path.exists():
        return {"observation_status": "unobserved", "row": None, "receipt_sha256": None,
                "observation_reason": "missing_engine_receipt"}
    payload, pf = read_json(receipt_path), read_json(destination / "preflight.json")
    verify_self_hash(payload)
    require(payload["schema_id"] == "betelgeuze.engine_v2_public_redocking_case_execution/1.1.0"
        and payload["runner_id"] == "betelgeuze.engine_v2_public_redocking_300_runner/2.13.0",
        "scientific receipt schema/runner changed")
    mat, _ = common_inputs(common, cid, index, m)
    row = payload["result"]
    require(pf["status"] == "ready" and pf["source"] == source and pf["case_id"] == cid and pf["engine_id"] == engine
        and pf["profile"] == profile and pf["seed"] == m["seed_base"] + index
        and pf["materialization_receipt_sha256"] == mat["receipt_sha256"], "worker preflight mismatch")
    require(payload["materialization_receipt_sha256"] == mat["receipt_sha256"]
        and payload["archive_sha256"] == m["inputs"]["archive"]["sha256"]
        and payload["source_ids_sha256"] == m["inputs"]["source_identifiers"]["sha256"], "receipt source/input mismatch")
    inputs = {role: mat["artifact_sha256s"][filename] for role, filename in ROLES.items()}
    require(payload["input_sha256s"] == pf["input_sha256s"] == inputs
        and all(row[role + "_artifact_sha256"] == value for role, value in inputs.items()), "receipt input roles mismatch")
    require(payload["evaluation_pipeline_sha256"] == pf["evaluation_pipeline_sha256"]
        and payload["execution_environment_sha256"] == pf["execution_environment_sha256"], "worker evaluator/environment mismatch")
    implementation = pf["engine_source_sha256"] if engine == "engine_v2" else m["inputs"]["gnina"]["sha256"]
    require(payload["implementation_sha256"] == implementation and payload["fresh_execution"] is True
            and payload["cache_read_allowed"] is False, "receipt implementation/freshness mismatch")
    require(row["case_id"] == cid and row["engine_id"] == engine, "receipt row identity mismatch")
    command = payload["command"]
    require(command == row["execution_command"] and command.count("--seed") == 1
        and int(command[command.index("--seed") + 1]) == m["seed_base"] + index, "receipt seed/command mismatch")
    require(command.count("--cpu") == 1 and command[command.index("--cpu") + 1] == "1", "CPU policy changed")
    require(command.count("--out") == 1 and command[command.index("--out") + 1] ==
            str(execution_root / "poses" / engine / (cid + ".sdf")), "receipt output path changed")
    if engine == "engine_v2":
        require(command.count("--candidate-count") == 1 and command[command.index("--candidate-count") + 1] == "64"
            and command.count("--scorer-backend") == 1 and command[command.index("--scorer-backend") + 1] == "python_reference",
            "Engine V2 numerical policy changed")
    else:
        require(command.count("--num_modes") == 1 and command[command.index("--num_modes") + 1] == "5"
            and command.count("--cnn_scoring") == 1 and command[command.index("--cnn_scoring") + 1] ==
            ("none" if engine == "vina" else "rescore") and "--no_gpu" in command, "external numerical policy changed")
    require(type(row["runtime_seconds"]) in (int, float) and math.isfinite(row["runtime_seconds"])
            and row["runtime_seconds"] >= 0, "invalid runtime")
    keys = ("rmsd_angstroms", "geometric_valid", "chemical_valid", "pose_artifact_sha256s")
    if row["status"] == "success":
        require(not row["failure_code"] and all(len(row[k]) == 5 for k in keys), "successful result lacks five poses")
        records, current = [], bytearray()
        data = (destination / "poses" / engine / (cid + ".sdf")).read_bytes()
        for line in data.splitlines(keepends=True):
            current.extend(line)
            if line == b"$$$$\n":
                records.append(bytes(current))
                current.clear()
        require(not current and b"\r" not in data and b"".join(records) == data and
            [hashlib.sha256(b).hexdigest() for b in records] == row["pose_artifact_sha256s"], "pose bytes differ from receipt")
        require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in row["rmsd_angstroms"])
            and all(type(v) is bool for v in row["geometric_valid"] + row["chemical_valid"]), "invalid outcomes")
    else:
        require(row["status"] == "failure" and bool(row["failure_code"]) and all(row[k] == [] for k in keys), "untyped failure")
    if engine == "engine_v2":
        d = row["engine_v2_diagnostics"]
        require(d["candidate_budget"] == 64, "candidate budget changed")
        if d["preparation_status"] == "success":
            candidates = d["candidates"]
            require(len(candidates) == 64 and {x["proposal_index"] for x in candidates} == set(range(64)), "candidate slots missing")
            ranked = sorted((x for x in candidates if x["status"] == "success"), key=lambda x: (x["score"], x["proposal_index"]))
            require(d["candidate_success_count"] == len(ranked) and d["candidate_failure_count"] == 64 - len(ranked), "candidate counts differ")
            if row["status"] == "success":
                require(len(ranked) >= 5 and all(ranked[i][ck] == row[rk][i]
                    for i in range(5) for ck, rk in (("rmsd_angstrom", "rmsd_angstroms"),
                        ("geometric_valid", "geometric_valid"), ("chemical_valid", "chemical_valid"),
                        ("pose_artifact_sha256", "pose_artifact_sha256s"))), "ranked Top5 binding differs")
        else:
            require(d["preparation_status"] == "failure" and bool(d["preparation_failure_code"])
                    and not d["candidates"], "invalid preparation failure")
    return {"observation_status": "observed", "row": row, "receipt_sha256": payload["receipt_sha256"],
            "evaluation_pipeline_sha256": pf["evaluation_pipeline_sha256"],
            "execution_environment_sha256": pf["execution_environment_sha256"], "observation_reason": None}


def _prune_private_binary(destination, expected_sha):
    """Only disposable GNINA copies in this fresh task directory are removed."""
    directory = destination / "private-external-binary"
    if not directory.exists():
        return
    require(not directory.is_symlink() and directory.is_dir(), "invalid private binary directory")
    for p in directory.iterdir():
        require(not p.is_symlink() and p.is_file() and (p.name == expected_sha or
            re.fullmatch(r"\." + re.escape(expected_sha) + r"\.[0-9a-f]{32}\.tmp", p.name)),
            "unexpected file in private binary stage")
    for p in directory.iterdir():
        p.unlink()
    directory.rmdir()


def run_task(request, m):
    destination = Path(request["task_root"])
    destination.mkdir(parents=True, exist_ok=False)
    request_path = destination / "request.json"
    atomic_json(request_path, request, replace=False)
    request_path.chmod(0o400)
    request_sha = digest_file(request_path)
    command = [sys.executable, "-m", "tools.run_redocking_isolated_development", "worker",
               "--request", str(request_path), "--expected-request-sha256", request_sha]
    errors, fatal = [], False
    try:
        execution = supervise(command, destination, task_limits(m, request["task"]), cwd=ROOT, env=cpu_environment())
    except CleanupError as exc:
        execution, fatal = exc.record, True
    checkpoint = None
    try:
        checkpoint = read_checkpoint(destination / "journal")
    except Exception as exc:
        errors.append("phase_checkpoint_invalid: " + str(exc))
    status_path = destination / "worker-status.json"
    status = read_json(status_path) if status_path.is_file() else None
    if status is not None:
        require(status["request_sha256"] == request_sha and status["source"] == request["source"], "worker status binding mismatch")
    termination = execution["termination"]
    operation = ("timeout" if termination == "wall_timeout" else
                 "resource_limit" if termination == "sampled_rss_limit" else
                 "cleanup_failed" if not execution["cleanup_complete"] else
                 "completed" if termination == "exited" and execution["returncode"] == 0
                    and status is not None and status["status"] == "completed" else "worker_failed")
    if execution["cleanup_complete"]:
        _prune_private_binary(destination, m["inputs"]["gnina"]["sha256"])
    return {"operation_status": operation, "execution": execution, "worker_status": status,
            "last_checkpoint": checkpoint, "request_sha256": request_sha,
            "task_root": str(destination), "errors": errors, "fatal_cleanup_failure": fatal}


def unobserved(reason="not_started"):
    return {"operation_status": "not_started", "observation_status": "unobserved", "row": None,
            "receipt_sha256": None, "observation_reason": reason, "execution": None,
            "last_checkpoint": None, "errors": []}


def publish_summary(output, m, source, profile, stage, indices, cases, fatal=None):
    metrics = {}
    for engine in ENGINES:
        observations = [c["engines"][engine] for c in cases]
        rows = [x["row"] for x in observations if x["observation_status"] == "observed"]
        metric = {"case_count": len(indices), "observed_rows": len(rows),
                  "success_rows": sum(r["status"] == "success" for r in rows),
                  "failure_rows": sum(r["status"] == "failure" for r in rows),
                  "unobserved_rows": len(indices) - len(rows)}
        for k in (1, 3, 5):
            metric[f"top{k}"] = sum(any(v <= 2 for v in r["rmsd_angstroms"][:k]) for r in rows) / len(indices)
            metric[f"valid_top{k}"] = sum(any(v <= 2 and g and ch for v, g, ch in zip(
                r["rmsd_angstroms"][:k], r["geometric_valid"][:k], r["chemical_valid"][:k])) for r in rows) / len(indices)
        metrics[engine] = metric
    science = not fatal and all(v["unobserved_rows"] == 0 for v in metrics.values())
    complete = not fatal and len(cases) == len(indices) and all(c["materialization"]["operation_status"] == "completed"
        and not c["materialization"].get("errors") and all(x["operation_status"] == "completed"
        and not x.get("errors") for x in c["engines"].values()) for c in cases)
    prepared = any(((c["engines"]["engine_v2"].get("row") or {}).get("engine_v2_diagnostics") or {}).get(
        "preparation_status") == "success" for c in cases)
    summary = {"schema_id": "betelgeuze.redocking_isolated_development_summary/1.0.0",
        "analysis_scope": "contaminated_development", "claim_safe": False, "primary_claim_eligible": False,
        "source": source, "profile": profile, "stage": stage, "expected_indices": indices,
        "attempted_cases": len(cases), "scientific_accuracy_complete": bool(science),
        "execution_complete": bool(complete), "metrics": metrics, "cases": cases, "fatal_error": fatal,
        "physical_energy_force_calls": None}
    atomic_json(output / "summary.json", summary)
    atomic_json(output / "stage-status.json", {"stage": stage, "profile": profile,
        "complete": bool(complete and science), "prepared_case_observed": prepared,
        "next_stage_ready": bool(complete and science and prepared), "accuracy_threshold_used_for_admission": False})
    return summary


def run(arguments):
    manifest, inputs, output = arguments.manifest.resolve(), arguments.input_root.resolve(), arguments.output_root.resolve()
    m = load_manifest(manifest)
    require(arguments.profile in PROFILES, "explicit development profile required")
    require(type(arguments.count) is int and 1 <= arguments.count <= 8, "one to eight cases per invocation")
    indices = list(range(arguments.start, arguments.start + arguments.count))
    require(set(indices) <= set(m[arguments.stage + "_indices"]), "indices are outside selected development stage")
    require(output != inputs and not output.is_relative_to(inputs), "output must not overlap public input directory")
    output.mkdir(parents=True, exist_ok=True)
    require(not (output / "cases").exists() and not (output / "run-manifest.json").exists(), "run output is not fresh")
    source = source_identity(manifest)
    preflight = None
    if arguments.preflight is not None:
        path = arguments.preflight.resolve()
        require(path.is_file() and not path.is_symlink(), "job preflight missing")
        preflight = {"path": str(path), "sha256": digest_file(path)}
    atomic_json(output / "run-manifest.json", {**m, "source": source, "profile": arguments.profile,
        "stage": arguments.stage, "active_indices": indices, "started_at": now(), "job_preflight": preflight}, replace=False)
    cases, fatal = [], None
    summary = publish_summary(output, m, source, arguments.profile, arguments.stage, indices, cases)
    for index in indices:
        cid = m["case_ids"][index]
        case_root = output / "cases" / cid
        case_root.mkdir(parents=True, exist_ok=False)
        common = case_root / "materialization"
        record = {"global_index": index, "case_id": cid, "seed": m["seed_base"] + index,
                  "profile": arguments.profile, "stage": arguments.stage, "started_at": now(),
                  "materialization": {"operation_status": "not_started", "errors": []},
                  "engines": {e: unobserved() for e in ENGINES}}
        cases.append(record)
        case_file = output / f"case-{index:02d}.json"
        atomic_json(case_file, record)
        journal = AtomicJournal(case_root / "controller-journal", {"source": source,
            "profile": arguments.profile, "case_id": cid, "seed": record["seed"]},
            max_bytes=m["isolation"]["journal_bytes"], max_events=m["isolation"]["journal_events"])
        request = {"schema_id": "betelgeuze.redocking_isolated_request/1.0.0",
            "source": source, "manifest_path": str(manifest), "profile": arguments.profile,
            "global_index": index, "case_id": cid, "input_root": str(inputs),
            "materialization_root": str(common), "job_preflight": preflight}
        try:
            journal.emit({"stage": "materialization", "phase": "start"})
            record["materialization"] = run_task({**request, "task": "materialize", "task_root": str(common)}, m)
            prepared = record["materialization"]
            if prepared["fatal_cleanup_failure"]:
                raise IsolationError("materialization cleanup failed; sequence stopped")
            if prepared["operation_status"] == "completed" and not prepared["errors"]:
                mat, _ = common_inputs(common, cid, index, m)
                require(prepared["worker_status"]["materialization_receipt_sha256"] == mat["receipt_sha256"],
                        "materialization completion binding mismatch")
                prepared["verified_input_receipt_sha256"] = mat["receipt_sha256"]
                journal.emit({"stage": "materialization", "phase": "complete", "receipt_sha256": mat["receipt_sha256"]})
                atomic_json(case_file, record)
                for engine in ENGINES:
                    destination = case_root / "engines" / engine
                    record["engines"][engine]["operation_status"] = "running"
                    atomic_json(case_file, record)
                    journal.emit({"stage": engine, "phase": "start"})
                    result = run_task({**request, "task": engine, "task_root": str(destination)}, m)
                    record["engines"][engine] = {**unobserved(), **result}
                    if result["fatal_cleanup_failure"]:
                        raise IsolationError("engine cleanup failed; next engine not started")
                    try:
                        observation = observe_science(destination, common, cid, index, engine, m, source,
                                                      profile=arguments.profile)
                    except Exception as exc:
                        observation = {**unobserved("invalid_engine_receipt"), "observation_status": "invalid"}
                        # Preserve process status; an invalid receipt is not a new process outcome.
                        observation.pop("operation_status")
                        observation.pop("execution")
                        observation.pop("last_checkpoint")
                        observation["errors"] = result["errors"] + [type(exc).__name__ + ": " + str(exc)]
                    record["engines"][engine].update(observation)
                    journal.emit({"stage": engine, "phase": "complete", "operation_status": result["operation_status"],
                                  "observation_status": observation["observation_status"]})
                    require(source_identity(manifest) == source, "controller source changed")
                    atomic_json(case_file, record)
                    publish_summary(output, m, source, arguments.profile, arguments.stage, indices, cases)
            else:
                for engine in ENGINES:
                    record["engines"][engine] = unobserved("materialization_not_verified")
                journal.emit({"stage": "materialization", "phase": "failed", "details": prepared["operation_status"]})
        except Exception as exc:
            fatal = {"exception_type": type(exc).__name__, "message": str(exc)}
            record["fatal_error"] = fatal
        finally:
            record["finished_at"] = now()
            atomic_json(case_file, record)
            summary = publish_summary(output, m, source, arguments.profile, arguments.stage, indices, cases, fatal)
        if fatal:
            break
    print(json.dumps({"profile": arguments.profile, "stage": arguments.stage,
        "expected_cases": len(indices), "attempted_cases": len(cases),
        "execution_complete": summary["execution_complete"],
        "scientific_accuracy_complete": summary["scientific_accuracy_complete"]}), flush=True)
    return 1 if fatal else 0 if summary["execution_complete"] and summary["scientific_accuracy_complete"] else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("run")
    for name in ("manifest", "input-root", "output-root"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--profile", choices=PROFILES, required=True)
    p.add_argument("--stage", choices=("smoke", "development"), required=True)
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--count", type=int, required=True)
    p.add_argument("--preflight", type=Path)
    p = sub.add_parser("worker")
    p.add_argument("--request", type=Path, required=True)
    p.add_argument("--expected-request-sha256", required=True)
    args = parser.parse_args(argv)
    return run(args) if args.action == "run" else worker(args.request, args.expected_request_sha256)


if __name__ == "__main__":
    raise SystemExit(main())
