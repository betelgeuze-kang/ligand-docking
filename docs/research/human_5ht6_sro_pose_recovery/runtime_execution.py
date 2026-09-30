"""Standalone, pinned SRO native execution and retained-result export.

No reference, transform, control, RMSD, or historical trajectory bodies are
optimizer inputs. Native execution is explicit, create-only and never resumed.
The numeric oracle is a separate, supplied-receipt phase.
"""

from __future__ import annotations
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import hashlib
from types import ModuleType
import json
import math
import os
from pathlib import Path
import re
import sys
import time

CASE_IDS = ["perturbed_01", "perturbed_02", "perturbed_03", "perturbed_04"]
WHEEL_SHA = "00814229724d90cca5b81d00c2a78a4ae6dfe983e95930552ca693d2c13484b8"
PROTOCOL_SHA = "5977f12ee7e35710e6a8eb09a19337ff579750f2573fa442d31b89fe3a94ca23"
MANIFEST_SHA = "4fa96ef4a8457fd20e8bce67dafa380c08b01e15765bcfbb0a1eb67634815dc3"
OLD_SITE = "/tmp/engine-v2-sro-old-runtime-20260930-urt3cf_3/site"
AUDIT_MANIFEST_SHA = "c1ba37cd6493ca9234c8d1ac162442a3b57d216d8a600854fedd6e5d05422b59"
ROOT_AUDIT_SHA = "ec0d4b2e9bc77250d5f694bec2520bf3a8b9d308d4f2610ff0845ecddb0096bb"
DERIVATION_SHA = "9ab197d0e47bb97750dca7a2cbbf105a831af82d5e92dfafa1ebf752fab0220c"
GEOMETRY_CHECKS = {
    "bond_lengths_preserved",
    "declared_chirality_preserved",
    "element_vdw_ligand_overlap_free",
    "element_vdw_receptor_overlap_free",
    "inside_declared_pocket",
    "ligand_self_clash_free",
    "proper_rotation",
    "receptor_ligand_clash_free",
}
AUDIT_ROOT = "/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-recovery-input-audit-20260930-bnag1vbf"
FRAME = "7XTB_original_cartesian_angstrom_development"
SHA = re.compile(r"^[0-9a-f]{64}$")
FILE_FIELDS = ("ligand", "parameters", "extensions", "cross_parameters", "receptor")
BUDGET = {
    "objective_attempts": 417,
    "accepted_steps": 416,
    "restart_force_calls": 2,
    "score_calls": 2,
    "oracle_states": 2,
    "wall_seconds": 7200,
}


class ExecutionError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise ExecutionError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def native_digest(value):
    return sha(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    )


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _finite(value, depth=0):
    require(depth < 96, "json_depth")
    if type(value) is float:
        require(math.isfinite(value), "nonfinite_json")
    elif type(value) is dict:
        for item in value.values():
            _finite(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _finite(item, depth + 1)
    else:
        require(value is None or type(value) in (str, int, bool), "invalid_json_type")
    return value


def loads(raw):
    return _finite(
        json.loads(
            raw,
            object_pairs_hook=_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ExecutionError("nonfinite_json")
            ),
        )
    )


def pin(path):
    path = Path(path)
    require(
        path.is_absolute()
        and not path.is_symlink()
        and str(path.resolve(strict=True)) == str(path),
        "canonical_path_required",
    )
    raw = path.read_bytes()
    return {"path": str(path), "sha256": sha(raw), "bytes": len(raw)}


def bound(ref, *, parse=True):
    require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}, "pin_fields")
    require(
        type(ref["sha256"]) is str
        and SHA.fullmatch(ref["sha256"])
        and type(ref["bytes"]) is int
        and 0 <= ref["bytes"] <= 256 * 1024 * 1024,
        "pin_shape",
    )
    path = Path(ref["path"])
    require(
        path.is_absolute()
        and not path.is_symlink()
        and str(path.resolve(strict=True)) == ref["path"],
        "canonical_path_required",
    )
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    require(
        (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        and len(raw) == ref["bytes"]
        and sha(raw) == ref["sha256"],
        "immutable_input_changed",
    )
    return loads(raw) if parse else raw


def publish(path, value):
    path = Path(path)
    with path.open("xb") as stream:
        stream.write(encode(value))
        stream.flush()
        os.fsync(stream.fileno())
    return pin(path)


def now():
    return datetime.now(timezone.utc).isoformat()


def load_adapter(ref):
    # Execute exactly the verified snapshot; never reread a loader path or pyc.
    raw = bound(ref, parse=False)
    module = ModuleType("sro_frozen_adapter")
    module.__file__ = ref["path"]
    exec(compile(raw, ref["path"], "exec"), module.__dict__)
    require(pin(ref["path"]) == ref, "adapter_changed")
    return module


def oracle_phase_contract(phase):
    if phase is None:
        return None
    require(
        type(phase) is dict
        and set(phase)
        == {
            "python_executable",
            "python_binary_ref",
            "argv_template",
            "source_refs",
            "receipt_name",
        },
        "oracle_phase_fields",
    )
    source = Path(__file__).resolve(strict=True).parent
    expected_paths = {
        str(source / name)
        for name in (
            "endpoint_oracle_runner.py",
            "campaign_supervisor.py",
            "sro_recovery_endpoint_numerics_v1.py",
        )
    }
    expected_paths.add(str(source.parent / "oracle-input-spec.json"))
    require(
        type(phase["source_refs"]) is list
        and len(phase["source_refs"]) == 4
        and {ref["path"] for ref in phase["source_refs"]} == expected_paths,
        "oracle_source_roles_required",
    )
    require(
        phase["python_executable"] == "/usr/bin/python3",
        "declared_oracle_python_required",
    )
    require(
        type(phase["python_executable"]) is str
        and Path(phase["python_executable"]).is_absolute()
        and pin(Path(phase["python_executable"]).resolve(strict=True))
        == phase["python_binary_ref"],
        "oracle_python_binary_changed",
    )
    require(
        type(phase["source_refs"]) is list
        and phase["source_refs"]
        and len({ref["path"] for ref in phase["source_refs"]})
        == len(phase["source_refs"]),
        "oracle_source_refs",
    )
    for ref in phase["source_refs"]:
        require(
            "evaluation_only" not in Path(ref["path"]).parts
            and "stability_control" not in Path(ref["path"]).parts
            and not Path(ref["path"]).name == "ligand-canonical.json",
            "oracle_reference_body_forbidden",
        )
        bound(ref, parse=False)
    argv = phase["argv_template"]
    require(
        type(argv) is list
        and len(argv) >= 3
        and all(type(arg) is str and arg for arg in argv)
        and argv[:3] == ["-I", "-B", str(source / "endpoint_oracle_runner.py")],
        "oracle_source_pinned_argv",
    )
    allowed = {
        "plan_path",
        "plan_sha256",
        "case_id",
        "child_result_path",
        "child_result_sha256",
        "oracle_output",
    }
    from string import Formatter

    for arg in argv:
        for _, field, format_spec, conversion in Formatter().parse(arg):
            if field is not None:
                require(
                    field in allowed and not format_spec and conversion is None,
                    "oracle_placeholder",
                )
        require(
            "evaluation_only" not in arg and "stability_control" not in arg,
            "oracle_reference_argument_forbidden",
        )
    require(phase["receipt_name"] == "numerical-receipt.json", "oracle_receipt_name")
    return phase


def request_contract(request):
    require(
        request["schema_id"] == "cpu_cartesian_registered_pose_request/1.3.0"
        and request["backend"] == "python_cpu_reference"
        and request["solvation"] is None,
        "native_request_required",
    )
    solver = request["solver"]
    require(
        solver["algorithm"] == "lbfgs"
        and solver["max_objective_attempts"] == 417
        and solver["max_accepted_steps"] == 416
        and solver["max_restart_verifications"] == 2
        and solver["force_tolerance"] == 0.001
        and solver["maximum_atom_displacement"] == 0.05,
        "frozen_solver_budget",
    )
    require(
        request["budget"]["candidate_count"] == request["budget"]["top_k"] == 1
        and request["budget"]["max_torsions"] == 0
        and request["budget"]["translation_radius_angstrom"] == 0
        and request["pocket"]["coordinate_frame_id"] == FRAME,
        "reference_free_single_start",
    )
    return request


def build_plan(audit_root, python_executable, output, *, oracle_phase=None):
    """Build a create-only plan from already audited derivative inputs, no calls."""
    root = Path(audit_root).resolve(strict=True)
    require(str(root) == AUDIT_ROOT, "declared_audit_root_required")
    audit_ref = pin(root / "root-audit.json")
    derivation_ref = pin(root / "derived-inputs/derivation.json")
    manifest_ref = pin(root / "manifest.json")
    require(
        (audit_ref["sha256"], derivation_ref["sha256"], manifest_ref["sha256"])
        == (ROOT_AUDIT_SHA, DERIVATION_SHA, AUDIT_MANIFEST_SHA),
        "frozen_audit_source_changed",
    )
    audit = bound(audit_ref)
    derivation = bound(derivation_ref)
    manifest = bound(manifest_ref)
    oracle_phase_contract(oracle_phase)
    require(
        audit["status"] == "passed"
        and audit["prepared_derivatives"] == 4
        and audit["reference_body_reads"] == audit["original_ligand_body_reads"] == 0,
        "audited_inputs_required",
    )
    require(
        audit["protocol_sha256"]
        == derivation["prospective_protocol_sha256"]
        == PROTOCOL_SHA
        and audit["manifest_sha256"]
        == derivation["prospective_manifest_sha256"]
        == MANIFEST_SHA
        and derivation["expected_executed_wheel_sha256"] == WHEEL_SHA,
        "historical_freeze_binding",
    )
    require(
        [case["case_id"] for case in derivation["cases"]] == CASE_IDS, "four_case_order"
    )
    artifact_refs = []
    for name, record in manifest["payload_files"].items():
        require(
            "evaluation_only" not in Path(name).parts
            and "stability_control" not in Path(name).parts,
            "forbidden_archive_member",
        )
        require((root / name).resolve().is_relative_to(root), "archive_escape")
        require(
            type(record) is dict and set(record) == {"sha256", "bytes"},
            "archive_pin_fields",
        )
        ref = {**record, "path": str(root / name)}
        bound(ref, parse=False)
        artifact_refs.append(ref)
    cases = []
    for case in derivation["cases"]:
        request = request_contract(bound(case["request_file_ref"]))
        require(
            set(case["derived_input_refs"]) == set(FILE_FIELDS), "derived_input_set"
        )
        for name, ref in case["derived_input_refs"].items():
            bound(ref, parse=False)
            require(
                request[name] == {key: ref[key] for key in ("path", "sha256")},
                "request_derivative_binding",
            )
        binding_ref = pin(root / (case["case_id"] + "-installed-binding.json"))
        binding = bound(binding_ref)
        require(
            binding["executed_wheel"]["sha256"] == WHEEL_SHA
            and binding["installed_site"] == OLD_SITE
            and binding["input_binding"]["request_sha256"] == native_digest(request),
            "old_binding_required",
        )
        bound(case["numeric_term_preservation_proof_ref"])
        cases.append({**deepcopy(case), "expected_binding_ref": binding_ref})
    adapter_ref = pin(root / "runtime_adapter_snapshot.py")
    require(
        adapter_ref["sha256"] == audit["source_adapter_sha256"],
        "audited_adapter_required",
    )
    plan = {
        "schema_id": "sro_native_execution_plan/1",
        "created_at": now(),
        "protocol_sha256": PROTOCOL_SHA,
        "manifest_sha256": MANIFEST_SHA,
        "budget": deepcopy(BUDGET),
        "execution_order": CASE_IDS,
        "audit_root": str(root),
        "root_audit_ref": audit_ref,
        "derivation_ref": derivation_ref,
        "audit_manifest_ref": manifest_ref,
        "archive_payload_refs": artifact_refs,
        "adapter_ref": adapter_ref,
        "driver_source_ref": pin(Path(__file__).resolve()),
        "python_executable": str(Path(python_executable).absolute()),
        "python_binary_ref": pin(Path(python_executable).resolve(strict=True)),
        "installed_site": OLD_SITE,
        "wheel_ref": bound(cases[0]["expected_binding_ref"])["executed_wheel"],
        "cases": cases,
        "oracle_phase": deepcopy(oracle_phase),
        "actual_execution_authorized": False,
        "scientifically_validated": False,
    }
    publish(Path(output).absolute(), plan)
    return plan


def validate_plan(plan):
    require(
        type(plan) is dict
        and set(plan)
        == {
            "schema_id",
            "created_at",
            "protocol_sha256",
            "manifest_sha256",
            "budget",
            "execution_order",
            "audit_root",
            "root_audit_ref",
            "derivation_ref",
            "audit_manifest_ref",
            "archive_payload_refs",
            "adapter_ref",
            "driver_source_ref",
            "python_executable",
            "python_binary_ref",
            "installed_site",
            "wheel_ref",
            "cases",
            "oracle_phase",
            "actual_execution_authorized",
            "scientifically_validated",
        },
        "plan_fields",
    )
    require(
        plan["schema_id"] == "sro_native_execution_plan/1"
        and plan["protocol_sha256"] == PROTOCOL_SHA
        and plan["manifest_sha256"] == MANIFEST_SHA
        and native_digest(plan["budget"]) == native_digest(BUDGET)
        and plan["execution_order"] == CASE_IDS
        and [c["case_id"] for c in plan["cases"]] == CASE_IDS,
        "plan_contract",
    )
    require(
        plan["audit_root"] == AUDIT_ROOT
        and plan["installed_site"] == OLD_SITE
        and plan["wheel_ref"]["sha256"] == WHEEL_SHA,
        "old_runtime_required",
    )
    require(
        pin(Path(__file__).resolve()) == plan["driver_source_ref"],
        "executing_driver_changed",
    )
    root = Path(AUDIT_ROOT)
    for field, name in [
        ("root_audit_ref", "root-audit.json"),
        ("derivation_ref", "derived-inputs/derivation.json"),
        ("audit_manifest_ref", "manifest.json"),
        ("adapter_ref", "runtime_adapter_snapshot.py"),
    ]:
        require(plan[field]["path"] == str(root / name), "plan_ref_path_changed")
    require(
        (
            plan["root_audit_ref"]["sha256"],
            plan["derivation_ref"]["sha256"],
            plan["audit_manifest_ref"]["sha256"],
        )
        == (ROOT_AUDIT_SHA, DERIVATION_SHA, AUDIT_MANIFEST_SHA),
        "frozen_audit_source_changed",
    )
    manifest = bound(plan["audit_manifest_ref"])
    expected_refs = []
    for name, record in manifest["payload_files"].items():
        require(
            type(record) is dict
            and set(record) == {"sha256", "bytes"}
            and (root / name).resolve().is_relative_to(root)
            and "evaluation_only" not in Path(name).parts
            and "stability_control" not in Path(name).parts,
            "archive_whitelist",
        )
        expected_refs.append({**record, "path": str(root / name)})
    require(
        plan["archive_payload_refs"] == expected_refs, "archive_reference_injection"
    )
    by_path = {ref["path"]: ref for ref in expected_refs}
    for field in ("root_audit_ref", "derivation_ref", "adapter_ref"):
        require(plan[field] == by_path[plan[field]["path"]], "audit_manifest_binding")
    derivation = bound(plan["derivation_ref"])
    audit = bound(plan["root_audit_ref"])
    require(
        audit["status"] == "passed"
        and audit["protocol_sha256"] == PROTOCOL_SHA
        and audit["manifest_sha256"] == MANIFEST_SHA
        and derivation["prospective_protocol_sha256"] == PROTOCOL_SHA
        and derivation["prospective_manifest_sha256"] == MANIFEST_SHA
        and derivation["expected_executed_wheel_sha256"] == WHEEL_SHA
        and plan["adapter_ref"]["sha256"] == audit["source_adapter_sha256"],
        "audited_derivation_binding",
    )
    expected_cases = [
        {
            **deepcopy(case),
            "expected_binding_ref": by_path[
                str(root / (case["case_id"] + "-installed-binding.json"))
            ],
        }
        for case in derivation["cases"]
    ]
    require(
        native_digest(plan["cases"]) == native_digest(expected_cases),
        "case_derivation_changed",
    )
    for ref in expected_refs:
        bound(ref, parse=False)
    require(
        Path(plan["python_executable"]).is_absolute()
        and pin(Path(plan["python_executable"]).resolve(strict=True))
        == plan["python_binary_ref"],
        "python_binary_changed",
    )
    bound(plan["wheel_ref"], parse=False)
    oracle_phase_contract(plan["oracle_phase"])
    for case in plan["cases"]:
        request = request_contract(bound(case["request_file_ref"]))
        expected = bound(case["expected_binding_ref"])
        require(
            expected["executed_wheel"] == plan["wheel_ref"]
            and expected["python_executable"] == plan["python_executable"]
            and expected["installed_site"] == OLD_SITE
            and expected["input_binding"]["request_sha256"] == native_digest(request),
            "expected_native_binding_changed",
        )
        for name, ref in case["derived_input_refs"].items():
            require(
                request[name] == {key: ref[key] for key in ("path", "sha256")},
                "request_derivative_binding",
            )
            bound(ref, parse=False)
        proof = bound(case["numeric_term_preservation_proof_ref"])
        require(
            proof["all_nonidentity_fields_exact"] is True
            and len(proof["rebound_identity_fields"]) == 5,
            "numeric_preservation_required",
        )
    return plan


def review_execution(plan_ref, review_ref):
    review = bound(review_ref)
    require(
        set(review)
        == {
            "schema_id",
            "plan_sha256",
            "driver_source_sha256",
            "reviewed_at",
            "reviewer",
            "execution_authorized",
        }
        and review["schema_id"] == "sro_native_execution_review/1"
        and review["execution_authorized"] is True
        and review["plan_sha256"] == plan_ref["sha256"]
        and review["driver_source_sha256"] == sha(Path(__file__).read_bytes())
        and type(review["reviewer"]) is str
        and review["reviewer"],
        "explicit_execution_review_required",
    )
    moment = datetime.fromisoformat(review["reviewed_at"])
    require(
        moment.utcoffset() is not None and moment < datetime.now(timezone.utc),
        "preexecution_review_required",
    )
    return review


class DispatchLedger:
    """Durable public dispatch intents; missing ends mean unknown actual work."""

    def __init__(self, path, *, deadline_monotonic_ns):
        self.path = Path(path)
        self.counts = {"force": 0, "score": 0, "graph": 0}
        self.active = []
        self.deadline_monotonic_ns = deadline_monotonic_ns

    def append(self, value):
        with self.path.open("ab") as stream:
            stream.write(
                (
                    json.dumps(
                        value, sort_keys=True, separators=(",", ":"), allow_nan=False
                    )
                    + "\n"
                ).encode()
            )
            stream.flush()
            os.fsync(stream.fileno())

    def wrap(self, original, kind):
        def observed(*args, **kwargs):
            require(
                time.monotonic_ns() < self.deadline_monotonic_ns,
                "case_deadline_exhausted",
            )
            limit = {"force": 419, "score": 2, "graph": 419}[kind]
            require(self.counts[kind] < limit, "dispatch_budget_exceeded")
            index = self.counts[kind]
            self.counts[kind] += 1
            self.active.append((kind, index))
            started = time.monotonic_ns()
            self.append(
                {
                    "event": "begin",
                    "kind": kind,
                    "index": index,
                    "at": now(),
                    "monotonic_ns": started,
                }
            )
            error = None
            try:
                return original(*args, **kwargs)
            except BaseException as exc:
                error = type(exc).__name__
                raise
            finally:
                self.append(
                    {
                        "event": "end",
                        "kind": kind,
                        "index": index,
                        "at": now(),
                        "error_type": error,
                        "inclusive_wall_ns": time.monotonic_ns() - started,
                    }
                )
                self.active.remove((kind, index))

        return observed

    def instrument(self, workflow, minimization):
        from unittest.mock import patch
        from betelgeuze_product.cpu_refinement_v1_2.chemical_features import (
            ExplicitGraphScorer,
        )

        stack = ExitStack()
        for target, name, kind in [
            (workflow.FixedReceptorEvaluator, "evaluate", "force"),
            (ExplicitGraphScorer, "score_terms", "score"),
            (minimization, "build_compact_radius_graph", "graph"),
        ]:
            stack.enter_context(
                patch.object(target, name, self.wrap(getattr(target, name), kind))
            )
        return stack


def inventory(directory):
    directory = Path(directory)
    if not directory.exists():
        return []
    refs = []
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), "retained_output_symlink")
        if path.is_file():
            refs.append(pin(path.resolve(strict=True)))
    return refs


def endpoint_document(case_id, result, native_artifact_refs):
    state = result["numerical_result"]["checkpoint"]["state"]
    require(
        state["initial"] is not None and state["current"] is not None,
        "retained_endpoints_missing",
    )
    states = []
    for label, key in [("initial", "initial"), ("last_accepted", "current")]:
        observed = state[key]
        states.append(
            {
                "label": label,
                **{
                    field: deepcopy(observed[field])
                    for field in ("coordinates", "energy", "forces", "components")
                },
            }
        )
    return {
        "schema_id": "sro_saved_numerical_endpoints/1",
        "case_id": case_id,
        "request_sha256": result["binding"]["request_sha256"],
        "binding_receipt_sha256": result["binding"]["receipt_sha256"],
        "native_artifact_refs": native_artifact_refs,
        "states": states,
    }


def supervisor_contract(supervisor_ref, plan_ref, review_ref, case_id, output):
    supervisor = bound(supervisor_ref)
    require(
        type(supervisor) is dict
        and set(supervisor)
        == {
            "schema_id",
            "case_id",
            "plan_ref",
            "execution_review_ref",
            "controller_pid",
            "started_at",
            "started_monotonic_ns",
            "deadline_monotonic_ns",
            "native_output",
        },
        "supervisor_fields",
    )
    require(
        supervisor["schema_id"] == "sro_native_case_supervisor/1"
        and supervisor["case_id"] == case_id
        and supervisor["plan_ref"] == plan_ref
        and supervisor["execution_review_ref"] == review_ref
        and supervisor["native_output"] == str(Path(output).absolute()),
        "supervisor_association",
    )
    require(
        type(supervisor["controller_pid"]) is int
        and supervisor["controller_pid"] == os.getppid()
        and supervisor["controller_pid"] > 1,
        "supervisor_parent_required",
    )
    start, deadline = (
        supervisor["started_monotonic_ns"],
        supervisor["deadline_monotonic_ns"],
    )
    require(
        type(start) is int
        and type(deadline) is int
        and deadline - start == 7200 * 1_000_000_000
        and start <= time.monotonic_ns() < deadline,
        "case_deadline_required",
    )
    started = datetime.fromisoformat(supervisor["started_at"])
    require(started.utcoffset() is not None, "supervisor_timezone")
    return supervisor


def completed_observations(result):
    require(
        result.get("execution_complete") is True
        and result["attempt"]["status"] == "success"
        and result["score_calls"] == 2,
        "native_completion_required",
    )
    for arm in ("baseline", "refined"):
        row = result["rows"][arm]
        require(
            row["succeeded"] is True
            and row["status"] == "success"
            and type(row["score"]) in (int, float)
            and math.isfinite(row["score"])
            and type(row["terms"]) is dict,
            "successful_finite_score_required",
        )
        _finite(row["terms"])
    refined = result["rows"]["refined"]
    pose = refined["pose_validity"]
    require(
        type(pose) is dict
        and set(pose)
        == {
            "valid",
            "checks",
            "evaluated_checks",
            "complete",
            "valid_within_evaluated_scope",
            "measurements",
            "blockers",
            "not_evaluated_reasons",
            "claim_safe",
        }
        and pose["complete"] is True
        and refined["validity_complete"] is True
        and set(pose["checks"]) == set(pose["evaluated_checks"]) == GEOMETRY_CHECKS
        and all(type(value) is bool for value in pose["checks"].values())
        and all(value is True for value in pose["evaluated_checks"].values()),
        "complete_authenticated_geometry_required",
    )
    current = result["numerical_result"]["checkpoint"]["state"]["current"]
    require(
        refined["coordinates_binary64_hex"]
        == current["coordinates"]
        == result["attempt"]["post_coordinates_binary64_hex"],
        "last_accepted_geometry_binding",
    )
    return result




def require_saved_geometry_guard(adapter):
    """Reject an older pinned adapter before importing or invoking native work."""
    from inspect import Parameter, signature

    guard = getattr(adapter, "forbid_physics", None)
    require(callable(guard), "saved_geometry_guard_capability_required")
    parameter = signature(guard).parameters.get("allow_saved_geometry")
    require(
        parameter is not None
        and parameter.kind is Parameter.KEYWORD_ONLY
        and parameter.default is False,
        "saved_geometry_guard_capability_required",
    )


def verify_saved_output(adapter, workflow, request, output):
    """Permit exact saved-pose geometry while denying new force/score work."""
    with adapter.forbid_physics(allow_saved_geometry=True):
        verification = workflow.verify_output(request, output)
    require(
        verification["structural_verification_passed"]
        and not verification["scoring_reexecuted"]
        and not verification["numerical_evaluation_reexecuted"],
        "read_only_semantic_verification_required",
    )
    return verification


def native_child(plan_ref, case_id, output, *, review_ref, supervisor_ref):
    """One evaluate invocation, supervised by parent; no retry or resume."""
    review = review_execution(plan_ref, review_ref)
    supervisor = supervisor_contract(
        supervisor_ref, plan_ref, review_ref, case_id, output
    )
    require(
        datetime.fromisoformat(supervisor["started_at"])
        > datetime.fromisoformat(review["reviewed_at"]),
        "supervisor_precedes_review",
    )
    plan = validate_plan(bound(plan_ref))
    require(case_id in CASE_IDS, "undeclared_case")
    require(
        sys.flags.isolated == 1
        and sys.dont_write_bytecode is True
        and str(Path(sys.executable).absolute()) == plan["python_executable"]
        and pin(Path(sys.executable).resolve(strict=True)) == plan["python_binary_ref"],
        "isolated_python_required",
    )
    require(
        not any(
            name.startswith(("betelgeuze_engine_v2", "betelgeuze_product"))
            for name in sys.modules
        ),
        "preloaded_native_package",
    )
    sys.path.insert(0, plan["installed_site"])
    adapter = load_adapter(plan["adapter_ref"])
    require_saved_geometry_guard(adapter)
    case = next(c for c in plan["cases"] if c["case_id"] == case_id)
    request = request_contract(bound(case["request_file_ref"]))
    expected = bound(case["expected_binding_ref"])
    import torch

    torch.set_num_threads(expected["input_binding"]["environment"]["torch_threads"])
    torch.set_num_interop_threads(
        expected["input_binding"]["environment"]["torch_interop_threads"]
    )
    binding = adapter.installed_input_binding(
        request, wheel_ref=plan["wheel_ref"], expected_wheel_sha256=WHEEL_SHA
    )
    require(
        binding["input_binding"] == expected["input_binding"], "fresh_binding_changed"
    )
    output = Path(output).absolute()
    output.mkdir(mode=0o700)
    preflight_ref = publish(output / "preflight.json", binding)
    publish(
        output / "native-start.json",
        {
            "schema_id": "sro_native_invocation_start/1",
            "case_id": case_id,
            "started_at": now(),
            "plan_ref": plan_ref,
            "execution_review_ref": review_ref,
            "supervisor_ref": supervisor_ref,
            "preflight_ref": preflight_ref,
        },
    )
    from betelgeuze_product.cpu_refinement_v1_3 import workflow, minimization

    ledger = DispatchLedger(
        output / "dispatch.jsonl",
        deadline_monotonic_ns=supervisor["deadline_monotonic_ns"],
    )
    envelope = None
    verification = None
    error = None
    post_error = None
    started = time.monotonic_ns()
    try:
        with ledger.instrument(workflow, minimization):
            envelope = workflow.evaluate(request, output / "run", resume=False)
        verification = verify_saved_output(adapter, workflow, request, output / "run")
        require(
            verification["result_sha256"]
            == envelope["result"]["result_sha256"]
            == envelope["invocation"]["completed_result_sha256"],
            "native_result_seal",
        )
        require(
            envelope["invocation"]["error"] is None
            and envelope["invocation"]["finalization_error"] is None
            and not envelope["invocation"]["prior_unfinished_invocations"]
            and not envelope["invocation"]["prior_unresolved_numerical_invocations"],
            "unfinished_native_invocation",
        )
    except BaseException as exc:
        error = type(exc).__name__
        raise
    finally:
        try:
            post = adapter.installed_input_binding(
                request, wheel_ref=plan["wheel_ref"], expected_wheel_sha256=WHEEL_SHA
            )
            require(
                post["input_binding"] == expected["input_binding"],
                "post_exit_native_binding_changed",
            )
            validate_plan(bound(plan_ref))
            publish(output / "post-exit-source-check.json", post)
        except BaseException as exc:
            post_error = type(exc).__name__
        publish(
            output / "native-end.json",
            {
                "schema_id": "sro_native_invocation_end/1",
                "case_id": case_id,
                "ended_at": now(),
                "error_type": error,
                "post_exit_error_type": post_error,
                "inclusive_wall_ns": time.monotonic_ns() - started,
                "dispatch_starts": ledger.counts,
                "pending_dispatches": ledger.active,
                "durations_are_inclusive_do_not_sum": True,
            },
        )
        if post_error is not None:
            raise ExecutionError("post_exit_runtime_or_inputs_changed:" + post_error)
    verification_ref = publish(output / "semantic-verification.json", verification)
    native_refs = inventory(output / "run")
    result = envelope["result"]
    try:
        completed_observations(result)
        status = "native_completed"
    except ExecutionError:
        status = "failed"
    endpoint_ref = None
    if status == "native_completed":
        endpoint_ref = publish(
            output / "endpoint-states.json",
            endpoint_document(
                case_id,
                result,
                [
                    ref
                    for ref in native_refs
                    if ref["bytes"] > 0
                    and Path(ref["path"]).suffix in (".json", ".jsonl")
                ],
            ),
        )
    lifecycle_refs = {
        name: pin(output / name)
        for name in (
            "native-start.json",
            "preflight.json",
            "native-end.json",
            "post-exit-source-check.json",
        )
    }
    require(
        time.monotonic_ns() < supervisor["deadline_monotonic_ns"],
        "case_deadline_exhausted",
    )
    return publish(
        output / "child-result.json",
        {
            "schema_id": "sro_native_child_result/1",
            "case_id": case_id,
            "status": status,
            "verification_ref": verification_ref,
            "lifecycle_refs": lifecycle_refs,
            "native_artifact_refs": native_refs,
            "endpoint_states_ref": endpoint_ref,
            "run_directory": str(output / "run"),
            "scientifically_validated": False,
            "refined_admitted": False,
        },
    )


def parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    child = sub.add_parser("child")
    child.add_argument("--plan", required=True, type=Path)
    child.add_argument("--case", required=True, choices=CASE_IDS)
    child.add_argument("--output", required=True, type=Path)
    child.add_argument("--review", required=True, type=Path)
    child.add_argument("--supervisor", required=True, type=Path)
    return parser


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "child":
        native_child(
            pin(args.plan.resolve(strict=True)),
            args.case,
            args.output,
            review_ref=pin(args.review.resolve(strict=True)),
            supervisor_ref=pin(args.supervisor.resolve(strict=True)),
        )


if __name__ == "__main__":
    main()
