"""Supported opt-in long-budget prepared Cartesian development route.

Frozen 40/80/160-step controls use the existing durable executor. Restart
verification has an explicit separate cumulative allowance. Historical profiles,
receipts, defaults and physics are unchanged; shape penalties are not admitted.
Budget exhaustion is not convergence or scientific qualification.
"""

import argparse
import hashlib
import json
from pathlib import Path

import torch

from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
from betelgeuze_product.comparison_receipts import MAX_JSON_BYTES, _json, _regular_file
from betelgeuze_product.cpu_prepared_cartesian_budget_v3 import preparation as prepared_helpers
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import (
    FourierCrossParameters, FourierEnvironment, FourierFixedEvaluator,
)
from betelgeuze_product.cpu_refinement_fourier_v1.parameters import FourierParameters
from betelgeuze_product.cpu_refinement_fourier_v1.workflow import BOUNDARY, REFS, _bound
from betelgeuze_product.cpu_refinement_linear_angle_v1 import cartesian as linear_angle
from betelgeuze_product.cpu_refinement_linear_angle_v1.evaluation import (
    LinearAngleEnvironment, LinearAngleFixedEvaluator,
)
from betelgeuze_product.cpu_refinement_linear_angle_v1.parameters import LinearAngleParameters
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import require_system
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, canonical, coordinates_hex, digest, environment, exact_fields, require_digest,
)
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig

PROFILE_ID = "prepared_cartesian_step_budget/3.0.0"
PROTOCOL = "prepared_cartesian_step_budget_protocol/3.0.0"
BINDING_SCHEMA = "prepared_cartesian_step_budget_binding/3.0.0"
RESULT_SCHEMA = "prepared_cartesian_step_budget_result/3.0.0"
MODELS = ("fourier", "linear_angle")
ACCEPTED_STEP_BUDGETS = (40, 80, 160)


def _require(condition, message):
    if not condition:
        raise ResearchError(message)


def budget_config(algorithm, accepted_steps, *, restart_verifications):
    """Frozen comparison controls; one initial plus four trials per step."""
    _require(type(accepted_steps) is int and accepted_steps in ACCEPTED_STEP_BUDGETS,
             "explicit 40/80/160 accepted-step budget required")
    _require(type(restart_verifications) is int and restart_verifications in (0, 1),
             "explicit zero/one restart-verification allowance required")
    return SolverConfig(algorithm=algorithm, max_accepted_steps=accepted_steps,
                        max_objective_attempts=1 + 4 * accepted_steps,
                        max_backtracks=3, max_restart_verifications=restart_verifications,
                        initial_step_size=.001, maximum_atom_displacement=.05,
                        force_tolerance=.001, armijo_constant=.0001,
                        backtrack_factor=.5, history_size=10,
                        curvature_relative_threshold=1.e-12,
                        max_neighbors=256, max_atoms_per_cell=256)


def implementation_sources():
    """Bind this adapter, reused preparation checks, and both numerical closures."""
    result = linear_angle.implementation_sources()
    for path in sorted(Path(__file__).resolve().parent.glob("*.py")):
        result["betelgeuze_product/cpu_prepared_cartesian_budget_v3/" + path.name] = (
            hashlib.sha256(path.read_bytes()).hexdigest())
    return result


def _context(ligand, parameters, config, fixed, binding):
    require_system(ligand, 256)
    _require(type(binding) is dict, "explicit step-budget input identity required")
    exact_fields(binding, {"profile_id", "model", "accepted_step_budget", "restart_verifications", "candidate_id",
                           "prepared_protocol_sha256", "initial_coordinates_sha256"})
    _require(binding["profile_id"] == PROFILE_ID, "step-budget profile identity mismatch")
    _require(type(config) is SolverConfig, "explicit Cartesian solver required")
    expected = budget_config(config.algorithm, binding["accepted_step_budget"],
                             restart_verifications=binding["restart_verifications"])
    _require(canonical(config.to_dict()) == canonical(expected.to_dict()),
             "frozen step-budget solver controls differ")
    model = binding["model"]
    if model == "fourier":
        _require(type(parameters) is FourierParameters and type(fixed) is FourierEnvironment,
                 "explicit Fourier model/environment required")
        evaluator = FourierFixedEvaluator(parameters, fixed)
    elif model == "linear_angle":
        _require(type(parameters) is LinearAngleParameters and type(fixed) is LinearAngleEnvironment,
                 "explicit linear-angle model/environment required")
        evaluator = LinearAngleFixedEvaluator(parameters, fixed)
    else:
        raise ResearchError("explicit prepared model required")
    _require(not parameters.constraints, "step-budget profile is unconstrained only")
    _require(torch.get_num_threads() == 1, "one CPU thread required")
    _require(type(binding["candidate_id"]) is str and 1 <= len(binding["candidate_id"]) <= 128,
             "bounded candidate ID required")
    require_digest(binding["prepared_protocol_sha256"])
    require_digest(binding["initial_coordinates_sha256"])
    _require(binding["initial_coordinates_sha256"] == digest(coordinates_hex(ligand.coordinates)),
             "exact initial coordinates changed")
    fixed.validate_ligand(ligand, parameters)
    identity = {
        "schema_id": BINDING_SCHEMA, "source_system_sha256": canonical_system_sha256(ligand),
        "evaluator": evaluator.identity(), "config": config.to_dict(),
        "implementation_sha256": digest(implementation_sources()),
        "environment": environment(), "external_binding": binding,
    }
    return evaluator, json.loads(canonical(identity))


def _load(protocol, protocol_sha256, model, accepted_steps, restart_verifications):
    exact_fields(protocol, {
        "schema_version", "profile_id", "model", "accepted_step_budget", "restart_verifications", "candidate_id",
        "evidence_kind", *REFS, "solver", "initial_coordinates_sha256",
        "implementation_sha256", "boundary",
    })
    _require(protocol["schema_version"] == PROTOCOL and protocol["profile_id"] == PROFILE_ID,
             "explicit step-budget protocol required")
    _require(type(model) is str and model in MODELS and protocol["model"] == model,
             "explicit model selection differs from protocol")
    _require(type(accepted_steps) is int and accepted_steps in ACCEPTED_STEP_BUDGETS
             and type(protocol["accepted_step_budget"]) is int
             and protocol["accepted_step_budget"] == accepted_steps,
             "explicit accepted-step budget differs from protocol")
    _require(type(restart_verifications) is int and restart_verifications in (0, 1)
             and type(protocol["restart_verifications"]) is int
             and protocol["restart_verifications"] == restart_verifications,
             "explicit restart allowance differs from protocol")
    _require(protocol["evidence_kind"] in {"prepared_real_development", "synthetic_control"},
             "explicit evidence kind required")
    _require(canonical(protocol["boundary"]) == canonical(BOUNDARY), "authority promotion forbidden")
    require_digest(protocol_sha256)
    require_digest(protocol["implementation_sha256"])
    _require(protocol["implementation_sha256"] == digest(implementation_sources()),
             "step-budget implementation changed")
    raw = {name: _bound(protocol[name]) for name in REFS}
    prepared_helpers._source_evidence(raw["source_evidence"], protocol["evidence_kind"])
    ligand = all_atom_system_from_canonical_json(raw["ligand"])
    receptor = all_atom_system_from_canonical_json(raw["receptor"])
    cross = FourierCrossParameters.from_dict(_json(raw["cross"]))
    if model == "fourier":
        parameters = FourierParameters.from_dict(_json(raw["parameters"]))
        fixed = FourierEnvironment(receptor, cross)
    else:
        parameters = LinearAngleParameters.from_dict(_json(raw["parameters"]))
        fixed = LinearAngleEnvironment(receptor, cross)
    config = SolverConfig.from_dict(protocol["solver"])
    binding = {name: protocol[name] for name in
               ("profile_id", "model", "accepted_step_budget", "restart_verifications", "candidate_id",
                "initial_coordinates_sha256")}
    binding["prepared_protocol_sha256"] = protocol_sha256
    evaluator, identity = _context(ligand, parameters, config, fixed, binding)
    return ligand, parameters, config, fixed, evaluator, identity


def _read(protocol_path, expected_sha256, model, accepted_steps, restart_verifications):
    require_digest(expected_sha256)
    raw = _regular_file(Path(protocol_path), MAX_JSON_BYTES)
    _require(hashlib.sha256(raw).hexdigest() == expected_sha256, "protocol bytes changed")
    protocol = _json(raw)
    return protocol, _load(protocol, expected_sha256, model, accepted_steps, restart_verifications)


def _preflight(protocol, protocol_sha256, loaded):
    ligand, parameters, config, fixed, _, _ = loaded
    return {
        "schema_id": "prepared_cartesian_step_budget_preflight/3.0.0",
        "profile_id": PROFILE_ID, "status": "admitted_for_bounded_development_execution",
        "prepared_protocol_sha256": protocol_sha256, "candidate_id": protocol["candidate_id"],
        "model": protocol["model"], "accepted_step_budget": protocol["accepted_step_budget"],
        "restart_verifications": protocol["restart_verifications"],
        "shape_penalty_enabled": False,
        "algorithm": config.algorithm, "evidence_kind": protocol["evidence_kind"],
        "ligand_atom_count": ligand.atom_count, "receptor_atom_count": fixed.receptor.atom_count,
        "ligand_system_sha256": canonical_system_sha256(ligand),
        "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "coordinate_frame_id": fixed.cross.coordinate_frame_id,
        "coordinate_frame_authenticity_verified": False, "original_source_hashes_verified": True,
        "exact_prepared_charge_rows_verified": True,
        "geometry": prepared_helpers._geometry(ligand, parameters, config, protocol["model"]),
        "implementation_sha256": protocol["implementation_sha256"],
        "solver": config.to_dict(), "boundary": dict(BOUNDARY),
    }


def preflight(protocol_path, expected_sha256, *, model, accepted_steps, restart_verifications):
    """Validate prepared sources/topology/geometry without energy or force work."""
    protocol, loaded = _read(protocol_path, expected_sha256, model, accepted_steps, restart_verifications)
    return _preflight(protocol, expected_sha256, loaded)


def prepare(*, model, accepted_steps, restart_verifications, candidate_id, evidence_kind, ligand, receptor,
            parameters, cross, source_evidence, solver, output):
    """Seal a new independent start under a predeclared model and step budget."""
    _require(type(model) is str and model in MODELS, "explicit prepared model required")
    files = dict(ligand=ligand, receptor=receptor, parameters=parameters,
                 cross=cross, source_evidence=source_evidence)
    refs = {}
    for name, value in files.items():
        path = Path(value).resolve(strict=True)
        refs[name] = {"path": str(path), "sha256": hashlib.sha256(
            _regular_file(path, MAX_JSON_BYTES)).hexdigest()}
    system = all_atom_system_from_canonical_json(_bound(refs["ligand"]))
    document = {
        "schema_version": PROTOCOL, "profile_id": PROFILE_ID, "model": model,
        "accepted_step_budget": accepted_steps, "restart_verifications": restart_verifications,
        "candidate_id": candidate_id,
        "evidence_kind": evidence_kind, **refs,
        "solver": solver.to_dict() if type(solver) is SolverConfig else solver,
        "initial_coordinates_sha256": digest(coordinates_hex(system.coordinates)),
        "implementation_sha256": digest(implementation_sources()), "boundary": dict(BOUNDARY),
    }
    raw = (canonical(document) + "\n").encode()
    sha256 = hashlib.sha256(raw).hexdigest()
    receipt = _preflight(document, sha256, _load(document, sha256, model, accepted_steps, restart_verifications))
    path = Path(output).absolute()
    with path.open("xb") as stream:
        stream.write(raw)
    return {"protocol_path": str(path), "protocol_sha256": sha256, "preflight": receipt}


def run(protocol_path, expected_sha256, run_dir, *, model, accepted_steps, restart_verifications,
        resume=False, pause_after_objective_attempts=None):
    """Run or safely resume this exact profile; pending unknown work is rejected."""
    _, loaded = _read(protocol_path, expected_sha256, model, accepted_steps, restart_verifications)
    ligand, _, config, fixed, evaluator, identity = loaded
    result = execution._minimize_profile(
        ligand, config, evaluator=evaluator, identity=identity, run_dir=run_dir,
        implementation_sources=implementation_sources, result_schema=RESULT_SCHEMA,
        model_guard=fixed.assert_intact, resume=resume,
        pause_after_objective_attempts=pause_after_objective_attempts,
    )
    _read(protocol_path, expected_sha256, model, accepted_steps, restart_verifications)
    return result


def verify(protocol_path, expected_sha256, run_dir, *, model, accepted_steps, restart_verifications):
    """Replay retained observations, without graph/energy/force work or mutation."""
    _, loaded = _read(protocol_path, expected_sha256, model, accepted_steps, restart_verifications)
    ligand, _, config, fixed, evaluator, identity = loaded
    return execution._verify_profile(
        ligand, config, evaluator=evaluator, identity=identity, run_dir=run_dir,
        implementation_sources=implementation_sources, result_schema=RESULT_SCHEMA,
        model_guard=fixed.assert_intact,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    for action in ("prepare", "preflight", "run", "resume", "verify"):
        command = actions.add_parser(action)
        command.add_argument("--model", choices=MODELS, required=True)
        command.add_argument("--accepted-steps", type=int, choices=ACCEPTED_STEP_BUDGETS, required=True)
        command.add_argument("--restart-verifications", type=int, choices=(0, 1), required=True)
        if action in {"run", "resume"}:
            command.add_argument("--pause-after-objective-attempts", type=int)
        if action == "prepare":
            command.add_argument("--candidate-id", required=True)
            command.add_argument("--evidence-kind", choices=("prepared_real_development", "synthetic_control"), required=True)
            for name in REFS:
                command.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
            command.add_argument("--algorithm", choices=("sd", "lbfgs"), required=True)
            command.add_argument("--output", type=Path, required=True)
        else:
            command.add_argument("--protocol", type=Path, required=True)
            command.add_argument("--expected-protocol-sha256", required=True)
            if action != "preflight":
                command.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    torch.set_num_threads(1)
    keywords = {"model": args.model, "accepted_steps": args.accepted_steps,
                "restart_verifications": args.restart_verifications}
    if args.action == "prepare":
        result = prepare(**keywords, candidate_id=args.candidate_id, evidence_kind=args.evidence_kind,
                         **{name: getattr(args, name) for name in REFS},
                         solver=budget_config(args.algorithm, args.accepted_steps,
                                              restart_verifications=args.restart_verifications), output=args.output)
    elif args.action == "preflight":
        result = preflight(args.protocol, args.expected_protocol_sha256, **keywords)
    elif args.action in {"run", "resume"}:
        result = run(args.protocol, args.expected_protocol_sha256, args.run_dir, **keywords,
                     resume=args.action == "resume",
                     pause_after_objective_attempts=args.pause_after_objective_attempts)
    else:
        result = verify(args.protocol, args.expected_protocol_sha256, args.run_dir, **keywords)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
