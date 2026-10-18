"""Installed prepared-input bridge; numerical work stays in the Fourier workflow."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import torch

from betelgeuze_product.comparison_receipts import _json, _regular_file, MAX_JSON_BYTES
from betelgeuze_product.cpu_refinement_fourier_v1 import workflow
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, decode_coordinates, digest, require_digest,
)


REPORT_SCHEMA = "prepared_refinement_report/1.0.0"


def add_arguments(parser):
    parser.add_argument("action", choices=("preflight", "run", "resume", "verify", "report"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--pause-after-accepted-iterations", type=int)
    parser.add_argument("--output", type=Path, required=True)


def _report_sources():
    from betelgeuze_engine_v2 import standalone_cli

    return {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in (
            ("betelgeuze_product/prepared_refinement_cli.py", Path(__file__)),
            ("betelgeuze_engine_v2/standalone_cli.py", Path(standalone_cli.__file__)),
        )
    }


def report(protocol, directory):
    """Compare retained B0/B3 observations after read-only structural verification.

    A last checkpoint may precede a failed/unknown invocation. It is always
    labelled as the last observed refinement, never as an admitted final pose.
    """
    result = workflow.verify(protocol, directory)
    baseline = result["baseline"]
    records = result["invocations"]
    checkpoint = next(
        (row["checkpoint"] for row in reversed(records) if row["status"] == "observed"),
        None,
    )
    work_rows = ([] if baseline is None else [baseline]) + records
    known_force = sum(row["work"]["force_evaluation_calls"] for row in work_rows)
    known_failed = sum(row["work"]["failed_force_evaluation_calls"] for row in work_rows)
    restarts = sum(row["work"]["restart_verification_calls"] for row in work_rows)
    total_known = result["unknown_stage"] is None
    initial = None
    if baseline is not None and baseline["status"] == "observed":
        forces = decode_coordinates(baseline["forces_binary64_hex"], baseline["atom_count"])
        initial = {
            "state_role": "baseline",
            "energy_kcal_per_mol": baseline["components"]["total"],
            "components_kcal_per_mol": baseline["components"],
            "max_force_kcal_per_mol_angstrom": float(torch.linalg.vector_norm(forces, dim=-1).max()),
            "coordinates_sha256": baseline["coordinates_sha256"],
        }
    last = None
    if checkpoint is not None:
        last = {
            "state_role": "last_observed_refinement",
            "energy_kcal_per_mol": checkpoint["current_energy"],
            "components_kcal_per_mol": checkpoint["current_components"],
            "max_force_kcal_per_mol_angstrom": checkpoint["current_max_tangent_force"],
            "coordinates_sha256": checkpoint["coordinates_sha256"],
            "coordinates_binary64_hex": checkpoint["coordinates"],
            "checkpoint_sha256": checkpoint["checkpoint_sha256"],
            "accepted_iterations": checkpoint["accepted_iterations"],
        }
    minimization = protocol["solver"]["minimization"]
    iterations = minimization["max_iterations"]
    objectives = 1 + iterations * (minimization["max_backtracks"] + 1)
    sources = _report_sources()
    document = {
        "schema_version": REPORT_SCHEMA,
        "binding": result["binding"],
        "candidate_id": result["candidate_id"],
        "evidence_kind": result["evidence_kind"],
        "requested_candidates": result["requested_candidates"],
        "execution_status": result["status"],
        "refinement_status": result["refinement_status"],
        "numerical_convergence": result["converged"],
        "structural_consistency_valid": True,
        "verification_scope": result["verification_scope"],
        "chemical_validity": None,
        "pose_accuracy": None,
        "pose_selection_admitted": False,
        "boundary": dict(result["boundary"]),
        "unknown_stage": result["unknown_stage"],
        "force_semantics": "unconstrained_raw_negative_coordinate_gradient_no_restraint_or_augmentation",
        "units": {"energy": "kcal/mol", "force": "kcal/mol/angstrom", "coordinates": "angstrom"},
        "states": {"baseline": initial, "last_observed_refinement": last},
        "comparison": {
            "energy_delta_kcal_per_mol": result["energy_delta_kcal_per_mol"],
            "max_force_delta_kcal_per_mol_angstrom": None if initial is None or last is None
            else last["max_force_kcal_per_mol_angstrom"] - initial["max_force_kcal_per_mol_angstrom"],
            "scope": "baseline_vs_last_observed_refinement_same_declared_model",
        },
        "work": {
            "known_force_evaluation_calls": known_force,
            "total_force_evaluation_calls": known_force if total_known else None,
            "known_failed_force_evaluation_calls": known_failed,
            "restart_verification_calls": restarts,
            "total_work_known": total_known,
            "unknown_work_reissued": False,
            "report_force_evaluation_calls": 0,
            "known_numerical_invocation_wall_seconds": sum(row["wall_seconds"] for row in work_rows),
            "timing_scope": "retained_numerical_invocations_excludes_install_preparation_and_report",
        },
        "limits": {
            "cpu_threads": 1,
            "optimizer_objective_attempts_upper_bound": objectives,
            "baseline_force_calls_upper_bound": 1,
            "restart_force_calls_upper_bound": iterations,
            "total_force_calls_upper_bound_with_all_known_restarts": 1 + objectives + iterations,
            "wall_clock_limit_enforced_by_cli": False,
        },
        "report_sources": sources,
        "report_source_sha256": digest(sources),
    }
    return {**document, "report_sha256": digest(document)}


def dispatch(args):
    # Reject invalid actions and existing/aliased output before numerical work.
    # No overwrite option is admitted. Final publication also uses the existing
    # descriptor-anchored no-replace writer in standalone_cli.
    if os.path.lexists(args.output):
        raise ResearchError("prepared refinement output already exists")
    from betelgeuze_engine_v2.cli import _open_parent_directory

    # Require an existing, descriptor-checked parent before expending work.
    # The final no-replace publication rechecks the path and leaf independently.
    parent, _ = _open_parent_directory(args.output, create=False)
    os.close(parent)
    if args.run_dir is not None:
        output = args.output.resolve()
        run_dir = args.run_dir.resolve()
        if output == run_dir or run_dir in output.parents:
            raise ResearchError("report output must be outside the immutable run directory")
    if args.action == "preflight":
        if args.run_dir is not None or args.pause_after_accepted_iterations is not None:
            raise ResearchError("preflight has no run state")
    elif args.run_dir is None:
        raise ResearchError("run directory required")
    if args.action in {"verify", "report"} and args.pause_after_accepted_iterations is not None:
        raise ResearchError("verify and report are read only")
    require_digest(args.expected_protocol_sha256)
    raw = _regular_file(args.protocol, MAX_JSON_BYTES)
    if hashlib.sha256(raw).hexdigest() != args.expected_protocol_sha256:
        raise ResearchError("protocol bytes changed")
    protocol = _json(raw)
    torch.set_num_threads(1)
    # Validate the entire model/input binding before run() creates its directory.
    frozen, _ = workflow.freeze(protocol)
    if args.action == "preflight":
        return {
            "status": "prepared", "binding": frozen["binding"],
            "force_calls": 0, "boundary": dict(workflow.BOUNDARY),
        }, 0
    if args.action == "report":
        document = report(protocol, args.run_dir)
        return document, 0 if document["execution_status"] in {"complete", "paused"} else 2
    if args.action == "verify":
        document = workflow.verify(protocol, args.run_dir)
    else:
        document = workflow.run(
            protocol, args.run_dir, resume=args.action == "resume",
            pause_after_accepted_iterations=args.pause_after_accepted_iterations,
        )
    return document, 0 if document["status"] in {"complete", "paused"} else 2
