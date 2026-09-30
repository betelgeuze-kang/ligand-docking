"""Benchmark-only prospective cross force observation; no campaign resume.

Importing this source imports neither Torch/OpenMM nor any product module and
opens no molecular body. ``prepare`` reads fixed metadata and wheel source code.
``execute`` is a separate explicitly authorized numerical phase.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import stat
import sys
import time
import types
import zipfile

SCHEMA = "sro_cross_force_decomposition_diagnostic/1"
PLAN_SCHEMA = "sro_cross_force_decomposition_diagnostic_plan/1"
CASE, STATE = "perturbed_02", "initial"
GATE = 1e-8
WORK = Path("/home/betelgeuze/.codex/worktrees/engine-v2-integrated-baseline/분자동역학")
R2 = Path("/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-guard-repair-four-case-20260930-p76d71f6")
HELPER_SHA = "f9d860e150542596457e546802ef8594365c112c424f8a1abf8e82a1734e9c3a"
WHEEL_SHA = "00814229724d90cca5b81d00c2a78a4ae6dfe983e95930552ca693d2c13484b8"
FIXED_MEMBER = "betelgeuze_product/cpu_refinement_v1_2/fixed_receptor.py"
FIXED_SHA = "22c7c9a6c5ceee1c508ec6003149037c4cca7c6e1034a991c8d33c488fa2d82a"
NUMERICAL_ROLES = {"receptor", "ligand", "parameters", "cross_parameters", "endpoint_states", "openmm_reference"}
METADATA_SHA = {"terminal_plan": "b5d7eb702534259e6689ae257cb8bb0ebb2a356131fe33dd07a3d2616b21706c",
                "oracle_input_spec": "2a1b69a03827787041c2ee9307ccbd400404bf96166e11343e36d41f2f73de89"}
ENDPOINT_REF = {"path": str(R2 / "campaign/perturbed_02/native/endpoint-states.json"), "bytes": 154238,
                "sha256": "f6bb712b6530cdc2b25549a2f051df7b62f46bea248d54c09a179ed0364fa81e"}
OPENMM_REF = {"path": "/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-particle-roundtrip-20261001-ri1tdoph/numerical/receipt.json",
              "bytes": 8783916, "sha256": "4d392e37f9c6a933b980fd39cd48fbd0dc12df7f8c4bf01c025dbb3b76ba8dfc"}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def helper():
    candidates = [Path(__file__).parent / "sro_particle_roundtrip_diagnostic_v1.py",
                  WORK / "benchmarks/oracles/sro_particle_roundtrip_diagnostic_v1.py"]
    path = next((p for p in candidates if p.is_file() and not p.is_symlink()), None)
    require(path is not None, "frozen_stdlib_helper_source_required")
    # This is owned source code, not a molecular input. Execute verified bytes.
    require(path.is_absolute() and path.resolve(strict=True) == path and stat.S_ISREG(path.stat().st_mode), "owned_regular_helper_required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 128 * 1024, "bounded_helper_required")
        raw = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
    def identity(value):
        return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns
    require(identity(before) == identity(after) == identity(path.stat()) and len(raw) == before.st_size, "helper_changed_during_read")
    require(sha(raw) == HELPER_SHA, "frozen_helper_source_changed")
    module = types.ModuleType("sro_cross_force_stdlib_helper")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def vectors(rows):
    require(type(rows) is list and len(rows) == 26 and all(type(row) is list and len(row) == 3 for row in rows),
            "26_ligand_vectors_required")
    parsed = [[float(value) for value in row] for row in rows]
    require(all(math.isfinite(value) for row in parsed for value in row), "finite_vectors_required")
    return parsed


def matrix_hex(rows):
    return [[value.hex() for value in row] for row in vectors(rows)]


def record(rows):
    rows = vectors(rows)
    atom, axis = max(((i, j) for i in range(26) for j in range(3)), key=lambda ij: abs(rows[ij[0]][ij[1]]))
    return {"vectors_binary64_hex": matrix_hex(rows), "components": 78, "argmax_atom_index": atom,
            "argmax_axis": "xyz"[axis], "max_absolute_component": abs(rows[atom][axis])}


def subtract(left, right):
    return [[a - b for a, b in zip(x, y, strict=True)] for x, y in zip(vectors(left), vectors(right), strict=True)]


class Ledger:
    """Maximum slots are reserved before dispatch; active counts are observed."""
    def __init__(self, maximum_blocks, sink=None):
        require(type(maximum_blocks) is int and 1 <= maximum_blocks <= 8192, "bounded_block_count")
        self.rows, self.sink, self.maximum_blocks = [], sink or (lambda event: None), maximum_blocks
        for arm in ("baseline", "diagnostic"):
            self.reserve("cross_entry", arm)
        for arm, term in (("baseline", "combined"), ("diagnostic", "combined"),
                          ("diagnostic", "lj"), ("diagnostic", "coulomb")):
            for block in range(maximum_blocks):
                self.reserve("backward", f"{arm}.{term}.{block}")

    def reserve(self, kind, key):
        row = {"kind": kind, "key": key, "status": "reserved", "work_quantity": "not_dispatched",
               "wall_seconds": None, "process_cpu_seconds": None, "dispatch_attempted": False}
        self.rows.append(row)
        self.sink({"event": "reserved", **row})

    def call(self, kind, key, function, *args, _on_completed_return=None, **kwargs):
        candidates = [r for r in self.rows if r["kind"] == kind and r["key"] == key]
        require(len(candidates) == 1 and candidates[0]["status"] == "reserved", "duplicate_or_unreserved_call")
        row = candidates[0]
        start, cpu = time.perf_counter(), time.process_time()
        row.update(status="unknown", work_quantity="unknown", start_monotonic_seconds=start)
        self.sink({"event": "started", **row})
        primary_failure = None
        try:
            row["dispatch_attempted"] = True
            value = function(*args, **kwargs)
        except BaseException as exc:
            primary_failure = exc
            row.update(status="error", error={"type": type(exc).__name__, "reason": str(exc)})
            raise
        else:
            row.update(status="completed", work_quantity="one_boundary_call_completed")
            try:
                if _on_completed_return is not None:
                    _on_completed_return(value)
            except BaseException as exc:
                primary_failure = exc
                row["observation_error"] = {"type": type(exc).__name__, "reason": str(exc)}
                raise
            return value
        finally:
            row.update(wall_seconds=time.perf_counter() - start, process_cpu_seconds=time.process_time() - cpu)
            try:
                self.sink({"event": "finished", **row})
            except BaseException as exc:
                row["journal_secondary_error"] = {"type": type(exc).__name__, "reason": str(exc)}
                if primary_failure is None:
                    raise

    def finish_entry(self, arm):
        for row in self.rows:
            if row["kind"] == "backward" and row["key"].startswith(arm + ".") and row["status"] == "reserved":
                row["not_dispatched_reason"] = "source_skipped_inactive_blocks"
                self.sink({"event": "known_not_dispatched", **row})

    def receipt(self):
        counts = {}
        for row in self.rows:
            group = row["kind"] if row["kind"] == "cross_entry" else ".".join(row["key"].split(".")[:2])
            count = counts.setdefault(group, {"maximum_reserved": 0, "completed": 0, "error": 0, "unknown": 0, "not_dispatched": 0})
            count["maximum_reserved"] += 1
            count["not_dispatched" if row["status"] == "reserved" else row["status"]] += 1
        return {"calls": self.rows, "counts": counts, "enclosing_cross_entry_costs_must_not_be_added_to_backward_costs": True,
                "failed_or_interrupted_backward_internal_work": "unknown", "reservation_is_not_completion": True}


class Observer:
    def __init__(self, torch, ledger, block_size, sink=None):
        self.torch, self.ledger, self.block_size = torch, ledger, block_size
        self.sink = sink or (lambda event: None)
        self.raw_gradients, self.blocks = [], []
        self.baseline_ordinal = 0

    def baseline_grad(self, *args, **kwargs):
        ordinal = self.baseline_ordinal
        self.baseline_ordinal += 1
        def capture(result):
            self.capture("baseline", "combined", ordinal, result[0])
        result = self.ledger.call("backward", f"baseline.combined.{ordinal}", self.torch.autograd.grad,
                                  *args, _on_completed_return=capture, **kwargs)
        return result

    def gradient(self, start, term, energy, xyz, *, retain_graph):
        block = start // self.block_size
        def capture(result):
            self.capture("diagnostic", term, block, result[0])
        # Capture before finishing the journal boundary; later failures retain it.
        result = self.ledger.call("backward", f"diagnostic.{term}.{block}", self.torch.autograd.grad,
                                  energy, xyz, retain_graph=retain_graph, _on_completed_return=capture)
        return result[0]

    def capture(self, arm, term, block, tensor):
        row = {"arm": arm, "term": term, "block_key": block,
               "key_semantics": "active_ordinal" if arm == "baseline" else "source_receptor_block_index",
               "gradient_vectors_binary64_hex": matrix_hex(tensor.detach().tolist())}
        self.raw_gradients.append(row)
        self.sink({"event": "completed_backward_observation", **row})

    def block(self, start, end, left, right, lj, electro, combined, lj_gradient, q_gradient):
        pairs = [[int(ligand_index), start + int(receptor_offset)]
                 for ligand_index, receptor_offset in zip(left.tolist(), right.tolist(), strict=True)]
        row = {"source_block_index": start // self.block_size, "start": start, "end": end,
               "active_pair_count": len(pairs), "ordered_pairs_ligand_receptor": pairs,
               "lj_energy_hex": float(lj.detach()).hex(), "coulomb_energy_hex": float(electro.detach()).hex()}
        self.blocks.append(row)
        self.sink({"event": "completed_block_observation", **row})

    def summary(self):
        summary = {}
        for arm, term in (("baseline", "combined"), ("diagnostic", "combined"), ("diagnostic", "lj"), ("diagnostic", "coulomb")):
            rows = [row for row in self.raw_gradients if row["arm"] == arm and row["term"] == term]
            blocks = [[[float.fromhex(value) for value in vec] for vec in row["gradient_vectors_binary64_hex"]] for row in rows]
            original = [[0.0] * 3 for _ in range(26)]
            for block in blocks:
                for i in range(26):
                    for j in range(3):
                        original[i][j] -= block[i][j]
            stable = [[math.fsum(-block[i][j] for block in blocks) for j in range(3)] for i in range(26)]
            summary[f"{arm}.{term}"] = {"completed_block_count": len(blocks), "original_order_force_sum": record(original),
                                         "math_fsum_force_sum": record(stable),
                                         "math_fsum_minus_original": record(subtract(stable, original))}
        return summary


class TorchProxy:
    """Baseline namespace proxy forwards every call; never patches module globals."""
    def __init__(self, torch, observer):
        self._torch = torch
        self.autograd = types.SimpleNamespace(grad=observer.baseline_grad)

    def __getattr__(self, name):
        return getattr(self._torch, name)


def method_ast(source):
    tree = ast.parse(source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "FixedReceptorEnvironment"]
    require(len(classes) == 1, "source_environment_class_required")
    methods = [node for node in classes[0].body if isinstance(node, ast.FunctionDef) and node.name == "evaluate_cross"]
    require(len(methods) == 1, "one_source_cross_method_required")
    return methods[0]


def compile_cross(source, namespace, observer, *, diagnostic, expected_source_sha256=FIXED_SHA):
    require(sha(source) == expected_source_sha256, "fixed_source_byte_identity_required")
    function = deepcopy(method_ast(source))
    original_dump = ast.dump(function, include_attributes=False)
    matches = []
    expected = ast.dump(ast.parse("gradient = torch.autograd.grad(lj + electro, xyz)[0]").body[0], include_attributes=False)
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and ast.dump(node, include_attributes=False) == expected:
            matches.append(node)
    require(len(matches) == 1, "exact_combined_gradient_statement_required")
    if diagnostic:
        replacements = ast.parse("""gradient = _observer.gradient(start, 'combined', lj + electro, xyz, retain_graph=True)
lj_gradient = _observer.gradient(start, 'lj', lj, xyz, retain_graph=True)
q_gradient = _observer.gradient(start, 'coulomb', electro, xyz, retain_graph=False)
_observer.block(start, end, left, right, lj, electro, gradient, lj_gradient, q_gradient)
""").body
        class Transform(ast.NodeTransformer):
            def visit_Assign(self, node):
                if ast.dump(node, include_attributes=False) == expected:
                    return [ast.copy_location(deepcopy(item), node) for item in replacements]
                return node
        function = Transform().visit(function)
    function.name = "_diagnostic_cross" if diagnostic else "_baseline_cross"
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), function], type_ignores=[])
    ast.fix_missing_locations(module)
    local = dict(namespace)
    local["_observer"] = observer
    if not diagnostic:
        local["torch"] = TorchProxy(namespace["torch"], observer)
    exec(compile(module, "<verified-frozen-cross-source>", "exec"), local)
    return local[function.name], {"original_method_ast_sha256": sha(original_dump.encode()),
                                 "compiled_method_ast_sha256": sha(ast.dump(function, include_attributes=False).encode()),
                                 "combined_operand_and_original_force_accumulation_retained": True,
                                 "baseline_only_namespace_proxy": not diagnostic}


def evaluate_pair(*, source, namespace, environment, ligand, base_parameters, maximum_blocks, block_size,
                  sink=None, expected_source_sha256=FIXED_SHA):
    ledger = Ledger(maximum_blocks, sink)
    observer = Observer(namespace["torch"], ledger, block_size, sink)
    outputs, transforms, failure = {}, {}, None
    started, cpu = time.perf_counter(), time.process_time()
    try:
        for arm in ("baseline", "diagnostic"):
            function, transforms[arm] = compile_cross(source, namespace, observer, diagnostic=arm == "diagnostic",
                                                      expected_source_sha256=expected_source_sha256)
            def capture_cross(result):
                # Raw authoritative output survives comparison and final-journal failures.
                row = {"energy_hex": {key: float(value[0]).hex() for key, value in result[0].items()},
                       "force_vectors_binary64_hex": matrix_hex(result[1][0].detach().tolist()),
                       "active_pair_count": int(result[2]), "role": "new_native_cross_observation"}
                outputs[arm] = row
                if sink:
                    sink({"event": "completed_cross_observation", "arm": arm, **row})
            ledger.call("cross_entry", arm, function, environment, ligand, base_parameters,
                        _on_completed_return=capture_cross)
            ledger.finish_entry(arm)
        require(outputs["baseline"] == outputs["diagnostic"], "new_baseline_diagnostic_cross_not_exact")
        summaries = observer.summary()
        for arm in ("baseline", "diagnostic"):
            require(summaries[arm + ".combined"]["original_order_force_sum"]["vectors_binary64_hex"]
                    == outputs[arm]["force_vectors_binary64_hex"], "combined_reaccumulation_not_exact")
        lj = [[float.fromhex(v) for v in row] for row in summaries["diagnostic.lj"]["original_order_force_sum"]["vectors_binary64_hex"]]
        q = [[float.fromhex(v) for v in row] for row in summaries["diagnostic.coulomb"]["original_order_force_sum"]["vectors_binary64_hex"]]
        total = [[float.fromhex(v) for v in row] for row in outputs["diagnostic"]["force_vectors_binary64_hex"]]
        decomposed = [[a + b for a, b in zip(x, y, strict=True)] for x, y in zip(lj, q, strict=True)]
        decomposition = {"combined_minus_separately_summed_lj_q": record(subtract(total, decomposed)),
                         "combined_output_overwritten": False}
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "reason": str(exc)}
    accounting = ledger.receipt()
    backward_rows = [row for row in ledger.rows if row["kind"] == "backward"]
    completed = sum(row["status"] == "completed" for row in backward_rows)
    attempted = sum(row["status"] in {"completed", "error", "unknown"} for row in backward_rows)
    uncertain = sum(row["status"] in {"error", "unknown"} for row in backward_rows)
    return {"schema_id": SCHEMA, "case_id": CASE, "state_label": STATE,
            "status": "completed" if failure is None else "failed", "failure": failure,
            "native_cross_observations": outputs, "transforms": transforms,
            "backward_observations": observer.raw_gradients, "block_observations": observer.blocks,
            "force_sum_observations": summaries if "summaries" in locals() else {},
            "decomposition": decomposition if "decomposition" in locals() else {},
            "call_accounting": accounting, "numerical_enclosing_wall_seconds": time.perf_counter() - started,
            "numerical_enclosing_process_cpu_seconds": time.process_time() - cpu,
            "enclosing_costs_must_not_be_added_to_nested_costs": True,
            "completed_native_backward_returns": completed, "attempted_native_backward_calls": attempted,
            "attempted_count_semantics": "completed/error/unknown boundary starts; see dispatch_attempted per call",
            "dispatched_native_backward_calls": sum(row["dispatch_attempted"] for row in backward_rows),
            "native_backward_error_calls": sum(row["status"] == "error" for row in backward_rows),
            "native_backward_unknown_calls": sum(row["status"] == "unknown" for row in backward_rows),
            "native_backward_internal_work_unknown": uncertain > 0,
            "native_backward_work_performed": True if completed else ("unknown" if uncertain else False),
            "raw_native_observations_performed": bool(observer.raw_gradients or outputs),
            "new_native_observations_are_historical_r2_vectors": False, "historical_total_minus_new_cross_is_old_internal": False,
            "new_internal_calls": 0, "new_optimizer_calls": 0, "new_score_calls": 0, "new_openmm_calls": 0,
            "native_graph_build_api_calls": 0, "autograd_graph_construction_is_within_cross_entry_cost": True,
            "intrareceptor_energy_evaluated": False, "frozen_gate": GATE, "cause_established": False,
            "scientifically_validated": False, "frozen_campaign_modified_or_resumed": False}


def wheel_sources(ref, h):
    require(ref["sha256"] == WHEEL_SHA, "frozen_old_wheel_required")
    raw = h.read_ref(ref)
    sources = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for entry in archive.infolist():
            if not entry.filename.endswith(".py"):
                continue
            parts = PurePosixPath(entry.filename)
            require(not parts.is_absolute() and ".." not in parts.parts and entry.file_size <= 2 * 1024 * 1024
                    and entry.filename not in sources, "bounded_unique_source_member_required")
            sources[entry.filename] = archive.read(entry)
    require(FIXED_MEMBER in sources and sha(sources[FIXED_MEMBER]) == FIXED_SHA, "fixed_cross_source_required")
    return sources


def ref_metadata(ref, name=None):
    require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}, "exact_file_pin_required")
    path = Path(ref["path"])
    require(path.is_absolute() and not {"reference", "evaluation_only", "stability_control", "Fresh-128", "fresh-128"}.intersection(path.parts)
            and path.name != "ligand-canonical.json", "forbidden_input_role_path")
    require(name is None or path.name == name, "role_filename_mismatch")
    require(type(ref["bytes"]) is int and 0 < ref["bytes"] <= 32 * 1024 * 1024,
            "bounded_file_required")
    require(type(ref["sha256"]) is str and len(ref["sha256"]) == 64 and all(c in "0123456789abcdef" for c in ref["sha256"]), "sha256_required")


def checked_new_output(output):
    output = Path(output)
    protected = {"reference", "evaluation_only", "stability_control", "Fresh-128", "fresh-128"}
    roots = (R2, Path(OPENMM_REF["path"]).parents[1], WORK, Path("/home/betelgeuze/분자동역학"))
    require(output.is_absolute() and not output.exists() and output.parent.resolve() == output.parent
            and not protected.intersection(output.parts) and output.name != "ligand-canonical.json"
            and not any(output.is_relative_to(root) for root in roots), "new_unprotected_non_source_output_required")
    return output


def validate_source_refs(plan, plan_path):
    names = {"diagnostic": "sro_cross_force_decomposition_diagnostic_v1.py",
             "tests": "test_sro_cross_force_decomposition_diagnostic_v1.py",
             "document": "sro_cross_force_decomposition_diagnostic_plan_20261001.md",
             "stdlib_helper": "sro_particle_roundtrip_diagnostic_v1.py"}
    require(set(plan["source_refs"]) == set(names), "exact_source_roles_required")
    source_directory = Path(plan_path).parent / "source"
    for role, name in names.items():
        ref = plan["source_refs"][role]
        ref_metadata(ref, name)
        require(Path(ref["path"]) == source_directory / name, "owned_snapshot_source_role_required")
    require(plan["source_refs"]["stdlib_helper"]["sha256"] == HELPER_SHA, "frozen_stdlib_helper_source_required")


def validate_unloaded_runtime():
    prefixes = ("betelgeuze_product", "betelgeuze_engine", "betelgeuze_engine_v2", "core", "torch", "numpy")
    require(not any(name == prefix or name.startswith(prefix + ".") for name in sys.modules for prefix in prefixes),
            "product_and_numerical_modules_must_not_be_preloaded")


def validate_loaded_closure(site, sources, required_modules):
    loaded = {}
    prefixes = ("betelgeuze_product", "betelgeuze_engine", "betelgeuze_engine_v2", "core")
    for name, imported in tuple(sys.modules.items()):
        if not any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes):
            continue
        origin = getattr(imported, "__file__", None)
        require(origin is not None, "product_source_origin_required")
        path = Path(origin).resolve(strict=True)
        require(path.is_relative_to(site), "loaded_product_outside_frozen_source_closure")
        relative = path.relative_to(site).as_posix()
        require(relative in sources and path.read_bytes() == sources[relative], "loaded_source_not_frozen_wheel")
        loaded[name] = {"member": relative, "sha256": sha(sources[relative])}
    require(set(required_modules).issubset(loaded), "required_frozen_imports_missing")
    return loaded


def prepare_plan(*, r2, output, test_source, document_source, openmm_receipt_ref, receptor_count, receptor_block_size):
    require(Path(r2) == R2, "fixed_r2_metadata_root_required")
    output = checked_new_output(output)
    require(Path(__file__).name == "sro_cross_force_decomposition_diagnostic_v1.py"
            and Path(test_source).name == "test_sro_cross_force_decomposition_diagnostic_v1.py"
            and Path(document_source).name == "sro_cross_force_decomposition_diagnostic_plan_20261001.md", "owned_source_names_required")
    require(openmm_receipt_ref == OPENMM_REF and receptor_count == 4376 and receptor_block_size == 256,
            "reviewed_newR_ref_and_shape_required")
    h = helper()
    refs = {}
    for role, name in (("terminal_plan", "plan.json"), ("oracle_input_spec", "oracle-input-spec.json")):
        refs[role] = h.pin(R2 / name, allowed_paths=[R2 / name])
        require(refs[role]["sha256"] == METADATA_SHA[role], "fixed_metadata_hash_required")
    old = json.loads(h.read_ref(refs["terminal_plan"]))
    spec = json.loads(h.read_ref(refs["oracle_input_spec"]))
    case = next(case for case in old["cases"] if case["case_id"] == CASE)
    numerical = {name: case["derived_input_refs"][name] for name in ("receptor", "ligand", "parameters", "cross_parameters")}
    numerical.update(endpoint_states=ENDPOINT_REF, openmm_reference=openmm_receipt_ref)
    for ref in numerical.values():
        ref_metadata(ref)
    sources = wheel_sources(old["wheel_ref"], h)
    fixed_ref = h.pin(WORK / FIXED_MEMBER, allowed_paths=[WORK / FIXED_MEMBER])
    require(h.read_ref(fixed_ref) == sources[FIXED_MEMBER], "current_fixed_source_not_old_wheel_identical")
    count = math.ceil(receptor_count / receptor_block_size)
    output.mkdir(mode=0o700)
    snapshot = output / "source"
    snapshot.mkdir()
    source_refs = {}
    for role, path in (("diagnostic", Path(__file__)), ("tests", Path(test_source)),
                       ("document", Path(document_source)), ("stdlib_helper", Path(h.__file__))):
        ref = h.pin(path, allowed_paths=[path])
        destination = snapshot / path.name
        destination.write_bytes(h.read_ref(ref))
        source_refs[role] = h.pin(destination, allowed_paths=[destination])
    plan = {"schema_id": PLAN_SCHEMA, "case_id": CASE, "state_label": STATE, "frozen_campaign_root": str(R2),
            "source_refs": source_refs, "metadata_refs": refs, "numerical_refs": numerical,
            "source_closure": {"wheel_ref": old["wheel_ref"], "fixed_receptor_member": FIXED_MEMBER,
                               "member_manifest": {name: {"bytes": len(raw), "sha256": sha(raw)} for name, raw in sorted(sources.items())}},
            "declared_shape": {"receptor_count": receptor_count, "receptor_block_size": receptor_block_size, "maximum_blocks": count},
            "protocol_budget": {"cross_entries": 2, "baseline_combined_backward": count, "diagnostic_combined_backward": count,
                                "diagnostic_lj_backward": count, "diagnostic_coulomb_backward": count, "total_reserved": 2 + 4 * count},
            "source_state_identity": {"derived_system_sha256": case["derived_system_sha256"],
                                      "derived_topology_sha256": case["derived_topology_sha256"],
                                      "request_ref": case["request_file_ref"], "expected_binding_ref": case["expected_binding_ref"]},
            "dependency_site": spec["dependency_site"], "python_binary_ref": old["oracle_phase"]["python_binary_ref"],
            "frozen_gate": GATE, "actual_execution_performed": False, "campaign_resume_allowed": False,
            "read_phases": {"prepare": "fixed plan/spec metadata, owned source, old wheel .py source only; no numerical bodies",
                            "execute_authorized": "matching derived ligand/parameters/cross, receptor, saved initial observation, newR original OpenMM observation"}}
    h.write_json(output / "plan.json", plan)
    return h.pin(output / "plan.json", allowed_paths=[output / "plan.json"])


def validate_roles(plan, h):
    require(plan["schema_id"] == PLAN_SCHEMA and plan["case_id"] == CASE and plan["state_label"] == STATE,
            "initial_case02_plan_required")
    require(Path(plan["frozen_campaign_root"]) == R2 and plan["frozen_gate"] == GATE
            and plan["campaign_resume_allowed"] is False, "frozen_scope_required")
    require(set(plan["metadata_refs"]) == set(METADATA_SHA), "exact_metadata_roles_required")
    for role, name in (("terminal_plan", "plan.json"), ("oracle_input_spec", "oracle-input-spec.json")):
        ref = plan["metadata_refs"][role]
        require(ref["path"] == str(R2 / name) and ref["sha256"] == METADATA_SHA[role], "fixed_metadata_ref_required")
    old = json.loads(h.read_ref(plan["metadata_refs"]["terminal_plan"]))
    case = next(case for case in old["cases"] if case["case_id"] == CASE)
    require(set(plan["numerical_refs"]) == NUMERICAL_ROLES, "exact_numerical_roles_required")
    expected = {name: case["derived_input_refs"][name] for name in ("receptor", "ligand", "parameters", "cross_parameters")}
    expected.update(endpoint_states=ENDPOINT_REF, openmm_reference=OPENMM_REF)
    require(plan["numerical_refs"] == expected, "matching_declared_numerical_refs_required")
    for ref in expected.values():
        ref_metadata(ref)
    require(plan["declared_shape"] == {"receptor_count": 4376, "receptor_block_size": 256, "maximum_blocks": 18}, "fixed_shape_required")
    require(plan["protocol_budget"] == {"cross_entries": 2, "baseline_combined_backward": 18, "diagnostic_combined_backward": 18,
                                        "diagnostic_lj_backward": 18, "diagnostic_coulomb_backward": 18, "total_reserved": 74}, "fixed_budget_required")
    require(plan["source_closure"]["wheel_ref"] == old["wheel_ref"] and old["wheel_ref"]["sha256"] == WHEEL_SHA,
            "frozen_source_wheel_required")
    require(plan["source_state_identity"] == {"derived_system_sha256": case["derived_system_sha256"],
                                              "derived_topology_sha256": case["derived_topology_sha256"],
                                              "request_ref": case["request_file_ref"], "expected_binding_ref": case["expected_binding_ref"]},
            "exact_terminal_source_state_identity_required")
    spec = json.loads(h.read_ref(plan["metadata_refs"]["oracle_input_spec"]))
    require(plan["dependency_site"] == spec["dependency_site"]
            and plan["python_binary_ref"] == old["oracle_phase"]["python_binary_ref"], "pinned_runtime_metadata_required")


def compare_openmm(receipt, saved):
    require(saved["schema_id"] == "sro_particle_roundtrip_diagnostic/1" and saved["case_id"] == CASE
            and saved["status"] == "completed" and saved["actual_openmm_observations"] is True, "newR_observation_required")
    require(saved["receipt_sha256"] == sha(canonical({k: v for k, v in saved.items() if k != "receipt_sha256"})), "newR_receipt_seal")
    terms = saved["states"][STATE]["original_xml_particles"]["terms"]
    mapping = {"combined": "cross", "lj": "cross_lj", "coulomb": "cross_coulomb"}
    result = {}
    for term, key in mapping.items():
        native = receipt["force_sum_observations"]["diagnostic." + term]["original_order_force_sum"]["vectors_binary64_hex"]
        reference = terms[key]["ligand_force"]["vectors_binary64_hex"]
        first, second = ([[float.fromhex(v) for v in row] for row in items] for items in (native, reference))
        difference = record(subtract(first, second))
        energy = receipt["native_cross_observations"]["diagnostic"]["energy_hex"]
        native_energy = (float.fromhex(energy["cross_lennard_jones"]) + float.fromhex(energy["cross_screened_coulomb"])) if term == "combined" else \
            float.fromhex(energy["cross_lennard_jones" if term == "lj" else "cross_screened_coulomb"])
        energy_delta = native_energy - float.fromhex(terms[key]["energy_kcal_per_mol_hex"])
        result[term] = {"new_native_minus_stored_newR_openmm_force": difference,
                        "passed_fixed_1e_minus_8_force_gate": difference["max_absolute_component"] <= GATE,
                        "native_energy_kcal_per_mol_hex": native_energy.hex(),
                        "new_native_minus_stored_newR_openmm_energy_hex": energy_delta.hex(),
                        "passed_fixed_1e_minus_8_energy_gate": abs(energy_delta) <= GATE,
                        "native_role": "new_native_cross_observation", "openmm_role": "stored_newR_original_arm_observation"}
    return result


def restore_runtime(raw_stream, original_path, original_bytecode_setting):
    """Cleanup never erases an earlier native or postprocessing failure."""
    sys.path[:] = original_path
    sys.dont_write_bytecode = original_bytecode_setting
    errors = []
    try:
        raw_stream.close()
    except BaseException as exc:
        errors.append({"type": type(exc).__name__, "reason": str(exc)})
    return errors


def failure_envelope(receipt, primary_failure, cleanup_errors):
    if primary_failure:
        receipt.update(status="failed", primary_post_execution_failure=primary_failure)
    if cleanup_errors:
        receipt.update(status="failed", cleanup_errors=cleanup_errors)
    return receipt


def module_source_pin(path, h):
    """Software module file pin; only canonical empty Python source permits size 0.

    This exception never applies to numerical inputs or to compiled modules.
    Nonempty module files retain the frozen helper's bounded pin behavior.
    """
    path = Path(path)
    if path.stat().st_size:
        return h.pin(path, allowed_paths=[path], max_bytes=128 * 1024 * 1024)
    path = h.validate_path(path)
    require(path.suffix == ".py" and "reference" not in path.parts,
            "empty_python_module_source_only")
    validated = path.stat()
    require(stat.S_ISREG(validated.st_mode) and validated.st_size == 0, "empty_regular_python_source_required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size == 0, "empty_regular_python_source_required")
        raw = stream.read(1)
        after = os.fstat(stream.fileno())
    require(h.file_identity(validated) == h.file_identity(before) == h.file_identity(after)
            == h.file_identity(path.stat()), "module_source_changed_during_read")
    require(raw == b"", "empty_module_source_eof_required")
    return {"path": str(path), "bytes": 0, "sha256": sha(raw)}


def environment_identity(torch, python_binary_ref, h):
    """Loaded module files only; never claims OS/dlopen/in-memory closure."""
    dependencies, unresolved = {}, {}
    for name, module in tuple(sys.modules.items()):
        if name == "torch" or name.startswith("torch.") or name == "numpy" or name.startswith("numpy."):
            origin = getattr(module, "__file__", None)
            if origin is None:
                unresolved[name] = {"origin": None, "reason": "module_file_origin_absent"}
            elif not isinstance(origin, (str, os.PathLike)):
                unresolved[name] = {"origin": str(origin), "reason": "module_file_origin_not_path"}
            else:
                path = Path(origin)  # Preserve symlink and noncanonical-origin evidence.
                require(not path.is_symlink(), "module_file_symlink_forbidden")
                if path.is_file():
                    dependencies[name] = module_source_pin(path, h)
                else:
                    unresolved[name] = {"origin": str(origin),
                                        "reason": "module_file_missing" if not path.exists() else "module_file_nonregular"}
    torch_path = Path(torch.__file__)
    return {"python_executable": sys.executable, "python_version": platform.python_version(),
            "python_binary_ref": python_binary_ref, "torch_version": torch.__version__,
            "torch_module_ref": module_source_pin(torch_path, h),
            "torch_threads": torch.get_num_threads(), "torch_interop_threads": torch.get_num_interop_threads(),
            "dtype": "float64", "device": "cpu", "loaded_dependency_modules": dependencies,
            "unresolved_dependency_module_origins": unresolved,
            "loaded_dependency_manifest_sha256": sha(canonical(dependencies)),
            "loaded_dependency_origin_manifest_sha256": sha(canonical({"files": dependencies, "unresolved": unresolved})),
            "manifest_scope": "file-backed loaded Torch/NumPy Python and extension module files only",
            "zero_byte_python_source_pins_allowed": True, "full_shared_library_closure_claimed": False,
            "complete_provenance_admission_claimed": False}


def compare_stored_initial_energies(receipt, initial):
    baseline = receipt["native_cross_observations"].get("baseline")
    if baseline is None:
        return {"status": "not_observed"}
    result = {}
    for name in ("cross_lennard_jones", "cross_screened_coulomb"):
        new_hex, old_hex = baseline["energy_hex"][name], initial["components"][name]
        difference = float.fromhex(new_hex) - float.fromhex(old_hex)
        result[name] = {"new_baseline_energy_hex": new_hex, "stored_r2_initial_component_energy_hex": old_hex,
                        "exact_hex_match": new_hex == old_hex, "new_minus_stored_energy_hex": difference.hex(),
                        "passed_fixed_1e_minus_8_energy_gate": abs(difference) <= GATE,
                        "stored_role": "historical_r2_initial_component_energy_observation"}
    return result


def execute_plan(plan_path, plan_sha256, output, *, numerical_phase_authorized=False):
    require(numerical_phase_authorized, "explicit_numerical_phase_authorization_required")
    h = helper()
    plan_ref = h.pin(Path(plan_path), allowed_paths=[Path(plan_path)])
    require(plan_ref["sha256"] == plan_sha256, "exact_reviewed_plan_hash_required")
    plan = json.loads(h.read_ref(plan_ref))
    validate_roles(plan, h)  # All role/ref checks precede every numerical body read.
    validate_source_refs(plan, plan_path)
    require(h.pin(Path(__file__), allowed_paths=[Path(__file__)]) == plan["source_refs"]["diagnostic"], "executing_snapshot_changed")
    executable = Path(sys.executable).resolve()
    require(h.pin(executable, allowed_paths=[executable]) == plan["python_binary_ref"], "python_binary_changed")
    output = checked_new_output(output)
    for ref in plan["source_refs"].values():
        h.read_ref(ref)
    sources = wheel_sources(plan["source_closure"]["wheel_ref"], h)
    require({name: {"bytes": len(raw), "sha256": sha(raw)} for name, raw in sorted(sources.items())}
            == plan["source_closure"]["member_manifest"], "source_closure_changed")
    output.mkdir(mode=0o700)
    raw_stream = (output / "events.jsonl").open("x")
    def sink(event):
        raw_stream.write(canonical(event).decode() + "\n")
        raw_stream.flush()
        h.os.fsync(raw_stream.fileno())
    receipt, input_reads, original_path, failure = None, [], list(sys.path), None
    original_bytecode_setting = sys.dont_write_bytecode
    native_protocol_entry_attempted = False
    started, cpu = time.perf_counter(), time.process_time()
    try:
        validate_unloaded_runtime()
        bodies = {}
        for role, ref in plan["numerical_refs"].items():
            raw = h.read_ref(ref)
            input_reads.append({"role": role, "phase": "authorized_numerical", "ref": ref, "status": "completed"})
            bodies[role] = raw
        # Fresh imports resolve only through the reviewed wheel source and dependency site.
        site = output / "old-wheel-source"
        for name, raw in sources.items():
            path = site / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        sys.path[:0] = [str(site), plan["dependency_site"]]
        sys.dont_write_bytecode = True
        import torch
        from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
        from betelgeuze_product.reference_minimization_workflow import _parameters
        from betelgeuze_product.cpu_refinement_v1_2 import fixed_receptor as module
        require(Path(torch.__file__).resolve(strict=True).is_relative_to(Path(plan["dependency_site"]).resolve(strict=True)),
                "torch_outside_pinned_dependency_site")
        required_modules = ("betelgeuze_engine_v2.molecular.serialization",
                            "betelgeuze_product.reference_minimization_workflow",
                            "betelgeuze_product.cpu_refinement_v1_2.fixed_receptor")
        validate_loaded_closure(site, sources, required_modules)
        receptor = all_atom_system_from_canonical_json(bodies["receptor"])
        ligand = all_atom_system_from_canonical_json(bodies["ligand"])
        parameters = _parameters(json.loads(bodies["parameters"]))
        cross = module.CrossParameters.from_dict(json.loads(bodies["cross_parameters"]))
        require(receptor.atom_count == 4376 and len(cross.receptor_atoms) == 4376
                and cross.receptor_block_size == 256, "pinned_body_shape_mismatch")
        endpoints = json.loads(bodies["endpoint_states"])
        require(endpoints["schema_id"] == "sro_saved_numerical_endpoints/1" and endpoints["case_id"] == CASE
                and [state["label"] for state in endpoints["states"]] == [STATE, "last_accepted"], "saved_initial_state_required")
        initial = endpoints["states"][0]
        require(matrix_hex(ligand.coordinates[0].tolist()) == initial["coordinates"], "derived_ligand_initial_coordinates_changed")
        require(json.loads(bodies["ligand"])["system_sha256"] == plan["source_state_identity"]["derived_system_sha256"],
                "derived_system_identity_changed")
        environment = module.FixedReceptorEnvironment(receptor, cross)
        environment.validate_ligand(ligand, parameters)
        with torch.inference_mode(False), torch.enable_grad(), torch.autocast(device_type="cpu", enabled=False):
            native_protocol_entry_attempted = True
            receipt = evaluate_pair(source=sources[FIXED_MEMBER], namespace=vars(module), environment=environment,
                                    ligand=ligand, base_parameters=parameters, maximum_blocks=18, block_size=256, sink=sink)
        # Preserve computed receipt if any later parsing/comparison/integrity check fails.
        receipt["stored_initial_component_energy_comparison"] = compare_stored_initial_energies(receipt, initial)
        if receipt["status"] == "completed":
            saved = json.loads(bodies["openmm_reference"])
            require(saved["stored_state_pins"][0]["coordinates_sha256"] == sha(canonical(initial["coordinates"])), "newR_initial_coordinate_pin_mismatch")
            receipt["openmm_comparison"] = compare_openmm(receipt, saved)
        receipt["loaded_product_source_closure"] = validate_loaded_closure(site, sources, required_modules)
        receipt["environment"] = environment_identity(torch, plan["python_binary_ref"], h)
        for ref in [*plan["source_refs"].values(), *plan["metadata_refs"].values(), *plan["numerical_refs"].values(),
                    plan["python_binary_ref"], plan["source_closure"]["wheel_ref"]]:
            h.read_ref(ref)
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "reason": str(exc)}
    finally:
        cleanup_errors = restore_runtime(raw_stream, original_path, original_bytecode_setting)
    if receipt is None:
        receipt = {"schema_id": SCHEMA, "case_id": CASE, "state_label": STATE, "status": "failed",
                   "raw_native_observations_performed": False,
                   "completed_native_backward_returns": None if native_protocol_entry_attempted else 0,
                   "attempted_native_backward_calls": None if native_protocol_entry_attempted else 0,
                   "native_backward_internal_work_unknown": native_protocol_entry_attempted,
                   "native_backward_work_performed": "unknown" if native_protocol_entry_attempted else False,
                   "call_accounting_recovery": "consult durable events.jsonl" if native_protocol_entry_attempted else "native protocol not entered"}
    failure_envelope(receipt, failure, cleanup_errors)
    receipt.update(plan_ref=plan_ref, input_reads=input_reads, input_refs=plan["numerical_refs"], source_refs=plan["source_refs"],
                   actual_execution_performed=True, native_protocol_entry_attempted=native_protocol_entry_attempted,
                   entry_enclosing_wall_seconds=time.perf_counter() - started,
                   entry_enclosing_process_cpu_seconds=time.process_time() - cpu,
                   entry_scope_must_not_be_added_to_cross_or_backward_cost=True, frozen_gate=GATE,
                   cause_established=False, scientifically_validated=False, historical_total_minus_new_cross_is_old_internal=False)
    receipt["receipt_sha256"] = sha(canonical(receipt))
    h.write_json(output / "receipt.json", receipt)
    return h.pin(output / "receipt.json", allowed_paths=[output / "receipt.json"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    prepare = commands.add_parser("prepare")
    for option in ("r2", "output", "test-source", "document-source", "openmm-receipt-ref"):
        prepare.add_argument("--" + option, required=True)
    prepare.add_argument("--receptor-count", type=int, required=True)
    prepare.add_argument("--receptor-block-size", type=int, required=True)
    execute = commands.add_parser("execute")
    for option in ("plan", "plan-sha256", "output"):
        execute.add_argument("--" + option, required=True)
    execute.add_argument("--numerical-phase-authorized", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "prepare":
        ref = prepare_plan(r2=args.r2, output=args.output, test_source=args.test_source, document_source=args.document_source,
                           openmm_receipt_ref=json.loads(args.openmm_receipt_ref), receptor_count=args.receptor_count,
                           receptor_block_size=args.receptor_block_size)
    else:
        ref = execute_plan(args.plan, args.plan_sha256, args.output, numerical_phase_authorized=args.numerical_phase_authorized)
    print(json.dumps(ref, sort_keys=True))
    if args.action == "execute" and json.loads(helper().read_ref(ref))["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()
