"""Single-candidate opt-in execution receipts with known checkpoint continuation.

Unfinished intents retain unknown work and cannot be automatically reissued.
This is not the synthetic four-arm protocol or a crash-safe per-force journal.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import torch
from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_engine_v2.molecular.serialization import (
    all_atom_system_from_canonical_json,
)
from betelgeuze_product.comparison_receipts import (
    _regular_file,
    _private_dir,
    _json,
    MAX_JSON_BYTES,
)
from betelgeuze_product.installed_synthetic_comparison import (
    _publish,
    _committed,
    _lock,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError,
    digest,
    coordinates_hex,
    decode_coordinates,
    environment,
    exact_fields,
    require_digest,
    finite,
    integer,
    canonical,
)
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
    components_document,
    validate_components,
)
from betelgeuze_product.cpu_refinement_v1_2.minimization import SolverConfig
from betelgeuze_product.cpu_refinement_v1_2.work import WorkMeter
from betelgeuze_product.cpu_refinement_v1_2.evidence_contracts import verify_work
from .parameters import FourierParameters
from .evaluation import (
    FourierCrossParameters,
    FourierEnvironment,
    FourierFixedEvaluator,
)
from .minimization import implementation_sources, require_checkpoint, minimize_fourier

PROTOCOL = "prepared_fourier_development_protocol/1.0.0"
BOUNDARY = {
    "source_authenticated": False,
    "scientifically_validated": False,
    "original_simulation_hamiltonian_reproduced": False,
    "training_admitted": False,
    "product_ranking_enabled": False,
    "independent_measurement_denominator": None,
}
REFS = ("ligand", "receptor", "parameters", "cross", "source_evidence")


def _require(condition, reason):
    if not condition:
        raise ResearchError(reason)


def _bound(ref):
    exact_fields(ref, {"path", "sha256"})
    require_digest(ref["sha256"])
    _require(type(ref["path"]) is str, "absolute bound input path required")
    path = Path(ref["path"])
    _require(
        path.is_absolute() and str(path.resolve(strict=True)) == ref["path"],
        "canonical bound input path required",
    )
    raw = _regular_file(path, MAX_JSON_BYTES)
    _require(
        hashlib.sha256(raw).hexdigest() == ref["sha256"], "bound input bytes changed"
    )
    return raw


def _load(protocol):
    exact_fields(
        protocol,
        {
            "schema_version",
            "candidate_id",
            "evidence_kind",
            *REFS,
            "solver",
            "initial_coordinates_sha256",
            "boundary",
        },
    )
    _require(
        protocol["schema_version"] == PROTOCOL,
        "explicit Fourier development protocol required",
    )
    _require(
        type(protocol["candidate_id"]) is str
        and 1 <= len(protocol["candidate_id"]) <= 128,
        "bounded candidate ID required",
    )
    _require(
        protocol["evidence_kind"] in {"prepared_real_development", "synthetic_control"},
        "explicit evidence kind required",
    )
    _require(
        canonical(protocol["boundary"]) == canonical(BOUNDARY),
        "authority promotion forbidden",
    )
    require_digest(protocol["initial_coordinates_sha256"])
    raw = {name: _bound(protocol[name]) for name in REFS}
    evidence = _json(raw["source_evidence"])
    exact_fields(
        evidence,
        {
            "schema_version",
            "evidence_kind",
            "source_files",
            "source_authenticated",
            "original_simulation_hamiltonian_reproduced",
        },
    )
    _require(
        evidence["schema_version"] == "declared_prepared_source_evidence/1.0.0"
        and evidence["evidence_kind"] == protocol["evidence_kind"]
        and evidence["source_authenticated"] is False
        and evidence["original_simulation_hamiltonian_reproduced"] is False,
        "source evidence boundary mismatch",
    )
    refs = evidence["source_files"]
    _require(
        type(refs) is list
        and len(refs) <= 32
        and (refs or protocol["evidence_kind"] == "synthetic_control"),
        "bounded original source references required",
    )
    for ref in refs:
        _bound(ref)
    ligand = all_atom_system_from_canonical_json(raw["ligand"])
    receptor = all_atom_system_from_canonical_json(raw["receptor"])
    parameters = FourierParameters.from_dict(_json(raw["parameters"]))
    cross = FourierCrossParameters.from_dict(_json(raw["cross"]))
    fixed = FourierEnvironment(receptor, cross)
    fixed.validate_ligand(ligand, parameters)
    config = SolverConfig.from_dict(protocol["solver"])
    _require(
        config.minimization.max_iterations <= 4
        and config.minimization.max_backtracks <= 3,
        "bounded development solver limits required",
    )
    _require(torch.get_num_threads() == 1, "one CPU thread required")
    _require(
        digest(coordinates_hex(ligand.coordinates))
        == protocol["initial_coordinates_sha256"],
        "exact initial coordinates changed",
    )
    return ligand, parameters, config, fixed


def freeze(protocol):
    ligand, parameters, config, fixed = _load(protocol)
    sources = implementation_sources()
    frozen = {
        "schema_version": "prepared_fourier_frozen/1.0.0",
        "protocol": protocol,
        "input_system_sha256": canonical_system_sha256(ligand),
        "input_atom_count": ligand.atom_count,
        "evaluator": FourierFixedEvaluator(parameters, fixed).identity(),
        "implementation_sources": sources,
        "implementation_sha256": digest(sources),
        "environment": environment(),
    }
    return {"payload": frozen, "binding": digest(frozen)}, (
        ligand,
        parameters,
        config,
        fixed,
    )


def _work(value):
    exact_fields(
        value,
        {
            "force_evaluation_calls",
            "failed_force_evaluation_calls",
            "restart_verification_calls",
            "constraint_projection_calls",
            "work",
        },
    )
    n = integer(value["force_evaluation_calls"], 0, 17)
    integer(value["failed_force_evaluation_calls"], 0, n)
    integer(value["restart_verification_calls"], 0, 1)
    integer(value["constraint_projection_calls"], 0, 18)
    rows = verify_work(value["work"])
    for scalar, stage in (
        ("restart_verification_calls", "restart.verify"),
        ("constraint_projection_calls", "constraint.project"),
    ):
        _require(
            value[scalar] == rows.get(stage, {}).get("calls", 0),
            "work scalar/stage mismatch",
        )
    force = rows.get("force.evaluate", {"calls": 0, "failed": 0})
    _require(
        force["calls"] == n
        and force["failed"] == value["failed_force_evaluation_calls"],
        "force counter mismatch",
    )


def _read_state(directory, frozen):
    binding = frozen["binding"]
    payload = frozen["payload"]
    status = "not_started"
    baseline = None
    records = []
    previous = None
    unknown = None
    if (directory / "baseline-intent.json").exists():
        intent = _committed(directory / "baseline-intent.json")
        _require(
            intent == {"binding": binding, "stage": "B0", "force_calls_reserved": 1},
            "baseline intent mismatch",
        )
        if not (directory / "baseline.json").exists():
            unknown = "B0"
        else:
            baseline = _committed(directory / "baseline.json")
            _require(baseline["binding"] == binding, "baseline binding mismatch")
            exact_fields(
                baseline,
                {"binding", "status", "work", "wall_seconds"}
                | (
                    {
                        "coordinates_sha256",
                        "atom_count",
                        "components",
                        "forces_binary64_hex",
                    }
                    if baseline["status"] == "observed"
                    else {"exception_class"}
                ),
            )
            finite(baseline["wall_seconds"], nonnegative=True)
            _work(baseline["work"])
            if baseline["status"] == "observed":
                _require(
                    baseline["work"]["force_evaluation_calls"] == 1
                    and baseline["work"]["failed_force_evaluation_calls"] == 0,
                    "baseline work mismatch",
                )
                _require(
                    baseline["coordinates_sha256"]
                    == payload["protocol"]["initial_coordinates_sha256"],
                    "baseline coordinates mismatch",
                )
                validate_components(
                    baseline["components"], baseline["components"]["total"]
                )
                integer(baseline["atom_count"], 1, 256)
                _require(
                    baseline["atom_count"] == payload["input_atom_count"],
                    "baseline atom count mismatch",
                )
                decode_coordinates(
                    baseline["forces_binary64_hex"], baseline["atom_count"]
                )
                status = "baseline_saved"
            else:
                _require(baseline["status"] == "failed", "unknown baseline status")
                status = "failed"
    elif (directory / "baseline.json").exists():
        raise ResearchError("baseline without reserved intent")
    intents = sorted(directory.glob("invocation-*-intent.json"))
    _require(
        len(intents)
        <= payload["protocol"]["solver"]["minimization"]["max_iterations"] + 1,
        "invocation count exceeds progress bound",
    )
    for index, path in enumerate(intents):
        _require(
            path.name == f"invocation-{index:03d}-intent.json",
            "noncontiguous invocation sequence",
        )
        _require(
            baseline is not None
            and baseline["status"] == "observed"
            and unknown is None
            and status not in {"failed", "complete"},
            "invocation after unavailable or terminal state",
        )
        intent = _committed(path)
        pause = intent.get("pause_after_accepted_iterations")
        if pause is not None:
            integer(
                pause,
                0,
                payload["protocol"]["solver"]["minimization"]["max_iterations"],
            )
            _require(
                previous is None or pause > previous["accepted_iterations"],
                "resume cannot request previously observed progress",
            )
        expected = {
            "binding": binding,
            "index": index,
            "previous_checkpoint_sha256": None
            if previous is None
            else previous["checkpoint_sha256"],
            "pause_after_accepted_iterations": pause,
        }
        _require(intent == expected, "invocation reservation mismatch")
        result_path = directory / f"invocation-{index:03d}.json"
        if not result_path.exists():
            _require(index == len(intents) - 1, "invocation after unknown work")
            unknown = f"B3_invocation_{index}"
            break
        record = _committed(result_path)
        records.append(record)
        _require(
            record["binding"] == binding and record["index"] == index,
            "invocation result identity mismatch",
        )
        exact_fields(
            record,
            {"binding", "index", "status", "work", "wall_seconds"}
            | (
                {"checkpoint"}
                if record["status"] == "observed"
                else {"exception_class"}
            ),
        )
        finite(record["wall_seconds"], nonnegative=True)
        _work(record["work"])
        if record["status"] == "failed":
            status = "failed"
            continue
        _require(record["status"] == "observed", "unknown invocation result status")
        cp = require_checkpoint(record["checkpoint"]).to_dict()
        for name, wanted in (
            ("source_system_sha256", payload["input_system_sha256"]),
            ("atom_count", payload["input_atom_count"]),
            ("evaluator", payload["evaluator"]),
            ("config", payload["protocol"]["solver"]),
            ("implementation_sha256", payload["implementation_sha256"]),
            ("environment", payload["environment"]),
        ):
            _require(
                canonical(cp[name]) == canonical(wanted),
                "checkpoint frozen identity mismatch",
            )
        _require(
            cp["observations"][0]["coordinates_sha256"]
            == payload["protocol"]["initial_coordinates_sha256"],
            "optimizer changed initial pose",
        )
        _require(
            cp["initial_components"] == baseline["components"],
            "B0/B3 initial component mismatch",
        )
        baseline_force = decode_coordinates(
            baseline["forces_binary64_hex"], baseline["atom_count"]
        )
        _require(
            float(torch.linalg.vector_norm(baseline_force[0], dim=-1).max()).hex()
            == float(cp["initial_max_tangent_force"]).hex(),
            "B0/B3 initial force norm mismatch",
        )
        if previous is not None:
            _require(
                cp["observations"][: len(previous["observations"])]
                == previous["observations"],
                "resume changed numerical history",
            )
            _require(
                record["work"]["restart_verification_calls"] == 1,
                "resume verification work missing",
            )
        else:
            _require(
                record["work"]["restart_verification_calls"] == 0,
                "initial invocation claims restart",
            )
        new_rows = cp["observations"][
            0 if previous is None else len(previous["observations"]) :
        ]
        restart = int(previous is not None)
        expected_forces = restart + sum(
            r["outcome"] not in {"rejected_projection", "rejected_displacement"}
            for r in new_rows
        )
        expected_projections = restart + len(new_rows)
        _require(
            record["work"]["force_evaluation_calls"] == expected_forces,
            "observed force work differs from checkpoint extension",
        )
        _require(
            record["work"]["constraint_projection_calls"] == expected_projections,
            "projection work differs from checkpoint extension",
        )
        stages = record["work"]["work"]["stages"]
        _require(
            stages.get("geometry.build", {}).get("completed", 0) == expected_forces,
            "geometry/force work mismatch",
        )
        _require(
            stages.get("force.project", {}).get("calls", 0)
            == stages.get("force.evaluate", {}).get("completed", 0),
            "force/tangent work mismatch",
        )
        if restart:
            _require(
                stages.get("restart.verify", {}).get("completed", 0) == 1,
                "restart verification did not complete",
            )
        if cp["status"] == "checkpointed":
            _require(
                pause is not None and cp["accepted_iterations"] == pause,
                "paused checkpoint does not match reserved progress",
            )
        previous = cp
        status = "paused" if cp["status"] == "checkpointed" else "complete"
    result_paths = list(directory.glob("invocation-*.json"))
    _require(
        len(result_paths) == len(intents) + len(records), "unreserved invocation result"
    )
    if unknown is not None:
        status = "interrupted_unknown"
    return {
        "status": status,
        "baseline": baseline,
        "invocations": records,
        "last_checkpoint": previous,
        "unknown_stage": unknown,
    }


def _summary(frozen, state):
    cp = state["last_checkpoint"]
    return {
        "schema_version": "prepared_fourier_development_result/1.0.0",
        "binding": frozen["binding"],
        "candidate_id": frozen["payload"]["protocol"]["candidate_id"],
        "evidence_kind": frozen["payload"]["protocol"]["evidence_kind"],
        "requested_candidates": 1,
        "status": state["status"],
        "baseline": state["baseline"],
        "invocations": state["invocations"],
        "unknown_stage": state["unknown_stage"],
        "refinement_status": None if cp is None else cp["status"],
        "converged": False if cp is None else cp["status"] == "converged",
        "final_checkpoint_sha256": None if cp is None else cp["checkpoint_sha256"],
        "energy_delta_kcal_per_mol": None
        if cp is None
        else cp["current_energy"] - cp["initial_energy"],
        "baseline_preserved": state["baseline"] is not None
        and state["baseline"]["status"] == "observed",
        "pose_score": None,
        "pose_selection_admitted": False,
        "unknown_work_reissued": False,
        "boundary": BOUNDARY,
        "verification_scope": "bound_bytes_structural_receipts_no_force_reexecution",
    }


def verify(protocol, directory):
    directory = Path(directory)
    _private_dir(directory)
    lock = _lock(directory / "run.lock", create=False, shared=True)
    try:
        frozen, _ = freeze(protocol)
        _require(
            _committed(directory / "frozen.json") == frozen,
            "frozen input/source/runtime drift",
        )
        state = _read_state(directory, frozen)
        result = _summary(frozen, state)
        if (directory / "completion.json").exists():
            _require(
                state["status"] in {"complete", "failed"},
                "completion cannot accompany nonterminal state",
            )
            _require(
                _committed(directory / "completion.json") == result,
                "completion differs from retained observations",
            )
        return result
    finally:
        os.close(lock)


def run(protocol, directory, *, resume=False, pause_after_accepted_iterations=None):
    directory = Path(directory)
    if not resume:
        directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    _private_dir(directory)
    lock = _lock(directory / "run.lock", create=not resume)
    try:
        frozen, loaded = freeze(protocol)
        ligand, parameters, config, fixed = loaded
        if resume:
            _require(
                _committed(directory / "frozen.json") == frozen,
                "frozen input/source/runtime drift",
            )
        else:
            _publish(directory / "frozen.json", frozen)
        state = _read_state(directory, frozen)
        if (directory / "completion.json").exists():
            _require(
                state["status"] in {"complete", "failed"},
                "completion cannot accompany nonterminal state",
            )
            _require(
                _committed(directory / "completion.json") == _summary(frozen, state),
                "completion mismatch",
            )
        if state["status"] in {"complete", "failed", "interrupted_unknown"}:
            result = _summary(frozen, state)
            if (directory / "completion.json").exists():
                _require(
                    _committed(directory / "completion.json") == result,
                    "completion mismatch",
                )
            elif state["status"] != "interrupted_unknown":
                _publish(directory / "completion.json", result)
            return result
        if pause_after_accepted_iterations is not None:
            integer(
                pause_after_accepted_iterations, 0, config.minimization.max_iterations
            )
            _require(
                state["last_checkpoint"] is None
                or pause_after_accepted_iterations
                > state["last_checkpoint"]["accepted_iterations"],
                "resume must advance beyond saved pause",
            )
        binding = frozen["binding"]
        if state["baseline"] is None:
            _publish(
                directory / "baseline-intent.json",
                {"binding": binding, "stage": "B0", "force_calls_reserved": 1},
            )
            meter = WorkMeter()
            started = time.perf_counter()
            baseline = {"binding": binding, "status": "failed"}
            try:
                with meter.measure("geometry.build"):
                    graph = build_compact_radius_graph(
                        ligand.coordinates,
                        RadiusGraphConfig(
                            cutoff_angstrom=parameters.cutoff_angstrom,
                            max_neighbors=config.minimization.max_neighbors,
                            max_atoms_per_cell=config.minimization.max_atoms_per_cell,
                        ),
                    )
                with meter.measure("force.evaluate"):
                    evaluation = FourierFixedEvaluator(parameters, fixed).evaluate(
                        ligand, graph
                    )
                baseline.update(
                    status="observed",
                    coordinates_sha256=protocol["initial_coordinates_sha256"],
                    atom_count=ligand.atom_count,
                    components=components_document(evaluation),
                    forces_binary64_hex=coordinates_hex(evaluation.term.forces),
                )
            except Exception as exc:
                baseline["exception_class"] = type(exc).__name__
            baseline.update(
                work=meter.numerical_calls(), wall_seconds=time.perf_counter() - started
            )
            _publish(directory / "baseline.json", baseline)
            state = _read_state(directory, frozen)
        if state["status"] != "failed":
            index = len(state["invocations"])
            previous = state["last_checkpoint"]
            _publish(
                directory / f"invocation-{index:03d}-intent.json",
                {
                    "binding": binding,
                    "index": index,
                    "previous_checkpoint_sha256": None
                    if previous is None
                    else previous["checkpoint_sha256"],
                    "pause_after_accepted_iterations": pause_after_accepted_iterations,
                },
            )
            meter = WorkMeter()
            started = time.perf_counter()
            record = {"binding": binding, "index": index, "status": "failed"}
            try:
                minimized = minimize_fourier(
                    ligand,
                    parameters,
                    config,
                    fixed_environment=fixed,
                    checkpoint=previous,
                    pause_after_accepted_iterations=pause_after_accepted_iterations,
                    meter=meter,
                )
                record.update(
                    status="observed", checkpoint=minimized.checkpoint.to_dict()
                )
            except Exception as exc:
                record["exception_class"] = type(exc).__name__
            record.update(
                work=meter.numerical_calls(), wall_seconds=time.perf_counter() - started
            )
            _publish(directory / f"invocation-{index:03d}.json", record)
        fresh, _ = freeze(protocol)
        _require(fresh == frozen, "input/source/runtime changed during run")
        state = _read_state(directory, frozen)
        result = _summary(frozen, state)
        if state["status"] in {"complete", "failed"}:
            _publish(directory / "completion.json", result)
        return result
    finally:
        os.close(lock)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "run", "resume", "verify"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--pause-after-accepted-iterations", type=int)
    args = parser.parse_args(argv)
    torch.set_num_threads(1)
    require_digest(args.expected_protocol_sha256)
    raw = _regular_file(args.protocol, MAX_JSON_BYTES)
    _require(
        hashlib.sha256(raw).hexdigest() == args.expected_protocol_sha256,
        "protocol bytes changed",
    )
    protocol = _json(raw)
    if args.action == "preflight":
        _require(
            args.run_dir is None and args.pause_after_accepted_iterations is None,
            "preflight has no run state",
        )
        frozen, _ = freeze(protocol)
        result = {
            "status": "prepared",
            "binding": frozen["binding"],
            "force_calls": 0,
            "boundary": BOUNDARY,
        }
    else:
        _require(args.run_dir is not None, "run directory required")
        if args.action == "verify":
            _require(
                args.pause_after_accepted_iterations is None, "verify is read only"
            )
            result = verify(protocol, args.run_dir)
        else:
            result = run(
                protocol,
                args.run_dir,
                resume=args.action == "resume",
                pause_after_accepted_iterations=args.pause_after_accepted_iterations,
            )
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result["status"] in {"prepared", "complete", "paused"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
