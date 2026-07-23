"""Uncalibrated PDBQT-charge and RDKit-UFF docking diagnostics.

This module is intentionally separate from :mod:`reference_scoring`.  It
accepts explicit nonbonded parameters derived from a bound PDBQT preparation
and delegates ligand intramolecular energy to an exact, provenance-bearing
evaluator such as RDKit UFF.  The four returned terms mirror the reference
scorer decomposition, but they are a test-only diagnostic and are not a
validated force field, docking score, or affinity model.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
from typing import Protocol

import numpy as np

from betelgeuze_engine_v2.physics.reference_parameters import (
    COULOMB_KCAL_ANGSTROM_PER_MOL_E2,
)

from .scoring import (
    DockingScoreBreakdown,
    DockingScoreDescriptor,
    DockingScoreTerm,
    ScoreDirection,
)


PDBQT_UFF_DIAGNOSTIC_SCORER_SCHEMA_ID = (
    "betelgeuze.engine_v2_pdbqt_uff_diagnostic_scorer/1.0.0"
)
PDBQT_UFF_NONBONDED_ATOM_PARAMETER_SCHEMA_ID = (
    "betelgeuze.engine_v2_pdbqt_uff_nonbonded_atom_parameter/1.0.0"
)
PDBQT_UFF_DIAGNOSTIC_SCORE_DIAGNOSTICS_SCHEMA_ID = (
    "betelgeuze.engine_v2_pdbqt_uff_diagnostic_score_diagnostics/1.0.0"
)
PDBQT_UFF_DIAGNOSTIC_SUPPORTED_ATOMIC_NUMBERS = (
    1,
    6,
    7,
    8,
    9,
    15,
    16,
    17,
    35,
    53,
)


class PdbqtUffDiagnosticScoringError(ValueError):
    """A diagnostic score input exceeds the frozen bounded contract."""


def _canonical_sha256(value: object) -> str:
    source = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(source).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PdbqtUffDiagnosticScoringError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _text(value: object, *, name: str, maximum: int = 256) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > maximum
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PdbqtUffDiagnosticScoringError(
            f"{name} must be bounded single-line text"
        )
    return value


def _finite(
    value: object,
    *,
    name: str,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PdbqtUffDiagnosticScoringError(f"{name} must be a finite real")
    result = float(value)
    if not math.isfinite(result):
        raise PdbqtUffDiagnosticScoringError(f"{name} must be finite")
    if positive and result <= 0.0:
        raise PdbqtUffDiagnosticScoringError(f"{name} must be positive")
    if nonnegative and result < 0.0:
        raise PdbqtUffDiagnosticScoringError(f"{name} must be non-negative")
    return result


def _integer(
    value: object,
    *,
    name: str,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    if type(value) is not int or value < minimum:
        raise PdbqtUffDiagnosticScoringError(
            f"{name} must be an integer >= {minimum}"
        )
    if maximum is not None and value > maximum:
        raise PdbqtUffDiagnosticScoringError(
            f"{name} must be an integer <= {maximum}"
        )
    return value


def _coordinates(
    value: object,
    *,
    name: str,
    atom_count: int | None = None,
) -> np.ndarray:
    if not isinstance(value, np.ndarray) or value.dtype != np.float64:
        raise PdbqtUffDiagnosticScoringError(
            f"{name} must be a NumPy float64 array"
        )
    expected = atom_count if atom_count is not None else value.shape[0]
    if value.ndim != 2 or value.shape != (expected, 3) or expected < 1:
        raise PdbqtUffDiagnosticScoringError(
            f"{name} must have shape [atom_count,3]"
        )
    if not bool(np.isfinite(value).all()):
        raise PdbqtUffDiagnosticScoringError(f"{name} must be finite")
    result = np.array(value, dtype=np.float64, copy=True, order="C")
    result.setflags(write=False)
    return result


def coordinate_sha256(value: np.ndarray) -> str:
    """Return a platform-independent identity for one float64 coordinate set."""

    coordinates = _coordinates(value, name="coordinates")
    little_endian = np.asarray(coordinates, dtype="<f8", order="C")
    descriptor = json.dumps(
        {
            "dtype": "float64-little-endian",
            "shape": list(little_endian.shape),
            "unit": "angstrom",
        },
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    digest = hashlib.sha256()
    digest.update(descriptor)
    digest.update(b"\x00")
    digest.update(little_endian.tobytes(order="C"))
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class PdbqtUffNonbondedAtomParameter:
    """One explicit PDBQT charge plus UFF self-vdW parameter row."""

    atom_id: str
    atomic_number: int
    partial_charge_e: float
    uff_x1_angstrom: float
    uff_d1_kcal_per_mol: float
    autodock4_atom_type: str
    parameter_source_sha256: str
    schema_id: str = PDBQT_UFF_NONBONDED_ATOM_PARAMETER_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PDBQT_UFF_NONBONDED_ATOM_PARAMETER_SCHEMA_ID:
            raise PdbqtUffDiagnosticScoringError(
                "unsupported nonbonded atom-parameter schema"
            )
        object.__setattr__(
            self,
            "atom_id",
            _text(self.atom_id, name="atom ID"),
        )
        atomic_number = _integer(
            self.atomic_number,
            name="atomic number",
            minimum=1,
            maximum=118,
        )
        if atomic_number not in PDBQT_UFF_DIAGNOSTIC_SUPPORTED_ATOMIC_NUMBERS:
            raise PdbqtUffDiagnosticScoringError(
                f"atomic number {atomic_number} is outside the diagnostic scope"
            )
        object.__setattr__(self, "atomic_number", atomic_number)
        object.__setattr__(
            self,
            "partial_charge_e",
            _finite(self.partial_charge_e, name="partial charge"),
        )
        object.__setattr__(
            self,
            "uff_x1_angstrom",
            _finite(
                self.uff_x1_angstrom,
                name="UFF x1",
                positive=True,
            ),
        )
        object.__setattr__(
            self,
            "uff_d1_kcal_per_mol",
            _finite(
                self.uff_d1_kcal_per_mol,
                name="UFF D1",
                positive=True,
            ),
        )
        object.__setattr__(
            self,
            "autodock4_atom_type",
            _text(
                self.autodock4_atom_type,
                name="AutoDock4 atom type",
                maximum=8,
            ),
        )
        object.__setattr__(
            self,
            "parameter_source_sha256",
            _digest(
                self.parameter_source_sha256,
                name="atom parameter source",
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "atom_id": self.atom_id,
            "atomic_number": self.atomic_number,
            "partial_charge_e": self.partial_charge_e,
            "partial_charge_binary64_hex": self.partial_charge_e.hex(),
            "uff_x1_angstrom": self.uff_x1_angstrom,
            "uff_x1_binary64_hex": self.uff_x1_angstrom.hex(),
            "uff_d1_kcal_per_mol": self.uff_d1_kcal_per_mol,
            "uff_d1_binary64_hex": self.uff_d1_kcal_per_mol.hex(),
            "autodock4_atom_type": self.autodock4_atom_type,
            "parameter_source_sha256": self.parameter_source_sha256,
        }


class LigandStrainEnergyEvaluator(Protocol):
    """Exact bound intramolecular-energy adapter used by the scorer."""

    evaluator_id: str
    evaluator_version: str
    source_atom_count: int
    parameter_source_sha256: str
    config_fingerprint_sha256: str

    def energy_kcal_per_mol(self, coordinates: np.ndarray) -> float: ...


@dataclass(frozen=True, slots=True)
class PdbqtUffDiagnosticScoreConfig:
    """Frozen numerical policy for the uncalibrated four-term score."""

    cutoff_angstrom: float = 8.0
    switch_start_angstrom: float = 6.0
    dielectric: float = 4.0
    screening_kappa_per_angstrom: float = 0.0
    softcore_distance_angstrom: float = 0.35
    clash_contact_scale: float = 0.75
    clash_force_constant_kcal_per_mol_angstrom2: float = 10.0
    uff_cross_vdw_weight: float = 1.0
    pdbqt_coulomb_weight: float = 1.0
    rdkit_uff_strain_weight: float = 1.0
    overlap_weight: float = 1.0
    max_cross_pairs: int = 1_000_000
    max_ligand_atoms: int = 256
    schema_id: str = PDBQT_UFF_DIAGNOSTIC_SCORER_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PDBQT_UFF_DIAGNOSTIC_SCORER_SCHEMA_ID:
            raise PdbqtUffDiagnosticScoringError(
                "unsupported diagnostic scorer schema"
            )
        cutoff = _finite(
            self.cutoff_angstrom,
            name="cutoff_angstrom",
            positive=True,
        )
        switch = _finite(
            self.switch_start_angstrom,
            name="switch_start_angstrom",
            nonnegative=True,
        )
        if switch >= cutoff:
            raise PdbqtUffDiagnosticScoringError(
                "switch_start_angstrom must be less than cutoff_angstrom"
            )
        object.__setattr__(self, "cutoff_angstrom", cutoff)
        object.__setattr__(self, "switch_start_angstrom", switch)
        for field_name in (
            "dielectric",
            "softcore_distance_angstrom",
            "clash_contact_scale",
            "clash_force_constant_kcal_per_mol_angstrom2",
        ):
            object.__setattr__(
                self,
                field_name,
                _finite(
                    getattr(self, field_name),
                    name=field_name,
                    positive=True,
                ),
            )
        object.__setattr__(
            self,
            "screening_kappa_per_angstrom",
            _finite(
                self.screening_kappa_per_angstrom,
                name="screening_kappa_per_angstrom",
                nonnegative=True,
            ),
        )
        for field_name in (
            "uff_cross_vdw_weight",
            "pdbqt_coulomb_weight",
            "rdkit_uff_strain_weight",
            "overlap_weight",
        ):
            object.__setattr__(
                self,
                field_name,
                _finite(
                    getattr(self, field_name),
                    name=field_name,
                    nonnegative=True,
                ),
            )
        object.__setattr__(
            self,
            "max_cross_pairs",
            _integer(
                self.max_cross_pairs,
                name="max_cross_pairs",
                minimum=1,
            ),
        )
        object.__setattr__(
            self,
            "max_ligand_atoms",
            _integer(
                self.max_ligand_atoms,
                name="max_ligand_atoms",
                minimum=1,
                maximum=256,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "cutoff_angstrom": self.cutoff_angstrom,
            "switch_start_angstrom": self.switch_start_angstrom,
            "dielectric": self.dielectric,
            "screening_kappa_per_angstrom": self.screening_kappa_per_angstrom,
            "softcore_distance_angstrom": self.softcore_distance_angstrom,
            "clash_contact_scale": self.clash_contact_scale,
            "clash_force_constant_kcal_per_mol_angstrom2": (
                self.clash_force_constant_kcal_per_mol_angstrom2
            ),
            "uff_cross_vdw_weight": self.uff_cross_vdw_weight,
            "pdbqt_coulomb_weight": self.pdbqt_coulomb_weight,
            "rdkit_uff_strain_weight": self.rdkit_uff_strain_weight,
            "overlap_weight": self.overlap_weight,
            "max_cross_pairs": self.max_cross_pairs,
            "max_ligand_atoms": self.max_ligand_atoms,
            "cross_vdw_formula": "Dij*((xij/r_soft)^12-2*(xij/r_soft)^6)",
            "uff_combining_rule": "xij=sqrt(x1_i*x1_j),Dij=sqrt(D1_i*D1_j)",
            "cross_switch_policy": "quintic_6_to_8_angstrom",
            "ligand_strain_policy": (
                "signed_exact_bound_evaluator_energy_delta_from_prepared_conformer"
            ),
            "score_direction": "minimize",
            "calibrated": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class PdbqtUffDiagnosticScoreDiagnostics:
    """Bound interaction and strain observations for one scored pose."""

    candidate_id: str
    coordinate_sha256: str
    scorer_fingerprint_sha256: str
    parameter_source_sha256: str
    total_cross_pair_count: int
    evaluated_cross_pair_count: int
    clashing_cross_pair_count: int
    excluded_ligand_pseudoatom_count: int
    minimum_cross_distance_angstrom: float | None
    maximum_cross_overlap_angstrom: float
    ligand_reference_energy_kcal_per_mol: float
    ligand_pose_energy_kcal_per_mol: float
    schema_id: str = PDBQT_UFF_DIAGNOSTIC_SCORE_DIAGNOSTICS_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != PDBQT_UFF_DIAGNOSTIC_SCORE_DIAGNOSTICS_SCHEMA_ID:
            raise PdbqtUffDiagnosticScoringError(
                "unsupported diagnostic observation schema"
            )
        object.__setattr__(
            self,
            "candidate_id",
            _text(self.candidate_id, name="candidate ID"),
        )
        for field_name in (
            "coordinate_sha256",
            "scorer_fingerprint_sha256",
            "parameter_source_sha256",
        ):
            object.__setattr__(
                self,
                field_name,
                _digest(
                    getattr(self, field_name),
                    name=field_name.replace("_", " "),
                ),
            )
        total = _integer(
            self.total_cross_pair_count,
            name="total cross-pair count",
        )
        evaluated = _integer(
            self.evaluated_cross_pair_count,
            name="evaluated cross-pair count",
        )
        clashing = _integer(
            self.clashing_cross_pair_count,
            name="clashing cross-pair count",
        )
        if evaluated > total or clashing > evaluated:
            raise PdbqtUffDiagnosticScoringError(
                "cross-pair diagnostic counts are inconsistent"
            )
        object.__setattr__(
            self,
            "excluded_ligand_pseudoatom_count",
            _integer(
                self.excluded_ligand_pseudoatom_count,
                name="excluded ligand pseudoatom count",
            ),
        )
        if evaluated:
            object.__setattr__(
                self,
                "minimum_cross_distance_angstrom",
                _finite(
                    self.minimum_cross_distance_angstrom,
                    name="minimum cross distance",
                    nonnegative=True,
                ),
            )
        elif self.minimum_cross_distance_angstrom is not None:
            raise PdbqtUffDiagnosticScoringError(
                "empty evaluated pairs cannot expose a minimum distance"
            )
        for field_name in (
            "maximum_cross_overlap_angstrom",
            "ligand_reference_energy_kcal_per_mol",
            "ligand_pose_energy_kcal_per_mol",
        ):
            object.__setattr__(
                self,
                field_name,
                _finite(
                    getattr(self, field_name),
                    name=field_name.replace("_", " "),
                    nonnegative=field_name == "maximum_cross_overlap_angstrom",
                ),
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "candidate_id": self.candidate_id,
            "coordinate_sha256": self.coordinate_sha256,
            "scorer_fingerprint_sha256": self.scorer_fingerprint_sha256,
            "parameter_source_sha256": self.parameter_source_sha256,
            "total_cross_pair_count": self.total_cross_pair_count,
            "evaluated_cross_pair_count": self.evaluated_cross_pair_count,
            "clashing_cross_pair_count": self.clashing_cross_pair_count,
            "excluded_ligand_pseudoatom_count": (
                self.excluded_ligand_pseudoatom_count
            ),
            "minimum_cross_distance_angstrom": (
                self.minimum_cross_distance_angstrom
            ),
            "minimum_cross_distance_binary64_hex": (
                None
                if self.minimum_cross_distance_angstrom is None
                else self.minimum_cross_distance_angstrom.hex()
            ),
            "maximum_cross_overlap_angstrom": (
                self.maximum_cross_overlap_angstrom
            ),
            "maximum_cross_overlap_binary64_hex": (
                self.maximum_cross_overlap_angstrom.hex()
            ),
            "ligand_reference_energy_kcal_per_mol": (
                self.ligand_reference_energy_kcal_per_mol
            ),
            "ligand_reference_energy_binary64_hex": (
                self.ligand_reference_energy_kcal_per_mol.hex()
            ),
            "ligand_pose_energy_kcal_per_mol": (
                self.ligand_pose_energy_kcal_per_mol
            ),
            "ligand_pose_energy_binary64_hex": (
                self.ligand_pose_energy_kcal_per_mol.hex()
            ),
        }


def _parameter_vectors(
    parameters: tuple[PdbqtUffNonbondedAtomParameter, ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    charges = np.asarray(
        [row.partial_charge_e for row in parameters],
        dtype=np.float64,
    )
    x1 = np.asarray(
        [row.uff_x1_angstrom for row in parameters],
        dtype=np.float64,
    )
    d1 = np.asarray(
        [row.uff_d1_kcal_per_mol for row in parameters],
        dtype=np.float64,
    )
    for value in (charges, x1, d1):
        value.setflags(write=False)
    return charges, x1, d1


def _switch(distance: np.ndarray, start: float, cutoff: float) -> np.ndarray:
    fraction = np.clip((distance - start) / (cutoff - start), 0.0, 1.0)
    smooth = (
        1.0
        - 10.0 * fraction**3
        + 15.0 * fraction**4
        - 6.0 * fraction**5
    )
    return np.where(
        distance <= start,
        1.0,
        np.where(distance < cutoff, smooth, 0.0),
    )


class UncalibratedPdbqtUffDiagnosticScorer:
    """CPU float64 four-term diagnostic over explicit PDBQT/UFF parameters."""

    scorer_id = "uncalibrated-pdbqt-charge-rdkit-uff-diagnostic"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False

    def __init__(
        self,
        receptor_coordinates: np.ndarray,
        receptor_parameters: tuple[PdbqtUffNonbondedAtomParameter, ...],
        ligand_reference_coordinates: np.ndarray,
        ligand_parameters: tuple[PdbqtUffNonbondedAtomParameter, ...],
        ligand_strain_source_atom_indices: tuple[int, ...],
        strain_evaluator: LigandStrainEnergyEvaluator,
        *,
        excluded_ligand_pseudoatom_count: int = 0,
        config: PdbqtUffDiagnosticScoreConfig | None = None,
    ) -> None:
        self.config = config or PdbqtUffDiagnosticScoreConfig()
        self.receptor_parameters = tuple(receptor_parameters)
        self.ligand_parameters = tuple(ligand_parameters)
        if (
            not self.receptor_parameters
            or not self.ligand_parameters
            or not all(
                isinstance(row, PdbqtUffNonbondedAtomParameter)
                for row in (*self.receptor_parameters, *self.ligand_parameters)
            )
        ):
            raise PdbqtUffDiagnosticScoringError(
                "scorer parameters must contain explicit atom rows"
            )
        if len({row.atom_id for row in self.receptor_parameters}) != len(
            self.receptor_parameters
        ) or len({row.atom_id for row in self.ligand_parameters}) != len(
            self.ligand_parameters
        ):
            raise PdbqtUffDiagnosticScoringError(
                "atom parameter IDs must be unique within each molecule"
            )
        self.receptor_coordinates = _coordinates(
            receptor_coordinates,
            name="receptor coordinates",
            atom_count=len(self.receptor_parameters),
        )
        self.ligand_reference_coordinates = _coordinates(
            ligand_reference_coordinates,
            name="ligand reference coordinates",
            atom_count=len(self.ligand_parameters),
        )
        if len(self.ligand_parameters) > self.config.max_ligand_atoms:
            raise PdbqtUffDiagnosticScoringError(
                "ligand atom count exceeds the configured bound"
            )
        pair_count = len(self.receptor_parameters) * len(self.ligand_parameters)
        if pair_count > self.config.max_cross_pairs:
            raise PdbqtUffDiagnosticScoringError(
                "receptor-ligand cross-pair capacity exceeded"
            )
        source_indices = tuple(
            _integer(
                value,
                name="ligand strain source atom index",
                minimum=0,
                maximum=len(self.ligand_parameters) - 1,
            )
            for value in ligand_strain_source_atom_indices
        )
        if not source_indices or len(set(source_indices)) != len(source_indices):
            raise PdbqtUffDiagnosticScoringError(
                "ligand strain source atom indices must be unique and non-empty"
            )
        required_evaluator_fields = (
            "evaluator_id",
            "evaluator_version",
            "source_atom_count",
            "parameter_source_sha256",
            "config_fingerprint_sha256",
        )
        if not callable(getattr(strain_evaluator, "energy_kcal_per_mol", None)) or any(
            not hasattr(strain_evaluator, field_name)
            for field_name in required_evaluator_fields
        ):
            raise PdbqtUffDiagnosticScoringError(
                "strain evaluator does not expose the required bound contract"
            )
        if _integer(
            strain_evaluator.source_atom_count,
            name="strain evaluator source atom count",
            minimum=1,
        ) != len(source_indices):
            raise PdbqtUffDiagnosticScoringError(
                "strain evaluator atom count does not match its ligand projection"
            )
        _text(strain_evaluator.evaluator_id, name="strain evaluator ID")
        _text(strain_evaluator.evaluator_version, name="strain evaluator version")
        _digest(
            strain_evaluator.parameter_source_sha256,
            name="strain evaluator parameter source",
        )
        _digest(
            strain_evaluator.config_fingerprint_sha256,
            name="strain evaluator config fingerprint",
        )
        self.ligand_strain_source_atom_indices = source_indices
        self.strain_evaluator = strain_evaluator
        self.excluded_ligand_pseudoatom_count = _integer(
            excluded_ligand_pseudoatom_count,
            name="excluded ligand pseudoatom count",
        )
        (
            self._receptor_charges,
            self._receptor_x1,
            self._receptor_d1,
        ) = _parameter_vectors(self.receptor_parameters)
        (
            self._ligand_charges,
            self._ligand_x1,
            self._ligand_d1,
        ) = _parameter_vectors(self.ligand_parameters)
        parameter_payload = {
            "schema_id": PDBQT_UFF_NONBONDED_ATOM_PARAMETER_SCHEMA_ID,
            "receptor_parameters": [
                row.to_dict() for row in self.receptor_parameters
            ],
            "ligand_parameters": [row.to_dict() for row in self.ligand_parameters],
            "ligand_strain_source_atom_indices": list(source_indices),
            "strain_evaluator": {
                "evaluator_id": strain_evaluator.evaluator_id,
                "evaluator_version": strain_evaluator.evaluator_version,
                "parameter_source_sha256": (
                    strain_evaluator.parameter_source_sha256
                ),
                "config_fingerprint_sha256": (
                    strain_evaluator.config_fingerprint_sha256
                ),
            },
            "excluded_ligand_pseudoatom_count": (
                self.excluded_ligand_pseudoatom_count
            ),
        }
        self.parameter_source_sha256 = _canonical_sha256(parameter_payload)
        self._ligand_reference_energy = _finite(
            strain_evaluator.energy_kcal_per_mol(
                self.ligand_reference_coordinates[
                    np.asarray(source_indices, dtype=np.int64)
                ]
            ),
            name="ligand reference strain energy",
        )
        self.config_fingerprint_sha256 = _canonical_sha256(
            {
                "schema_id": PDBQT_UFF_DIAGNOSTIC_SCORER_SCHEMA_ID,
                "config_sha256": self.config.fingerprint_sha256,
                "parameter_source_sha256": self.parameter_source_sha256,
                "receptor_coordinate_sha256": coordinate_sha256(
                    self.receptor_coordinates
                ),
                "ligand_reference_coordinate_sha256": coordinate_sha256(
                    self.ligand_reference_coordinates
                ),
            }
        )
        self.score_descriptor = DockingScoreDescriptor(
            score_id="uncalibrated_pdbqt_charge_rdkit_uff_diagnostic",
            direction=ScoreDirection.MINIMIZE,
            unit="kcal/mol",
            semantics=(
                "fixed_sum_of_softcore_switched_uff_cross_vdw_pdbqt_charge_"
                "coulomb_exact_bound_rdkit_uff_source_atom_strain_delta_and_"
                "quadratic_overlap"
            ),
            calibrated=False,
            applicability_domain_id=self.config_fingerprint_sha256,
        )
        self._blockers = (
            "diagnostic_score_not_a_validated_force_field",
            "diagnostic_score_uncalibrated",
            "pdbqt_partial_charges_are_not_an_independent_charge_oracle",
            "uff_element_vdw_is_not_calibrated_docking_atom_typing",
            "ligand_strain_uses_only_embedded_smiles_source_atoms",
            "implicit_and_merged_hydrogen_coordinates_are_absent_from_strain",
            "receptor_internal_energy_and_flexibility_are_omitted",
            "solvation_and_directional_interactions_are_omitted",
            "metals_and_cofactors_are_outside_scope",
            "aromatic_and_stereo_validity_are_external_to_the_score",
            "holdout_calibration_and_independent_review_are_missing",
        )

    @property
    def ligand_reference_energy_kcal_per_mol(self) -> float:
        return self._ligand_reference_energy

    def score_coordinates(
        self,
        candidate_id: str,
        ligand_coordinates: np.ndarray,
    ) -> tuple[DockingScoreBreakdown, PdbqtUffDiagnosticScoreDiagnostics]:
        """Score one exact pose and return a complete four-term decomposition."""

        candidate = _text(candidate_id, name="candidate ID")
        coordinates = _coordinates(
            ligand_coordinates,
            name="ligand pose coordinates",
            atom_count=len(self.ligand_parameters),
        )
        delta = (
            self.receptor_coordinates[:, np.newaxis, :]
            - coordinates[np.newaxis, :, :]
        )
        full_distance = np.sqrt(np.sum(delta * delta, axis=2, dtype=np.float64))
        selected = full_distance < self.config.cutoff_angstrom
        receptor_indices, ligand_indices = np.nonzero(selected)
        raw_distance = full_distance[receptor_indices, ligand_indices]
        if raw_distance.size:
            effective_distance = np.sqrt(
                raw_distance * raw_distance
                + self.config.softcore_distance_angstrom**2
            )
            xij = np.sqrt(
                self._receptor_x1[receptor_indices]
                * self._ligand_x1[ligand_indices]
            )
            dij = np.sqrt(
                self._receptor_d1[receptor_indices]
                * self._ligand_d1[ligand_indices]
            )
            switching = _switch(
                raw_distance,
                self.config.switch_start_angstrom,
                self.config.cutoff_angstrom,
            )
            ratio6 = (xij / effective_distance) ** 6
            pair_vdw = dij * (ratio6 * ratio6 - 2.0 * ratio6) * switching
            uff_cross_vdw = float(np.sum(pair_vdw, dtype=np.float64))
            charge_product = (
                self._receptor_charges[receptor_indices]
                * self._ligand_charges[ligand_indices]
            )
            pair_coulomb = (
                COULOMB_KCAL_ANGSTROM_PER_MOL_E2
                / self.config.dielectric
                * charge_product
                * np.exp(
                    -self.config.screening_kappa_per_angstrom
                    * effective_distance
                )
                / effective_distance
                * switching
            )
            pdbqt_coulomb = float(np.sum(pair_coulomb, dtype=np.float64))
            contact_distance = self.config.clash_contact_scale * xij
            overlap = np.maximum(contact_distance - raw_distance, 0.0)
            overlap_penalty = float(
                self.config.clash_force_constant_kcal_per_mol_angstrom2
                * np.sum(overlap * overlap, dtype=np.float64)
            )
            clashing_count = int(np.count_nonzero(overlap > 0.0))
            minimum_distance = float(np.min(raw_distance))
            maximum_overlap = float(np.max(overlap))
        else:
            uff_cross_vdw = 0.0
            pdbqt_coulomb = 0.0
            overlap_penalty = 0.0
            clashing_count = 0
            minimum_distance = None
            maximum_overlap = 0.0
        source_coordinates = coordinates[
            np.asarray(self.ligand_strain_source_atom_indices, dtype=np.int64)
        ]
        pose_energy = _finite(
            self.strain_evaluator.energy_kcal_per_mol(source_coordinates),
            name="ligand pose strain energy",
        )
        strain_delta = pose_energy - self._ligand_reference_energy
        terms = (
            DockingScoreTerm(
                term_id="uff_receptor_ligand_vdw",
                raw_value=uff_cross_vdw,
                weight=self.config.uff_cross_vdw_weight,
                unit="kcal/mol",
                semantics=(
                    "softcore_switched_cross_uff_vdw_with_geometric_x1_D1_"
                    "combining"
                ),
                parameter_source_sha256=self.parameter_source_sha256,
            ),
            DockingScoreTerm(
                term_id="pdbqt_receptor_ligand_coulomb",
                raw_value=pdbqt_coulomb,
                weight=self.config.pdbqt_coulomb_weight,
                unit="kcal/mol",
                semantics=(
                    "softcore_switched_cross_coulomb_from_bound_pdbqt_partial_"
                    "charges"
                ),
                parameter_source_sha256=self.parameter_source_sha256,
            ),
            DockingScoreTerm(
                term_id="rdkit_uff_source_atom_strain_delta",
                raw_value=strain_delta,
                weight=self.config.rdkit_uff_strain_weight,
                unit="kcal/mol",
                semantics=(
                    "signed_exact_bound_rdkit_uff_source_atom_energy_delta_from_"
                    "the_prepared_ligand_conformer"
                ),
                parameter_source_sha256=(
                    self.strain_evaluator.parameter_source_sha256
                ),
            ),
            DockingScoreTerm(
                term_id="uff_vdw_overlap_penalty",
                raw_value=overlap_penalty,
                weight=self.config.overlap_weight,
                unit="kcal/mol",
                semantics=(
                    "quadratic_overlap_below_scaled_uff_xij_contact_distance"
                ),
                parameter_source_sha256=self.parameter_source_sha256,
            ),
        )
        breakdown = DockingScoreBreakdown(
            terms=terms,
            blockers=self._blockers,
        )
        diagnostics = PdbqtUffDiagnosticScoreDiagnostics(
            candidate_id=candidate,
            coordinate_sha256=coordinate_sha256(coordinates),
            scorer_fingerprint_sha256=self.config_fingerprint_sha256,
            parameter_source_sha256=self.parameter_source_sha256,
            total_cross_pair_count=(
                len(self.receptor_parameters) * len(self.ligand_parameters)
            ),
            evaluated_cross_pair_count=int(raw_distance.size),
            clashing_cross_pair_count=clashing_count,
            excluded_ligand_pseudoatom_count=(
                self.excluded_ligand_pseudoatom_count
            ),
            minimum_cross_distance_angstrom=minimum_distance,
            maximum_cross_overlap_angstrom=maximum_overlap,
            ligand_reference_energy_kcal_per_mol=(
                self._ligand_reference_energy
            ),
            ligand_pose_energy_kcal_per_mol=pose_energy,
        )
        return breakdown, diagnostics


__all__ = [
    "PDBQT_UFF_DIAGNOSTIC_SCORER_SCHEMA_ID",
    "PDBQT_UFF_DIAGNOSTIC_SCORE_DIAGNOSTICS_SCHEMA_ID",
    "PDBQT_UFF_DIAGNOSTIC_SUPPORTED_ATOMIC_NUMBERS",
    "PDBQT_UFF_NONBONDED_ATOM_PARAMETER_SCHEMA_ID",
    "LigandStrainEnergyEvaluator",
    "PdbqtUffDiagnosticScoreConfig",
    "PdbqtUffDiagnosticScoreDiagnostics",
    "PdbqtUffDiagnosticScoringError",
    "PdbqtUffNonbondedAtomParameter",
    "UncalibratedPdbqtUffDiagnosticScorer",
    "coordinate_sha256",
]
