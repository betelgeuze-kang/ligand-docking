"""New checkpoint identity using the shared bounded descent kernel, no migration."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
from types import SimpleNamespace
from betelgeuze_product.cpu_refinement_v1_2 import minimization as kernel
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError,
    digest,
    coordinates_hex,
    source_manifest,
    require_digest,
    exact_fields,
)
from .parameters import FourierParameters
from .evaluation import FourierFixedEvaluator, FourierEnvironment, FIXED_ID

CHECKPOINT_SCHEMA = "cpu_prepared_fourier_checkpoint/1.0.0"


def implementation_sources():
    result = source_manifest()
    root = Path(__file__).resolve().parent
    for path in sorted(root.glob("*.py")):
        result["betelgeuze_product/cpu_refinement_fourier_v1/" + path.name] = (
            hashlib.sha256(path.read_bytes()).hexdigest()
        )
    from betelgeuze_product import comparison_receipts, installed_synthetic_comparison

    for module in (comparison_receipts, installed_synthetic_comparison):
        result[module.__name__.replace(".", "/") + ".py"] = hashlib.sha256(
            Path(module.__file__).read_bytes()
        ).hexdigest()
    return result


def require_checkpoint(value):
    document = value.to_dict() if isinstance(value, kernel.Checkpoint) else value
    if type(document) is not dict or type(document.get("evaluator")) is not dict:
        raise ResearchError("explicit fixed Fourier checkpoint required")
    evaluator = document["evaluator"]
    exact_fields(
        evaluator,
        {"evaluator_id", "parameter_fingerprint_sha256", "cross_parameters_sha256"},
    )
    if evaluator["evaluator_id"] != FIXED_ID:
        raise ResearchError("fixed Fourier checkpoint evaluator identity required")
    require_digest(evaluator["parameter_fingerprint_sha256"])
    require_digest(evaluator["cross_parameters_sha256"])
    return kernel._require_checkpoint_profile(document, CHECKPOINT_SCHEMA, FIXED_ID)


@dataclass(frozen=True)
class FourierMinimizationResult(kernel.MinimizationResult):
    def to_dict(self):
        result = super().to_dict()
        result["schema_id"] = "cpu_prepared_fourier_minimization_result/1.0.0"
        return result


def minimize_fourier(
    system,
    parameters,
    config,
    *,
    fixed_environment,
    checkpoint=None,
    pause_after_accepted_iterations=None,
    meter=None,
):
    if (
        type(parameters) is not FourierParameters
        or type(fixed_environment) is not FourierEnvironment
        or type(config) is not kernel.SolverConfig
    ):
        raise ResearchError("explicit Fourier model/environment/solver required")
    if parameters.constraints:
        raise ResearchError("Fourier v1 is unconstrained B3 only")
    if checkpoint is not None:
        checkpoint = require_checkpoint(checkpoint)
    fixed_environment.validate_ligand(system, parameters)
    evaluator = FourierFixedEvaluator(parameters, fixed_environment)

    def identity_projection(state):
        return SimpleNamespace(
            system=state,
            converged=True,
            projection_sha256=digest(
                {
                    "policy": "unconstrained_identity_projection/1.0.0",
                    "parameters": parameters.fingerprint_sha256,
                    "coordinates": coordinates_hex(state.coordinates),
                }
            ),
            final_observation=SimpleNamespace(max_absolute_residual_angstrom=0.0),
        )

    return kernel._minimize_profile(
        system,
        parameters,
        config,
        evaluator=evaluator,
        project_parameters=identity_projection,
        checkpoint=checkpoint,
        pause_after_accepted_iterations=pause_after_accepted_iterations,
        meter=meter,
        fixed_mode=True,
        checkpoint_schema=CHECKPOINT_SCHEMA,
        fixed_evaluator_id=FIXED_ID,
        implementation_sources=implementation_sources,
        result_type=FourierMinimizationResult,
    )
