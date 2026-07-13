"""End-to-end CPU reference orchestration for the independent engine v2."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.ai import LocalEnergyConfig, ParityAwareLocalEnergyModel
from betelgeuze_engine_v2.contracts import ENGINE_API_VERSION
from betelgeuze_engine_v2.features import (
    ATOM_FEATURE_NAMES,
    ATOM_FEATURE_SCHEMA_VERSION,
    build_deterministic_atom_features,
)
from betelgeuze_engine_v2.geometry import (
    NEIGHBOR_SCHEMA_VERSION,
    RadiusGraphConfig,
    build_compact_radius_graph,
)
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    StructureProvenance,
    require_molecular_preparation_ready,
    require_valid_all_atom_system,
)
from betelgeuze_engine_v2.physics import project_rigid_body_forces


REFERENCE_EXECUTION_MODE = "internal_unvalidated_cpu_reference"
RIGID_PROJECTION_NOTE = (
    "Rigid-body force projection is a post-gradient constraint operation; "
    "the projected field is not guaranteed to remain the gradient of the reported energy."
)


class PeriodicReferencePathError(RuntimeError):
    """Raised before execution when periodic geometry is not gradient-safe."""


@dataclass(frozen=True)
class ClaimBlocker:
    gate: str
    code: str
    status: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "gate": self.gate,
            "code": self.code,
            "status": self.status,
            "reason": self.reason,
        }


REFERENCE_CLAIM_BLOCKERS = (
    ClaimBlocker(
        gate="checkpoint",
        code="uncalibrated_checkpoint",
        status="blocked",
        reason="Parameters are reproducibly initialized but have not been trained or calibrated.",
    ),
    ClaimBlocker(
        gate="scientific",
        code="scientific_validation_missing",
        status="blocked",
        reason="Energy and force accuracy have not passed an independent molecular validation suite.",
    ),
    ClaimBlocker(
        gate="benchmark",
        code="public_benchmark_missing",
        status="blocked",
        reason="Held-out public accuracy, scaling, and robustness benchmarks have not been completed.",
    ),
    ClaimBlocker(
        gate="gpu",
        code="gpu_validation_missing",
        status="blocked",
        reason="This reference execution is CPU-only; accelerator correctness and performance are unverified.",
    ),
    ClaimBlocker(
        gate="product",
        code="product_release_qualification_missing",
        status="blocked",
        reason="Release, safety, support, and intended-use qualification have not been completed.",
    ),
)


@dataclass(frozen=True)
class IndependentEngineV2Config:
    """Deterministic capacity and model settings for one CPU reference engine."""

    seed: int = 20260710
    cutoff_angstrom: float = 6.0
    max_neighbors: int = 64
    max_atoms_per_cell: int = 64
    hidden_features: int = 48
    radial_features: int = 16
    layers: int = 3
    dtype: torch.dtype = torch.float64
    project_rigid_body_forces: bool = False

    def __post_init__(self) -> None:
        if int(self.seed) < 0 or int(self.seed) >= 2**63:
            raise ValueError("seed must be in [0, 2**63)")
        if self.dtype not in (torch.float32, torch.float64):
            raise TypeError("CPU reference execution supports torch.float32 or torch.float64")
        # Reuse the component validators so orchestration cannot weaken their
        # scientific or bounded-capacity contracts.
        RadiusGraphConfig(
            cutoff_angstrom=float(self.cutoff_angstrom),
            max_neighbors=int(self.max_neighbors),
            max_atoms_per_cell=int(self.max_atoms_per_cell),
        )
        LocalEnergyConfig(
            input_features=len(ATOM_FEATURE_NAMES),
            hidden_features=int(self.hidden_features),
            radial_features=int(self.radial_features),
            layers=int(self.layers),
            cutoff=float(self.cutoff_angstrom),
            max_neighbors=int(self.max_neighbors),
        )


@dataclass(frozen=True)
class EngineExecutionProvenance:
    engine_api_version: str
    execution_mode: str
    system_id: str
    input_schema_id: str
    input_source_format: str
    input_source_id: str
    input_source_sha256: str
    input_parser_name: str
    input_parser_version: str
    input_operations: tuple[str, ...]
    feature_schema_version: str
    neighbor_schema_version: str
    initialization_seed: int
    parameter_fingerprint_sha256: str
    device: str
    dtype: str
    rigid_body_projection_applied: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_api_version": self.engine_api_version,
            "execution_mode": self.execution_mode,
            "system_id": self.system_id,
            "input": {
                "schema_id": self.input_schema_id,
                "source_format": self.input_source_format,
                "source_id": self.input_source_id,
                "source_sha256": self.input_source_sha256,
                "parser_name": self.input_parser_name,
                "parser_version": self.input_parser_version,
                "operations": list(self.input_operations),
            },
            "feature_schema_version": self.feature_schema_version,
            "neighbor_schema_version": self.neighbor_schema_version,
            "initialization": {
                "kind": "deterministic_untrained_parameters",
                "seed": int(self.initialization_seed),
                "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            },
            "device": self.device,
            "dtype": self.dtype,
            "rigid_body_projection_applied": bool(self.rigid_body_projection_applied),
        }


@dataclass(frozen=True)
class IndependentEngineV2Result:
    """Reference prediction with immutable claim gates.

    ``energy_gradient_forces`` always stores the exact negative coordinate
    derivative.  ``forces`` equals that tensor unless the caller explicitly
    requests rigid-body projection.
    """

    energy: torch.Tensor
    forces: torch.Tensor
    energy_gradient_forces: torch.Tensor
    parity_odd: torch.Tensor
    forces_are_conservative: bool
    projection_applied: bool
    projection_note: str
    blockers: tuple[ClaimBlocker, ...]
    diagnostics: Mapping[str, Any]
    provenance: EngineExecutionProvenance
    claim_safe: bool = field(default=False, init=False)

    @property
    def parity(self) -> torch.Tensor:
        return self.parity_odd

    def to_dict(self, *, include_tensors: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "claim_safe": False,
            "forces_are_conservative": bool(self.forces_are_conservative),
            "projection_applied": bool(self.projection_applied),
            "projection_note": self.projection_note,
            "blockers": [blocker.to_dict() for blocker in self.blockers],
            "diagnostics": dict(self.diagnostics),
            "provenance": self.provenance.to_dict(),
            "shapes": {
                "energy": list(self.energy.shape),
                "forces": list(self.forces.shape),
                "parity_odd": list(self.parity_odd.shape),
            },
        }
        if include_tensors:
            payload["energy"] = self.energy.detach().cpu().tolist()
            payload["forces"] = self.forces.detach().cpu().tolist()
            payload["energy_gradient_forces"] = self.energy_gradient_forces.detach().cpu().tolist()
            payload["parity_odd"] = self.parity_odd.detach().cpu().tolist()
        return payload


def _source_provenance(system: AllAtomSystem) -> StructureProvenance:
    provenance = system.provenance
    if not isinstance(provenance, StructureProvenance):
        raise TypeError("system provenance must be StructureProvenance")
    return provenance


def _parameter_fingerprint(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        value = tensor.detach().to(device="cpu").contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(tuple(value.shape)).encode("ascii"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(value.numpy().tobytes(order="C"))
    return digest.hexdigest()


class IndependentEngineV2:
    """Owns a reproducible, untrained local-energy CPU reference model."""

    scientific_status = "unvalidated_reference_execution"
    product_status = "blocked"

    def __init__(self, config: IndependentEngineV2Config | None = None):
        self.config = IndependentEngineV2Config() if config is None else config
        if not isinstance(self.config, IndependentEngineV2Config):
            raise TypeError("config must be IndependentEngineV2Config")
        model_config = LocalEnergyConfig(
            input_features=len(ATOM_FEATURE_NAMES),
            hidden_features=int(self.config.hidden_features),
            radial_features=int(self.config.radial_features),
            layers=int(self.config.layers),
            cutoff=float(self.config.cutoff_angstrom),
            max_neighbors=int(self.config.max_neighbors),
        )
        # fork_rng restores the process-global CPU RNG after construction.
        with torch.random.fork_rng(devices=[], enabled=True):
            torch.manual_seed(int(self.config.seed))
            model = ParityAwareLocalEnergyModel(model_config)
        self.model = model.to(device="cpu", dtype=self.config.dtype).eval()
        for parameter in self.model.parameters():
            parameter.requires_grad_(False)
        self.parameter_fingerprint_sha256 = _parameter_fingerprint(self.model)

    def run(
        self,
        system: AllAtomSystem,
        *,
        project_rigid_body: bool | None = None,
        create_graph: bool = False,
    ) -> IndependentEngineV2Result:
        """Validate and execute the internal CPU reference path.

        Invalid topology and capacity overflow exceptions are intentionally
        allowed to propagate.  No partial or truncated prediction is returned.
        """

        if not isinstance(system, AllAtomSystem):
            raise TypeError("system must be an AllAtomSystem")
        validation = require_valid_all_atom_system(system)
        require_molecular_preparation_ready(system)
        if system.cell is not None and any(system.cell.periodic):
            raise PeriodicReferencePathError(
                "periodic reference execution is blocked until minimum-image "
                "displacements are carried through the energy-gradient path"
            )
        projection_requested = (
            bool(self.config.project_rigid_body_forces)
            if project_rigid_body is None
            else bool(project_rigid_body)
        )

        coordinates = system.coordinates.detach().to(device="cpu", dtype=self.config.dtype).clone()
        features = build_deterministic_atom_features(
            system,
            dtype=self.config.dtype,
            device="cpu",
        )
        neighbors = build_compact_radius_graph(
            coordinates,
            RadiusGraphConfig(
                cutoff_angstrom=float(self.config.cutoff_angstrom),
                max_neighbors=int(self.config.max_neighbors),
                max_atoms_per_cell=int(self.config.max_atoms_per_cell),
            ),
            cell=system.cell,
        )
        with torch.enable_grad():
            prediction = self.model.energy_and_forces(
                coordinates,
                features.values,
                neighbors,
                create_graph=bool(create_graph),
            )

        energy_gradient_forces = prediction.forces
        projection_diagnostics: dict[str, Any]
        if projection_requested:
            projected = project_rigid_body_forces(
                prediction.coordinates_used,
                energy_gradient_forces,
                return_diagnostics=True,
            )
            assert isinstance(projected, tuple)
            output_forces, projection_metadata = projected
            forces_are_conservative = False
            projection_note = RIGID_PROJECTION_NOTE
            projection_diagnostics = {
                "applied": True,
                "guaranteed_conservative": False,
                "note": projection_note,
                **projection_metadata.to_dict(),
            }
        else:
            output_forces = energy_gradient_forces
            forces_are_conservative = True
            projection_note = "Not applied; forces are the exact negative derivative of the reported energy."
            projection_diagnostics = {
                "applied": False,
                "guaranteed_conservative": True,
                "note": projection_note,
            }

        source = _source_provenance(system)
        dtype_name = str(self.config.dtype).removeprefix("torch.")
        provenance = EngineExecutionProvenance(
            engine_api_version=ENGINE_API_VERSION,
            execution_mode=REFERENCE_EXECUTION_MODE,
            system_id=system.system_id,
            input_schema_id=system.schema_id,
            input_source_format=source.source_format,
            input_source_id=source.source_id,
            input_source_sha256=source.source_sha256,
            input_parser_name=source.parser_name,
            input_parser_version=source.parser_version,
            input_operations=source.operations,
            feature_schema_version=ATOM_FEATURE_SCHEMA_VERSION,
            neighbor_schema_version=NEIGHBOR_SCHEMA_VERSION,
            initialization_seed=int(self.config.seed),
            parameter_fingerprint_sha256=self.parameter_fingerprint_sha256,
            device="cpu",
            dtype=dtype_name,
            rigid_body_projection_applied=projection_requested,
        )
        blocker_payload = {blocker.gate: blocker.to_dict() for blocker in REFERENCE_CLAIM_BLOCKERS}
        diagnostics: dict[str, Any] = {
            "status": REFERENCE_EXECUTION_MODE,
            "claim_safe": False,
            "validation": validation.to_dict(),
            "features": dict(features.diagnostics),
            "neighbors": neighbors.diagnostics.to_dict(),
            "model": dict(prediction.diagnostics),
            "force_evidence": {
                "definition": "negative_exact_coordinate_gradient_of_scalar_energy",
                "exact_autograd": True,
                "create_graph": bool(create_graph),
                "raw_force_shape": list(energy_gradient_forces.shape),
            },
            "projection": projection_diagnostics,
            "initialization": {
                "seed_isolated": True,
                "kind": "deterministic_untrained_parameters",
                "seed": int(self.config.seed),
                "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
                "parameters_trainable_during_reference_execution": False,
            },
            "claim_gates": blocker_payload,
            "provenance": provenance.to_dict(),
        }
        return IndependentEngineV2Result(
            energy=prediction.energy,
            forces=output_forces,
            energy_gradient_forces=energy_gradient_forces,
            parity_odd=prediction.parity_odd,
            forces_are_conservative=forces_are_conservative,
            projection_applied=projection_requested,
            projection_note=projection_note,
            blockers=REFERENCE_CLAIM_BLOCKERS,
            diagnostics=diagnostics,
            provenance=provenance,
        )


def run_internal_cpu_reference(
    system: AllAtomSystem,
    *,
    config: IndependentEngineV2Config | None = None,
    project_rigid_body: bool | None = None,
) -> IndependentEngineV2Result:
    """Convenience entry point with the same immutable blocked-claim status."""

    return IndependentEngineV2(config).run(
        system,
        project_rigid_body=project_rigid_body,
    )


__all__ = [
    "REFERENCE_CLAIM_BLOCKERS",
    "REFERENCE_EXECUTION_MODE",
    "RIGID_PROJECTION_NOTE",
    "ClaimBlocker",
    "EngineExecutionProvenance",
    "IndependentEngineV2",
    "IndependentEngineV2Config",
    "IndependentEngineV2Result",
    "PeriodicReferencePathError",
    "run_internal_cpu_reference",
]
