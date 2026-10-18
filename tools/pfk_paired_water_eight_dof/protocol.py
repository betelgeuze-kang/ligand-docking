"""Stdlib-only source and budget admission for one fresh paired PFK campaign.

Building a plan hashes inputs and probes installed versions; it performs no
prepared-real objective, force, coordinate fit, or reference evaluation. The
expected plan byte hash is supplied independently to every verifier.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import uuid


SCHEMA = "pfk_paired_dry_wet_eight_dof/1.0.0"
PHASE_ORDER = ("diagnostic-dry", "diagnostic-wet", "P0-dry", "P0-wet",
               "Qplus-wet", "Qplus-dry", "Qminus-dry", "Qminus-wet")
INPUT_NAMES = ("ligand", "receptor", "parameters", "cross", "source_evidence")
SOURCE_EVIDENCE_REF_COUNT = 16
SOURCE_EVIDENCE_RELOCATION_SCHEMA = "pfk_source_evidence_path_relocation/1.0.0"
SOURCE_BRANCH = "codex/docking-paired-source-relocation"
BOUNDARY = {"independent_measurement_denominator": None,
            "original_simulation_hamiltonian_reproduced": False,
            "product_ranking_enabled": False, "scientifically_validated": False,
            "source_authenticated": False, "training_admitted": False,
            "affinity_validated": False, "chemical_validity_qualified": False,
            "blind_docking_validated": False, "release_qualified": False}
STOPPING = {"ligand_force_tolerance": 0.001, "water_torque_tolerance": 0.001,
            "fd_step": 1e-5, "fd_atol": 1e-4, "fd_rtol": 1e-4,
            "max_geometric_halvings_per_step": 32, "restart_verifications": 0,
            "model_warm_starts": False, "reference_used_in_objective_or_selection": False}
METRICS_POLICY = {
    "schema": "pfk_new_primary_reference_policy/1.0.0",
    "metric_id": "p2_new_6hvi_receptor_ca415_symmetry_heavy30_v1",
    "receptor_fit": "proper_unweighted_Kabsch_crystal_CA_to_prepared_CA",
    "receptor_ca_count": 415, "receptor_residual_outlier_removal": False,
    "receptor_reflection_allowed": False,
    "alternate_policy": "unique_blank_or_highest_occupancy_nonblank_ties_lexicographic_A_first",
    "ligand_fit_allowed": False, "ligand_heavy_atom_count": 30,
    "graph_admitted_mapping_count": 4,
    "score": "minimum_unweighted_heavy_atom_RMSD_over_all_four_fixed_graph_mappings",
    "transform_applied_to": "observed_crystal_ligand_reference_only",
    "same_metric_for_every_arm": True, "reference_used_in_objective_or_selection": False,
    "historical_missing_reference_hash_reproduced": False,
    "P0_no_harm_margin_angstrom": 1e-6,
    "Q_recovery": "endpoint_RMSD_strictly_less_than_own_start_RMSD",
    "report_all_starts_endpoints_and_mappings": True,
    "pose_contact_ratio_threshold": 0.85,
    "pose_contacts_are_diagnostic_only": True,
}
GEOMETRY_CAPS = {"geometry_admit": 100000, "geometry_pullback": 100000,
                 "geometry_coordinates": 100000}
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class PlanError(ValueError):
    """Admission failed; no numerical work is authorized by this module."""


def _absolute(path):
    value = os.fspath(path)
    if (not isinstance(value, str) or not value.startswith("/") or value.startswith("//")
            or os.path.normpath(value) != value or ".." in Path(value).parts):
        raise PlanError("normalized absolute path required")
    return Path(value)


def _directory_fd(path):
    path = _absolute(path)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _file_fd(path):
    path = _absolute(path)
    parent = _directory_fd(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    finally:
        os.close(parent)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise PlanError("regular source file required")
    return fd


def hash_file(path):
    """Stream a regular file, refusing symlinks in every path component."""
    with os.fdopen(_file_fd(path), "rb") as stream:
        before = os.fstat(stream.fileno())
        result = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
        after = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != \
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise PlanError("source changed during hashing")
        return result.hexdigest()


def _json_file(path):
    with os.fdopen(_file_fd(path), "r", encoding="utf-8") as handle:
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise PlanError("duplicate JSON key")
                result[key] = value
            return result
        return json.load(handle, object_pairs_hook=pairs,
                         parse_constant=lambda value: (_ for _ in ()).throw(PlanError("nonfinite JSON")))


def write_json_absent(path, value):
    """Publish a new file with durable bytes and durable directory entry."""
    path = _absolute(path)
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    parent = _directory_fd(path.parent)
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.fsync(parent)
    finally:
        os.close(parent)
    return hashlib.sha256(data).hexdigest()


def _fresh_directory(path):
    path = _absolute(path)
    parent = _directory_fd(path.parent)
    try:
        os.mkdir(path.name, 0o700, dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(parent)


def _tree_files(root):
    root = _absolute(root)
    result = set()
    def visit(fd, relative):
        with os.scandir(fd) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                name = relative / entry.name
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        visit(child, name)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(info.st_mode):
                    result.add(str(root / name))
                else:
                    raise PlanError("symlink or special file in immutable source closure")
    fd = _directory_fd(root)
    try:
        visit(fd, Path())
    finally:
        os.close(fd)
    return result


def phase_spec(phase, roots):
    if phase not in PHASE_ORDER:
        raise PlanError("unknown phase")
    wet = phase.endswith("-wet")
    diagnostic = phase.startswith("diagnostic-")
    start = "P0" if diagnostic else phase.rsplit("-", 1)[0]
    chart_root = roots["dry"] if start == "P0" else roots["heldout"]
    return {"start": start, "wet": wet, "kind": "diagnostic" if diagnostic else "optimizer",
            "chart_path": str(Path(chart_root) / "start/chart-contracts.json"), "chart_key": start,
            "objective_cap": 17 if diagnostic else 641, "accepted_cap": 600}


def stage_caps(phase):
    if phase not in PHASE_ORDER:
        raise PlanError("unknown phase")
    diagnostic = phase.startswith("diagnostic-")
    n = 17 if diagnostic else 641
    wet = phase.endswith("-wet")
    return {"objective": n, "source_base_full_EF": n, "cross_correction_EF": n,
            "internal_correction_EF": n, "backward_base": 55 * n, "backward_cross": n,
            "backward_internal": n, "external_graph": n, "source_admission_graph": n,
            "WL_EF": n if wet else 0, "backward_WL": 9 * n if wet else 0,
            "terminal_water_global": 0 if diagnostic else 1,
            "terminal_water_kernel": 0 if diagnostic else 102,
            "terminal_water_backward": 0 if diagnostic else 726,
            "terminal_water_screen": 0 if diagnostic else 1}


def phase_limits(phase):
    if phase not in PHASE_ORDER:
        raise PlanError("unknown phase")
    diagnostic = phase.startswith("diagnostic-")
    return {"wall_seconds": 300 if diagnostic else 2400,
            "cpu_seconds": 300 if diagnostic else 2400,
            "optimizer_budget_seconds": 0 if diagnostic else 2100,
            "terminal_budget_seconds": 0 if diagnostic else 300,
            "address_space_bytes": 4 * 1024 ** 3, "file_bytes": 64 * 1024 ** 2,
            "tree_bytes": 200 * 1024 ** 2, "poll_seconds": 0.5,
            "minimum_free_disk_bytes": 2 * 1024 ** 3,
            "minimum_available_memory_bytes": 1024 ** 3}


def aggregate_caps():
    return {key: sum(stage_caps(phase)[key] for phase in PHASE_ORDER)
            for key in stage_caps(PHASE_ORDER[0])}


def _sha(value):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise PlanError("lowercase SHA256 required")


def _binding(value, hash_key="sha256"):
    if not isinstance(value, dict) or "path" not in value or hash_key not in value:
        raise PlanError("path/hash binding required")
    _absolute(value["path"])
    _sha(value[hash_key])


def _check_exact(actual, expected, description):
    # JSON equality alone treats True as 1; compare canonical bytes as well.
    if json.dumps(actual, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
        raise PlanError(description)


def validate_plan(plan):
    """Validate the frozen experiment contract without touching source files."""
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA:
        raise PlanError("paired eight-DOF plan schema required")
    try:
        if str(uuid.UUID(plan["run_id"])) != plan["run_id"]:
            raise PlanError("canonical run UUID required")
        roots = plan["source_roots"]
        if set(roots) != {"dry", "heldout", "water"} or len(set(roots.values())) != 3:
            raise PlanError("three distinct source roots required")
        for root in roots.values():
            _absolute(root)
        _check_exact(plan["phase_order"], list(PHASE_ORDER), "fixed phase order changed")
        _check_exact(plan["phases"], {p: phase_spec(p, roots) for p in PHASE_ORDER}, "arm/start/chart/cap changed")
        _check_exact(plan["stage_caps_by_phase"], {p: stage_caps(p) for p in PHASE_ORDER}, "physical stage cap changed")
        _check_exact(plan["limits_by_phase"], {p: phase_limits(p) for p in PHASE_ORDER}, "phase resource limit changed")
        _check_exact(plan["geometry_caps_by_phase"], {p: GEOMETRY_CAPS for p in PHASE_ORDER}, "geometry memory cap changed")
        _check_exact(plan["aggregate_stage_caps"], aggregate_caps(), "aggregate stage cap changed")
        _check_exact(plan["stopping_policy"], STOPPING, "stopping policy changed")
        _check_exact(plan["boundary"], BOUNDARY, "research boundary changed")
        _check_exact(plan["review_requirements"], {"root_source_review_before_diagnostics": True,
                     "independent_source_review_before_diagnostics": True,
                     "root_and_independent_diagnostic_review_before_optimizer": True,
                     "automatic_retry_after_unknown_or_failure": False}, "review gate changed")
        for key in ("protocol", "reference", "metrics_policy"):
            _binding(plan[key])
        _binding(plan["water_checkpoint"], "bytes_sha256")
        _sha(plan["water_checkpoint"]["state_sha256"])
        if plan["water_checkpoint"]["path"] != str(Path(roots["water"]) / "runs/optimization/final-checkpoint.json"):
            raise PlanError("retained final water checkpoint required")
        if "limits" in plan:
            raise PlanError("limits_by_phase is the single resource limit authority")
        runtime = plan["runtime"]
        _absolute(runtime["python_executable"])
        if not re.fullmatch(r"3\.10\.\d+", runtime["python"]) or runtime["torch"] != "2.6.0+cpu" or runtime["numpy"] != "1.26.4":
            raise PlanError("admitted Python 3.10 / Torch 2.6 CPU / NumPy 1.26.4 required")
        if not isinstance(runtime["pip_freeze"], list) or not isinstance(runtime["import_roots"], dict):
            raise PlanError("runtime distribution/import-root record required")
        affinity = runtime["cpu_affinity"]
        if (not isinstance(affinity, list) or len(affinity) != 1 or type(affinity[0]) is not int
                or affinity[0] not in os.sched_getaffinity(0)
                or type(runtime["cpu_threads"]) is not int or runtime["cpu_threads"] != 1
                or type(runtime["interop_threads"]) is not int or runtime["interop_threads"] != 1):
            raise PlanError("one available fixed CPU and one intra/inter-op thread required")
        files = plan["source_files"]
        if not isinstance(files, dict) or not files:
            raise PlanError("immutable source files required")
        for path, checksum in files.items():
            _absolute(path)
            _sha(checksum)
        for key, hash_key in (("protocol", "sha256"), ("reference", "sha256"), ("metrics_policy", "sha256"), ("water_checkpoint", "bytes_sha256")):
            if files.get(plan[key]["path"]) != plan[key][hash_key]:
                raise PlanError("binding omitted from immutable source files")
        relocation = plan["source_evidence_relocation"]
        if (set(relocation) != {"schema", "original", "derived", "source_files"}
                or relocation["schema"] != SOURCE_EVIDENCE_RELOCATION_SCHEMA):
            raise PlanError("explicit nested source-evidence relocation required")
        for key in ("original", "derived"):
            _binding(relocation[key])
            if set(relocation[key]) != {"path", "sha256"} or files.get(relocation[key]["path"]) != relocation[key]["sha256"]:
                raise PlanError("original and derived source-evidence byte bindings required")
        if relocation["original"]["path"] != str(Path(roots["dry"]) / "snapshot/inputs/PFKFB3/source_evidence.json"):
            raise PlanError("original source-evidence path changed")
        if relocation["derived"]["path"] != str(Path(plan["protocol"]["path"]).parent / "relocated-source-evidence.json"):
            raise PlanError("fresh sibling derived source-evidence required")
        if relocation["derived"]["path"] == relocation["original"]["path"]:
            raise PlanError("original source-evidence must remain unchanged")
        if type(relocation["source_files"]) is not list or len(relocation["source_files"]) != SOURCE_EVIDENCE_REF_COUNT:
            raise PlanError("all sixteen nested source bindings required")
        nested_targets = set()
        for row in relocation["source_files"]:
            if set(row) != {"original_path", "path", "sha256"}:
                raise PlanError("exact nested source relocation fields required")
            _absolute(row["original_path"])
            _binding(row)
            target = str(Path(roots["dry"]) / "snapshot/evidence/PFKFB3" / Path(row["original_path"]).name)
            if row["path"] != target or target in nested_targets or files.get(target) != row["sha256"]:
                raise PlanError("nested evidence target missing, duplicated or outside selected dry evidence")
            nested_targets.add(target)
        _binding(plan["structural_policy"])
        if files.get(plan["structural_policy"]["path"]) != plan["structural_policy"]["sha256"]:
            raise PlanError("structural policy omitted from immutable files")
        closures = plan["source_roots_closure"]
        if not isinstance(closures, dict) or len(closures) != 2:
            raise PlanError("two complete archive tree closures required")
        covered = set()
        for root, entries in closures.items():
            base = _absolute(root)
            if not isinstance(entries, dict) or not entries:
                raise PlanError("nonempty closure required")
            for relative, checksum in entries.items():
                parts = PurePosixPath(relative)
                if parts.is_absolute() or ".." in parts.parts or str(parts) != relative:
                    raise PlanError("safe relative archive member required")
                path = str(base / relative)
                _sha(checksum)
                if files.get(path) != checksum or path in covered:
                    raise PlanError("archive closure missing or duplicated source binding")
                covered.add(path)
        if not all(any(Path(root).is_relative_to(Path(base)) for base in closures) for root in roots.values()):
            raise PlanError("execution roots must belong to admitted archive closures")
        if len(plan["receipt_paths"]) != 2 or any(path not in files for path in plan["receipt_paths"]):
            raise PlanError("two byte-admission receipts required")
        own = plan["own_source"]
        _absolute(own["root"])
        if not re.fullmatch(r"[0-9a-f]{40,64}", own["git_commit"]):
            raise PlanError("source Git commit required")
        if own["branch"] != SOURCE_BRANCH:
            raise PlanError("dedicated source branch required")
        if not own["files"] or any(files.get(path) != checksum for path, checksum in own["files"].items()):
            raise PlanError("own source byte binding required")
    except (KeyError, TypeError, AttributeError) as exc:
        raise PlanError("incomplete paired plan") from exc
    return plan


def _receipt_sources(receipt_paths):
    files, closures = {}, {}
    for path in receipt_paths:
        receipt = _json_file(path)
        if "restored_parent" in receipt:
            root, field = _absolute(receipt["restored_parent"]), "member"
        elif "restored_root" in receipt:
            root, field = _absolute(receipt["restored_root"]), "source_path"
        else:
            raise PlanError("unrecognized byte admission receipt")
        if str(root) in closures:
            raise PlanError("duplicate archive source root")
        entries = {}
        for row in receipt["files"]:
            member = PurePosixPath(row[field])
            if member.is_absolute() or ".." in member.parts:
                raise PlanError("unsafe receipt member")
            if field == "source_path":
                if not member.parts or member.parts[0] != root.name:
                    raise PlanError("water receipt root mismatch")
                member = PurePosixPath(*member.parts[1:])
            relative = str(member)
            if relative in entries or relative in ("", "."):
                raise PlanError("duplicate or empty archive member")
            _sha(row["sha256"])
            entries[relative] = row["sha256"]
            files[str(root / relative)] = row["sha256"]
        if len(entries) != receipt["regular_files_verified"]:
            raise PlanError("receipt file census mismatch")
        closures[str(root)] = entries
    if len(closures) != 2:
        raise PlanError("both complete byte admission receipts required")
    return files, closures


def _verify_closure(files, closures):
    for root, entries in closures.items():
        expected = {str(Path(root) / relative) for relative in entries}
        if _tree_files(root) != expected:
            raise PlanError("extra or missing immutable archive file")
    for path, expected in files.items():
        if hash_file(path) != expected:
            raise PlanError("immutable source SHA256 mismatch: " + path)


def _relocated_source_evidence(roots, files):
    """Rebase exactly sixteen opaque evidence refs, preserving every digest.

    Evidence leaves are hash-checked, never parsed or recursively rewritten.
    The original reader also requires single-link regular files <=32MiB.
    """
    source = str(Path(roots["dry"]) / "snapshot/inputs/PFKFB3/source_evidence.json")
    if files.get(source) != hash_file(source):
        raise PlanError("original source-evidence bytes not admitted")
    document = _json_file(source)
    if (type(document) is not dict or set(document) != {
            "schema_version", "evidence_kind", "source_files", "source_authenticated",
            "original_simulation_hamiltonian_reproduced"}
            or document["schema_version"] != "declared_prepared_source_evidence/1.0.0"
            or document["evidence_kind"] != "prepared_real_development"
            or document["source_authenticated"] is not False
            or document["original_simulation_hamiltonian_reproduced"] is not False
            or type(document["source_files"]) is not list
            or len(document["source_files"]) != SOURCE_EVIDENCE_REF_COUNT):
        raise PlanError("original sixteen-file source-evidence contract changed")
    derived, records = deepcopy(document), []
    originals, targets = set(), set()
    for index, row in enumerate(document["source_files"]):
        if type(row) is not dict or set(row) != {"path", "sha256"}:
            raise PlanError("exact source-evidence binding fields required")
        original = _absolute(row["path"])
        _sha(row["sha256"])
        if original.parts[-4:-1] != ("snapshot", "evidence", "PFKFB3"):
            raise PlanError("original nested evidence suffix changed")
        target = str(Path(roots["dry"]) / "snapshot/evidence/PFKFB3" / original.name)
        if str(original) in originals or target in targets or files.get(target) != row["sha256"]:
            raise PlanError("nested evidence target missing, duplicated or not byte-admitted")
        fd = _file_fd(target)
        try:
            info = os.fstat(fd)
            if info.st_nlink != 1 or info.st_size > 32 * 1024 ** 2:
                raise PlanError("nested evidence must be single-link and at most 32MiB")
        finally:
            os.close(fd)
        if hash_file(target) != row["sha256"]:
            raise PlanError("nested source-evidence target bytes changed")
        originals.add(str(original))
        targets.add(target)
        derived["source_files"][index]["path"] = target
        records.append({"original_path": str(original), "path": target, "sha256": row["sha256"]})
    return derived, {"path": source, "sha256": files[source]}, records


def _relocation_record(original, derived, records):
    return {"schema": SOURCE_EVIDENCE_RELOCATION_SCHEMA,
            "original": original, "derived": derived, "source_files": records}


def _relocated_protocol(roots, files, *, source_evidence_binding):
    document = deepcopy(_json_file(Path(roots["dry"]) / "start/protocol.json"))
    for name in INPUT_NAMES:
        binding = document[name]
        new = str(Path(roots["dry"]) / "snapshot/inputs/PFKFB3" / (name + ".json"))
        if set(binding) != {"path", "sha256"} or files.get(new) != binding["sha256"]:
            raise PlanError("original protocol input binding mismatch")
        binding["path"] = new
    _binding(source_evidence_binding)
    if (set(source_evidence_binding) != {"path", "sha256"}
            or files.get(source_evidence_binding["path"]) != source_evidence_binding["sha256"]):
        raise PlanError("derived source-evidence byte binding missing")
    document["source_evidence"] = deepcopy(source_evidence_binding)
    if document["boundary"] != {key: BOUNDARY[key] for key in document["boundary"]}:
        raise PlanError("original protocol boundary changed")
    return document


def verify_plan(plan_path, expectedsha):
    """Verify complete source bytes/closures before any archived module import."""
    _sha(expectedsha)
    if hash_file(plan_path) != expectedsha:
        raise PlanError("frozen plan byte hash mismatch")
    plan = validate_plan(_json_file(plan_path))
    receipt_files, closures = _receipt_sources(plan["receipt_paths"])
    _check_exact(plan["source_roots_closure"], closures, "receipt/archive closure disagreement")
    if any(plan["source_files"].get(path) != checksum for path, checksum in receipt_files.items()):
        raise PlanError("receipt source omitted from plan")
    _verify_closure(plan["source_files"], closures)
    own_root = Path(plan["own_source"]["root"])
    own_paths = {str(p) for p in (own_root / "tools/pfk_paired_water_eight_dof").glob("*.py")}
    own_paths.add(str(own_root / "tools/run_pfk_paired_water_eight_dof.py"))
    if own_paths != set(plan["own_source"]["files"]):
        raise PlanError("own implementation file closure changed")
    derived_document, original_binding, nested_records = _relocated_source_evidence(plan["source_roots"], receipt_files)
    derived_binding = plan["source_evidence_relocation"]["derived"]
    _check_exact(plan["source_evidence_relocation"], _relocation_record(original_binding, derived_binding, nested_records),
                 "nested source-evidence relocation record changed")
    _check_exact(_json_file(derived_binding["path"]), derived_document,
                 "derived source-evidence changed more than sixteen paths")
    _check_exact(_json_file(plan["protocol"]["path"]),
                 _relocated_protocol(plan["source_roots"], plan["source_files"], source_evidence_binding=derived_binding),
                 "relocated protocol changed beyond four input paths and derived source-evidence binding")
    policy = _json_file(plan["metrics_policy"]["path"])
    _check_exact(policy, {**METRICS_POLICY, "reference": plan["reference"]}, "new metric policy changed")
    checkpoint = _json_file(plan["water_checkpoint"]["path"])
    if checkpoint["state_sha256"] != plan["water_checkpoint"]["state_sha256"]:
        raise PlanError("retained water state identity changed")
    if (checkpoint.get("solver_status") != "current_global_world_torque_converged"
            or checkpoint.get("extra_final_objectives") != 0 or checkpoint.get("weights_applied") is not False):
        raise PlanError("original terminal water checkpoint contract changed")
    return plan


def _own_sources(root):
    root = _absolute(root)
    folder = root / "tools/pfk_paired_water_eight_dof"
    source_paths = sorted(folder.glob("*.py")) + [root / "tools/run_pfk_paired_water_eight_dof.py"]
    if not source_paths or (folder / "protocol.py") not in source_paths:
        raise PlanError("own implementation source missing")
    relative = [str(p.relative_to(root)) for p in source_paths]
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, text=True, timeout=15).stdout.strip()
    branch = git("branch", "--show-current")
    commit = git("rev-parse", "HEAD")
    if git("status", "--porcelain=1", "--untracked-files=all", "--", *relative):
        raise PlanError("own source must be committed before plan freeze")
    git("ls-files", "--error-unmatch", "--", *relative)
    return {"root": str(root), "git_commit": commit, "branch": branch,
            "files": {str(p): hash_file(p) for p in source_paths}}


def _runtime(python, cwd):
    executable = str(_absolute(python))
    # Venv executable symlinks are admitted explicitly; immutable input hashes
    # use no-follow traversal. Isolated mode excludes user paths and env imports.
    code = ("import json,platform,sys,torch,numpy; "
            "print(json.dumps({'python':platform.python_version(),'torch':torch.__version__,"
            "'numpy':numpy.__version__,'import_roots':{'torch':torch.__file__,'numpy':numpy.__file__},"
            "'sys_prefix':sys.prefix,'reported_executable':sys.executable}))")
    env = {"PATH": "/usr/bin:/bin", "OMP_NUM_THREADS": "1",
           "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    def run(args):
        return subprocess.run([executable, "-B", "-I", *args], check=True, capture_output=True,
                              text=True, cwd=cwd, env=env, timeout=60).stdout
    result = json.loads(run(["-c", code]))
    result["python_executable"] = executable
    result["pip_freeze"] = sorted(run(["-m", "pip", "freeze", "--all"]).splitlines())
    result["cpu_affinity"] = [max(os.sched_getaffinity(0))]
    result["cpu_threads"] = 1
    result["interop_threads"] = 1
    return result


def build_plan(*, source_roots, reference_path, runtime_python, output_dir, own_source_root, receipt_paths):
    """Build one absent-only frozen plan after source/independent code review.

    The caller launches nothing here. Returned plan_path and plan_sha256 are
    passed separately to the supervisor/worker. Partial output is preserved on
    any failure and cannot be resumed or overwritten by this function.
    """
    roots = {key: str(_absolute(value)) for key, value in source_roots.items()}
    if set(roots) != {"dry", "heldout", "water"}:
        raise PlanError("dry/heldout/water roots required")
    receipts = [str(_absolute(path)) for path in receipt_paths]
    files, closures = _receipt_sources(receipts)
    if sorted(map(len, closures.values())) != [2113, 2250] or len(files) != 4363:
        raise PlanError("original admitted 2113+2250 archive files required for this research builder")
    _verify_closure(files, closures)
    own = _own_sources(own_source_root)
    files.update(own["files"])
    for path in receipts:
        files[path] = hash_file(path)
    reference_path = _absolute(reference_path)
    reference = {"path": str(reference_path), "sha256": hash_file(reference_path)}
    admission = _json_file(reference_path)
    if (admission.get("schema") != "p2_new_primary_reference_graph_and_ca_admission.v1"
            or admission["scope"]["coordinate_alignment_or_transform_performed"] is not False
            or admission["graph_admission"]["heavy_atom_isomorphism_count"] != 4
            or admission["receptor_ca_admission"]["matched_ca_count"] != 415):
        raise PlanError("new source-only primary reference admission required")
    files[str(reference_path)] = reference["sha256"]
    for row in admission["official_primary_sources"]:
        if hash_file(row["path"]) != row["sha256"]:
            raise PlanError("primary source bytes changed")
        files[row["path"]] = row["sha256"]
        files[row["receipt_path"]] = hash_file(row["receipt_path"])
    files[admission["audit_script_path"]] = admission["audit_script_sha256"]
    checkpoint_path = str(Path(roots["water"]) / "runs/optimization/final-checkpoint.json")
    checkpoint = _json_file(checkpoint_path)
    checkpoint_binding = {"path": checkpoint_path, "bytes_sha256": hash_file(checkpoint_path),
                          "state_sha256": checkpoint["state_sha256"]}
    output = _absolute(output_dir)
    _fresh_directory(output)
    protocol_path, policy_path = output / "relocated-protocol.json", output / "metrics-policy.json"
    evidence_document, original_evidence_binding, nested_records = _relocated_source_evidence(roots, files)
    derived_evidence_path = output / "relocated-source-evidence.json"
    derived_evidence_binding = {"path": str(derived_evidence_path),
                                "sha256": write_json_absent(derived_evidence_path, evidence_document)}
    files[str(derived_evidence_path)] = derived_evidence_binding["sha256"]
    protocol_binding = {"path": str(protocol_path), "sha256": write_json_absent(
        protocol_path, _relocated_protocol(roots, files, source_evidence_binding=derived_evidence_binding))}
    policy_binding = {"path": str(policy_path), "sha256": write_json_absent(policy_path, {**METRICS_POLICY, "reference": reference})}
    files[str(protocol_path)], files[str(policy_path)] = protocol_binding["sha256"], policy_binding["sha256"]
    runtime = _runtime(runtime_python, output)
    plan = {"schema": SCHEMA, "run_id": str(uuid.uuid4()), "source_roots": roots,
            "protocol": protocol_binding, "water_checkpoint": checkpoint_binding,
            "source_evidence_relocation": _relocation_record(original_evidence_binding, derived_evidence_binding, nested_records),
            "runtime": runtime, "own_source": own, "receipt_paths": receipts,
            "source_files": dict(sorted(files.items())), "source_roots_closure": closures,
            "reference": reference, "metrics_policy": policy_binding,
            "phase_order": list(PHASE_ORDER), "phases": {p: phase_spec(p, roots) for p in PHASE_ORDER},
            "stage_caps_by_phase": {p: stage_caps(p) for p in PHASE_ORDER},
            "limits_by_phase": {p: phase_limits(p) for p in PHASE_ORDER},
            "geometry_caps_by_phase": {p: dict(GEOMETRY_CAPS) for p in PHASE_ORDER},
            "aggregate_stage_caps": aggregate_caps(), "stopping_policy": deepcopy(STOPPING),
            "boundary": deepcopy(BOUNDARY),
            "review_requirements": {"root_source_review_before_diagnostics": True,
                                    "independent_source_review_before_diagnostics": True,
                                    "root_and_independent_diagnostic_review_before_optimizer": True,
                                    "automatic_retry_after_unknown_or_failure": False},
            "authorization_scope": "Human-authorized bounded new paired research; historical approval/execution assertions are not imported",
            "water_constant_policy": "Retained checkpoint WP/WW constants; no fresh baseline water-global call; six terminal globals only",
            "budget_scope_note": "Each new arm has total2400s including2100s optimizer and300s terminal reserve; historical optimizer-only2400s is a different scope"}
    structural = reference_path.parent / "structural-policy-inputs.json"
    plan["structural_policy"] = {"path": str(structural), "sha256": hash_file(structural)}
    plan["source_files"][str(structural)] = plan["structural_policy"]["sha256"]
    structural_metadata = _json_file(structural)
    if structural_metadata.get("schema") != "pfk_structural_policy_inputs/1.0.0":
        raise PlanError("frozen graph/radius structural policy required")
    for row in structural_metadata["declared_source_files"]:
        if hash_file(row["path"]) != row["sha256"]:
            raise PlanError("structural-policy source changed")
        plan["source_files"][row["path"]] = row["sha256"]
    validate_plan(plan)
    plan_path = output / "plan.json"
    checksum = write_json_absent(plan_path, plan)
    verify_plan(plan_path, checksum)
    return {"plan_path": str(plan_path), "plan_sha256": checksum, "plan": plan}
