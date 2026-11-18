#!/usr/bin/env python3
"""Read-only, standard-library audit of saved redocking stage artifacts.

The only write is --output. No engine imports, network requests, or molecular
calculations occur. Missing observations and corrupted evidence are distinct.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import re
import statistics
import sys
import tempfile

SCHEMA = "betelgeuze.redocking_development_evidence_analysis/1.0.0"
ENGINES = ("engine_v2", "vina", "gnina")
KS = (1, 3, 5)
ARTIFACTS = {"smoke": tuple(range(2)), **{
    f"development-{start}": tuple(range(start, start + 8)) for start in (2, 10, 18, 26)}}
ROLES = dict(zip(("receptor", "reference", "native", "seed"),
                 ("protein.pdb", "ligands.sdf", "ligand.sdf", "ligand_start_conf.sdf")))
SOURCE_KEYS = ("commit", "tree", "baseline_commit", "baseline_tree", "wrapper_sha256",
               "manifest_sha256", "runner_sha256", "workflow_run_id", "workflow_run_attempt")
RECOVERIES = tuple(f"{prefix}{k}" for prefix in ("top", "valid_top") for k in KS)


class IntegrityError(ValueError):
    """Present evidence is inconsistent, rather than merely unobserved."""


def require(condition, message):
    if not condition:
        raise IntegrityError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse_json(data, label):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"{label}: duplicate JSON key {key}")
            result[key] = value
        return result
    def invalid(value):
        raise IntegrityError(f"{label}: nonfinite JSON {value}")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def number(value, label, nonnegative=True):
    require(type(value) in (int, float) and math.isfinite(value), f"{label}: not finite")
    require(not nonnegative or value >= 0, f"{label}: negative")
    return value


def digest(value, label):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), f"{label}: invalid SHA256")
    return value


def receipt_digest(payload, label):
    recorded = digest(payload.get("receipt_sha256"), label)
    require(sha(canonical({k: v for k, v in payload.items() if k != "receipt_sha256"})) == recorded,
            f"{label}: canonical receipt digest mismatch")
    return recorded


def option(command, name):
    require(isinstance(command, list) and all(isinstance(x, str) for x in command)
            and command.count(name) == 1, f"command requires exactly one {name}")
    index = command.index(name)
    require(index + 1 < len(command), f"command lacks {name} value")
    return command[index + 1]


def percentile(values, probability):
    values = sorted(values)
    position = probability * (len(values) - 1)
    lo, hi = math.floor(position), math.ceil(position)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def stats(values):
    values = list(values)
    return {"count": len(values), "sum": math.fsum(values) if values else None,
            "median": statistics.median(values) if values else None,
            "p90": percentile(values, .9) if values else None,
            "max": max(values) if values else None, "min": min(values) if values else None}


def load_manifest(path):
    require(path.is_file() and not path.is_symlink(), "manifest must be a regular file")
    body = path.read_bytes()
    m = parse_json(body, str(path))
    require(m.get("schema_id") == "betelgeuze.redocking_development_stages/1.0.0", "unsupported manifest")
    ids = m.get("case_ids", [])
    require(len(ids) == len(set(ids)) == 34 and all(isinstance(x, str) and
            re.fullmatch(r"[0-9][A-Z0-9]{3}_[A-Z0-9]{3}", x) for x in ids), "invalid 34-case manifest")
    require(m.get("smoke_indices") == [0, 1] and m.get("development_indices") == list(range(2, 34)),
            "stage indices changed")
    require(m.get("analysis_scope") == "contaminated_development" and m.get("claim_safe") is False
            and m.get("primary_claim_eligible") is False, "manifest claim boundary changed")
    for key, expected in (("seed_base", 2026072700), ("repetitions", 1), ("candidate_count", 64),
                          ("output_pose_count", 5), ("rmsd_threshold_angstrom", 2),
                          ("external_timeout_seconds", 300)):
        require(type(m.get(key)) in (int, float) and m[key] == expected, f"manifest {key} changed")
    require(m.get("scorer_backend") == "python_reference", "scorer backend changed")
    require(set(m["inputs"]) == {"archive", "source_identifiers", "gnina"}, "input set changed")
    for key, spec in m["inputs"].items():
        digest(spec["sha256"], key)
    return m, sha(body)


class Bundle:
    """Verified byte snapshot. Missing pinned duplicates remain explicitly missing."""

    def __init__(self, path):
        self.path, self.files = path, {}
        require(path.is_dir() and not path.is_symlink(), f"{path}: invalid artifact directory")
        inv_path = path / "artifact-inventory.json"
        require(inv_path.is_file() and not inv_path.is_symlink(), f"{path}: no sealed inventory")
        inv_bytes = inv_path.read_bytes()
        inventory = parse_json(inv_bytes, str(inv_path))
        missing, declared = [], {}
        for item in inventory["files"]:
            name = item["path"]
            require(isinstance(name, str), "inventory path is not a string")
            rel = PurePosixPath(name)
            require(not rel.is_absolute() and rel.as_posix() == name and ".." not in rel.parts
                    and "\\" not in name and name != "artifact-inventory.json", f"unsafe path {name}")
            require(name not in declared, f"duplicate inventory path {name}")
            require(type(item["size"]) is int and item["size"] >= 0, f"invalid size {name}")
            digest(item["sha256"], name)
            declared[name] = item
            q = path.joinpath(*rel.parts)
            require(not q.is_symlink(), f"symlink {q}")
            if not q.exists():
                missing.append(item)
                continue
            require(q.is_file(), f"not a regular file {q}")
            body = q.read_bytes()
            require(len(body) == item["size"] and sha(body) == item["sha256"], f"inventory hash/size mismatch {q}")
            self.files[name] = body
        actual = set()
        for q in path.rglob("*"):
            require(not q.is_symlink(), f"symlink in artifact {q}")
            if q.is_file() and q != inv_path:
                actual.add(q.relative_to(path).as_posix())
        require(actual == set(self.files), f"{path}: unlisted files")
        require(sum(x["size"] for x in declared.values()) == inventory["bytes"], "inventory byte total mismatch")
        missing_audit = []
        role_files = {"native.sdf": "ligand.sdf", "reference.sdf": "ligands.sdf",
                      "receptor.pdb": "protein.pdb", "seed.sdf": "ligand_start_conf.sdf"}
        for item in missing:
            match = re.fullmatch(r"raw/([^/]+)/inputs/\.([^/]+)\.pinned-[0-9a-f]{32}/([^/]+)", item["path"])
            require(match is not None and match[1] == match[2] and match[3] in role_files,
                    f"unexplained inventoried file missing: {item['path']}")
            case_id, role_file = match[1], role_files[match[3]]
            preserved = f"raw/{case_id}/inputs/{case_id}/{case_id}_{role_file}"
            require(preserved in self.files and len(self.files[preserved]) == item["size"]
                    and sha(self.files[preserved]) == item["sha256"],
                    f"missing pinned input has no verified identical preserved copy: {item['path']}")
            missing_audit.append({**item, "case_id": case_id, "materialization_role_file": role_file,
                "classification": "missing_duplicate_materialized_input", "preserved_path": preserved,
                "preserved_size_and_sha256_match": True})
        self.audit = {"artifact": path.name, "inventory_sha256": sha(inv_bytes),
            "inventoried_files": len(declared), "inventoried_bytes": inventory["bytes"],
            "verified_present_files": len(self.files), "verified_present_bytes": sum(map(len, self.files.values())),
            "full_inventory_pass": not missing, "inventory_missing_paths": missing_audit,
            "missing_bytes": sum(x["size"] for x in missing),
            "summary_sha256": sha(self.files["summary.json"]) if "summary.json" in self.files else None,
            "canonical_execution_receipts": 0, "canonical_materializations": 0}

    def json(self, name, required=True):
        if name not in self.files:
            require(not required, f"{self.path.name}: missing {name}")
            return None
        return parse_json(self.files[name], f"{self.path.name}/{name}")


def verify_materialization(bundle, name, case_id, index, m):
    record = bundle.json(name)
    receipt_digest(record, name)
    require(record["case_id"] == case_id and record["frozen_case_seed"] == m["seed_base"] + index,
            f"{name}: case/seed mismatch")
    require(record["source_archive_sha256"] == m["inputs"]["archive"]["sha256"]
            and record["hash_verified_archive"] is True, f"{name}: archive mismatch")
    require(set(record["artifact_sha256s"]) == set(ROLES.values()), f"{name}: role set mismatch")
    for filename, value in record["artifact_sha256s"].items():
        digest(value, name)
        require(record["archive_members"][filename] == f"posebusters_benchmark_set/{case_id}/{case_id}_{filename}",
                f"{name}: member mismatch")
    bundle.audit["canonical_materializations"] += 1
    return record


def candidate_analysis(row):
    d = row.get("engine_v2_diagnostics")
    require(isinstance(d, dict) and d["candidate_budget"] == 64, "missing/invalid V2 diagnostics")
    require(d["preparation_status"] in ("success", "failure"), "invalid preparation status")
    candidates = d["candidates"]
    if d["preparation_status"] == "success":
        require(len(candidates) == 64 and all(type(x["proposal_index"]) is int for x in candidates)
                and {x["proposal_index"] for x in candidates} == set(range(64)), "candidate slots changed")
    else:
        require(not candidates and bool(d["preparation_failure_code"]), "invalid preparation failure")
    good, checks, failed = [], Counter(), Counter()
    penalties = Counter({k: 0 for k in ("paired", "decreased", "unchanged", "increased", "unavailable",
                                       "decreased_but_joint_invalid", "decreased_but_not_close")})
    for c in candidates:
        require(c["status"] in ("success", "failure"), "invalid candidate status")
        if c["status"] == "success":
            number(c["score"], "candidate score", False)
            number(c["rmsd_angstrom"], "candidate RMSD")
            require(type(c["geometric_valid"]) is bool and type(c["chemical_valid"]) is bool,
                    "candidate validity is not Boolean")
            digest(c["pose_artifact_sha256"], "candidate pose")
            require(isinstance(c["posebusters_failed_check_ids"], list)
                    and all(isinstance(x, str) for x in c["posebusters_failed_check_ids"]), "invalid PB check list")
            checks.update(c["posebusters_failed_check_ids"])
            good.append(c)
        else:
            require(bool(c["error_code"]), "candidate failure has no reason")
            failed[c["error_code"]] += 1
        initial, final = c.get("refinement_initial_penalty_binary64_hex"), c.get("refinement_final_penalty_binary64_hex")
        if not initial or not final:
            penalties["unavailable"] += 1
        else:
            require(isinstance(initial, str) and isinstance(final, str), "penalty is not binary64 hex")
            a, b = float.fromhex(initial), float.fromhex(final)
            number(a, "initial penalty", False)
            number(b, "final penalty", False)
            penalties["paired"] += 1
            penalties["decreased" if b < a else "increased" if b > a else "unchanged"] += 1
            if b < a and c["status"] == "success":
                penalties["decreased_but_joint_invalid"] += int(not (c["geometric_valid"] and c["chemical_valid"]))
                penalties["decreased_but_not_close"] += int(c["rmsd_angstrom"] > 2)
    require(d["candidate_success_count"] == len(good)
            and d["candidate_failure_count"] == len(candidates) - len(good), "candidate count mismatch")
    ranked = sorted(good, key=lambda x: (x["score"], x["proposal_index"]))
    if row["status"] == "success":
        require(len(ranked) >= 5, "successful row lacks five scored candidates")
        for i, c in enumerate(ranked[:5]):
            for ck, rk in (("rmsd_angstrom", "rmsd_angstroms"), ("geometric_valid", "geometric_valid"),
                           ("chemical_valid", "chemical_valid"), ("pose_artifact_sha256", "pose_artifact_sha256s")):
                require(c[ck] == row[rk][i], "score-ranked Top5 binding mismatch")
    valid = [c for c in good if c["geometric_valid"] and c["chemical_valid"]]
    close = [c for c in good if c["rmsd_angstrom"] <= 2]
    minimum = min((c["rmsd_angstrom"] for c in good), default=None)
    require(d["proposal_oracle_rmsd_angstrom"] == minimum, "recorded oracle RMSD mismatch")
    ranks = {c["proposal_index"]: i + 1 for i, c in enumerate(ranked)}
    def detail(c):
        if c is None:
            return None
        result = {key: c.get(key) for key in ("proposal_index", "proposal_mode", "score", "rmsd_angstrom",
            "geometric_valid", "chemical_valid", "selection_eligible", "posebusters_failed_check_ids",
            "score_term_binary64_hex", "refinement_initial_penalty_binary64_hex", "refinement_final_penalty_binary64_hex")}
        result["score_rank_1based"] = ranks[c["proposal_index"]]
        return result
    def best(rows):
        return min(rows, key=lambda c: (c["rmsd_angstrom"], c["proposal_index"])) if rows else None
    require(d["diagnostic_evaluation_excluded_from_runtime"] is True, "diagnostic time accounting changed")
    return {"preparation_status": d["preparation_status"], "preparation_failure_code": d["preparation_failure_code"],
        "candidate_budget": 64, "candidate_slots": len(candidates), "successful_candidate_count": len(good),
        "failed_candidate_count": len(candidates) - len(good),
        "chemical_valid_candidate_count": sum(c["chemical_valid"] for c in good),
        "geometric_valid_candidate_count": sum(c["geometric_valid"] for c in good),
        "joint_valid_candidate_count": len(valid), "close_candidate_count": len(close),
        "close_valid_candidate_count": sum(c["geometric_valid"] and c["chemical_valid"] for c in close),
        "oracle": int(bool(close)), "valid_oracle": int(any(c["geometric_valid"] and c["chemical_valid"] for c in close)),
        "minimum_rmsd_angstrom": minimum,
        "minimum_joint_valid_rmsd_angstrom": min((c["rmsd_angstrom"] for c in valid), default=None),
        "candidate_posebusters_failure_check_counts": dict(sorted(checks.items())),
        "candidate_failure_codes": dict(sorted(failed.items())), "refinement_penalty_counts": dict(penalties),
        "diagnostic_evaluation_seconds": number(d["diagnostic_evaluation_seconds"], "diagnostic time"),
        "score_top1_candidate": detail(ranked[0] if ranked else None), "rmsd_oracle_candidate": detail(best(good)),
        "best_joint_valid_candidate": detail(best(valid)),
        "close_candidates": [detail(c) for c in sorted(close, key=lambda c: c["proposal_index"])]}


def verify_execution(bundle, name, row, cid, index, engine, mat, m, preflight):
    r = bundle.json(name)
    receipt_digest(r, name)
    require(r["result"] == row and (row["case_id"], row["engine_id"]) == (cid, engine), "receipt/result mismatch")
    require(r["archive_sha256"] == m["inputs"]["archive"]["sha256"]
            and r["source_ids_sha256"] == m["inputs"]["source_identifiers"]["sha256"], "source archive mismatch")
    require(r["fresh_execution"] is True and r["cache_read_allowed"] is False, "cached receipt")
    require(r["materialization_receipt_sha256"] == mat["receipt_sha256"], "materialization binding mismatch")
    impl = preflight["engine_source_sha256"] if engine == "engine_v2" else m["inputs"]["gnina"]["sha256"]
    require(r["implementation_sha256"] == impl, "implementation identity mismatch")
    require(r["evaluation_pipeline_sha256"] == preflight["evaluation_pipeline_sha256"],
            "receipt does not match its own artifact evaluator")
    inputs = {role: mat["artifact_sha256s"][filename] for role, filename in ROLES.items()}
    require(r["input_sha256s"] == inputs and all(row[k + "_artifact_sha256"] == v for k, v in inputs.items()),
            "input artifact binding mismatch")
    require(r["command"] == row["execution_command"], "command binding mismatch")
    require(int(option(r["command"], "--seed")) == m["seed_base"] + index
            and option(r["command"], "--cpu") == "1", "case seed/CPU changed")
    if engine == "engine_v2":
        require(option(r["command"], "--candidate-count") == "64"
                and option(r["command"], "--scorer-backend") == "python_reference", "V2 profile changed")
    else:
        require(option(r["command"], "--num_modes") == "5" and "--no_gpu" in r["command"]
                and option(r["command"], "--cnn_scoring") == ("none" if engine == "vina" else "rescore"),
                "external mode changed")
        require(row.get("engine_v2_diagnostics") is None, "external row has V2 diagnostics")
    number(row["runtime_seconds"], "runtime")
    arrays = [row[key] for key in ("rmsd_angstroms", "geometric_valid", "chemical_valid", "pose_artifact_sha256s")]
    require(row["status"] in ("success", "failure"), "invalid row status")
    if row["status"] == "success":
        require(all(isinstance(x, list) and len(x) == 5 for x in arrays) and not row["failure_code"],
                "incomplete successful result")
        for x in arrays[0]:
            number(x, "RMSD")
        require(all(type(x) is bool for x in arrays[1] + arrays[2]), "validity is not Boolean")
        for x in arrays[3]:
            digest(x, "pose")
    else:
        require(all(x == [] for x in arrays) and bool(row["failure_code"]), "malformed failure row")
    bundle.audit["canonical_execution_receipts"] += 1
    return r


def result_metrics(row):
    result = {key: 0 for key in RECOVERIES}
    if row is None:
        return {**result, "status": "unobserved", "failure_code": None,
                "observation_reason": "missing_engine_receipt", "runtime_seconds": None,
                "diagnostic_evaluation_seconds": None}
    result.update(status=row["status"], failure_code=row["failure_code"], runtime_seconds=row["runtime_seconds"],
                  rmsd_angstroms=row["rmsd_angstroms"], geometric_valid=row["geometric_valid"], chemical_valid=row["chemical_valid"])
    for k in KS:
        rmsds = row["rmsd_angstroms"][:k]
        result[f"top{k}_minimum_rmsd_angstrom"] = min(rmsds) if rmsds else None
        result[f"top{k}"] = int(any(x <= 2 for x in rmsds))
        result[f"valid_top{k}"] = int(any(r <= 2 and g and c for r, g, c in zip(
            rmsds, row["geometric_valid"][:k], row["chemical_valid"][:k], strict=True)))
    if row["engine_id"] == "engine_v2":
        d = candidate_analysis(row)
        result["candidate_diagnostics"] = d
        result["diagnostic_evaluation_seconds"] = d["diagnostic_evaluation_seconds"]
        require(result["valid_top1"] <= result["valid_top3"] <= result["valid_top5"] <= d["valid_oracle"] <= d["oracle"],
                "ranking/oracle invariant violated")
        result["diagnostic_category"] = ("prep" if d["preparation_status"] == "failure" else
            "output" if row["status"] == "failure" else "no-close" if not d["oracle"] else
            "close-invalid" if not d["valid_oracle"] else "validoutsideTop5" if not result["valid_top5"] else
            "top5notTop1" if not result["valid_top1"] else "success")
    return result


def read_artifact(bundle, indices, m, manifest_hash, common, attempts):
    pf = bundle.json("preflight.json")
    source = pf["source"]
    identity = {k: source[k] for k in SOURCE_KEYS}
    require(source["manifest_sha256"] == manifest_hash and source["baseline_commit"] == m["baseline_commit"]
            and source["baseline_tree"] == m["baseline_tree"], "artifact baseline/manifest mismatch")
    if "source" not in common:
        common["source"] = identity
    require(common["source"] == identity, "artifacts mix sources/wrappers/workflow attempts")
    run = bundle.json("run-manifest.json", required=False)
    stage = "smoke" if indices == (0, 1) else "development"
    if run is not None:
        require(all(run.get(k) == v for k, v in m.items()) and run["source"] == source
                and run["active_indices"] == list(indices) and run["stage"] == stage, "run manifest mismatch")
    if pf["status"] == "ready":
        if "versions" not in common:
            common["versions"] = pf["evaluator_versions"]
            common["engine_source_sha256"] = pf["engine_source_sha256"]
        require(pf["evaluator_versions"] == common["versions"], "declared evaluator versions differ")
        require(pf["engine_source_sha256"] == common["engine_source_sha256"], "engine source hashes differ")
        frame = pf["rmsd_semantics_test"]
        require(abs(frame["rmsd"] - 3) < 1e-9 and frame["kabsch_rmsd"] < 1e-6, "RMSD frame check failed")
    bundle.audit.update(source=source, preflight_status=pf["status"],
        evaluator={k: pf.get(k) for k in ("evaluation_pipeline_sha256", "evaluator_versions",
            "evaluator_payload_sha256s", "engine_source_sha256", "torch_version", "python", "platform")},
        stage_status=bundle.json("stage-status.json", required=False), execution_environment_sha256s=[])
    consumed = set()
    materializations = {}
    for name in sorted(x for x in bundle.files if re.fullmatch(r"attempt-\d+\.json", x)):
        require(pf["status"] == "ready" and run is not None, "attempt without ready preflight/run manifest")
        a = bundle.json(name)
        index = a["global_index"]
        require(type(index) is int and index in indices and index not in attempts, "duplicate/wrong-shard attempt")
        cid = m["case_ids"][index]
        require(name == f"attempt-{index:02d}.json" and a["case_id"] == cid and a["stage"] == stage,
                "attempt identity mismatch")
        command = a["command"]
        require(option(command, "--start-index") == str(index) and option(command, "--limit") == "1"
                and option(command, "--case-subset") == "all" and option(command, "--seed") == str(m["seed_base"]),
                "attempt subset/global seed changed")
        require(set(a["rows"]) <= set(ENGINES) and isinstance(a["verification_errors"], list), "invalid attempt rows/errors")
        for key in ("wall_seconds", "child_cpu_seconds", "sampled_peak_process_tree_rss_bytes"):
            if key in a["execution"]:
                number(a["execution"][key], key)
        mat_name = f"raw/{cid}/receipts/materializations/{cid}.json"
        mat = verify_materialization(bundle, mat_name, cid, index, m) if mat_name in bundle.files else None
        if mat is not None:
            consumed.add(mat_name)
            materializations[cid] = mat
        metrics = {}
        for engine in ENGINES:
            row = a["rows"].get(engine)
            receipt_name = f"raw/{cid}/receipts/{engine}/{cid}.json"
            require((receipt_name in bundle.files) == (row is not None),
                    f"present receipt/result binding mismatch for {cid}/{engine}")
            if row is not None:
                require(mat is not None, "observed result has no materialization")
                receipt = verify_execution(bundle, receipt_name, row, cid, index, engine, mat, m, pf)
                consumed.add(receipt_name)
                env = digest(receipt["execution_environment_sha256"], "execution environment")
                if env not in bundle.audit["execution_environment_sha256s"]:
                    bundle.audit["execution_environment_sha256s"].append(env)
            metrics[engine] = result_metrics(row)
        attempts[index] = {"global_index": index, "case_id": cid, "seed": m["seed_base"] + index,
            "artifact": bundle.path.name, "attempted": True, "attempt_sha256": sha(bundle.files[name]),
            "execution": a["execution"], "verification_errors": a["verification_errors"],
            "started_at": a.get("started_at"), "finished_at": a.get("finished_at"), "engines": metrics}
    require({x for x in bundle.files if "/receipts/" in x and x.endswith(".json")} == consumed,
            f"{bundle.path.name}: unbound/orphan receipt")
    for missing in bundle.audit["inventory_missing_paths"]:
        cid = missing["case_id"]
        matches = [attempts[i] for i in indices if i in attempts and attempts[i]["case_id"] == cid]
        require(len(matches) == 1 and matches[0]["execution"]["termination"] == "wall_timeout"
                and all(r["status"] == "unobserved" for r in matches[0]["engines"].values()),
                "missing pinned duplicate is outside the observed timeout/no-receipt case")
        require(cid in materializations and materializations[cid]["artifact_sha256s"][missing["materialization_role_file"]]
                == missing["sha256"], "missing pinned duplicate does not match materialization")
        missing["materialization_receipt_sha256"] = materializations[cid]["receipt_sha256"]
    summary = bundle.json("summary.json", required=False)
    if summary is not None:
        require(summary["source"] == source and summary["expected_indices"] == list(indices)
                and summary["claim_safe"] is False and summary["primary_claim_eligible"] is False, "summary scope/source mismatch")
        seen = set()
        for row in summary["case_metrics"]:
            index, engine = row["global_index"], row["engine_id"]
            require(index in indices and engine in ENGINES and (index, engine) not in seen, "duplicate/unexpected summary row")
            seen.add((index, engine))
            actual = attempts[index]["engines"][engine] if index in attempts else result_metrics(None)
            require(row["case_id"] == m["case_ids"][index] and row["status"] == actual["status"]
                    and all(row[k] == actual[k] for k in RECOVERIES), "summary recovery differs from raw receipt")
            d = actual.get("candidate_diagnostics")
            if d is not None:
                for key in ("oracle", "valid_oracle", "candidate_slots", "successful_candidate_count",
                            "close_candidate_count", "joint_valid_candidate_count"):
                    if key in row:
                        require(row[key] == d[key], f"summary candidate count differs: {key}")
        require(seen == {(i, e) for i in indices for e in ENGINES}, "summary case denominator incomplete")


def missing_case(index, m):
    return {"global_index": index, "case_id": m["case_ids"][index], "seed": m["seed_base"] + index,
            "artifact": None, "attempted": False, "execution": {"termination": "not_executed"},
            "verification_errors": [], "engines": {e: result_metrics(None) for e in ENGINES}}


def scope_summary(indices, attempts, m):
    cases = [attempts.get(i, missing_case(i, m)) for i in indices]
    n = len(cases)
    engines, diagnostics, close = {}, [], []
    checks, penalties, counts, categories = Counter(), Counter(), Counter(), Counter()
    for case in cases:
        row = case["engines"]["engine_v2"]
        categories[row.get("diagnostic_category", "unobserved")] += 1
        d = row.get("candidate_diagnostics")
        if d is None:
            continue
        diagnostics.append(d)
        checks.update(d["candidate_posebusters_failure_check_counts"])
        penalties.update(d["refinement_penalty_counts"])
        for key in ("candidate_slots", "successful_candidate_count", "failed_candidate_count",
                    "chemical_valid_candidate_count", "geometric_valid_candidate_count",
                    "joint_valid_candidate_count", "close_candidate_count", "close_valid_candidate_count"):
            counts[key] += d[key]
        close.extend({"case_id": case["case_id"], "global_index": case["global_index"], **c} for c in d["close_candidates"])
    for engine in ENGINES:
        rows = [case["engines"][engine] for case in cases]
        u = sum(r["status"] == "unobserved" for r in rows)
        successes = {key: sum(r[key] for r in rows) for key in RECOVERIES}
        engines[engine] = {"case_count": n, "observed_rows": n - u, "unobserved_rows": u,
            "success_rows": sum(r["status"] == "success" for r in rows),
            "failure_rows": sum(r["status"] == "failure" for r in rows),
            "failure_codes": dict(Counter(r["failure_code"] for r in rows if r["status"] == "failure")),
            "success_counts": successes, "operational_rates": {k: v / n for k, v in successes.items()},
            "missing_observation_bounds": {k: [v / n, (v + u) / n] for k, v in successes.items()},
            "observed_runtime_seconds": stats(r["runtime_seconds"] for r in rows if r["runtime_seconds"] is not None)}
        if engine == "engine_v2":
            oracles = {key: sum(r.get("candidate_diagnostics", {}).get(key, 0) for r in rows)
                       for key in ("oracle", "valid_oracle")}
            engines[engine].update(oracle_case_counts=oracles,
                oracle_operational_rates={k: v / n for k, v in oracles.items()},
                oracle_missing_observation_bounds={k: [v / n, (v + u) / n] for k, v in oracles.items()})
    return {"expected_case_count": n, "attempted_cases": sum(c["attempted"] for c in cases),
        "scientific_accuracy_complete": all(v["unobserved_rows"] == 0 for v in engines.values()),
        "execution_complete": all(c["attempted"] and not c["verification_errors"]
            and c["execution"].get("returncode") == 0 and c["execution"].get("termination") == "exited"
            and c["execution"].get("cleanup_complete") is True for c in cases),
        "engine_metrics": engines, "engine_v2_diagnostic_categories": dict(categories),
        "observed_candidate_totals": dict(counts), "candidate_posebusters_failure_check_counts": dict(sorted(checks.items())),
        "refinement_penalty_counts": dict(penalties), "close_candidates": close,
        "termination_counts": dict(Counter(c["execution"]["termination"] for c in cases)),
        "timing": {"diagnostic_evaluation_seconds": stats(d["diagnostic_evaluation_seconds"] for d in diagnostics),
            **{key: stats(c["execution"][key] for c in cases if key in c["execution"])
               for key in ("wall_seconds", "child_cpu_seconds", "sampled_peak_process_tree_rss_bytes")}},
        "cases": cases}


def paired_bootstrap(development):
    if not development["scientific_accuracy_complete"]:
        return {"performed": False, "reason": "All 32 development cases must have all three verified engine results."}
    cases = development["cases"]
    require(len(cases) == 32, "bootstrap requires 32 cases")
    rng = random.Random(20261103)
    samples = [[rng.randrange(32) for _ in range(32)] for _ in range(2000)]
    comparisons = []
    for baseline in ("vina", "gnina"):
        for k in KS:
            key = f"valid_top{k}"
            a = [c["engines"]["engine_v2"][key] for c in cases]
            b = [c["engines"][baseline][key] for c in cases]
            delta = [x - y for x, y in zip(a, b, strict=True)]
            draws = [sum(delta[i] for i in sample) / 32 for sample in samples]
            comparisons.append({"baseline": baseline, "metric": key, "case_count": 32,
                "paired_mean_delta": sum(delta) / 32,
                "percentile_95_interval": [percentile(draws, .025), percentile(draws, .975)],
                "wins": sum(x > y for x, y in zip(a, b, strict=True)),
                "losses": sum(x < y for x, y in zip(a, b, strict=True)),
                "both_success": sum(x == y == 1 for x, y in zip(a, b, strict=True)),
                "both_nonrecovery": sum(x == y == 0 for x, y in zip(a, b, strict=True)),
                "degenerate_bootstrap_distribution": len(set(draws)) == 1})
    return {"performed": True, "resamples": 2000, "seed": 20261103,
        "sampling_unit": "paired case; common resampled case indices for all metrics/engines",
        "interpretation": "Descriptive for this historical fixed prefix and one seed per case; not independent holdout or seed-robustness evidence.",
        "comparisons": comparisons}


def analyze(root, manifest_path):
    require(root.is_dir(), "artifact root must be an existing directory")
    m, manifest_hash = load_manifest(manifest_path)
    attempts, common, audits, absent = {}, {}, [], []
    for name, indices in ARTIFACTS.items():
        if not (root / name).exists():
            absent.append(name)
            continue
        bundle = Bundle(root / name)
        read_artifact(bundle, indices, m, manifest_hash, common, attempts)
        audits.append(bundle.audit)
    require(audits, "artifact root contains no recognized stage artifacts")
    smoke = scope_summary(tuple(range(2)), attempts, m)
    development = scope_summary(tuple(range(2, 34)), attempts, m)
    evaluator_hashes = {a["evaluator"]["evaluation_pipeline_sha256"] for a in audits
                        if a["evaluator"].get("evaluation_pipeline_sha256")}
    full_inventory = all(a["full_inventory_pass"] for a in audits)
    return {"schema_id": SCHEMA, "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_scope": "contaminated_development", "claim_safe": False, "primary_claim_eligible": False,
        "analyzer_sha256": sha(Path(__file__).read_bytes()), "manifest_sha256": manifest_hash,
        "source": common.get("source"), "artifact_audits": audits, "missing_artifacts": absent,
        "integrity": {"valid_present_evidence": True, "full_inventory_pass": full_inventory,
            "status": "verified" if full_inventory else "limited_inventory_with_verified_duplicate_inputs",
            "verified_execution_receipts": sum(a["canonical_execution_receipts"] for a in audits),
            "verified_materializations": sum(a["canonical_materializations"] for a in audits),
            "inventoried_missing_files": sum(len(a["inventory_missing_paths"]) for a in audits)},
        "evaluator_provenance": {"same_declared_package_versions": True if common.get("versions") else None,
            "declared_package_versions": common.get("versions"),
            "cross_shard_byte_identical_evaluator": len(evaluator_hashes) == 1 if evaluator_hashes else None,
            "distinct_pipeline_sha256s": sorted(evaluator_hashes),
            "note": "Every receipt is bound to its own artifact preflight. Different evaluator payload/pipeline hashes are preserved; their cause is not inferred."},
        "method": {"rmsd_threshold_angstrom": 2.0,
            "joint_validity": "Same pose: RMSD <= 2 AND geometric AND chemical.",
            "oracle_scope": "Successful recorded Engine V2 candidates; 64 slots per prepared case.",
            "unknown_policy": "Missing receipt is unobserved, operational non-recovery in the full stage denominator; no engine result is invented.",
            "missing_bounds": "[observed_success/N, (observed_success+unobserved)/N]; not confidence intervals.",
            "penalty_decrease": "Strict final < initial comparison of recorded binary64 penalties; not physical E/F or measured pre/post RMSD improvement.",
            "p90": "Linear interpolation at 0.9*(n-1).",
            "timing": "Observed engine runtime, excluded diagnostic evaluation, and case wall/CPU are distinct. Missing time is null and excluded; observed preparation-failure zero remains a measurement.",
            "rss": "Sampled descendant RSS may double-count shared pages. Sum of case peaks is not concurrent peak RAM or total memory consumption.",
            "categories": "Engine V2: unobserved; prep; output; no-close; close-invalid; validoutsideTop5; top5notTop1; success. First applicable condition wins.",
            "comparison_limits": m["comparison_limits"]},
        "smoke": smoke, "development": development, "paired_case_bootstrap": paired_bootstrap(development),
        "require_complete_satisfied": smoke["scientific_accuracy_complete"] and development["scientific_accuracy_complete"]}


def write_output(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as f:
            temp = Path(f.name)
            f.write(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args(argv)
    root, manifest, output = args.artifact_root.resolve(), args.manifest.resolve(), args.output.resolve()
    protected = {root / name for name in ARTIFACTS}
    protected.update(p.parent.resolve() for p in root.glob("*/artifact-inventory.json"))
    if (args.output.is_symlink() or output in (manifest, Path(__file__).resolve())
            or any(output == directory or output.is_relative_to(directory) for directory in protected)):
        parser.error("output must not overwrite original artifacts, manifest, or analyzer")
    if output.exists():
        try:
            previous = parse_json(output.read_bytes(), str(output))
            require(isinstance(previous, dict) and previous.get("schema_id") == SCHEMA,
                    "existing output is not an analyzer-generated report")
        except (OSError, ValueError, TypeError, UnicodeError) as exc:
            parser.error(f"refusing to overwrite existing non-analysis file: {exc}")
    try:
        result = analyze(root, manifest)
    except (IntegrityError, OSError, KeyError, TypeError, ValueError, OverflowError) as exc:
        result = {"schema_id": SCHEMA, "integrity": {"status": "failed", "error": str(exc)},
                  "claim_safe": False, "metrics_available": False,
                  "paired_case_bootstrap": {"performed": False, "reason": "integrity validation failed"}}
        write_output(output, result)
        print(json.dumps({"integrity": "failed", "error": str(exc), "output": str(output)}), file=sys.stderr)
        return 1
    write_output(output, result)
    print(json.dumps({"integrity": result["integrity"]["status"],
        "verified_receipts": result["integrity"]["verified_execution_receipts"],
        "development_observed_cases_all_engines": sum(all(r["status"] != "unobserved" for r in c["engines"].values())
                                                     for c in result["development"]["cases"]),
        "development_expected_cases": 32, "bootstrap_performed": result["paired_case_bootstrap"]["performed"],
        "complete": result["require_complete_satisfied"], "output": str(output)}))
    return 2 if args.require_complete and not result["require_complete_satisfied"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
