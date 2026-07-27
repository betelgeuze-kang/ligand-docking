"""Bounded ligand-internal reference-energy refinement for docking poses.

This adapter connects authenticated docking proposals to the existing CPU
reference force field and bounded minimizer.  It relaxes ligand-internal
coordinates only; receptor--ligand interaction energy is not part of this
minimization and no docking-accuracy or physical-affinity claim is made.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Mapping

import torch

from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
)
from betelgeuze_engine_v2.physics.reference_minimization import (
    REFERENCE_MINIMIZATION_ALGORITHM_ID,
    ReferenceMinimizationConfig,
    minimize_reference_force_field,
)
from betelgeuze_engine_v2.physics.reference_parameters import (
    ReferenceForceFieldParameters,
)

from .authority import AuthenticatedDockingProblem, DockingAuthorityError
from .guided_placement import GuidedPlacementContext
from .identity import coordinate_fingerprint
from .proposals import DockingBudget, DockingProposal
from .scorer_v1 import (
    ChemistryPoseScorerV1,
    ScorerV1GuidedSearchResult,
    run_authenticated_scorer_v1_guided_search,
)
from .scoring import component_contract_fingerprint


ENERGY_REFINEMENT_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_energy_local_refinement_config/1.0.0"
)
ENERGY_REFINEMENT_ATTEMPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_energy_local_refinement_attempt/1.0.0"
)
ENERGY_REFINEMENT_SEARCH_ROW_SCHEMA_ID = (
    "betelgeuze.engine_v2_energy_local_refinement_search_row/1.0.0"
)
ENERGY_REFINEMENT_SEARCH_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_energy_local_refinement_search_result/1.0.0"
)
ENERGY_REFINER_ID = "betelgeuze.engine_v2_ligand_internal_energy_refiner"
ENERGY_REFINER_VERSION = "1.0.0"
ENERGY_REFINER_ALGORITHM_ID = (
    "authenticated_ligand_internal_reference_forcefield_bounded_minimization/1.0.0"
)
MAX_ENERGY_REFINEMENT_ATTEMPTS = 10_000
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MINIMIZATION_OUTCOMES = MappingProxyType(
    {
        "converged": (True, ""),
        "checkpointed": (False, ""),
        "max_iterations_reached": (
            False,
            "maximum_iteration_budget_exhausted",
        ),
        "line_search_failed": (False, "bounded_backtracking_exhausted"),
    }
)


class EnergyRefinementError(DockingAuthorityError):
    """The local-refinement evidence contract cannot be satisfied."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise EnergyRefinementError(
            "energy-refinement state is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str, allow_empty: bool = False) -> str:
    text = str(value or "").strip().lower()
    if allow_empty and not text:
        return ""
    if _SHA256_RE.fullmatch(text) is None:
        raise EnergyRefinementError(f"{name} must be a lowercase SHA-256")
    return text


def _exact_int(value: object, *, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise EnergyRefinementError(
            f"{name} must be an integer in [{minimum},{maximum}]"
        )
    return value


def _finite(value: object, *, name: str, minimum: float | None = None) -> float:
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        suffix = "" if minimum is None else f" >= {minimum}"
        raise EnergyRefinementError(f"{name} must be finite{suffix}")
    return result


def _coordinate_hex(coordinates: torch.Tensor) -> tuple[tuple[str, str, str], ...]:
    value = coordinates.detach().to(dtype=torch.float64, device="cpu")
    if value.ndim != 2 or value.shape[1] != 3:
        raise EnergyRefinementError("refinement coordinates must have shape [N,3]")
    if not bool(torch.isfinite(value).all().item()):
        raise EnergyRefinementError("refinement coordinates must be finite")
    return tuple(
        tuple(float(component).hex() for component in row) for row in value.tolist()
    )


def _coordinates_from_hex(
    rows: object,
    *,
    name: str,
    allow_empty: bool = False,
) -> tuple[tuple[tuple[str, str, str], ...], torch.Tensor | None]:
    try:
        normalized = tuple(
            tuple(float.fromhex(str(component)).hex() for component in row)
            for row in rows
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise EnergyRefinementError(f"{name} coordinates are invalid") from exc
    if allow_empty and not normalized:
        return (), None
    if not normalized or any(len(row) != 3 for row in normalized):
        raise EnergyRefinementError(f"{name} coordinates are invalid")
    coordinates = torch.tensor(
        [[float.fromhex(component) for component in row] for row in normalized],
        dtype=torch.float64,
    )
    if not bool(torch.isfinite(coordinates).all().item()):
        raise EnergyRefinementError(f"{name} coordinates are invalid")
    return normalized, coordinates


@dataclass(frozen=True, slots=True)
class EnergyLocalRefinementConfig:
    """Immutable adapter configuration around the reference minimizer."""

    minimization: ReferenceMinimizationConfig = field(
        default_factory=ReferenceMinimizationConfig
    )
    max_attempts: int = MAX_ENERGY_REFINEMENT_ATTEMPTS
    schema_id: str = ENERGY_REFINEMENT_CONFIG_SCHEMA_ID
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != ENERGY_REFINEMENT_CONFIG_SCHEMA_ID:
            raise EnergyRefinementError("unsupported energy-refinement config schema")
        if not isinstance(self.minimization, ReferenceMinimizationConfig):
            raise TypeError("minimization must be ReferenceMinimizationConfig")
        object.__setattr__(
            self,
            "max_attempts",
            _exact_int(
                self.max_attempts,
                name="max_attempts",
                minimum=1,
                maximum=MAX_ENERGY_REFINEMENT_ATTEMPTS,
            ),
        )
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": ENERGY_REFINER_ALGORITHM_ID,
            "reference_minimization_algorithm_id": (
                REFERENCE_MINIMIZATION_ALGORITHM_ID
            ),
            "minimization": self.minimization.to_dict(),
            "max_attempts": self.max_attempts,
            "scope": "ligand_internal_coordinates_only",
            "receptor_ligand_interaction_energy_included": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise EnergyRefinementError("energy-refinement config changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


@dataclass(frozen=True, slots=True)
class EnergyRefinementAttempt:
    """Failure-complete exact evidence for one refinement invocation."""

    candidate_id: str
    proposal_index: int
    source_proposal_fingerprint_sha256: str
    authority_input_receipt_sha256: str
    ligand_system_sha256: str
    parameter_fingerprint_sha256: str
    parameter_set_id: str
    parameter_set_version: str
    implementation_source_sha256: str
    refiner_config_fingerprint_sha256: str
    effective_minimization_config_fingerprint_sha256: str
    max_steps: int
    maximum_atom_displacement_per_step_angstrom: float
    status: str
    pre_coordinates_sha256: str
    pre_coordinates_binary64_hex: tuple[tuple[str, str, str], ...]
    post_coordinates_sha256: str = ""
    post_coordinates_binary64_hex: tuple[tuple[str, str, str], ...] = ()
    initial_energy_kcal_per_mol: float | None = None
    final_energy_kcal_per_mol: float | None = None
    energy_delta_kcal_per_mol: float | None = None
    maximum_displacement_angstrom: float | None = None
    minimization_status: str = ""
    minimization_failure_code: str = ""
    converged: bool = False
    accepted_iterations: int = 0
    rejected_evaluations: int = 0
    evaluation_count: int = 0
    checkpoint_sha256: str = ""
    public_error_code: str = ""
    private_error_sha256: str = ""
    private_error_byte_length: int = 0
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        candidate_id = str(self.candidate_id or "").strip()
        if not candidate_id:
            raise EnergyRefinementError("refinement candidate ID is empty")
        proposal_index = _exact_int(
            self.proposal_index,
            name="proposal_index",
            minimum=0,
            maximum=MAX_ENERGY_REFINEMENT_ATTEMPTS,
        )
        max_steps = _exact_int(
            self.max_steps,
            name="max_steps",
            minimum=1,
            maximum=1_000_000,
        )
        per_step_displacement = _finite(
            self.maximum_atom_displacement_per_step_angstrom,
            name="maximum_atom_displacement_per_step_angstrom",
            minimum=0.0,
        )
        if per_step_displacement <= 0.0:
            raise EnergyRefinementError(
                "maximum_atom_displacement_per_step_angstrom must be positive"
            )
        for name in (
            "source_proposal_fingerprint_sha256",
            "authority_input_receipt_sha256",
            "ligand_system_sha256",
            "parameter_fingerprint_sha256",
            "implementation_source_sha256",
            "refiner_config_fingerprint_sha256",
            "effective_minimization_config_fingerprint_sha256",
            "pre_coordinates_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        parameter_set_id = str(self.parameter_set_id or "").strip()
        parameter_set_version = str(self.parameter_set_version or "").strip()
        if not parameter_set_id or not parameter_set_version:
            raise EnergyRefinementError("refinement parameter identity is empty")
        status = str(self.status or "").strip()
        if status not in {"success", "failure"}:
            raise EnergyRefinementError("refinement attempt status is invalid")
        for name in (
            "accepted_iterations",
            "rejected_evaluations",
            "evaluation_count",
            "private_error_byte_length",
        ):
            object.__setattr__(
                self,
                name,
                _exact_int(
                    getattr(self, name),
                    name=name,
                    minimum=0,
                    maximum=10_000_000,
                ),
            )
        minimization_failure_code = str(self.minimization_failure_code or "").strip()
        object.__setattr__(
            self,
            "minimization_failure_code",
            minimization_failure_code,
        )
        pre_coordinates, pre_tensor = _coordinates_from_hex(
            self.pre_coordinates_binary64_hex,
            name="pre-refinement",
        )
        assert pre_tensor is not None
        if coordinate_fingerprint(pre_tensor) != self.pre_coordinates_sha256:
            raise EnergyRefinementError(
                "pre-refinement coordinate hash is inconsistent"
            )
        post_coordinates, post_tensor = _coordinates_from_hex(
            self.post_coordinates_binary64_hex,
            name="post-refinement",
            allow_empty=True,
        )
        if type(self.converged) is not bool:
            raise EnergyRefinementError("converged must be a boolean")
        if status == "success":
            post_sha = _digest(
                self.post_coordinates_sha256,
                name="post_coordinates_sha256",
            )
            if post_tensor is None or len(post_coordinates) != len(pre_coordinates):
                raise EnergyRefinementError("post-refinement coordinates are invalid")
            if coordinate_fingerprint(post_tensor) != post_sha:
                raise EnergyRefinementError(
                    "post-refinement coordinate hash is inconsistent"
                )
            initial = _finite(
                self.initial_energy_kcal_per_mol,
                name="initial_energy_kcal_per_mol",
            )
            final = _finite(
                self.final_energy_kcal_per_mol,
                name="final_energy_kcal_per_mol",
            )
            delta = _finite(
                self.energy_delta_kcal_per_mol,
                name="energy_delta_kcal_per_mol",
            )
            displacement = _finite(
                self.maximum_displacement_angstrom,
                name="maximum_displacement_angstrom",
                minimum=0.0,
            )
            observed_displacement = float(
                torch.linalg.vector_norm(
                    post_tensor - pre_tensor,
                    dim=-1,
                )
                .max()
                .item()
            )
            if displacement.hex() != observed_displacement.hex():
                raise EnergyRefinementError(
                    "maximum refinement displacement is inconsistent"
                )
            if delta.hex() != (final - initial).hex():
                raise EnergyRefinementError("refinement energy delta is inconsistent")
            if final > initial + 1.0e-12:
                raise EnergyRefinementError("bounded minimization increased energy")
            minimization_status = str(self.minimization_status or "").strip()
            expected_outcome = _MINIMIZATION_OUTCOMES.get(minimization_status)
            if expected_outcome is None:
                raise EnergyRefinementError("minimization status is invalid")
            expected_converged, expected_failure_code = expected_outcome
            if (
                self.converged is not expected_converged
                or minimization_failure_code != expected_failure_code
            ):
                raise EnergyRefinementError(
                    "minimization outcome evidence is inconsistent"
                )
            checkpoint = _digest(
                self.checkpoint_sha256,
                name="checkpoint_sha256",
            )
            if self.accepted_iterations > max_steps:
                raise EnergyRefinementError(
                    "accepted iterations exceed the requested step bound"
                )
            if self.evaluation_count != (
                1 + self.accepted_iterations + self.rejected_evaluations
            ):
                raise EnergyRefinementError(
                    "refinement evaluation counters are inconsistent"
                )
            displacement_bound = self.accepted_iterations * per_step_displacement
            if displacement > displacement_bound + 1.0e-12:
                raise EnergyRefinementError(
                    "maximum refinement displacement exceeds the step bound"
                )
            if (
                self.public_error_code
                or self.private_error_sha256
                or self.private_error_byte_length
            ):
                raise EnergyRefinementError(
                    "successful refinement cannot carry execution failure evidence"
                )
            object.__setattr__(self, "post_coordinates_sha256", post_sha)
            object.__setattr__(self, "initial_energy_kcal_per_mol", initial)
            object.__setattr__(self, "final_energy_kcal_per_mol", final)
            object.__setattr__(self, "energy_delta_kcal_per_mol", delta)
            object.__setattr__(self, "maximum_displacement_angstrom", displacement)
            object.__setattr__(self, "minimization_status", minimization_status)
            object.__setattr__(self, "checkpoint_sha256", checkpoint)
        else:
            if (
                self.post_coordinates_sha256
                or post_coordinates
                or self.initial_energy_kcal_per_mol is not None
                or self.final_energy_kcal_per_mol is not None
                or self.energy_delta_kcal_per_mol is not None
                or self.maximum_displacement_angstrom is not None
                or self.minimization_status
                or self.minimization_failure_code
                or self.checkpoint_sha256
                or self.converged
                or self.accepted_iterations
                or self.rejected_evaluations
                or self.evaluation_count
            ):
                raise EnergyRefinementError(
                    "failed refinement cannot fabricate minimization evidence"
                )
            public_error = str(self.public_error_code or "").strip()
            if not public_error:
                raise EnergyRefinementError("failed refinement requires an error code")
            private_digest = _digest(
                self.private_error_sha256,
                name="private_error_sha256",
            )
            private_length = self.private_error_byte_length
            if private_length < 1:
                raise EnergyRefinementError(
                    "private_error_byte_length must be positive"
                )
            object.__setattr__(self, "public_error_code", public_error)
            object.__setattr__(self, "private_error_sha256", private_digest)
            object.__setattr__(self, "private_error_byte_length", private_length)
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "proposal_index", proposal_index)
        object.__setattr__(self, "max_steps", max_steps)
        object.__setattr__(
            self,
            "maximum_atom_displacement_per_step_angstrom",
            per_step_displacement,
        )
        object.__setattr__(self, "parameter_set_id", parameter_set_id)
        object.__setattr__(self, "parameter_set_version", parameter_set_version)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "pre_coordinates_binary64_hex", pre_coordinates)
        object.__setattr__(self, "post_coordinates_binary64_hex", post_coordinates)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        def energy(value: float | None) -> str | None:
            return None if value is None else value.hex()

        return {
            "schema_id": ENERGY_REFINEMENT_ATTEMPT_SCHEMA_ID,
            "algorithm_id": ENERGY_REFINER_ALGORITHM_ID,
            "reference_minimization_algorithm_id": (
                REFERENCE_MINIMIZATION_ALGORITHM_ID
            ),
            "candidate_id": self.candidate_id,
            "proposal_index": self.proposal_index,
            "source_proposal_fingerprint_sha256": (
                self.source_proposal_fingerprint_sha256
            ),
            "authority_input_receipt_sha256": self.authority_input_receipt_sha256,
            "ligand_system_sha256": self.ligand_system_sha256,
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "parameter_set_id": self.parameter_set_id,
            "parameter_set_version": self.parameter_set_version,
            "implementation_source_sha256": self.implementation_source_sha256,
            "refiner_config_fingerprint_sha256": (
                self.refiner_config_fingerprint_sha256
            ),
            "effective_minimization_config_fingerprint_sha256": (
                self.effective_minimization_config_fingerprint_sha256
            ),
            "max_steps": self.max_steps,
            "maximum_atom_displacement_per_step_angstrom_binary64_hex": (
                self.maximum_atom_displacement_per_step_angstrom.hex()
            ),
            "status": self.status,
            "pre_coordinates_sha256": self.pre_coordinates_sha256,
            "pre_coordinates_binary64_hex": [
                list(row) for row in self.pre_coordinates_binary64_hex
            ],
            "post_coordinates_sha256": self.post_coordinates_sha256,
            "post_coordinates_binary64_hex": [
                list(row) for row in self.post_coordinates_binary64_hex
            ],
            "initial_energy_kcal_per_mol_binary64_hex": energy(
                self.initial_energy_kcal_per_mol
            ),
            "final_energy_kcal_per_mol_binary64_hex": energy(
                self.final_energy_kcal_per_mol
            ),
            "energy_delta_kcal_per_mol_binary64_hex": energy(
                self.energy_delta_kcal_per_mol
            ),
            "maximum_displacement_angstrom_binary64_hex": energy(
                self.maximum_displacement_angstrom
            ),
            "minimization_status": self.minimization_status,
            "minimization_failure_code": self.minimization_failure_code,
            "converged": bool(self.converged),
            "accepted_iterations": self.accepted_iterations,
            "rejected_evaluations": self.rejected_evaluations,
            "evaluation_count": self.evaluation_count,
            "checkpoint_sha256": self.checkpoint_sha256,
            "public_error_code": self.public_error_code,
            "private_error_sha256": self.private_error_sha256,
            "private_error_byte_length": self.private_error_byte_length,
            "scope": "ligand_internal_coordinates_only",
            "receptor_ligand_interaction_energy_included": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise EnergyRefinementError("energy-refinement attempt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


class EnergyBasedLocalRefiner:
    """Docking refiner backed by the existing bounded reference minimizer."""

    refiner_id = ENERGY_REFINER_ID
    refiner_version = ENERGY_REFINER_VERSION

    def __init__(
        self,
        authority: AuthenticatedDockingProblem,
        ligand_system: AllAtomSystem,
        parameters: ReferenceForceFieldParameters,
        *,
        implementation_source_sha256: str,
        config: EnergyLocalRefinementConfig | None = None,
    ) -> None:
        if not isinstance(authority, AuthenticatedDockingProblem):
            raise TypeError("authority must be AuthenticatedDockingProblem")
        if not isinstance(ligand_system, AllAtomSystem):
            raise TypeError("ligand_system must be AllAtomSystem")
        require_valid_all_atom_system(ligand_system)
        if (
            ligand_system.coordinates.device.type != "cpu"
            or ligand_system.coordinates.dtype != torch.float64
        ):
            raise EnergyRefinementError(
                "energy refinement requires CPU float64 ligand coordinates"
            )
        if canonical_system_sha256(ligand_system) != authority.ligand_system_sha256:
            raise EnergyRefinementError("refiner ligand system is cross-wired")
        if not isinstance(parameters, ReferenceForceFieldParameters):
            raise TypeError("parameters must be ReferenceForceFieldParameters")
        if parameters.topology_sha256 != canonical_topology_sha256(ligand_system):
            raise EnergyRefinementError("refiner parameter topology is cross-wired")
        selected_config = EnergyLocalRefinementConfig() if config is None else config
        if not isinstance(selected_config, EnergyLocalRefinementConfig):
            raise TypeError("config must be EnergyLocalRefinementConfig")
        authority.input_receipt_sha256
        selected_config.fingerprint_sha256
        parameter_fingerprint_sha256 = parameters.fingerprint_sha256
        self._authority = authority
        self._ligand_system = ligand_system
        self._parameters = parameters
        self._config = selected_config
        self._parameter_fingerprint_sha256 = parameter_fingerprint_sha256
        self._implementation_source_sha256 = _digest(
            implementation_source_sha256,
            name="implementation_source_sha256",
        )
        self._attempts: dict[str, EnergyRefinementAttempt] = {}

    @property
    def config(self) -> EnergyLocalRefinementConfig:
        return self._config

    @property
    def problem_fingerprint_sha256(self) -> str:
        return self._authority.problem.fingerprint_sha256

    @property
    def config_fingerprint_sha256(self) -> str:
        return self._config.fingerprint_sha256

    @property
    def parameter_fingerprint_sha256(self) -> str:
        observed = self._parameters.fingerprint_sha256
        if observed != self._parameter_fingerprint_sha256:
            raise EnergyRefinementError("refiner parameter state changed")
        return observed

    @property
    def implementation_source_sha256(self) -> str:
        return self._implementation_source_sha256

    @property
    def authority_input_receipt_sha256(self) -> str:
        return self._authority.input_receipt_sha256

    @property
    def ligand_system_sha256(self) -> str:
        return self._authority.ligand_system_sha256

    @property
    def attempts(self) -> Mapping[str, EnergyRefinementAttempt]:
        return MappingProxyType(dict(self._attempts))

    def attempt_for(
        self,
        source_proposal_fingerprint_sha256: str,
    ) -> EnergyRefinementAttempt:
        fingerprint = _digest(
            source_proposal_fingerprint_sha256,
            name="source_proposal_fingerprint_sha256",
        )
        try:
            return self._attempts[fingerprint]
        except KeyError as exc:
            raise EnergyRefinementError(
                "no energy-refinement attempt exists for proposal"
            ) from exc

    def _assert_inputs(self, proposal: DockingProposal, max_steps: int) -> int:
        if not isinstance(proposal, DockingProposal):
            raise TypeError("proposal must be DockingProposal")
        proposal.assert_integrity()
        if (
            proposal.problem_fingerprint_sha256 != self.problem_fingerprint_sha256
            or proposal.search_space_fingerprint_sha256
            != self._authority.search_space.fingerprint_sha256
            or tuple(proposal.coordinates.shape)
            != (self._authority.search_space.atom_count, 3)
            or tuple(proposal.torsion_angles.shape)
            != (self._authority.search_space.atom_count,)
            or proposal.coordinates.dtype != torch.float64
        ):
            raise EnergyRefinementError("refinement proposal is cross-wired")
        steps = _exact_int(
            max_steps,
            name="max_steps",
            minimum=1,
            maximum=self._config.minimization.max_iterations,
        )
        if (
            proposal.fingerprint_sha256 not in self._attempts
            and len(self._attempts) >= self._config.max_attempts
        ):
            raise EnergyRefinementError("energy-refinement attempt capacity exceeded")
        self._authority.input_receipt_sha256
        self._config.fingerprint_sha256
        self.parameter_fingerprint_sha256
        try:
            source_system_sha256 = canonical_system_sha256(self._ligand_system)
            source_topology_sha256 = canonical_topology_sha256(self._ligand_system)
        except (TypeError, ValueError, RuntimeError) as exc:
            raise EnergyRefinementError("refiner source state changed") from exc
        if (
            source_system_sha256 != self._authority.ligand_system_sha256
            or source_topology_sha256 != self._parameters.topology_sha256
        ):
            raise EnergyRefinementError("refiner source state changed")
        return steps

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        steps = self._assert_inputs(proposal, max_steps)
        if proposal.fingerprint_sha256 in self._attempts:
            raise EnergyRefinementError("proposal refinement was already attempted")
        pre_coordinates = (
            proposal.coordinates.detach()
            .to(dtype=torch.float64, device="cpu")
            .clone()
            .contiguous()
        )
        effective_config = replace(
            self._config.minimization,
            max_iterations=steps,
        )
        common = {
            "candidate_id": proposal.candidate_id,
            "proposal_index": proposal.proposal_index,
            "source_proposal_fingerprint_sha256": proposal.fingerprint_sha256,
            "authority_input_receipt_sha256": self._authority.input_receipt_sha256,
            "ligand_system_sha256": self._authority.ligand_system_sha256,
            "parameter_fingerprint_sha256": self._parameter_fingerprint_sha256,
            "parameter_set_id": self._parameters.parameter_set_id,
            "parameter_set_version": self._parameters.parameter_set_version,
            "implementation_source_sha256": self._implementation_source_sha256,
            "refiner_config_fingerprint_sha256": self._config.fingerprint_sha256,
            "effective_minimization_config_fingerprint_sha256": (
                effective_config.fingerprint_sha256
            ),
            "max_steps": steps,
            "maximum_atom_displacement_per_step_angstrom": (
                effective_config.maximum_atom_displacement_angstrom
            ),
            "pre_coordinates_sha256": coordinate_fingerprint(pre_coordinates),
            "pre_coordinates_binary64_hex": _coordinate_hex(pre_coordinates),
        }
        try:
            source = self._ligand_system.with_coordinates(
                pre_coordinates.unsqueeze(0),
                operation="docking_energy_local_refinement_input",
            )
            result = minimize_reference_force_field(
                source,
                self._parameters,
                effective_config,
            )
            post_coordinates = (
                result.system.coordinates[0]
                .detach()
                .to(dtype=torch.float64, device="cpu")
                .clone()
                .contiguous()
            )
            maximum_displacement = float(
                torch.linalg.vector_norm(
                    post_coordinates - pre_coordinates,
                    dim=-1,
                )
                .max()
                .item()
            )
            attempt = EnergyRefinementAttempt(
                **common,
                status="success",
                post_coordinates_sha256=coordinate_fingerprint(post_coordinates),
                post_coordinates_binary64_hex=_coordinate_hex(post_coordinates),
                initial_energy_kcal_per_mol=result.initial_energy_kcal_per_mol,
                final_energy_kcal_per_mol=result.final_energy_kcal_per_mol,
                energy_delta_kcal_per_mol=(
                    result.final_energy_kcal_per_mol
                    - result.initial_energy_kcal_per_mol
                ),
                maximum_displacement_angstrom=maximum_displacement,
                minimization_status=result.status,
                minimization_failure_code=str(result.failure_code or ""),
                converged=result.converged,
                accepted_iterations=result.accepted_iterations,
                rejected_evaluations=result.rejected_evaluations,
                evaluation_count=result.evaluation_count,
                checkpoint_sha256=result.checkpoint.checkpoint_sha256,
            )
            refined = proposal.with_refined_coordinates(
                post_coordinates.to(dtype=proposal.coordinates.dtype),
                refiner_id=self.refiner_id,
                refiner_version=self.refiner_version,
                refinement_receipt_sha256=attempt.receipt_sha256,
            )
            self._attempts[proposal.fingerprint_sha256] = attempt
            self._assert_inputs(proposal, steps)
            return refined
        except Exception as exc:
            receipt = failure_receipt(
                exc,
                public_message="energy-based local refinement failed",
            )
            attempt = EnergyRefinementAttempt(
                **common,
                status="failure",
                public_error_code=receipt.public_error_code,
                private_error_sha256=receipt.private_error_sha256,
                private_error_byte_length=receipt.private_error_byte_length,
            )
            self._attempts[proposal.fingerprint_sha256] = attempt
            if isinstance(exc, EnergyRefinementError):
                raise
            raise EnergyRefinementError("energy-based local refinement failed") from exc


@dataclass(frozen=True, slots=True)
class EnergyRefinementSearchRow:
    """One scorer-v1 search row bound to its exact refinement attempt."""

    candidate_id: str
    proposal_index: int
    search_status: str
    scorer_v1_row_receipt_sha256: str
    source_proposal_fingerprint_sha256: str
    result_proposal_fingerprint_sha256: str
    attempt: EnergyRefinementAttempt
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        candidate_id = str(self.candidate_id or "").strip()
        if not candidate_id:
            raise EnergyRefinementError(
                "energy-refinement search candidate ID is empty"
            )
        proposal_index = _exact_int(
            self.proposal_index,
            name="proposal_index",
            minimum=0,
            maximum=MAX_ENERGY_REFINEMENT_ATTEMPTS,
        )
        search_status = str(self.search_status or "").strip()
        if search_status not in {"success", "failure"}:
            raise EnergyRefinementError(
                "energy-refinement search row status is invalid"
            )
        scorer_receipt = _digest(
            self.scorer_v1_row_receipt_sha256,
            name="scorer_v1_row_receipt_sha256",
        )
        source_fingerprint = _digest(
            self.source_proposal_fingerprint_sha256,
            name="source_proposal_fingerprint_sha256",
        )
        result_fingerprint = _digest(
            self.result_proposal_fingerprint_sha256,
            name="result_proposal_fingerprint_sha256",
            allow_empty=True,
        )
        if not isinstance(self.attempt, EnergyRefinementAttempt):
            raise TypeError("attempt must be EnergyRefinementAttempt")
        if (
            self.attempt.candidate_id != candidate_id
            or self.attempt.proposal_index != proposal_index
            or self.attempt.source_proposal_fingerprint_sha256 != source_fingerprint
        ):
            raise EnergyRefinementError(
                "energy-refinement search row attempt is cross-wired"
            )
        if search_status == "success":
            if self.attempt.status != "success" or not result_fingerprint:
                raise EnergyRefinementError(
                    "successful search row lacks successful refinement evidence"
                )
        elif result_fingerprint:
            raise EnergyRefinementError(
                "failed search row cannot fabricate a result proposal"
            )
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "proposal_index", proposal_index)
        object.__setattr__(self, "search_status", search_status)
        object.__setattr__(
            self,
            "scorer_v1_row_receipt_sha256",
            scorer_receipt,
        )
        object.__setattr__(
            self,
            "source_proposal_fingerprint_sha256",
            source_fingerprint,
        )
        object.__setattr__(
            self,
            "result_proposal_fingerprint_sha256",
            result_fingerprint,
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": ENERGY_REFINEMENT_SEARCH_ROW_SCHEMA_ID,
            "candidate_id": self.candidate_id,
            "proposal_index": self.proposal_index,
            "search_status": self.search_status,
            "scorer_v1_row_receipt_sha256": self.scorer_v1_row_receipt_sha256,
            "source_proposal_fingerprint_sha256": (
                self.source_proposal_fingerprint_sha256
            ),
            "result_proposal_fingerprint_sha256": (
                self.result_proposal_fingerprint_sha256
            ),
            "refinement_attempt_receipt_sha256": self.attempt.receipt_sha256,
            "refinement_status": self.attempt.status,
            "failure_row_retained": self.search_status == "failure",
            "scope": "ligand_internal_coordinates_only",
            "receptor_ligand_interaction_energy_included": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise EnergyRefinementError("energy-refinement search row changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
            "attempt": self.attempt.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class EnergyRefinedGuidedSearchResult:
    """Failure-complete scorer-v1 result with exact local-refinement evidence."""

    scorer_v1_result: ScorerV1GuidedSearchResult
    refiner: EnergyBasedLocalRefiner = field(repr=False, compare=False)
    refiner_contract_fingerprint_sha256: str
    refiner_config_fingerprint_sha256: str
    parameter_fingerprint_sha256: str
    rows: tuple[EnergyRefinementSearchRow, ...]
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.scorer_v1_result, ScorerV1GuidedSearchResult):
            raise TypeError("scorer_v1_result must be ScorerV1GuidedSearchResult")
        if not isinstance(self.refiner, EnergyBasedLocalRefiner):
            raise TypeError("refiner must be EnergyBasedLocalRefiner")
        refiner_contract = _digest(
            self.refiner_contract_fingerprint_sha256,
            name="refiner_contract_fingerprint_sha256",
        )
        refiner_config = _digest(
            self.refiner_config_fingerprint_sha256,
            name="refiner_config_fingerprint_sha256",
        )
        parameter_fingerprint = _digest(
            self.parameter_fingerprint_sha256,
            name="parameter_fingerprint_sha256",
        )
        search = self.scorer_v1_result.guided_search_result.authenticated_search_result.search_result
        expected_contract = component_contract_fingerprint(
            self.refiner,
            kind="refiner",
            expected_problem_fingerprint_sha256=search.problem_fingerprint_sha256,
        )
        if (
            refiner_contract != expected_contract
            or search.refiner_contract_fingerprint_sha256 != refiner_contract
            or search.refiner_id != self.refiner.refiner_id
            or refiner_config != self.refiner.config_fingerprint_sha256
            or parameter_fingerprint != self.refiner.parameter_fingerprint_sha256
        ):
            raise EnergyRefinementError(
                "energy-refinement search refiner is cross-wired"
            )
        rows = tuple(self.rows)
        scorer_rows = self.scorer_v1_result.rows
        search_rows = search.rows
        if len(rows) != len(search_rows) or len(rows) != len(scorer_rows):
            raise EnergyRefinementError(
                "energy-refinement rows do not preserve the search denominator"
            )
        authority_receipt = self.scorer_v1_result.scorer_authority_input_receipt_sha256
        for retained, scorer_row, source in zip(
            rows,
            scorer_rows,
            search_rows,
            strict=True,
        ):
            if (
                retained.candidate_id != source.candidate_id
                or retained.proposal_index != source.proposal_index
                or retained.search_status != source.status
                or retained.scorer_v1_row_receipt_sha256 != scorer_row.receipt_sha256
                or retained.source_proposal_fingerprint_sha256
                != source.proposal_fingerprint_sha256
                or retained.result_proposal_fingerprint_sha256
                != source.result_proposal_fingerprint_sha256
            ):
                raise EnergyRefinementError(
                    "energy-refinement search row is cross-wired"
                )
            attempt = retained.attempt
            if (
                attempt.authority_input_receipt_sha256 != authority_receipt
                or attempt.ligand_system_sha256 != self.refiner.ligand_system_sha256
                or attempt.implementation_source_sha256
                != self.refiner.implementation_source_sha256
                or attempt.refiner_config_fingerprint_sha256 != refiner_config
                or attempt.parameter_fingerprint_sha256 != parameter_fingerprint
                or attempt.effective_minimization_config_fingerprint_sha256
                != replace(
                    self.refiner.config.minimization,
                    max_iterations=attempt.max_steps,
                ).fingerprint_sha256
                or attempt.maximum_atom_displacement_per_step_angstrom.hex()
                != self.refiner.config.minimization.maximum_atom_displacement_angstrom.hex()
                or attempt.receipt_sha256
                != self.refiner.attempt_for(
                    source.proposal_fingerprint_sha256
                ).receipt_sha256
            ):
                raise EnergyRefinementError(
                    "energy-refinement attempt identity is cross-wired"
                )
            if source.succeeded:
                assert source.proposal is not None
                if (
                    not source.refined
                    or source.proposal.parent_proposal_fingerprint_sha256
                    != source.proposal_fingerprint_sha256
                    or source.proposal.refinement_receipt_sha256
                    != attempt.receipt_sha256
                    or source.proposal.coordinate_fingerprint_sha256
                    != attempt.post_coordinates_sha256
                ):
                    raise EnergyRefinementError(
                        "refined proposal receipt is cross-wired"
                    )
            elif attempt.status == "success" and not source.refined:
                raise EnergyRefinementError(
                    "successful refinement is missing from failed search row"
                )
            elif attempt.status == "failure" and source.refined:
                raise EnergyRefinementError(
                    "failed refinement cannot mark a search row refined"
                )
        object.__setattr__(self, "rows", rows)
        object.__setattr__(
            self,
            "refiner_contract_fingerprint_sha256",
            refiner_contract,
        )
        object.__setattr__(
            self,
            "refiner_config_fingerprint_sha256",
            refiner_config,
        )
        object.__setattr__(
            self,
            "parameter_fingerprint_sha256",
            parameter_fingerprint,
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def success_count(self) -> int:
        return sum(row.search_status == "success" for row in self.rows)

    @property
    def failure_count(self) -> int:
        return len(self.rows) - self.success_count

    @property
    def refinement_success_count(self) -> int:
        return sum(row.attempt.status == "success" for row in self.rows)

    @property
    def refinement_failure_count(self) -> int:
        return len(self.rows) - self.refinement_success_count

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": ENERGY_REFINEMENT_SEARCH_RESULT_SCHEMA_ID,
            "scorer_v1_result_receipt_sha256": (self.scorer_v1_result.receipt_sha256),
            "refiner_contract_fingerprint_sha256": (
                self.refiner_contract_fingerprint_sha256
            ),
            "refiner_config_fingerprint_sha256": (
                self.refiner_config_fingerprint_sha256
            ),
            "parameter_fingerprint_sha256": self.parameter_fingerprint_sha256,
            "candidate_count": len(self.rows),
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "refinement_success_count": self.refinement_success_count,
            "refinement_failure_count": self.refinement_failure_count,
            "row_receipt_sha256s": [row.receipt_sha256 for row in self.rows],
            "failure_rows_retained": True,
            "pre_post_coordinates_retained": True,
            "energy_delta_retained": True,
            "maximum_displacement_retained": True,
            "convergence_evidence_retained": True,
            "exact_parameter_identity_retained": True,
            "scope": "ligand_internal_coordinates_only",
            "receptor_ligand_interaction_energy_included": False,
            "validated_for_docking_ranking": False,
            "scientifically_validated": False,
            "benchmark_validated": False,
            "claim_safe": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise EnergyRefinementError(
                "energy-refinement guided search result changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "receipt_sha256": self.receipt_sha256,
            "rows": [row.to_dict() for row in self.rows],
            "scorer_v1_result": self.scorer_v1_result.to_dict(),
        }


def run_authenticated_energy_refined_scorer_v1_guided_search(
    authenticated_problem: AuthenticatedDockingProblem,
    budget: DockingBudget,
    scorer: ChemistryPoseScorerV1,
    guided_context: GuidedPlacementContext,
    refiner: EnergyBasedLocalRefiner,
    *,
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    diversity_rmsd_angstrom: float = 0.5,
    diversity_metric: str = "direct_rmsd",
    symmetry_permutations=None,
) -> EnergyRefinedGuidedSearchResult:
    """Run scorer-v1 guided search and retain every refinement attempt."""

    if not isinstance(refiner, EnergyBasedLocalRefiner):
        raise TypeError("refiner must be EnergyBasedLocalRefiner")
    if budget.max_refinement_steps < 1:
        raise EnergyRefinementError(
            "energy-refined search requires max_refinement_steps >= 1"
        )
    if budget.max_refinement_steps > refiner.config.minimization.max_iterations:
        raise EnergyRefinementError(
            "search refinement steps exceed the refiner configuration"
        )
    if refiner.attempts:
        raise EnergyRefinementError(
            "energy-refined search requires a fresh refiner with no prior attempts"
        )
    if budget.candidate_count > refiner.config.max_attempts:
        raise EnergyRefinementError(
            "search candidate count exceeds the refinement attempt capacity"
        )
    if (
        refiner.problem_fingerprint_sha256
        != authenticated_problem.problem.fingerprint_sha256
        or refiner.authority_input_receipt_sha256
        != authenticated_problem.input_receipt_sha256
    ):
        raise EnergyRefinementError("energy refiner authority is cross-wired")
    result = run_authenticated_scorer_v1_guided_search(
        authenticated_problem,
        budget,
        scorer,
        guided_context,
        receptor_system=receptor_system,
        ligand_system=ligand_system,
        refiner=refiner,
        diversity_rmsd_angstrom=diversity_rmsd_angstrom,
        diversity_metric=diversity_metric,
        symmetry_permutations=symmetry_permutations,
    )
    search = result.guided_search_result.authenticated_search_result.search_result
    rows = tuple(
        EnergyRefinementSearchRow(
            candidate_id=source.candidate_id,
            proposal_index=source.proposal_index,
            search_status=source.status,
            scorer_v1_row_receipt_sha256=scorer_row.receipt_sha256,
            source_proposal_fingerprint_sha256=(source.proposal_fingerprint_sha256),
            result_proposal_fingerprint_sha256=(
                source.result_proposal_fingerprint_sha256
            ),
            attempt=refiner.attempt_for(source.proposal_fingerprint_sha256),
        )
        for scorer_row, source in zip(result.rows, search.rows, strict=True)
    )
    return EnergyRefinedGuidedSearchResult(
        scorer_v1_result=result,
        refiner=refiner,
        refiner_contract_fingerprint_sha256=(
            search.refiner_contract_fingerprint_sha256
        ),
        refiner_config_fingerprint_sha256=refiner.config_fingerprint_sha256,
        parameter_fingerprint_sha256=refiner.parameter_fingerprint_sha256,
        rows=rows,
    )


__all__ = [
    "ENERGY_REFINEMENT_ATTEMPT_SCHEMA_ID",
    "ENERGY_REFINEMENT_CONFIG_SCHEMA_ID",
    "ENERGY_REFINEMENT_SEARCH_RESULT_SCHEMA_ID",
    "ENERGY_REFINEMENT_SEARCH_ROW_SCHEMA_ID",
    "ENERGY_REFINER_ALGORITHM_ID",
    "ENERGY_REFINER_ID",
    "ENERGY_REFINER_VERSION",
    "MAX_ENERGY_REFINEMENT_ATTEMPTS",
    "EnergyBasedLocalRefiner",
    "EnergyLocalRefinementConfig",
    "EnergyRefinedGuidedSearchResult",
    "EnergyRefinementAttempt",
    "EnergyRefinementError",
    "EnergyRefinementSearchRow",
    "run_authenticated_energy_refined_scorer_v1_guided_search",
]
