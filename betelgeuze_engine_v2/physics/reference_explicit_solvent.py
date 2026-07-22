"""Deterministic bounded TIP3P water and monovalent-ion preparation.

The module composes a caller-parameterized solute with a frozen, source-bound
TIP3P/Na+/Cl- profile.  It creates real atoms, residues, bonds, angle terms,
nonbonded parameters, intramolecular exclusions, and rigid-water
SHAKE/RATTLE constraints in a fully periodic orthorhombic box.  Placement is a
deterministic lattice construction intended for implementation tests and
replay, not an equilibrated liquid or scientific solvation protocol.

The frozen profile is transcribed from the OpenMM Force Fields Amber TIP3P
standard XML snapshot identified below.  No source file is downloaded at
runtime.  The preparation remains claim-closed until independent energy,
force, liquid-property, cross-host, and external implementation evidence is
approved.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
from numbers import Real
import operator
from typing import Mapping

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    atomic_number_for_element,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
)
from .reference_ewald import REFERENCE_EWALD_MAX_ATOMS
from .reference_parameters import (
    AtomNonbondedParameter,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    ReferenceForceFieldParameters,
)
from .reference_shake_rattle import (
    ReferenceSHAKERATTLEConfig,
    ReferenceSHAKERATTLEDistanceConstraint,
    validate_reference_shake_rattle_inputs,
)


REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID = (
    "cpu_float64_deterministic_tip3p_jc_na_cl_lattice_preparation/1.0.0"
)
REFERENCE_EXPLICIT_SOLVENT_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_explicit_solvent_config/1.0.0"
)
REFERENCE_EXPLICIT_SOLVENT_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_explicit_solvent_receipt/1.0.0"
)
REFERENCE_EXPLICIT_SOLVENT_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_explicit_solvent_result/1.0.0"
)

REFERENCE_EXPLICIT_SOLVENT_PROFILE_ID = (
    "openmmforcefields_amber_tip3p_standard_na_cl"
)
REFERENCE_EXPLICIT_SOLVENT_PROFILE_VERSION = (
    "openmmforcefields-89cd3a18d19c207b595269f36cb7e0d63950944e"
)
REFERENCE_EXPLICIT_SOLVENT_PROFILE_SOURCE_URL = (
    "https://raw.githubusercontent.com/openmm/openmmforcefields/"
    "89cd3a18d19c207b595269f36cb7e0d63950944e/"
    "openmmforcefields/ffxml/amber/tip3p_standard.xml"
)
REFERENCE_EXPLICIT_SOLVENT_PROFILE_SOURCE_SHA256 = (
    "fc528100bfb3587f632c0492166026ed5658c897026de0408f371604a79271fc"
)
REFERENCE_EXPLICIT_SOLVENT_PRIMARY_REFERENCE_DOI = "10.1063/1.445869"
REFERENCE_EXPLICIT_ION_REFERENCE_DOI = "10.1021/jp8001614"

REFERENCE_EXPLICIT_SOLVENT_MAX_WATERS = 160
REFERENCE_EXPLICIT_SOLVENT_MAX_IONS_PER_SPECIES = 32
REFERENCE_EXPLICIT_SOLVENT_MAX_GRID_CANDIDATES = 32_768
REFERENCE_EXPLICIT_SOLVENT_NEUTRALITY_TOLERANCE_E = 1.0e-12
REFERENCE_EXPLICIT_SOLVENT_AVOGADRO_PER_MOL = 6.02214076e23

# OpenMM XML values converted from nm to Angstrom and kJ/mol to kcal/mol.
TIP3P_O_MASS_DA = 15.99943
TIP3P_H_MASS_DA = 1.007947
TIP3P_O_CHARGE_E = -0.834
TIP3P_H_CHARGE_E = 0.417
TIP3P_O_SIGMA_ANGSTROM = 3.150752406575124
TIP3P_O_EPSILON_KCAL_PER_MOL = 0.152
TIP3P_H_SIGMA_ANGSTROM = 10.0
TIP3P_H_EPSILON_KCAL_PER_MOL = 0.0
TIP3P_OH_DISTANCE_ANGSTROM = 0.9572
TIP3P_HOH_ANGLE_RADIANS = 1.82421813418
TIP3P_HH_DISTANCE_ANGSTROM = math.sqrt(
    2.0
    * TIP3P_OH_DISTANCE_ANGSTROM**2
    * (1.0 - math.cos(TIP3P_HOH_ANGLE_RADIANS))
)
TIP3P_OH_BOND_K_KCAL_PER_MOL_ANGSTROM2 = 1106.0
TIP3P_HOH_ANGLE_K_KCAL_PER_MOL_RADIAN2 = 200.0

JC_NA_MASS_DA = 22.99
JC_NA_CHARGE_E = 1.0
JC_NA_SIGMA_ANGSTROM = 2.439280690268249
JC_NA_EPSILON_KCAL_PER_MOL = 0.0874393
JC_CL_MASS_DA = 35.45
JC_CL_CHARGE_E = -1.0
JC_CL_SIGMA_ANGSTROM = 4.477656957373345
JC_CL_EPSILON_KCAL_PER_MOL = 0.035591

REFERENCE_EXPLICIT_SOLVENT_SCIENTIFIC_BLOCKERS = (
    "caller_supplied_solute_parameters_not_independently_reviewed",
    "tip3p_joung_cheatham_snapshot_not_independently_validated_in_engine_v2",
    "deterministic_lattice_is_not_an_equilibrated_liquid",
    "water_and_ion_placement_not_energy_minimized",
    "explicit_solvent_energy_force_external_comparison_missing",
    "direct_ewald_convergence_acceptance_evidence_missing",
    "water_density_diffusion_dielectric_and_rdf_evidence_missing",
    "nvt_npt_ensemble_acceptance_evidence_missing",
    "two_cpu_host_reproducibility_missing",
    "cpu_gpu_parity_evidence_missing",
    "product_integration_not_qualified",
)


class ReferenceExplicitSolventError(ValueError):
    """The explicit-solvent request or derived artifact failed closed."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReferenceExplicitSolventError(
            "explicit-solvent payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ReferenceExplicitSolventError(f"{name} must be a SHA-256 digest")
    digest = value.strip().lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ReferenceExplicitSolventError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return digest


def _exact_int(
    value: object,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise ReferenceExplicitSolventError(f"{name} must be an integer")
    try:
        result = int(operator.index(value))
    except TypeError:
        raise ReferenceExplicitSolventError(f"{name} must be an integer") from None
    if not minimum <= result <= maximum:
        raise ReferenceExplicitSolventError(
            f"{name} must be in [{minimum},{maximum}]"
        )
    return result


def _finite_float(
    value: object,
    *,
    name: str,
    minimum: float | None = None,
    maximum: float | None = None,
    allow_minimum: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ReferenceExplicitSolventError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise ReferenceExplicitSolventError(f"{name} must be finite")
    if minimum is not None:
        invalid = result < minimum if allow_minimum else result <= minimum
        if invalid:
            relation = ">=" if allow_minimum else ">"
            raise ReferenceExplicitSolventError(
                f"{name} must be {relation} {minimum}"
            )
    if maximum is not None and result > maximum:
        raise ReferenceExplicitSolventError(f"{name} must be <= {maximum}")
    return result


def _float_tuple(
    value: object,
    *,
    name: str,
    minimum: float,
    maximum: float,
) -> tuple[float, float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ReferenceExplicitSolventError(f"{name} must contain three values")
    return tuple(
        _finite_float(
            item,
            name=f"{name}[{index}]",
            minimum=minimum,
            maximum=maximum,
        )
        for index, item in enumerate(value)
    )  # type: ignore[return-value]


def _require_float_hex(value: object, *, name: str) -> float:
    if not isinstance(value, str):
        raise ReferenceExplicitSolventError(f"{name} must be canonical binary64 hex")
    try:
        result = float.fromhex(value)
    except ValueError as exc:
        raise ReferenceExplicitSolventError(
            f"{name} must be canonical binary64 hex"
        ) from exc
    if not math.isfinite(result) or result.hex() != value:
        raise ReferenceExplicitSolventError(
            f"{name} must be canonical finite binary64 hex"
        )
    return result


def reference_explicit_solvent_profile() -> dict[str, object]:
    """Return the immutable-profile projection used by the preparation."""

    return {
        "profile_id": REFERENCE_EXPLICIT_SOLVENT_PROFILE_ID,
        "profile_version": REFERENCE_EXPLICIT_SOLVENT_PROFILE_VERSION,
        "source_url": REFERENCE_EXPLICIT_SOLVENT_PROFILE_SOURCE_URL,
        "source_sha256": REFERENCE_EXPLICIT_SOLVENT_PROFILE_SOURCE_SHA256,
        "water_primary_reference_doi": (
            REFERENCE_EXPLICIT_SOLVENT_PRIMARY_REFERENCE_DOI
        ),
        "ion_primary_reference_doi": REFERENCE_EXPLICIT_ION_REFERENCE_DOI,
        "source_units": {
            "length": "nanometer",
            "energy": "kilojoule_per_mole",
            "mass": "dalton",
            "charge": "elementary_charge",
        },
        "runtime_units": {
            "length": "angstrom",
            "energy": "kilocalorie_per_mole",
            "mass": "dalton",
            "charge": "elementary_charge",
        },
        "water": {
            "model": "TIP3P",
            "oxygen": {
                "mass_da_hex": TIP3P_O_MASS_DA.hex(),
                "charge_e_hex": TIP3P_O_CHARGE_E.hex(),
                "sigma_angstrom_hex": TIP3P_O_SIGMA_ANGSTROM.hex(),
                "epsilon_kcal_per_mol_hex": (
                    TIP3P_O_EPSILON_KCAL_PER_MOL.hex()
                ),
            },
            "hydrogen": {
                "mass_da_hex": TIP3P_H_MASS_DA.hex(),
                "charge_e_hex": TIP3P_H_CHARGE_E.hex(),
                "sigma_angstrom_hex": TIP3P_H_SIGMA_ANGSTROM.hex(),
                "epsilon_kcal_per_mol_hex": (
                    TIP3P_H_EPSILON_KCAL_PER_MOL.hex()
                ),
            },
            "oh_distance_angstrom_hex": TIP3P_OH_DISTANCE_ANGSTROM.hex(),
            "hoh_angle_radians_hex": TIP3P_HOH_ANGLE_RADIANS.hex(),
            "hh_distance_angstrom_hex": TIP3P_HH_DISTANCE_ANGSTROM.hex(),
            "oh_bond_k_kcal_per_mol_angstrom2_hex": (
                TIP3P_OH_BOND_K_KCAL_PER_MOL_ANGSTROM2.hex()
            ),
            "hoh_angle_k_kcal_per_mol_radian2_hex": (
                TIP3P_HOH_ANGLE_K_KCAL_PER_MOL_RADIAN2.hex()
            ),
            "rigid_constraint_pairs": ["O-H1", "O-H2", "H1-H2"],
        },
        "ions": {
            "sodium": {
                "mass_da_hex": JC_NA_MASS_DA.hex(),
                "charge_e_hex": JC_NA_CHARGE_E.hex(),
                "sigma_angstrom_hex": JC_NA_SIGMA_ANGSTROM.hex(),
                "epsilon_kcal_per_mol_hex": JC_NA_EPSILON_KCAL_PER_MOL.hex(),
            },
            "chloride": {
                "mass_da_hex": JC_CL_MASS_DA.hex(),
                "charge_e_hex": JC_CL_CHARGE_E.hex(),
                "sigma_angstrom_hex": JC_CL_SIGMA_ANGSTROM.hex(),
                "epsilon_kcal_per_mol_hex": JC_CL_EPSILON_KCAL_PER_MOL.hex(),
            },
        },
        "combining_rule": "lorentz_berthelot",
        "scientifically_validated": False,
    }


REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256 = (
    "761211b79a889052706ad91626432eda8970eba2fa68123515f93e8990cb2886"
)
if _sha256(reference_explicit_solvent_profile()) != (
    REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
):
    raise ReferenceExplicitSolventError(
        "frozen explicit-solvent profile fingerprint drifted"
    )


@dataclass(frozen=True, slots=True)
class ReferenceExplicitSolventConfig:
    """Bounded box, composition, clearance, and placement contract."""

    box_lengths_angstrom: tuple[float, float, float]
    water_count: int
    sodium_count: int = 0
    chloride_count: int = 0
    lattice_spacing_angstrom: float = 3.1
    minimum_solute_site_distance_angstrom: float = 2.0
    minimum_intermolecular_site_distance_angstrom: float = 0.75
    minimum_solute_box_clearance_angstrom: float = 2.0
    water_constraint_tolerance_angstrom: float = 1.0e-8
    neutrality_tolerance_e: float = REFERENCE_EXPLICIT_SOLVENT_NEUTRALITY_TOLERANCE_E
    require_neutral_system: bool = True
    placement_policy: str = "sha256_ordered_orthorhombic_lattice"
    solute_position_policy: str = "recenter_bounding_box_then_wrap"
    schema_id: str = REFERENCE_EXPLICIT_SOLVENT_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_EXPLICIT_SOLVENT_CONFIG_SCHEMA_ID:
            raise ReferenceExplicitSolventError(
                "unsupported explicit-solvent config schema"
            )
        lengths = _float_tuple(
            self.box_lengths_angstrom,
            name="box_lengths_angstrom",
            minimum=4.0,
            maximum=1000.0,
        )
        object.__setattr__(self, "box_lengths_angstrom", lengths)
        object.__setattr__(
            self,
            "water_count",
            _exact_int(
                self.water_count,
                name="water_count",
                minimum=1,
                maximum=REFERENCE_EXPLICIT_SOLVENT_MAX_WATERS,
            ),
        )
        for name in ("sodium_count", "chloride_count"):
            object.__setattr__(
                self,
                name,
                _exact_int(
                    getattr(self, name),
                    name=name,
                    minimum=0,
                    maximum=REFERENCE_EXPLICIT_SOLVENT_MAX_IONS_PER_SPECIES,
                ),
            )
        for name, minimum, maximum in (
            ("lattice_spacing_angstrom", 1.5, 20.0),
            ("minimum_solute_site_distance_angstrom", 0.0, 20.0),
            ("minimum_intermolecular_site_distance_angstrom", 0.0, 5.0),
            ("minimum_solute_box_clearance_angstrom", 0.0, 100.0),
            ("water_constraint_tolerance_angstrom", 0.0, 1.0),
            ("neutrality_tolerance_e", 0.0, 1.0e-6),
        ):
            object.__setattr__(
                self,
                name,
                _finite_float(
                    getattr(self, name),
                    name=name,
                    minimum=minimum,
                    maximum=maximum,
                ),
            )
        if self.neutrality_tolerance_e != (
            REFERENCE_EXPLICIT_SOLVENT_NEUTRALITY_TOLERANCE_E
        ):
            raise ReferenceExplicitSolventError(
                "neutrality_tolerance_e must equal the frozen value"
            )
        if self.require_neutral_system is not True:
            raise ReferenceExplicitSolventError(
                "explicit-solvent direct-Ewald preparation requires neutrality"
            )
        fixed = {
            "placement_policy": "sha256_ordered_orthorhombic_lattice",
            "solute_position_policy": "recenter_bounding_box_then_wrap",
        }
        for name, expected in fixed.items():
            if getattr(self, name) != expected:
                raise ReferenceExplicitSolventError(
                    f"unsupported explicit-solvent {name}"
                )
        if (
            self.water_count * 3 + self.sodium_count + self.chloride_count
            > REFERENCE_EWALD_MAX_ATOMS
        ):
            raise ReferenceExplicitSolventError(
                "requested solvent atoms exceed the direct-Ewald atom bound"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID,
            "profile_id": REFERENCE_EXPLICIT_SOLVENT_PROFILE_ID,
            "profile_fingerprint_sha256": (
                REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
            ),
            "box_lengths_angstrom_hex": [
                value.hex() for value in self.box_lengths_angstrom
            ],
            "water_count": self.water_count,
            "sodium_count": self.sodium_count,
            "chloride_count": self.chloride_count,
            "lattice_spacing_angstrom_hex": self.lattice_spacing_angstrom.hex(),
            "minimum_solute_site_distance_angstrom_hex": (
                self.minimum_solute_site_distance_angstrom.hex()
            ),
            "minimum_intermolecular_site_distance_angstrom_hex": (
                self.minimum_intermolecular_site_distance_angstrom.hex()
            ),
            "minimum_solute_box_clearance_angstrom_hex": (
                self.minimum_solute_box_clearance_angstrom.hex()
            ),
            "water_constraint_tolerance_angstrom_hex": (
                self.water_constraint_tolerance_angstrom.hex()
            ),
            "neutrality_tolerance_e_hex": self.neutrality_tolerance_e.hex(),
            "require_neutral_system": True,
            "placement_policy": self.placement_policy,
            "solute_position_policy": self.solute_position_policy,
        }

    @classmethod
    def from_dict(cls, value: object) -> "ReferenceExplicitSolventConfig":
        expected = {
            "schema_id",
            "algorithm_id",
            "profile_id",
            "profile_fingerprint_sha256",
            "box_lengths_angstrom_hex",
            "water_count",
            "sodium_count",
            "chloride_count",
            "lattice_spacing_angstrom_hex",
            "minimum_solute_site_distance_angstrom_hex",
            "minimum_intermolecular_site_distance_angstrom_hex",
            "minimum_solute_box_clearance_angstrom_hex",
            "water_constraint_tolerance_angstrom_hex",
            "neutrality_tolerance_e_hex",
            "require_neutral_system",
            "placement_policy",
            "solute_position_policy",
        }
        if not isinstance(value, Mapping) or set(value) != expected:
            raise ReferenceExplicitSolventError(
                "explicit-solvent config payload is invalid"
            )
        if value["algorithm_id"] != REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID:
            raise ReferenceExplicitSolventError(
                "unsupported explicit-solvent algorithm"
            )
        if value["profile_id"] != REFERENCE_EXPLICIT_SOLVENT_PROFILE_ID or value[
            "profile_fingerprint_sha256"
        ] != REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256:
            raise ReferenceExplicitSolventError(
                "explicit-solvent profile identity mismatch"
            )
        raw_lengths = value["box_lengths_angstrom_hex"]
        if not isinstance(raw_lengths, list) or len(raw_lengths) != 3:
            raise ReferenceExplicitSolventError(
                "box_lengths_angstrom_hex must contain three values"
            )
        result = cls(
            box_lengths_angstrom=tuple(
                _require_float_hex(item, name="box length") for item in raw_lengths
            ),
            water_count=value["water_count"],
            sodium_count=value["sodium_count"],
            chloride_count=value["chloride_count"],
            lattice_spacing_angstrom=_require_float_hex(
                value["lattice_spacing_angstrom_hex"],
                name="lattice_spacing_angstrom_hex",
            ),
            minimum_solute_site_distance_angstrom=_require_float_hex(
                value["minimum_solute_site_distance_angstrom_hex"],
                name="minimum_solute_site_distance_angstrom_hex",
            ),
            minimum_intermolecular_site_distance_angstrom=_require_float_hex(
                value["minimum_intermolecular_site_distance_angstrom_hex"],
                name="minimum_intermolecular_site_distance_angstrom_hex",
            ),
            minimum_solute_box_clearance_angstrom=_require_float_hex(
                value["minimum_solute_box_clearance_angstrom_hex"],
                name="minimum_solute_box_clearance_angstrom_hex",
            ),
            water_constraint_tolerance_angstrom=_require_float_hex(
                value["water_constraint_tolerance_angstrom_hex"],
                name="water_constraint_tolerance_angstrom_hex",
            ),
            neutrality_tolerance_e=_require_float_hex(
                value["neutrality_tolerance_e_hex"],
                name="neutrality_tolerance_e_hex",
            ),
            require_neutral_system=value["require_neutral_system"],
            placement_policy=str(value["placement_policy"]),
            solute_position_policy=str(value["solute_position_policy"]),
            schema_id=str(value["schema_id"]),
        )
        if result.to_dict() != dict(value):
            raise ReferenceExplicitSolventError(
                "explicit-solvent config payload is not canonical"
            )
        return result

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class ReferenceExplicitSolventReceipt:
    source_system_sha256: str
    source_topology_sha256: str
    source_parameter_fingerprint_sha256: str
    config_fingerprint_sha256: str
    profile_fingerprint_sha256: str
    solvated_system_sha256: str
    solvated_topology_sha256: str
    solvated_parameter_fingerprint_sha256: str
    constraint_config_fingerprint_sha256: str
    placement_trace_sha256: str
    water_count: int
    sodium_count: int
    chloride_count: int
    source_atom_count: int
    solvated_atom_count: int
    solvated_residue_count: int
    solvated_bond_count: int
    constraint_count: int
    source_total_charge_e: float
    solvated_total_charge_e: float
    box_lengths_angstrom: tuple[float, float, float]
    solute_shift_angstrom: tuple[float, float, float]
    volume_angstrom3: float
    water_molarity: float
    sodium_molarity: float
    chloride_molarity: float
    minimum_solute_site_distance_angstrom: float
    minimum_intermolecular_solvent_site_distance_angstrom: float | None
    scientific_blockers: tuple[str, ...] = (
        REFERENCE_EXPLICIT_SOLVENT_SCIENTIFIC_BLOCKERS
    )
    schema_id: str = REFERENCE_EXPLICIT_SOLVENT_RECEIPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_EXPLICIT_SOLVENT_RECEIPT_SCHEMA_ID:
            raise ReferenceExplicitSolventError(
                "unsupported explicit-solvent receipt schema"
            )
        for name in (
            "source_system_sha256",
            "source_topology_sha256",
            "source_parameter_fingerprint_sha256",
            "config_fingerprint_sha256",
            "profile_fingerprint_sha256",
            "solvated_system_sha256",
            "solvated_topology_sha256",
            "solvated_parameter_fingerprint_sha256",
            "constraint_config_fingerprint_sha256",
            "placement_trace_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        bounds = {
            "water_count": REFERENCE_EXPLICIT_SOLVENT_MAX_WATERS,
            "sodium_count": REFERENCE_EXPLICIT_SOLVENT_MAX_IONS_PER_SPECIES,
            "chloride_count": REFERENCE_EXPLICIT_SOLVENT_MAX_IONS_PER_SPECIES,
            "source_atom_count": REFERENCE_EWALD_MAX_ATOMS,
            "solvated_atom_count": REFERENCE_EWALD_MAX_ATOMS,
            "solvated_residue_count": REFERENCE_EWALD_MAX_ATOMS,
            "solvated_bond_count": REFERENCE_EWALD_MAX_ATOMS * 4,
            "constraint_count": 4096,
        }
        for name, maximum in bounds.items():
            minimum = 1 if name in {"water_count", "source_atom_count"} else 0
            object.__setattr__(
                self,
                name,
                _exact_int(
                    getattr(self, name),
                    name=name,
                    minimum=minimum,
                    maximum=maximum,
                ),
            )
        for name in (
            "source_total_charge_e",
            "solvated_total_charge_e",
            "volume_angstrom3",
            "water_molarity",
            "sodium_molarity",
            "chloride_molarity",
            "minimum_solute_site_distance_angstrom",
        ):
            minimum = None if "charge" in name else 0.0
            object.__setattr__(
                self,
                name,
                _finite_float(
                    getattr(self, name),
                    name=name,
                    minimum=minimum,
                    allow_minimum=name not in {"volume_angstrom3"},
                ),
            )
        object.__setattr__(
            self,
            "box_lengths_angstrom",
            _float_tuple(
                self.box_lengths_angstrom,
                name="box_lengths_angstrom",
                minimum=0.0,
                maximum=1000.0,
            ),
        )
        object.__setattr__(
            self,
            "solute_shift_angstrom",
            tuple(
                _finite_float(value, name="solute_shift_angstrom")
                for value in self.solute_shift_angstrom
            ),
        )
        if len(self.solute_shift_angstrom) != 3:
            raise ReferenceExplicitSolventError(
                "solute_shift_angstrom must contain three values"
            )
        if self.minimum_intermolecular_solvent_site_distance_angstrom is not None:
            object.__setattr__(
                self,
                "minimum_intermolecular_solvent_site_distance_angstrom",
                _finite_float(
                    self.minimum_intermolecular_solvent_site_distance_angstrom,
                    name="minimum_intermolecular_solvent_site_distance_angstrom",
                    minimum=0.0,
                    allow_minimum=True,
                ),
            )
        if abs(self.solvated_total_charge_e) > (
            REFERENCE_EXPLICIT_SOLVENT_NEUTRALITY_TOLERANCE_E
        ):
            raise ReferenceExplicitSolventError(
                "explicit-solvent receipt must describe a neutral system"
            )
        if self.profile_fingerprint_sha256 != (
            REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
        ):
            raise ReferenceExplicitSolventError(
                "explicit-solvent receipt profile mismatch"
            )
        if tuple(self.scientific_blockers) != (
            REFERENCE_EXPLICIT_SOLVENT_SCIENTIFIC_BLOCKERS
        ):
            raise ReferenceExplicitSolventError(
                "explicit-solvent scientific blockers cannot be promoted"
            )

    @property
    def scientifically_validated(self) -> bool:
        return False

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID,
            "profile_id": REFERENCE_EXPLICIT_SOLVENT_PROFILE_ID,
            "source_system_sha256": self.source_system_sha256,
            "source_topology_sha256": self.source_topology_sha256,
            "source_parameter_fingerprint_sha256": (
                self.source_parameter_fingerprint_sha256
            ),
            "config_fingerprint_sha256": self.config_fingerprint_sha256,
            "profile_fingerprint_sha256": self.profile_fingerprint_sha256,
            "solvated_system_sha256": self.solvated_system_sha256,
            "solvated_topology_sha256": self.solvated_topology_sha256,
            "solvated_parameter_fingerprint_sha256": (
                self.solvated_parameter_fingerprint_sha256
            ),
            "constraint_config_fingerprint_sha256": (
                self.constraint_config_fingerprint_sha256
            ),
            "placement_trace_sha256": self.placement_trace_sha256,
            "water_count": self.water_count,
            "sodium_count": self.sodium_count,
            "chloride_count": self.chloride_count,
            "source_atom_count": self.source_atom_count,
            "solvated_atom_count": self.solvated_atom_count,
            "solvated_residue_count": self.solvated_residue_count,
            "solvated_bond_count": self.solvated_bond_count,
            "constraint_count": self.constraint_count,
            "source_total_charge_e_hex": self.source_total_charge_e.hex(),
            "solvated_total_charge_e_hex": self.solvated_total_charge_e.hex(),
            "neutrality_satisfied": True,
            "box_lengths_angstrom_hex": [
                value.hex() for value in self.box_lengths_angstrom
            ],
            "solute_shift_angstrom_hex": [
                value.hex() for value in self.solute_shift_angstrom
            ],
            "volume_angstrom3_hex": self.volume_angstrom3.hex(),
            "water_molarity_hex": self.water_molarity.hex(),
            "sodium_molarity_hex": self.sodium_molarity.hex(),
            "chloride_molarity_hex": self.chloride_molarity.hex(),
            "minimum_solute_site_distance_angstrom_hex": (
                self.minimum_solute_site_distance_angstrom.hex()
            ),
            "minimum_intermolecular_solvent_site_distance_angstrom_hex": (
                None
                if self.minimum_intermolecular_solvent_site_distance_angstrom
                is None
                else self.minimum_intermolecular_solvent_site_distance_angstrom.hex()
            ),
            "scientifically_validated": False,
            "claim_safe": False,
            "scientific_blockers": list(self.scientific_blockers),
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class ReferenceExplicitSolventPreparation:
    system: AllAtomSystem
    parameters: ReferenceForceFieldParameters
    constraint_config: ReferenceSHAKERATTLEConfig
    config: ReferenceExplicitSolventConfig
    receipt: ReferenceExplicitSolventReceipt
    schema_id: str = REFERENCE_EXPLICIT_SOLVENT_RESULT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_EXPLICIT_SOLVENT_RESULT_SCHEMA_ID:
            raise ReferenceExplicitSolventError(
                "unsupported explicit-solvent result schema"
            )
        if not isinstance(self.system, AllAtomSystem):
            raise ReferenceExplicitSolventError("system must be AllAtomSystem")
        if not isinstance(self.parameters, ReferenceForceFieldParameters):
            raise ReferenceExplicitSolventError(
                "parameters must be ReferenceForceFieldParameters"
            )
        if not isinstance(self.constraint_config, ReferenceSHAKERATTLEConfig):
            raise ReferenceExplicitSolventError(
                "constraint_config must be ReferenceSHAKERATTLEConfig"
            )
        if not isinstance(self.config, ReferenceExplicitSolventConfig):
            raise ReferenceExplicitSolventError(
                "config must be ReferenceExplicitSolventConfig"
            )
        if not isinstance(self.receipt, ReferenceExplicitSolventReceipt):
            raise ReferenceExplicitSolventError(
                "receipt must be ReferenceExplicitSolventReceipt"
            )
        require_valid_all_atom_system(self.system)
        system_sha256 = canonical_system_sha256(self.system)
        topology_sha256 = canonical_topology_sha256(self.system)
        checks = {
            "solvated_system_sha256": system_sha256,
            "solvated_topology_sha256": topology_sha256,
            "solvated_parameter_fingerprint_sha256": (
                self.parameters.fingerprint_sha256
            ),
            "constraint_config_fingerprint_sha256": (
                self.constraint_config.fingerprint_sha256
            ),
            "config_fingerprint_sha256": self.config.fingerprint_sha256,
            "profile_fingerprint_sha256": (
                REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
            ),
        }
        for name, expected in checks.items():
            if getattr(self.receipt, name) != expected:
                raise ReferenceExplicitSolventError(
                    f"explicit-solvent result {name} mismatch"
                )
        if self.parameters.topology_sha256 != topology_sha256:
            raise ReferenceExplicitSolventError(
                "solvated parameter topology identity mismatch"
            )
        if self.system.atom_count != self.receipt.solvated_atom_count:
            raise ReferenceExplicitSolventError(
                "solvated atom count does not match receipt"
            )
        if len(self.system.residues) != self.receipt.solvated_residue_count:
            raise ReferenceExplicitSolventError(
                "solvated residue count does not match receipt"
            )
        if len(self.system.bonds) != self.receipt.solvated_bond_count:
            raise ReferenceExplicitSolventError(
                "solvated bond count does not match receipt"
            )
        if len(self.constraint_config.constraints) != self.receipt.constraint_count:
            raise ReferenceExplicitSolventError(
                "solvated constraint count does not match receipt"
            )
        atom_map = self.parameters.atom_parameter_map
        total_charge = math.fsum(
            atom_map[index].charge_e for index in range(self.system.atom_count)
        )
        if total_charge.hex() != self.receipt.solvated_total_charge_e.hex():
            raise ReferenceExplicitSolventError(
                "solvated total charge does not match receipt"
            )
        if self.system.cell is None or self.system.cell.periodic != (True, True, True):
            raise ReferenceExplicitSolventError(
                "explicit-solvent result requires full three-dimensional PBC"
            )
        lengths = tuple(
            float(value)
            for value in self.system.cell.orthorhombic_lengths().tolist()
        )
        if tuple(value.hex() for value in lengths) != tuple(
            value.hex() for value in self.receipt.box_lengths_angstrom
        ):
            raise ReferenceExplicitSolventError(
                "solvated box lengths do not match receipt"
            )
        _validate_prepared_profile(self)

    @property
    def scientifically_validated(self) -> bool:
        return False

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "algorithm_id": REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID,
            "system_sha256": canonical_system_sha256(self.system),
            "topology_sha256": canonical_topology_sha256(self.system),
            "parameter_fingerprint_sha256": self.parameters.fingerprint_sha256,
            "constraint_config_fingerprint_sha256": (
                self.constraint_config.fingerprint_sha256
            ),
            "config": self.config.to_dict(),
            "receipt": self.receipt.to_dict(),
            "scientifically_validated": False,
            "claim_safe": False,
        }


@dataclass(frozen=True, slots=True)
class _Placement:
    species: str
    candidate_index: tuple[int, int, int]
    orientation_index: int
    sites: tuple[tuple[float, float, float], ...]

    def trace_dict(self) -> dict[str, object]:
        return {
            "species": self.species,
            "candidate_index": list(self.candidate_index),
            "orientation_index": self.orientation_index,
            "site_coordinates_angstrom_hex": [
                [value.hex() for value in site] for site in self.sites
            ],
        }


def _same_float(first: float | None, second: float) -> bool:
    return first is not None and float(first).hex() == float(second).hex()


def _validate_prepared_profile(
    preparation: ReferenceExplicitSolventPreparation,
) -> None:
    """Recompute profile, trace, composition, and diagnostic receipt fields."""

    system = preparation.system
    parameters = preparation.parameters
    config = preparation.config
    receipt = preparation.receipt
    if (
        receipt.water_count != config.water_count
        or receipt.sodium_count != config.sodium_count
        or receipt.chloride_count != config.chloride_count
    ):
        raise ReferenceExplicitSolventError(
            "explicit-solvent composition does not match config"
        )
    expected_atom_count = (
        receipt.source_atom_count
        + 3 * config.water_count
        + config.sodium_count
        + config.chloride_count
    )
    if expected_atom_count != system.atom_count:
        raise ReferenceExplicitSolventError(
            "explicit-solvent composition atom count is inconsistent"
        )
    atom_map = parameters.atom_parameter_map
    source_total_charge = math.fsum(
        atom_map[index].charge_e for index in range(receipt.source_atom_count)
    )
    if source_total_charge.hex() != receipt.source_total_charge_e.hex():
        raise ReferenceExplicitSolventError(
            "source total charge does not match explicit-solvent receipt"
        )

    water_residues = tuple(
        residue
        for residue in system.residues
        if residue.metadata.get("component_role") == "explicit_water"
    )
    sodium_residues = tuple(
        residue
        for residue in system.residues
        if residue.metadata.get("component_role") == "explicit_sodium_ion"
    )
    chloride_residues = tuple(
        residue
        for residue in system.residues
        if residue.metadata.get("component_role") == "explicit_chloride_ion"
    )
    if (
        len(water_residues) != config.water_count
        or len(sodium_residues) != config.sodium_count
        or len(chloride_residues) != config.chloride_count
    ):
        raise ReferenceExplicitSolventError(
            "explicit-solvent residue roles do not match composition"
        )
    explicit_atom_indices = {
        atom_index
        for residue in (*water_residues, *sodium_residues, *chloride_residues)
        for atom_index in residue.atom_indices
    }
    if explicit_atom_indices != set(range(receipt.source_atom_count, system.atom_count)):
        raise ReferenceExplicitSolventError(
            "explicit-solvent atom roles do not exactly cover appended atoms"
        )

    system_bond_pairs = {(row.atom_i, row.atom_j) for row in system.bonds}
    parameter_bond_map = {
        (row.atom_i, row.atom_j): row for row in parameters.bonds
    }
    parameter_angle_map = {
        (row.atom_i, row.atom_j, row.atom_k): row for row in parameters.angles
    }
    excluded_pairs = set(parameters.excluded_pairs)
    constraint_map = {
        row.pair: row for row in preparation.constraint_config.constraints
    }
    coordinates = system.coordinates[0]
    lengths = receipt.box_lengths_angstrom
    placement_groups: list[tuple[tuple[float, float, float], ...]] = []
    water_trace: list[dict[str, object]] = []
    ion_trace: list[dict[str, object]] = []

    for water_index, residue in enumerate(water_residues):
        if residue.name != "HOH" or len(residue.atom_indices) != 3:
            raise ReferenceExplicitSolventError(
                "explicit-water residue topology is invalid"
            )
        oxygen, hydrogen_one, hydrogen_two = residue.atom_indices
        expected_sites = (
            (
                oxygen,
                "O",
                "O",
                TIP3P_O_CHARGE_E,
                TIP3P_O_MASS_DA,
                TIP3P_O_SIGMA_ANGSTROM,
                TIP3P_O_EPSILON_KCAL_PER_MOL,
            ),
            (
                hydrogen_one,
                "H1",
                "H",
                TIP3P_H_CHARGE_E,
                TIP3P_H_MASS_DA,
                TIP3P_H_SIGMA_ANGSTROM,
                TIP3P_H_EPSILON_KCAL_PER_MOL,
            ),
            (
                hydrogen_two,
                "H2",
                "H",
                TIP3P_H_CHARGE_E,
                TIP3P_H_MASS_DA,
                TIP3P_H_SIGMA_ANGSTROM,
                TIP3P_H_EPSILON_KCAL_PER_MOL,
            ),
        )
        for atom_index, name, element, charge, mass, sigma, epsilon in expected_sites:
            atom = system.atoms[atom_index]
            row = atom_map[atom_index]
            if (
                atom.name != name
                or atom.element != element
                or atom.residue_index != residue.index
                or atom.metadata.get("component_role") != "explicit_water"
                or atom.metadata.get("water_index") != water_index
                or atom.metadata.get("water_site") != name
                or not _same_float(atom.partial_charge_e, charge)
                or not _same_float(atom.mass_da, mass)
                or row.charge_e.hex() != charge.hex()
                or row.sigma_angstrom.hex() != sigma.hex()
                or row.epsilon_kcal_per_mol.hex() != epsilon.hex()
            ):
                raise ReferenceExplicitSolventError(
                    "explicit-water atom or nonbonded profile drifted"
                )
        expected_bonds = ((oxygen, hydrogen_one), (oxygen, hydrogen_two))
        for pair in expected_bonds:
            if pair not in system_bond_pairs or pair not in parameter_bond_map:
                raise ReferenceExplicitSolventError(
                    "explicit-water bond profile is incomplete"
                )
            row = parameter_bond_map[pair]
            if (
                row.equilibrium_angstrom.hex()
                != TIP3P_OH_DISTANCE_ANGSTROM.hex()
                or row.force_constant_kcal_per_mol_angstrom2.hex()
                != TIP3P_OH_BOND_K_KCAL_PER_MOL_ANGSTROM2.hex()
            ):
                raise ReferenceExplicitSolventError(
                    "explicit-water bond parameters drifted"
                )
        angle_key = (hydrogen_one, oxygen, hydrogen_two)
        if angle_key not in parameter_angle_map:
            raise ReferenceExplicitSolventError(
                "explicit-water angle profile is incomplete"
            )
        angle = parameter_angle_map[angle_key]
        if (
            angle.equilibrium_radians.hex() != TIP3P_HOH_ANGLE_RADIANS.hex()
            or angle.force_constant_kcal_per_mol_radian2.hex()
            != TIP3P_HOH_ANGLE_K_KCAL_PER_MOL_RADIAN2.hex()
        ):
            raise ReferenceExplicitSolventError(
                "explicit-water angle parameters drifted"
            )
        expected_pairs = {
            (oxygen, hydrogen_one): TIP3P_OH_DISTANCE_ANGSTROM,
            (oxygen, hydrogen_two): TIP3P_OH_DISTANCE_ANGSTROM,
            (hydrogen_one, hydrogen_two): TIP3P_HH_DISTANCE_ANGSTROM,
        }
        if not set(expected_pairs).issubset(excluded_pairs):
            raise ReferenceExplicitSolventError(
                "explicit-water exclusions are incomplete"
            )
        for pair, target in expected_pairs.items():
            constraint = constraint_map.get(pair)
            if (
                constraint is None
                or constraint.target_distance_angstrom.hex() != target.hex()
                or constraint.tolerance_angstrom.hex()
                != config.water_constraint_tolerance_angstrom.hex()
            ):
                raise ReferenceExplicitSolventError(
                    "explicit-water constraint profile drifted"
                )
        sites = tuple(
            tuple(float(value) for value in coordinates[atom_index].tolist())
            for atom_index in residue.atom_indices
        )
        placement_groups.append(sites)
        try:
            candidate_index = tuple(int(value) for value in residue.metadata["candidate_index"])
            orientation_index = int(residue.metadata["orientation_index"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ReferenceExplicitSolventError(
                "explicit-water placement metadata is invalid"
            ) from exc
        if len(candidate_index) != 3:
            raise ReferenceExplicitSolventError(
                "explicit-water candidate index is invalid"
            )
        water_trace.append(
            _Placement(
                species="water",
                candidate_index=candidate_index,  # type: ignore[arg-type]
                orientation_index=orientation_index,
                sites=sites,
            ).trace_dict()
        )

    ion_profiles = {
        "explicit_sodium_ion": (
            "sodium",
            "NA",
            "Na",
            1,
            JC_NA_CHARGE_E,
            JC_NA_MASS_DA,
            JC_NA_SIGMA_ANGSTROM,
            JC_NA_EPSILON_KCAL_PER_MOL,
        ),
        "explicit_chloride_ion": (
            "chloride",
            "CL",
            "Cl",
            -1,
            JC_CL_CHARGE_E,
            JC_CL_MASS_DA,
            JC_CL_SIGMA_ANGSTROM,
            JC_CL_EPSILON_KCAL_PER_MOL,
        ),
    }
    ion_residues = tuple(
        residue
        for residue in system.residues
        if residue.metadata.get("component_role") in ion_profiles
    )
    for residue in ion_residues:
        role = str(residue.metadata.get("component_role"))
        (
            species,
            name,
            element,
            formal_charge,
            charge,
            mass,
            sigma,
            epsilon,
        ) = ion_profiles[role]
        if len(residue.atom_indices) != 1:
            raise ReferenceExplicitSolventError(
                "explicit-ion residue topology is invalid"
            )
        atom_index = residue.atom_indices[0]
        atom = system.atoms[atom_index]
        row = atom_map[atom_index]
        if (
            atom.name != name
            or atom.element != element
            or atom.formal_charge != formal_charge
            or atom.residue_index != residue.index
            or atom.metadata.get("component_role") != role
            or not _same_float(atom.partial_charge_e, charge)
            or not _same_float(atom.mass_da, mass)
            or row.charge_e.hex() != charge.hex()
            or row.sigma_angstrom.hex() != sigma.hex()
            or row.epsilon_kcal_per_mol.hex() != epsilon.hex()
        ):
            raise ReferenceExplicitSolventError(
                "explicit-ion atom or nonbonded profile drifted"
            )
        sites = (
            tuple(float(value) for value in coordinates[atom_index].tolist()),
        )
        placement_groups.append(sites)
        try:
            candidate_index = tuple(
                int(value) for value in residue.metadata["candidate_index"]
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ReferenceExplicitSolventError(
                "explicit-ion placement metadata is invalid"
            ) from exc
        if len(candidate_index) != 3:
            raise ReferenceExplicitSolventError(
                "explicit-ion candidate index is invalid"
            )
        ion_trace.append(
            _Placement(
                species=species,
                candidate_index=candidate_index,  # type: ignore[arg-type]
                orientation_index=-1,
                sites=sites,
            ).trace_dict()
        )

    expected_trace = {
        "algorithm_id": REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID,
        "config_fingerprint_sha256": config.fingerprint_sha256,
        "profile_fingerprint_sha256": (
            REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
        ),
        "water_placements": water_trace,
        "ion_placements": ion_trace,
    }
    if _sha256(expected_trace) != receipt.placement_trace_sha256:
        raise ReferenceExplicitSolventError(
            "explicit-solvent placement trace does not match result"
        )
    for metadata in (
        system.metadata.get("reference_explicit_solvent"),
        system.provenance.metadata.get("reference_explicit_solvent"),
        parameters.to_dict()["metadata"].get("reference_explicit_solvent"),
    ):
        if (
            not isinstance(metadata, Mapping)
            or metadata.get("profile_fingerprint_sha256")
            != REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
            or metadata.get("config_fingerprint_sha256")
            != config.fingerprint_sha256
        ):
            raise ReferenceExplicitSolventError(
                "explicit-solvent provenance metadata is inconsistent"
            )
    if system.metadata["reference_explicit_solvent"]["placement_trace_sha256"] != (
        receipt.placement_trace_sha256
    ):
        raise ReferenceExplicitSolventError(
            "explicit-solvent system metadata placement trace mismatch"
        )

    solute_sites = tuple(
        tuple(float(value) for value in coordinates[index].tolist())
        for index in range(receipt.source_atom_count)
    )
    minimum_solute = min(
        _minimum_between(group, solute_sites, lengths)
        for group in placement_groups
    )
    if minimum_solute.hex() != receipt.minimum_solute_site_distance_angstrom.hex():
        raise ReferenceExplicitSolventError(
            "minimum solute-site distance does not match receipt"
        )
    intermolecular = [
        _minimum_between(first, second, lengths)
        for first_index, first in enumerate(placement_groups)
        for second in placement_groups[first_index + 1 :]
    ]
    expected_intermolecular = min(intermolecular) if intermolecular else None
    observed_intermolecular = (
        receipt.minimum_intermolecular_solvent_site_distance_angstrom
    )
    if (expected_intermolecular is None) != (observed_intermolecular is None) or (
        expected_intermolecular is not None
        and observed_intermolecular is not None
        and expected_intermolecular.hex() != observed_intermolecular.hex()
    ):
        raise ReferenceExplicitSolventError(
            "minimum intermolecular solvent distance does not match receipt"
        )
    volume = math.prod(lengths)
    count_to_molar = 1.0e27 / (
        REFERENCE_EXPLICIT_SOLVENT_AVOGADRO_PER_MOL * volume
    )
    scalar_checks = {
        "volume_angstrom3": volume,
        "water_molarity": config.water_count * count_to_molar,
        "sodium_molarity": config.sodium_count * count_to_molar,
        "chloride_molarity": config.chloride_count * count_to_molar,
    }
    for name, expected in scalar_checks.items():
        if getattr(receipt, name).hex() != expected.hex():
            raise ReferenceExplicitSolventError(
                f"explicit-solvent {name} does not match result"
            )


def _wrap_site(
    site: tuple[float, float, float],
    lengths: tuple[float, float, float],
) -> tuple[float, float, float]:
    return tuple(
        value - math.floor(value / length) * length
        for value, length in zip(site, lengths)
    )  # type: ignore[return-value]


def _distance(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
    lengths: tuple[float, float, float],
) -> float:
    squared = 0.0
    for left, right, length in zip(first, second, lengths):
        delta = left - right
        delta -= round(delta / length) * length
        squared += delta * delta
    return math.sqrt(squared)


def _minimum_between(
    first: tuple[tuple[float, float, float], ...],
    second: tuple[tuple[float, float, float], ...],
    lengths: tuple[float, float, float],
) -> float:
    return min(_distance(left, right, lengths) for left in first for right in second)


def _water_sites(
    center: tuple[float, float, float],
    orientation_index: int,
    lengths: tuple[float, float, float],
) -> tuple[tuple[float, float, float], ...]:
    orientations = (
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
        ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, 0.0, -1.0), (1.0, 0.0, 0.0)),
        ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
        ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)),
        ((0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
        ((-1.0, 0.0, 0.0), (0.0, 0.0, -1.0)),
        ((0.0, -1.0, 0.0), (-1.0, 0.0, 0.0)),
        ((0.0, 0.0, -1.0), (0.0, -1.0, 0.0)),
    )
    first_axis, second_axis = orientations[orientation_index % len(orientations)]
    cosine = math.cos(TIP3P_HOH_ANGLE_RADIANS)
    sine = math.sin(TIP3P_HOH_ANGLE_RADIANS)
    first_hydrogen = tuple(
        center[axis] + TIP3P_OH_DISTANCE_ANGSTROM * first_axis[axis]
        for axis in range(3)
    )
    second_hydrogen = tuple(
        center[axis]
        + TIP3P_OH_DISTANCE_ANGSTROM
        * (cosine * first_axis[axis] + sine * second_axis[axis])
        for axis in range(3)
    )
    return (
        _wrap_site(center, lengths),
        _wrap_site(first_hydrogen, lengths),
        _wrap_site(second_hydrogen, lengths),
    )


def _candidate_centers(
    config: ReferenceExplicitSolventConfig,
) -> tuple[tuple[tuple[int, int, int], tuple[float, float, float]], ...]:
    counts = tuple(
        int(math.floor(length / config.lattice_spacing_angstrom))
        for length in config.box_lengths_angstrom
    )
    if min(counts) < 1:
        raise ReferenceExplicitSolventError(
            "box is too small for the requested solvent lattice spacing"
        )
    candidate_count = math.prod(counts)
    if candidate_count > REFERENCE_EXPLICIT_SOLVENT_MAX_GRID_CANDIDATES:
        raise ReferenceExplicitSolventError(
            "solvent lattice candidate capacity exceeded"
        )
    actual_spacing = tuple(
        length / count for length, count in zip(config.box_lengths_angstrom, counts)
    )
    rows: list[
        tuple[str, tuple[int, int, int], tuple[float, float, float]]
    ] = []
    for first in range(counts[0]):
        for second in range(counts[1]):
            for third in range(counts[2]):
                index = (first, second, third)
                center = tuple(
                    (axis_index + 0.5) * actual_spacing[axis]
                    for axis, axis_index in enumerate(index)
                )
                key = hashlib.sha256(
                    (
                        config.fingerprint_sha256
                        + ":"
                        + ":".join(str(value) for value in index)
                    ).encode("ascii")
                ).hexdigest()
                rows.append((key, index, center))
    rows.sort(key=lambda row: (row[0], row[1]))
    return tuple((index, center) for _, index, center in rows)


def _place_components(
    solute_sites: tuple[tuple[float, float, float], ...],
    config: ReferenceExplicitSolventConfig,
) -> tuple[tuple[_Placement, ...], tuple[_Placement, ...]]:
    candidates = _candidate_centers(config)
    lengths = config.box_lengths_angstrom
    used: set[tuple[int, int, int]] = set()
    placed_groups: list[tuple[tuple[float, float, float], ...]] = []
    ion_placements: list[_Placement] = []
    water_placements: list[_Placement] = []

    ion_species: list[str] = []
    sodium_remaining = config.sodium_count
    chloride_remaining = config.chloride_count
    while sodium_remaining or chloride_remaining:
        if sodium_remaining:
            ion_species.append("sodium")
            sodium_remaining -= 1
        if chloride_remaining:
            ion_species.append("chloride")
            chloride_remaining -= 1

    def clear(sites: tuple[tuple[float, float, float], ...]) -> bool:
        if _minimum_between(sites, solute_sites, lengths) < (
            config.minimum_solute_site_distance_angstrom
        ):
            return False
        return all(
            _minimum_between(sites, group, lengths)
            >= config.minimum_intermolecular_site_distance_angstrom
            for group in placed_groups
        )

    cursor = 0
    for species in ion_species:
        selected: _Placement | None = None
        while cursor < len(candidates):
            index, center = candidates[cursor]
            cursor += 1
            sites = (_wrap_site(center, lengths),)
            if index not in used and clear(sites):
                selected = _Placement(
                    species=species,
                    candidate_index=index,
                    orientation_index=-1,
                    sites=sites,
                )
                break
        if selected is None:
            raise ReferenceExplicitSolventError(
                f"insufficient lattice capacity to place {species} ions"
            )
        used.add(selected.candidate_index)
        placed_groups.append(selected.sites)
        ion_placements.append(selected)

    for water_index in range(config.water_count):
        selected = None
        while cursor < len(candidates):
            index, center = candidates[cursor]
            cursor += 1
            orientation_index = (
                water_index + index[0] + 3 * index[1] + 7 * index[2]
            ) % 12
            sites = _water_sites(center, orientation_index, lengths)
            if index not in used and clear(sites):
                selected = _Placement(
                    species="water",
                    candidate_index=index,
                    orientation_index=orientation_index,
                    sites=sites,
                )
                break
        if selected is None:
            raise ReferenceExplicitSolventError(
                "insufficient lattice capacity to place requested waters"
            )
        used.add(selected.candidate_index)
        placed_groups.append(selected.sites)
        water_placements.append(selected)

    return tuple(water_placements), tuple(ion_placements)


def _unique_chain_id(system: AllAtomSystem) -> str:
    existing = {chain.chain_id for chain in system.chains}
    for candidate in ("W", *(f"W{index}" for index in range(1, 10_000))):
        if candidate not in existing:
            return candidate
    raise ReferenceExplicitSolventError("unable to allocate solvent chain ID")


def _required_bonded_paths(
    atom_count: int,
    bond_pairs: tuple[tuple[int, int], ...],
) -> tuple[set[tuple[int, int, int]], set[tuple[int, int, int, int]]]:
    adjacency = {index: set() for index in range(atom_count)}
    for atom_i, atom_j in bond_pairs:
        adjacency[atom_i].add(atom_j)
        adjacency[atom_j].add(atom_i)
    angles: set[tuple[int, int, int]] = set()
    for center, neighbors in adjacency.items():
        ordered = sorted(neighbors)
        for position, atom_i in enumerate(ordered):
            for atom_k in ordered[position + 1 :]:
                angles.add((atom_i, center, atom_k))
    torsions: set[tuple[int, int, int, int]] = set()
    for atom_j, atom_k in bond_pairs:
        for atom_i in adjacency[atom_j] - {atom_k}:
            for atom_l in adjacency[atom_k] - {atom_j}:
                path = (atom_i, atom_j, atom_k, atom_l)
                if len(set(path)) == 4:
                    torsions.add(min(path, tuple(reversed(path))))
    return angles, torsions


def _source_requirements(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceExplicitSolventConfig,
    solute_constraints: ReferenceSHAKERATTLEConfig,
) -> tuple[torch.Tensor, tuple[float, float, float], float]:
    if not isinstance(system, AllAtomSystem):
        raise ReferenceExplicitSolventError("system must be AllAtomSystem")
    if not isinstance(parameters, ReferenceForceFieldParameters):
        raise ReferenceExplicitSolventError(
            "parameters must be ReferenceForceFieldParameters"
        )
    require_valid_all_atom_system(system)
    if (
        system.coordinates.dtype != torch.float64
        or system.coordinates.device.type != "cpu"
        or system.model_count != 1
    ):
        raise ReferenceExplicitSolventError(
            "explicit-solvent preparation requires one CPU float64 model"
        )
    if system.cell is not None:
        raise ReferenceExplicitSolventError(
            "explicit-solvent preparation requires an unboxed source solute"
        )
    topology_sha256 = canonical_topology_sha256(system)
    if parameters.topology_sha256 != topology_sha256:
        raise ReferenceExplicitSolventError(
            "source parameter topology identity mismatch"
        )
    if set(parameters.atom_parameter_map) != set(range(system.atom_count)):
        raise ReferenceExplicitSolventError(
            "source nonbonded parameters must exactly cover every atom"
        )
    source_bond_pairs = tuple((bond.atom_i, bond.atom_j) for bond in system.bonds)
    parameter_bond_pairs = tuple((row.atom_i, row.atom_j) for row in parameters.bonds)
    if set(source_bond_pairs) != set(parameter_bond_pairs):
        raise ReferenceExplicitSolventError(
            "source bond parameters must exactly cover the solute topology"
        )
    required_angles, required_torsions = _required_bonded_paths(
        system.atom_count,
        source_bond_pairs,
    )
    parameter_angles = {
        (min(row.atom_i, row.atom_k), row.atom_j, max(row.atom_i, row.atom_k))
        for row in parameters.angles
    }
    parameter_torsions = {
        min(
            (row.atom_i, row.atom_j, row.atom_k, row.atom_l),
            (row.atom_l, row.atom_k, row.atom_j, row.atom_i),
        )
        for row in parameters.torsions
    }
    if parameter_angles != required_angles:
        raise ReferenceExplicitSolventError(
            "source angle parameters must exactly cover the solute topology"
        )
    if parameter_torsions != required_torsions:
        raise ReferenceExplicitSolventError(
            "source torsion parameters must exactly cover the solute topology"
        )
    for pair in parameters.excluded_pairs:
        if max(pair) >= system.atom_count:
            raise ReferenceExplicitSolventError(
                "source excluded pair index is outside the solute topology"
            )
    for row in parameters.scaled_pairs:
        if max(row.atom_i, row.atom_j) >= system.atom_count:
            raise ReferenceExplicitSolventError(
                "source scaled pair index is outside the solute topology"
            )
    if parameters.dielectric != 1.0 or parameters.screening_kappa_per_angstrom != 0.0:
        raise ReferenceExplicitSolventError(
            "explicit-solvent direct-Ewald preparation requires dielectric 1 and zero screening"
        )
    if parameters.cutoff_angstrom >= 0.5 * min(config.box_lengths_angstrom):
        raise ReferenceExplicitSolventError(
            "source cutoff must be below half the shortest solvent box length"
        )
    appended_atoms = config.water_count * 3 + config.sodium_count + config.chloride_count
    total_atoms = system.atom_count + appended_atoms
    if total_atoms > REFERENCE_EWALD_MAX_ATOMS:
        raise ReferenceExplicitSolventError(
            "solvated system exceeds the bounded direct-Ewald atom limit"
        )
    if total_atoms > parameters.applicability_domain.max_atoms:
        raise ReferenceExplicitSolventError(
            "solvated system exceeds the source parameter atom domain"
        )
    projected_bond_count = len(parameters.bonds) + 2 * config.water_count
    projected_angle_count = len(parameters.angles) + config.water_count
    projected_pair_count = total_atoms * (total_atoms - 1) // 2
    if projected_bond_count > parameters.applicability_domain.max_bonds:
        raise ReferenceExplicitSolventError(
            "solvated system exceeds the source parameter bond domain"
        )
    if projected_angle_count > parameters.applicability_domain.max_angles:
        raise ReferenceExplicitSolventError(
            "solvated system exceeds the source parameter angle domain"
        )
    if projected_pair_count > parameters.applicability_domain.max_nonbonded_pairs:
        raise ReferenceExplicitSolventError(
            "solvated system exceeds the source nonbonded-pair domain"
        )
    masses: list[float] = []
    for atom in system.atoms:
        if atom.mass_da is None:
            raise ReferenceExplicitSolventError(
                f"source atom {atom.index} is missing mass_da"
            )
        mass = _finite_float(
            atom.mass_da,
            name=f"source atom {atom.index} mass_da",
            minimum=0.0,
        )
        masses.append(mass)
        atom_parameter = parameters.atom_parameter_map[atom.index]
        if atom.partial_charge_e is None or atom.partial_charge_e.hex() != (
            atom_parameter.charge_e.hex()
        ):
            raise ReferenceExplicitSolventError(
                f"source atom {atom.index} partial charge is not bound to parameters"
            )
    validate_reference_shake_rattle_inputs(
        system,
        torch.tensor(masses, dtype=torch.float64),
        solute_constraints,
    )
    coordinates = system.coordinates[0]
    minima = coordinates.min(dim=0).values
    maxima = coordinates.max(dim=0).values
    spans = maxima - minima
    lengths = torch.tensor(config.box_lengths_angstrom, dtype=torch.float64)
    if bool(
        (
            spans
            + 2.0 * config.minimum_solute_box_clearance_angstrom
            > lengths
        ).any().item()
    ):
        raise ReferenceExplicitSolventError(
            "solute does not satisfy the minimum periodic box clearance"
        )
    shift = 0.5 * lengths - 0.5 * (minima + maxima)
    shifted = coordinates + shift
    shifted = shifted - torch.floor(shifted / lengths) * lengths
    source_total_charge = math.fsum(
        parameters.atom_parameter_map[index].charge_e
        for index in range(system.atom_count)
    )
    expected_total = (
        source_total_charge
        + config.sodium_count * JC_NA_CHARGE_E
        + config.chloride_count * JC_CL_CHARGE_E
    )
    if abs(expected_total) > config.neutrality_tolerance_e:
        raise ReferenceExplicitSolventError(
            "solute and requested ion counts do not produce a neutral system"
        )
    return (
        shifted.unsqueeze(0),
        tuple(float(value) for value in shift.tolist()),
        source_total_charge,
    )


def prepare_reference_explicit_solvent(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    config: ReferenceExplicitSolventConfig,
    *,
    solute_constraints: ReferenceSHAKERATTLEConfig | None = None,
) -> ReferenceExplicitSolventPreparation:
    """Compose a deterministic, neutral TIP3P/Na+/Cl- periodic system."""

    if not isinstance(config, ReferenceExplicitSolventConfig):
        raise ReferenceExplicitSolventError(
            "config must be ReferenceExplicitSolventConfig"
        )
    active_constraints = (
        ReferenceSHAKERATTLEConfig()
        if solute_constraints is None
        else solute_constraints
    )
    if not isinstance(active_constraints, ReferenceSHAKERATTLEConfig):
        raise ReferenceExplicitSolventError(
            "solute_constraints must be ReferenceSHAKERATTLEConfig or None"
        )
    shifted_coordinates, solute_shift, source_total_charge = _source_requirements(
        system,
        parameters,
        config,
        active_constraints,
    )
    lengths = config.box_lengths_angstrom
    solute_sites = tuple(
        tuple(float(value) for value in row)
        for row in shifted_coordinates[0].tolist()
    )
    water_placements, ion_placements = _place_components(solute_sites, config)

    atoms = list(system.atoms)
    bonds = list(system.bonds)
    residues = list(system.residues)
    chains = list(system.chains)
    coordinate_rows = [tuple(float(value) for value in row) for row in solute_sites]
    atom_parameters = list(parameters.atom_parameters)
    bond_parameters = list(parameters.bonds)
    angle_parameters = list(parameters.angles)
    excluded_pairs = list(parameters.excluded_pairs)
    water_constraints: list[ReferenceSHAKERATTLEDistanceConstraint] = []
    solvent_residue_indices: list[int] = []
    chain_index = len(chains)

    for placement_index, placement in enumerate(water_placements, start=1):
        residue_index = len(residues)
        solvent_residue_indices.append(residue_index)
        first_atom = len(atoms)
        site_definitions = (
            (
                "O",
                "O",
                TIP3P_O_CHARGE_E,
                TIP3P_O_MASS_DA,
                TIP3P_O_SIGMA_ANGSTROM,
                TIP3P_O_EPSILON_KCAL_PER_MOL,
            ),
            (
                "H1",
                "H",
                TIP3P_H_CHARGE_E,
                TIP3P_H_MASS_DA,
                TIP3P_H_SIGMA_ANGSTROM,
                TIP3P_H_EPSILON_KCAL_PER_MOL,
            ),
            (
                "H2",
                "H",
                TIP3P_H_CHARGE_E,
                TIP3P_H_MASS_DA,
                TIP3P_H_SIGMA_ANGSTROM,
                TIP3P_H_EPSILON_KCAL_PER_MOL,
            ),
        )
        for offset, (name, element, charge, mass, sigma, epsilon) in enumerate(
            site_definitions
        ):
            atom_index = first_atom + offset
            atoms.append(
                Atom(
                    index=atom_index,
                    name=name,
                    element=element,
                    atomic_number=atomic_number_for_element(element),
                    residue_index=residue_index,
                    formal_charge=0,
                    partial_charge_e=charge,
                    mass_da=mass,
                    metadata={
                        "component_role": "explicit_water",
                        "parameter_profile_id": (
                            REFERENCE_EXPLICIT_SOLVENT_PROFILE_ID
                        ),
                        "water_index": placement_index - 1,
                        "water_site": name,
                    },
                )
            )
            atom_parameters.append(
                AtomNonbondedParameter(
                    atom_index=atom_index,
                    sigma_angstrom=sigma,
                    epsilon_kcal_per_mol=epsilon,
                    charge_e=charge,
                )
            )
            coordinate_rows.append(placement.sites[offset])
        oxygen, hydrogen_one, hydrogen_two = (
            first_atom,
            first_atom + 1,
            first_atom + 2,
        )
        for first, second in ((oxygen, hydrogen_one), (oxygen, hydrogen_two)):
            bonds.append(
                Bond(
                    index=len(bonds),
                    atom_i=first,
                    atom_j=second,
                    order=1.0,
                    source="reference_explicit_solvent_profile",
                )
            )
            bond_parameters.append(
                HarmonicBondParameter(
                    atom_i=first,
                    atom_j=second,
                    equilibrium_angstrom=TIP3P_OH_DISTANCE_ANGSTROM,
                    force_constant_kcal_per_mol_angstrom2=(
                        TIP3P_OH_BOND_K_KCAL_PER_MOL_ANGSTROM2
                    ),
                )
            )
        angle_parameters.append(
            HarmonicAngleParameter(
                atom_i=hydrogen_one,
                atom_j=oxygen,
                atom_k=hydrogen_two,
                equilibrium_radians=TIP3P_HOH_ANGLE_RADIANS,
                force_constant_kcal_per_mol_radian2=(
                    TIP3P_HOH_ANGLE_K_KCAL_PER_MOL_RADIAN2
                ),
            )
        )
        excluded_pairs.extend(
            (
                (oxygen, hydrogen_one),
                (oxygen, hydrogen_two),
                (hydrogen_one, hydrogen_two),
            )
        )
        for first, second, target in (
            (oxygen, hydrogen_one, TIP3P_OH_DISTANCE_ANGSTROM),
            (oxygen, hydrogen_two, TIP3P_OH_DISTANCE_ANGSTROM),
            (hydrogen_one, hydrogen_two, TIP3P_HH_DISTANCE_ANGSTROM),
        ):
            water_constraints.append(
                ReferenceSHAKERATTLEDistanceConstraint(
                    atom_i=first,
                    atom_j=second,
                    target_distance_angstrom=target,
                    tolerance_angstrom=(
                        config.water_constraint_tolerance_angstrom
                    ),
                )
            )
        residues.append(
            Residue(
                index=residue_index,
                name="HOH",
                chain_index=chain_index,
                sequence_number=placement_index,
                atom_indices=(oxygen, hydrogen_one, hydrogen_two),
                entity_type="water",
                hetero=True,
                metadata={
                    "component_role": "explicit_water",
                    "candidate_index": list(placement.candidate_index),
                    "orientation_index": placement.orientation_index,
                },
            )
        )

    ion_sequence = config.water_count
    for placement in ion_placements:
        residue_index = len(residues)
        solvent_residue_indices.append(residue_index)
        atom_index = len(atoms)
        ion_sequence += 1
        if placement.species == "sodium":
            name, element, residue_name, formal_charge = "NA", "Na", "NA", 1
            charge, mass = JC_NA_CHARGE_E, JC_NA_MASS_DA
            sigma, epsilon = JC_NA_SIGMA_ANGSTROM, JC_NA_EPSILON_KCAL_PER_MOL
        else:
            name, element, residue_name, formal_charge = "CL", "Cl", "CL", -1
            charge, mass = JC_CL_CHARGE_E, JC_CL_MASS_DA
            sigma, epsilon = JC_CL_SIGMA_ANGSTROM, JC_CL_EPSILON_KCAL_PER_MOL
        atoms.append(
            Atom(
                index=atom_index,
                name=name,
                element=element,
                atomic_number=atomic_number_for_element(element),
                residue_index=residue_index,
                formal_charge=formal_charge,
                partial_charge_e=charge,
                mass_da=mass,
                metadata={
                    "component_role": f"explicit_{placement.species}_ion",
                    "parameter_profile_id": REFERENCE_EXPLICIT_SOLVENT_PROFILE_ID,
                },
            )
        )
        atom_parameters.append(
            AtomNonbondedParameter(
                atom_index=atom_index,
                sigma_angstrom=sigma,
                epsilon_kcal_per_mol=epsilon,
                charge_e=charge,
            )
        )
        coordinate_rows.append(placement.sites[0])
        residues.append(
            Residue(
                index=residue_index,
                name=residue_name,
                chain_index=chain_index,
                sequence_number=ion_sequence,
                atom_indices=(atom_index,),
                entity_type="ion",
                hetero=True,
                metadata={
                    "component_role": f"explicit_{placement.species}_ion",
                    "candidate_index": list(placement.candidate_index),
                },
            )
        )

    chains.append(
        Chain(
            index=chain_index,
            chain_id=_unique_chain_id(system),
            residue_indices=tuple(solvent_residue_indices),
            entity_id="reference-explicit-solvent",
            metadata={
                "component_role": "explicit_solvent_and_ions",
                "profile_id": REFERENCE_EXPLICIT_SOLVENT_PROFILE_ID,
            },
        )
    )
    placement_trace = {
        "algorithm_id": REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID,
        "config_fingerprint_sha256": config.fingerprint_sha256,
        "profile_fingerprint_sha256": (
            REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
        ),
        "water_placements": [row.trace_dict() for row in water_placements],
        "ion_placements": [row.trace_dict() for row in ion_placements],
    }
    placement_trace_sha256 = _sha256(placement_trace)
    source_system_sha256 = canonical_system_sha256(system)
    source_topology_sha256 = canonical_topology_sha256(system)
    provenance_metadata = dict(system.provenance.metadata)
    provenance_metadata["reference_explicit_solvent"] = {
        "algorithm_id": REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID,
        "config_fingerprint_sha256": config.fingerprint_sha256,
        "profile_fingerprint_sha256": (
            REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
        ),
        "profile_source_sha256": (
            REFERENCE_EXPLICIT_SOLVENT_PROFILE_SOURCE_SHA256
        ),
        "source_parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "placement_trace_sha256": placement_trace_sha256,
        "water_count": config.water_count,
        "sodium_count": config.sodium_count,
        "chloride_count": config.chloride_count,
        "scientifically_validated": False,
    }
    derived_provenance = StructureProvenance(
        source_format="engine-v2-derived-explicit-solvent",
        source_id=system.system_id,
        source_sha256=source_system_sha256,
        parser_name="reference_explicit_solvent",
        parser_version="1.0.0",
        operations=(
            *system.provenance.operations,
            REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID,
        ),
        parent_sha256=(*system.provenance.parent_sha256, source_system_sha256),
        source_digest_verified=True,
        transformation_chain_verified=False,
        chemistry_validated=False,
        scientifically_validated=False,
        product_qualified=False,
        metadata=provenance_metadata,
    )
    system_metadata = dict(system.metadata)
    system_metadata["reference_explicit_solvent"] = {
        "config_fingerprint_sha256": config.fingerprint_sha256,
        "profile_fingerprint_sha256": (
            REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
        ),
        "placement_trace_sha256": placement_trace_sha256,
        "water_count": config.water_count,
        "sodium_count": config.sodium_count,
        "chloride_count": config.chloride_count,
        "scientifically_validated": False,
    }
    solvated_system = AllAtomSystem(
        system_id=f"{system.system_id}:explicit-solvent:{config.fingerprint_sha256[:16]}",
        atoms=tuple(atoms),
        bonds=tuple(bonds),
        residues=tuple(residues),
        chains=tuple(chains),
        coordinates=torch.tensor((coordinate_rows,), dtype=torch.float64),
        provenance=derived_provenance,
        cell=UnitCell.orthorhombic(
            lengths,
            dtype=torch.float64,
            periodic=(True, True, True),
        ),
        metadata=system_metadata,
    )
    require_valid_all_atom_system(solvated_system)
    solvated_topology_sha256 = canonical_topology_sha256(solvated_system)
    parameter_metadata = dict(parameters.to_dict()["metadata"])
    parameter_metadata["reference_explicit_solvent"] = {
        "profile_id": REFERENCE_EXPLICIT_SOLVENT_PROFILE_ID,
        "profile_version": REFERENCE_EXPLICIT_SOLVENT_PROFILE_VERSION,
        "profile_fingerprint_sha256": (
            REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
        ),
        "profile_source_sha256": REFERENCE_EXPLICIT_SOLVENT_PROFILE_SOURCE_SHA256,
        "source_parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "config_fingerprint_sha256": config.fingerprint_sha256,
        "scientifically_validated": False,
    }
    solvated_parameters = ReferenceForceFieldParameters(
        parameter_set_id=(
            f"{parameters.parameter_set_id}+{REFERENCE_EXPLICIT_SOLVENT_PROFILE_ID}"
        ),
        parameter_set_version=(
            f"{parameters.parameter_set_version}+explicit-solvent-1.0.0"
        ),
        topology_sha256=solvated_topology_sha256,
        atom_parameters=tuple(atom_parameters),
        bonds=tuple(bond_parameters),
        angles=tuple(angle_parameters),
        torsions=parameters.torsions,
        excluded_pairs=tuple(excluded_pairs),
        scaled_pairs=parameters.scaled_pairs,
        cutoff_angstrom=parameters.cutoff_angstrom,
        switch_start_angstrom=parameters.switch_start_angstrom,
        dielectric=parameters.dielectric,
        screening_kappa_per_angstrom=parameters.screening_kappa_per_angstrom,
        applicability_domain=parameters.applicability_domain,
        scientifically_validated=False,
        metadata=parameter_metadata,
    )
    combined_constraints = ReferenceSHAKERATTLEConfig(
        constraints=(*active_constraints.constraints, *water_constraints),
        velocity_tolerance_angstrom_per_ps=(
            active_constraints.velocity_tolerance_angstrom_per_ps
        ),
        max_position_iterations=max(
            active_constraints.max_position_iterations,
            200,
        ),
        max_velocity_iterations=max(
            active_constraints.max_velocity_iterations,
            200,
        ),
        max_pair_position_correction_angstrom=(
            active_constraints.max_pair_position_correction_angstrom
        ),
        convergence_tolerance_scale=(
            active_constraints.convergence_tolerance_scale
        ),
    )
    masses = torch.tensor(
        [float(atom.mass_da) for atom in solvated_system.atoms],
        dtype=torch.float64,
    )
    validate_reference_shake_rattle_inputs(
        solvated_system,
        masses,
        combined_constraints,
    )
    all_placements = (*water_placements, *ion_placements)
    placement_groups = tuple(row.sites for row in all_placements)
    minimum_solute_distance = min(
        _minimum_between(group, solute_sites, lengths)
        for group in placement_groups
    )
    intermolecular_distances = [
        _minimum_between(first, second, lengths)
        for first_index, first in enumerate(placement_groups)
        for second in placement_groups[first_index + 1 :]
    ]
    minimum_intermolecular = (
        min(intermolecular_distances) if intermolecular_distances else None
    )
    volume = math.prod(lengths)
    count_to_molar = 1.0e27 / (REFERENCE_EXPLICIT_SOLVENT_AVOGADRO_PER_MOL * volume)
    solvated_total_charge = math.fsum(
        row.charge_e for row in solvated_parameters.atom_parameters
    )
    receipt = ReferenceExplicitSolventReceipt(
        source_system_sha256=source_system_sha256,
        source_topology_sha256=source_topology_sha256,
        source_parameter_fingerprint_sha256=parameters.fingerprint_sha256,
        config_fingerprint_sha256=config.fingerprint_sha256,
        profile_fingerprint_sha256=(
            REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256
        ),
        solvated_system_sha256=canonical_system_sha256(solvated_system),
        solvated_topology_sha256=solvated_topology_sha256,
        solvated_parameter_fingerprint_sha256=(
            solvated_parameters.fingerprint_sha256
        ),
        constraint_config_fingerprint_sha256=(
            combined_constraints.fingerprint_sha256
        ),
        placement_trace_sha256=placement_trace_sha256,
        water_count=config.water_count,
        sodium_count=config.sodium_count,
        chloride_count=config.chloride_count,
        source_atom_count=system.atom_count,
        solvated_atom_count=solvated_system.atom_count,
        solvated_residue_count=len(solvated_system.residues),
        solvated_bond_count=len(solvated_system.bonds),
        constraint_count=len(combined_constraints.constraints),
        source_total_charge_e=source_total_charge,
        solvated_total_charge_e=solvated_total_charge,
        box_lengths_angstrom=lengths,
        solute_shift_angstrom=solute_shift,
        volume_angstrom3=volume,
        water_molarity=config.water_count * count_to_molar,
        sodium_molarity=config.sodium_count * count_to_molar,
        chloride_molarity=config.chloride_count * count_to_molar,
        minimum_solute_site_distance_angstrom=minimum_solute_distance,
        minimum_intermolecular_solvent_site_distance_angstrom=(
            minimum_intermolecular
        ),
    )
    return ReferenceExplicitSolventPreparation(
        system=solvated_system,
        parameters=solvated_parameters,
        constraint_config=combined_constraints,
        config=config,
        receipt=receipt,
    )


def require_reference_explicit_solvent_preparation(
    value: object,
) -> ReferenceExplicitSolventPreparation:
    """Require an already constructed preparation and re-run its invariants."""

    if not isinstance(value, ReferenceExplicitSolventPreparation):
        raise ReferenceExplicitSolventError(
            "value must be ReferenceExplicitSolventPreparation"
        )
    return replace(value)


def verify_reference_explicit_solvent_replay(
    source_system: AllAtomSystem,
    source_parameters: ReferenceForceFieldParameters,
    config: ReferenceExplicitSolventConfig,
    observed: ReferenceExplicitSolventPreparation,
    *,
    solute_constraints: ReferenceSHAKERATTLEConfig | None = None,
) -> ReferenceExplicitSolventPreparation:
    """Re-run preparation from trusted inputs and require exact identity replay."""

    require_reference_explicit_solvent_preparation(observed)
    expected = prepare_reference_explicit_solvent(
        source_system,
        source_parameters,
        config,
        solute_constraints=solute_constraints,
    )
    if expected.to_dict() != observed.to_dict():
        raise ReferenceExplicitSolventError(
            "explicit-solvent preparation does not match trusted-input replay"
        )
    if not torch.equal(expected.system.coordinates, observed.system.coordinates):
        raise ReferenceExplicitSolventError(
            "explicit-solvent coordinate bytes do not match trusted-input replay"
        )
    return observed


__all__ = [
    "JC_CL_CHARGE_E",
    "JC_CL_EPSILON_KCAL_PER_MOL",
    "JC_CL_MASS_DA",
    "JC_CL_SIGMA_ANGSTROM",
    "JC_NA_CHARGE_E",
    "JC_NA_EPSILON_KCAL_PER_MOL",
    "JC_NA_MASS_DA",
    "JC_NA_SIGMA_ANGSTROM",
    "REFERENCE_EXPLICIT_ION_REFERENCE_DOI",
    "REFERENCE_EXPLICIT_SOLVENT_ALGORITHM_ID",
    "REFERENCE_EXPLICIT_SOLVENT_CONFIG_SCHEMA_ID",
    "REFERENCE_EXPLICIT_SOLVENT_MAX_GRID_CANDIDATES",
    "REFERENCE_EXPLICIT_SOLVENT_MAX_IONS_PER_SPECIES",
    "REFERENCE_EXPLICIT_SOLVENT_MAX_WATERS",
    "REFERENCE_EXPLICIT_SOLVENT_NEUTRALITY_TOLERANCE_E",
    "REFERENCE_EXPLICIT_SOLVENT_PRIMARY_REFERENCE_DOI",
    "REFERENCE_EXPLICIT_SOLVENT_PROFILE_FINGERPRINT_SHA256",
    "REFERENCE_EXPLICIT_SOLVENT_PROFILE_ID",
    "REFERENCE_EXPLICIT_SOLVENT_PROFILE_SOURCE_SHA256",
    "REFERENCE_EXPLICIT_SOLVENT_PROFILE_SOURCE_URL",
    "REFERENCE_EXPLICIT_SOLVENT_PROFILE_VERSION",
    "REFERENCE_EXPLICIT_SOLVENT_RECEIPT_SCHEMA_ID",
    "REFERENCE_EXPLICIT_SOLVENT_RESULT_SCHEMA_ID",
    "REFERENCE_EXPLICIT_SOLVENT_SCIENTIFIC_BLOCKERS",
    "TIP3P_HH_DISTANCE_ANGSTROM",
    "TIP3P_HOH_ANGLE_K_KCAL_PER_MOL_RADIAN2",
    "TIP3P_HOH_ANGLE_RADIANS",
    "TIP3P_H_CHARGE_E",
    "TIP3P_H_EPSILON_KCAL_PER_MOL",
    "TIP3P_H_MASS_DA",
    "TIP3P_H_SIGMA_ANGSTROM",
    "TIP3P_OH_BOND_K_KCAL_PER_MOL_ANGSTROM2",
    "TIP3P_OH_DISTANCE_ANGSTROM",
    "TIP3P_O_CHARGE_E",
    "TIP3P_O_EPSILON_KCAL_PER_MOL",
    "TIP3P_O_MASS_DA",
    "TIP3P_O_SIGMA_ANGSTROM",
    "ReferenceExplicitSolventConfig",
    "ReferenceExplicitSolventError",
    "ReferenceExplicitSolventPreparation",
    "ReferenceExplicitSolventReceipt",
    "prepare_reference_explicit_solvent",
    "reference_explicit_solvent_profile",
    "require_reference_explicit_solvent_preparation",
    "verify_reference_explicit_solvent_replay",
]
