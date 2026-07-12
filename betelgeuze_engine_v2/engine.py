"""Fail-closed internal CPU orchestrator for independent Engine v2."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

import torch

from betelgeuze_engine_v2.ai import (
    EnergyForcePrediction,
    LocalEnergyConfig,
    ParityAwareLocalEnergyModel,
    SparseNeighborGraph,
)
from betelgeuze_engine_v2.contracts import (
    ENGINE_RESULT_SCHEMA_VERSION,
    UNCALIBRATED_ENERGY,
    UNCALIBRATED_FORCE,
)
from betelgeuze_engine_v2.features import (
    ATOM_FEATURE_NAMES,
    build_deterministic_atom_features,
)
from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    ValidationReport,
    canonical_system_sha256,
    require_valid_all_atom_system,
)
from betelgeuze_engine_v2.physics import (
    EnergyCompositionResult,
    EnergyTermResult,
    IndependentPhysicsProvider,
    compose_energy_terms,
    project_rigid_body_forces,
)


REFERENCE_EXECUTION_MODE = "internal_unvalidated_cpu_reference"
REFERENCE_CLAIM_BLOCKERS = (
    "uncalibrated_checkpoint",
    "independent_physics_validation_missing",
    "public_benchmark_evidence_missing",
    "gpu_parity_evidence_missing",
    "product_integration_not_qualified",
)
RIGID_PROJECTION_NOTE = (
    "Rigid-body projection removes net translation/rotation components but is "
    "not guaranteed to remain the exact gradient of the reported scalar."
)


@dataclass(frozen=True)
class IndependentEngineV2Config:
    seed: int = 7301
    cutoff_angstrom: float = 6.0
    max_neighbors: int = 64
    max_atoms_per_cell: int = 64
    hidden_features: int = 48
    radial_features: int = 16
    layers: int = 3
    dtype: torch.dtype = torch.float64
    enable_reference_residual: bool = True

    def __post_init__(self) -> None:
        if self.dtype not in (torch.float32, torch.float64):
            raise TypeError("reference engine dtype must be torch.float32 or torch.float64")
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

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "seed": int(self.seed),
            "cutoff_angstrom": float(self.cutoff_angstrom).hex(),
            "max_neighbors": int(self.max_neighbors),
            "max_atoms_per_cell": int(self.max_atoms_per_cell),
            "hidden_features": int(self.hidden_features),
            "radial_features": int(self.radial_features),
            "layers": int(self.layers),
            "dtype": str(self.dtype).removeprefix("torch."),
            "enable_reference_residual": bool(self.enable_reference_residual),
            "atom_feature_names": list(ATOM_FEATURE_NAMES),
        }


@dataclass(frozen=True)
class ClaimBlocker:
    gate: str
    code: str
    status: str = "blocked"
    message: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "gate": self.gate,
            "code": self.code,
            "status": self.status,
            "message": self.message,
        }


@dataclass(frozen=True)
class EngineExecutionProvenance:
    execution_mode: str
    input_system_sha256: str
    parameter_fingerprint_sha256: str
    config_fingerprint_sha256: str
    result_schema_version: str = ENGINE_RESULT_SCHEMA_VERSION
    device: str = "cpu"

    def to_dict(self) -> dict[str, str]:
        return {
            "execution_mode": self.execution_mode,
            "input_system_sha256": self.input_system_sha256,
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "result_schema_version": self.result_schema_version,
            "device": self.device,
        }


@dataclass
class IndependentEngineV2Result:
    reference_scalar_energy: torch.Tensor | None
    reference_scalar_forces: torch.Tensor | None
    energy_gradient_forces: torch.Tensor | None
    parity_odd: torch.Tensor | None
    composition: EnergyCompositionResult
    validation: ValidationReport
    provenance: EngineExecutionProvenance
    blockers: tuple[ClaimBlocker, ...]
    diagnostics: dict[str, object]
    projection_applied: bool = False
    projection_note: str = ""

    @property
    def energy(self) -> torch.Tensor | None:
        """Compatibility alias for the explicitly uncalibrated reference scalar."""

        return self.reference_scalar_energy

    @property
    def forces(self) -> torch.Tensor | None:
        """Compatibility alias for reference forces, projected when requested."""

        return self.reference_scalar_forces

    @property
    def total_physical_energy(self) -> torch.Tensor | None:
        return self.composition.total_energy

    @property
    def total_physical_forces(self) -> torch.Tensor | None:
        return self.composition.total_forces

    @property
    def forces_are_conservative(self) -> bool:
        return bool(
            self.energy_gradient_forces is not None
            and not self.projection_applied
            and self.reference_scalar_forces is not None
        )

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "result_schema_version": ENGINE_RESULT_SCHEMA_VERSION,
            "claim_safe": False,
            "reference_scalar_present": self.reference_scalar_energy is not None,
            "reference_force_present": self.reference_scalar_forces is not None,
            "reference_energy_descriptor": UNCALIBRATED_ENERGY.to_dict(),
            "reference_force_descriptor": UNCALIBRATED_FORCE.to_dict(),
            "total_physical_energy_present": self.total_physical_energy is not None,
            "total_physical_forces_present": self.total_physical_forces is not None,
            "composition": self.composition.to_dict(),
            "validation": self.validation.to_dict(),
            "provenance": self.provenance.to_dict(),
            "blockers": [blocker.to_dict() for blocker in self.blockers],
            "projection_applied": self.projection_applied,
            "projection_note": self.projection_note,
            "forces_are_conservative": self.forces_are_conservative,
            "diagnostics": dict(self.diagnostics),
        }


def _sha256_text(payload: object) -> str:
    import json

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parameter_fingerprint(model: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        value = tensor.detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(str(tuple(value.shape)).encode("ascii"))
        digest.update(value.numpy().tobytes())
    return digest.hexdigest()


def _reference_blockers(composition: EnergyCompositionResult) -> tuple[ClaimBlocker, ...]:
    rows = [
        ClaimBlocker("checkpoint", "uncalibrated_checkpoint", message="Reference parameters are deterministic but untrained."),
        ClaimBlocker("scientific", "independent_physics_validation_missing", message="No validated independent physics stack is promoted."),
        ClaimBlocker("benchmark", "public_benchmark_evidence_missing"),
        ClaimBlocker("gpu", "gpu_parity_evidence_missing"),
        ClaimBlocker("product", "product_integration_not_qualified"),
    ]
    existing = {row.code for row in rows}
    for code in composition.blockers:
        if code not in existing:
            rows.append(ClaimBlocker("composition", code))
    return tuple(rows)


class IndependentEngineV2:
    """Internal CPU reference that keeps physics and residual terms separate."""

    def __init__(
        self,
        config: IndependentEngineV2Config | None = None,
        *,
        physics_provider: IndependentPhysicsProvider | None = None,
    ):
        self.config = config or IndependentEngineV2Config()
        self.physics_provider = physics_provider
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(int(self.config.seed))
            self.residual_model = ParityAwareLocalEnergyModel(
                LocalEnergyConfig(
                    input_features=len(ATOM_FEATURE_NAMES),
                    hidden_features=int(self.config.hidden_features),
                    radial_features=int(self.config.radial_features),
                    layers=int(self.config.layers),
                    cutoff=float(self.config.cutoff_angstrom),
                    max_neighbors=int(self.config.max_neighbors),
                )
            ).to(dtype=self.config.dtype, device="cpu")
        self.residual_model.eval()
        self.parameter_fingerprint_sha256 = _parameter_fingerprint(self.residual_model)
        self.config_fingerprint_sha256 = _sha256_text(self.config.fingerprint_payload())

    def run(
        self,
        system: AllAtomSystem,
        *,
        project_rigid_body: bool = False,
    ) -> IndependentEngineV2Result:
        validation = require_valid_all_atom_system(system)
        coordinates = system.coordinates.to(dtype=self.config.dtype, device="cpu")
        features = build_deterministic_atom_features(
            system,
            dtype=self.config.dtype,
            device="cpu",
        )
        compact = build_compact_radius_graph(
            coordinates,
            RadiusGraphConfig(
                cutoff_angstrom=float(self.config.cutoff_angstrom),
                max_neighbors=int(self.config.max_neighbors),
                max_atoms_per_cell=int(self.config.max_atoms_per_cell),
            ),
            cell=system.cell,
        )
        sparse = SparseNeighborGraph.from_compact_neighbor_list(
            compact,
            max_neighbors=int(self.config.max_neighbors),
            cell=system.cell,
        )

        residual_prediction: EnergyForcePrediction | None = None
        residual_term: EnergyTermResult | None = None
        if self.config.enable_reference_residual:
            residual_prediction = self.residual_model.energy_and_forces(
                coordinates,
                features.values,
                sparse,
            )
            residual_term = EnergyTermResult(
                name="uncalibrated_ai_reference_residual",
                energy=residual_prediction.energy,
                forces=residual_prediction.forces,
                energy_descriptor=residual_prediction.energy_descriptor,
                force_descriptor=residual_prediction.force_descriptor,
                validated_for_composition=False,
                provenance_sha256=self.parameter_fingerprint_sha256,
            )

        physics_term = (
            None
            if self.physics_provider is None
            else self.physics_provider.evaluate(system, compact)
        )
        composition = compose_energy_terms(physics_term, residual_term)

        gradient_forces = None if residual_prediction is None else residual_prediction.forces
        reported_forces = gradient_forces
        projection_note = ""
        if project_rigid_body and reported_forces is not None:
            reported_forces = project_rigid_body_forces(coordinates, reported_forces)
            projection_note = RIGID_PROJECTION_NOTE

        blockers = _reference_blockers(composition)
        provenance = EngineExecutionProvenance(
            execution_mode=REFERENCE_EXECUTION_MODE,
            input_system_sha256=canonical_system_sha256(system),
            parameter_fingerprint_sha256=self.parameter_fingerprint_sha256,
            config_fingerprint_sha256=self.config_fingerprint_sha256,
        )
        diagnostics: dict[str, object] = {
            "claim_safe": False,
            "initialization": {
                "kind": "deterministic_untrained_parameters",
                "seed": int(self.config.seed),
            },
            "features": dict(features.diagnostics),
            "neighbors": compact.diagnostics.to_dict(),
            "sparse_graph": sparse.complexity,
            "composition": composition.to_dict(),
            "reference_residual_enabled": bool(self.config.enable_reference_residual),
            "independent_physics_provider": None
            if self.physics_provider is None
            else str(self.physics_provider.provider_id),
            "force_evidence": {
                "exact_autograd": residual_prediction is not None,
                "definition": "negative_exact_coordinate_gradient_of_uncalibrated_scalar"
                if residual_prediction is not None
                else "not_available",
            },
            "projection": {
                "applied": bool(project_rigid_body),
                "constructs_nxn": False,
            },
            "blocker_codes": [blocker.code for blocker in blockers],
        }
        if residual_prediction is not None:
            diagnostics["model"] = dict(residual_prediction.diagnostics)

        return IndependentEngineV2Result(
            reference_scalar_energy=None
            if residual_prediction is None
            else residual_prediction.energy,
            reference_scalar_forces=reported_forces,
            energy_gradient_forces=gradient_forces,
            parity_odd=None
            if residual_prediction is None
            else residual_prediction.parity_odd,
            composition=composition,
            validation=validation,
            provenance=provenance,
            blockers=blockers,
            diagnostics=diagnostics,
            projection_applied=bool(project_rigid_body),
            projection_note=projection_note,
        )


def run_internal_cpu_reference(
    system: AllAtomSystem,
    *,
    config: IndependentEngineV2Config | None = None,
    physics_provider: IndependentPhysicsProvider | None = None,
    project_rigid_body: bool = False,
) -> IndependentEngineV2Result:
    return IndependentEngineV2(
        config,
        physics_provider=physics_provider,
    ).run(system, project_rigid_body=project_rigid_body)
