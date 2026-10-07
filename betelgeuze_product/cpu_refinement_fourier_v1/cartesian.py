"""Opt-in bounded Cartesian algorithms on the unchanged explicit Fourier model.

This is a model-binding wrapper around the shared Cartesian execution loop, not
a candidate search, pose scorer, source admission or installed campaign driver.
"""

import hashlib
import json
from pathlib import Path

import torch

from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import require_system
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, canonical, coordinates_hex, digest, environment, exact_fields,
    require_digest,
)
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig
from .evaluation import FourierEnvironment, FourierFixedEvaluator
from .minimization import implementation_sources as fourier_sources
from .parameters import FourierParameters

INPUT_SCHEMA = "cpu_prepared_fourier_cartesian_input/1.0.0"
BINDING_SCHEMA = "cpu_prepared_fourier_cartesian_binding/1.0.0"
RESULT_SCHEMA = "cpu_prepared_fourier_cartesian_result/1.0.0"


def implementation_sources():
    """Bind both numerical closures; never migrate an older source-bound run."""
    result = fourier_sources()
    folder = Path(execution.__file__).resolve().parent
    for path in sorted(folder.glob("*.py")):
        result["betelgeuze_product/cpu_refinement_v1_3/" + path.name] = (
            hashlib.sha256(path.read_bytes()).hexdigest()
        )
    return result


def _context(system, parameters, config, fixed_environment, binding):
    require_system(system, 256)
    if (type(parameters) is not FourierParameters
            or type(fixed_environment) is not FourierEnvironment
            or type(config) is not SolverConfig):
        raise ResearchError("explicit Fourier Cartesian model/environment/solver required")
    if parameters.constraints:
        raise ResearchError("Fourier Cartesian profile is unconstrained only")
    if (config.max_objective_attempts > 17 or config.max_accepted_steps > 4
            or config.max_backtracks > 3 or config.max_restart_verifications > 2
            or config.force_tolerance > .001):
        raise ResearchError("bounded Fourier Cartesian development limits required")
    if torch.get_num_threads() != 1:
        raise ResearchError("one CPU thread required")
    if type(binding) is not dict:
        raise ResearchError("explicit Fourier Cartesian input binding required")
    exact_fields(binding, {"schema_id", "candidate_id", "prepared_protocol_sha256",
                           "initial_coordinates_sha256"})
    if (binding["schema_id"] != INPUT_SCHEMA
            or type(binding["candidate_id"]) is not str
            or not 1 <= len(binding["candidate_id"]) <= 128):
        raise ResearchError("explicit Fourier Cartesian input identity required")
    require_digest(binding["prepared_protocol_sha256"])
    require_digest(binding["initial_coordinates_sha256"])
    if binding["initial_coordinates_sha256"] != digest(coordinates_hex(system.coordinates)):
        raise ResearchError("exact initial coordinates changed")
    fixed_environment.validate_ligand(system, parameters)
    evaluator = FourierFixedEvaluator(parameters, fixed_environment)
    identity = {
        "schema_id": BINDING_SCHEMA,
        "source_system_sha256": canonical_system_sha256(system),
        "evaluator": evaluator.identity(),
        "config": config.to_dict(),
        "implementation_sha256": digest(implementation_sources()),
        "environment": environment(),
        "external_binding": binding,
    }
    return evaluator, json.loads(canonical(identity))


def minimize_cartesian(system, parameters, config, *, fixed_environment, run_dir,
                       binding, pause_after_objective_attempts=None, resume=False):
    """Run B1 L-BFGS or B2 Cartesian SD; B3 keeps its distinct existing API."""
    evaluator, identity = _context(system, parameters, config, fixed_environment, binding)
    return execution._minimize_profile(
        system, config, evaluator=evaluator, identity=identity, run_dir=run_dir,
        implementation_sources=implementation_sources, result_schema=RESULT_SCHEMA,
        model_guard=fixed_environment.assert_intact,
        pause_after_objective_attempts=pause_after_objective_attempts, resume=resume,
    )


def verify_cartesian(system, parameters, config, *, fixed_environment, run_dir, binding):
    """Rebind and replay retained observations without graph, force or score work."""
    evaluator, identity = _context(system, parameters, config, fixed_environment, binding)
    return execution._verify_profile(
        system, config, evaluator=evaluator, identity=identity, run_dir=run_dir,
        implementation_sources=implementation_sources, result_schema=RESULT_SCHEMA,
        model_guard=fixed_environment.assert_intact,
    )
