"""Chemistry-aware pose validity bound to the reference docking scorer."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real

from .proposals import DockingProposal
from .reference_scoring import (
    ReferenceDockingInteractionDiagnostics,
    UncalibratedReferenceDockingScorer,
)
from .scoring import DockingScoreBreakdown


CHEMISTRY_AWARE_POSE_VALIDITY_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_chemistry_aware_pose_validity_config/1.0.0"
)
CHEMISTRY_AWARE_POSE_VALIDITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_chemistry_aware_pose_validity/1.0.0"
)
_UNSPECIFIED_STEREO = {"", "NONE", "UNKNOWN", "UNSPECIFIED"}


class ChemistryAwarePoseValidityError(ValueError):
    """Inputs violate the bounded chemistry-aware pose-validity contract."""


def _finite_nonnegative(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ChemistryAwarePoseValidityError(
            f"{name} must be a finite non-negative real number"
        )
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ChemistryAwarePoseValidityError(
            f"{name} must be a finite non-negative real number"
        )
    return result


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256(value: object, *, name: str) -> str:
    if not isinstance(value, str):
        raise ChemistryAwarePoseValidityError(f"{name} must be a lowercase SHA-256")
    digest = value.strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ChemistryAwarePoseValidityError(f"{name} must be a lowercase SHA-256")
    return digest


@dataclass(frozen=True)
class ChemistryAwarePoseValidityConfig:
    """Caller-declared, deliberately uncalibrated validity thresholds."""

    maximum_ligand_strain_delta_kcal_per_mol: float
    maximum_repulsive_screened_coulomb_kcal_per_mol: float
    schema_id: str = CHEMISTRY_AWARE_POSE_VALIDITY_CONFIG_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != CHEMISTRY_AWARE_POSE_VALIDITY_CONFIG_SCHEMA_ID:
            raise ChemistryAwarePoseValidityError(
                "unsupported chemistry-aware pose-validity config schema"
            )
        object.__setattr__(
            self,
            "maximum_ligand_strain_delta_kcal_per_mol",
            _finite_nonnegative(
                self.maximum_ligand_strain_delta_kcal_per_mol,
                name="maximum_ligand_strain_delta_kcal_per_mol",
            ),
        )
        object.__setattr__(
            self,
            "maximum_repulsive_screened_coulomb_kcal_per_mol",
            _finite_nonnegative(
                self.maximum_repulsive_screened_coulomb_kcal_per_mol,
                name="maximum_repulsive_screened_coulomb_kcal_per_mol",
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "maximum_ligand_strain_delta_kcal_per_mol": (
                self.maximum_ligand_strain_delta_kcal_per_mol
            ),
            "maximum_repulsive_screened_coulomb_kcal_per_mol": (
                self.maximum_repulsive_screened_coulomb_kcal_per_mol
            ),
            "threshold_source": "caller_declared_unfitted_policy",
            "calibrated": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())


@dataclass(frozen=True)
class ChemistryAwarePoseValidityResult:
    """One exact proposal's parameter-bound validity observation."""

    checks: dict[str, bool]
    evaluated_checks: dict[str, bool]
    complete: bool
    valid_within_evaluated_scope: bool
    measurements: dict[str, float | int]
    blockers: tuple[str, ...]
    not_evaluated_reasons: dict[str, str]
    validity_config_fingerprint_sha256: str
    problem_fingerprint_sha256: str
    proposal_fingerprint_sha256: str
    parameter_source_sha256: str
    score_breakdown: DockingScoreBreakdown
    interaction_diagnostics: ReferenceDockingInteractionDiagnostics
    schema_id: str = CHEMISTRY_AWARE_POSE_VALIDITY_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != CHEMISTRY_AWARE_POSE_VALIDITY_SCHEMA_ID:
            raise ChemistryAwarePoseValidityError(
                "unsupported chemistry-aware pose-validity schema"
            )
        checks = dict(self.checks)
        evaluated = dict(self.evaluated_checks)
        if not checks or set(checks) != set(evaluated):
            raise ChemistryAwarePoseValidityError(
                "checks and evaluated_checks must have the same non-empty keys"
            )
        if not all(
            isinstance(value, bool) for value in (*checks.values(), *evaluated.values())
        ):
            raise ChemistryAwarePoseValidityError(
                "checks and evaluated_checks must contain booleans"
            )
        expected_complete = all(evaluated.values())
        expected_valid_within_scope = all(
            checks[name] for name, was_evaluated in evaluated.items() if was_evaluated
        )
        if self.complete is not expected_complete:
            raise ChemistryAwarePoseValidityError(
                "complete does not match evaluated_checks"
            )
        if self.valid_within_evaluated_scope is not expected_valid_within_scope:
            raise ChemistryAwarePoseValidityError(
                "valid_within_evaluated_scope does not match checks"
            )
        reasons = {
            str(key): str(value or "").strip()
            for key, value in self.not_evaluated_reasons.items()
        }
        expected_reason_keys = {name for name, value in evaluated.items() if not value}
        if set(reasons) != expected_reason_keys or any(
            not value for value in reasons.values()
        ):
            raise ChemistryAwarePoseValidityError(
                "not_evaluated_reasons must explain every unevaluated check"
            )
        measurements = dict(self.measurements)
        for name, value in measurements.items():
            if (
                not isinstance(name, str)
                or not name
                or isinstance(value, bool)
                or not isinstance(value, Real)
                or not math.isfinite(float(value))
            ):
                raise ChemistryAwarePoseValidityError(
                    "measurements must contain finite numeric values"
                )
        blockers = tuple(str(value or "").strip() for value in self.blockers)
        if any(not value for value in blockers) or len(blockers) != len(set(blockers)):
            raise ChemistryAwarePoseValidityError(
                "blockers must be unique non-empty strings"
            )
        for name in (
            "validity_config_fingerprint_sha256",
            "problem_fingerprint_sha256",
            "proposal_fingerprint_sha256",
            "parameter_source_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _sha256(getattr(self, name), name=name),
            )
        if not isinstance(self.score_breakdown, DockingScoreBreakdown):
            raise ChemistryAwarePoseValidityError(
                "score_breakdown must be DockingScoreBreakdown"
            )
        if not isinstance(
            self.interaction_diagnostics,
            ReferenceDockingInteractionDiagnostics,
        ):
            raise ChemistryAwarePoseValidityError(
                "interaction_diagnostics has the wrong type"
            )
        diagnostics = self.interaction_diagnostics
        if (
            diagnostics.problem_fingerprint_sha256 != self.problem_fingerprint_sha256
            or diagnostics.proposal_fingerprint_sha256
            != self.proposal_fingerprint_sha256
            or diagnostics.parameter_source_sha256 != self.parameter_source_sha256
        ):
            raise ChemistryAwarePoseValidityError(
                "result identities do not match interaction diagnostics"
            )
        object.__setattr__(self, "checks", checks)
        object.__setattr__(self, "evaluated_checks", evaluated)
        object.__setattr__(self, "measurements", measurements)
        object.__setattr__(self, "blockers", blockers)
        object.__setattr__(self, "not_evaluated_reasons", reasons)

    @property
    def valid(self) -> bool:
        return bool(self.complete and self.valid_within_evaluated_scope)

    @property
    def claim_safe(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "valid": self.valid,
            "checks": dict(self.checks),
            "evaluated_checks": dict(self.evaluated_checks),
            "complete": self.complete,
            "valid_within_evaluated_scope": self.valid_within_evaluated_scope,
            "measurements": dict(self.measurements),
            "blockers": list(self.blockers),
            "not_evaluated_reasons": dict(self.not_evaluated_reasons),
            "validity_config_fingerprint_sha256": (
                self.validity_config_fingerprint_sha256
            ),
            "problem_fingerprint_sha256": self.problem_fingerprint_sha256,
            "proposal_fingerprint_sha256": self.proposal_fingerprint_sha256,
            "parameter_source_sha256": self.parameter_source_sha256,
            "score_breakdown": self.score_breakdown.to_dict(),
            "interaction_diagnostics": self.interaction_diagnostics.to_dict(),
            "thresholds_calibrated": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }


def evaluate_chemistry_aware_pose_validity(
    scorer: UncalibratedReferenceDockingScorer,
    proposal: DockingProposal,
    *,
    config: ChemistryAwarePoseValidityConfig,
) -> ChemistryAwarePoseValidityResult:
    """Evaluate one proposal under exact scorer parameters and caller thresholds."""

    if not isinstance(scorer, UncalibratedReferenceDockingScorer):
        raise ChemistryAwarePoseValidityError(
            "scorer must be UncalibratedReferenceDockingScorer"
        )
    if not isinstance(proposal, DockingProposal):
        raise ChemistryAwarePoseValidityError("proposal must be DockingProposal")
    if not isinstance(config, ChemistryAwarePoseValidityConfig):
        raise ChemistryAwarePoseValidityError(
            "config must be ChemistryAwarePoseValidityConfig"
        )

    breakdown, diagnostics = scorer.score_with_diagnostics(proposal)
    terms = {term.term_id: term for term in breakdown.terms}
    required_terms = {
        "receptor_ligand_lennard_jones",
        "receptor_ligand_screened_coulomb",
        "ligand_internal_strain_delta",
        "vdw_overlap_penalty",
    }
    if set(terms) != required_terms:
        raise ChemistryAwarePoseValidityError(
            "reference scorer term decomposition is incomplete"
        )
    if (
        terms["vdw_overlap_penalty"].raw_value
        != diagnostics.receptor_ligand_vdw_overlap_penalty_kcal_per_mol
        or terms["receptor_ligand_screened_coulomb"].raw_value
        != diagnostics.receptor_ligand_charges.signed_screened_coulomb_kcal_per_mol
    ):
        raise ChemistryAwarePoseValidityError(
            "score terms and interaction diagnostics disagree"
        )

    scope = scorer.config.chemistry_scope
    systems = (scorer.receptor_system, scorer.ligand_system)
    parameter_maps = (
        scorer.receptor_parameters.atom_parameter_map,
        scorer.ligand_parameters.atom_parameter_map,
    )
    partial_charge_match = all(
        atom.partial_charge_e is not None
        and math.isclose(
            float(atom.partial_charge_e),
            parameter_map[atom.index].charge_e,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        for system, parameter_map in zip(systems, parameter_maps)
        for atom in system.atoms
    )
    formal_charge_in_scope = all(
        abs(atom.formal_charge) <= scope.maximum_absolute_formal_charge
        for system in systems
        for atom in system.atoms
    )
    supported_elements = all(
        atom.atomic_number in scope.supported_atomic_numbers
        for system in systems
        for atom in system.atoms
    )
    receptor_polymer_only = all(
        residue.entity_type.strip().lower() == "polymer"
        for residue in scorer.receptor_system.residues
    )
    has_aromatic = any(
        atom.aromatic for system in systems for atom in system.atoms
    ) or any(bond.aromatic for system in systems for bond in system.bonds)
    has_declared_stereo = any(
        atom.stereo.strip().upper() not in _UNSPECIFIED_STEREO
        for atom in scorer.ligand_system.atoms
    ) or any(
        bond.stereo.strip().upper() not in _UNSPECIFIED_STEREO
        for bond in scorer.ligand_system.bonds
    )

    strain_delta = terms["ligand_internal_strain_delta"].raw_value
    repulsive_coulomb = (
        diagnostics.receptor_ligand_charges.repulsive_screened_coulomb_kcal_per_mol
    )
    checks = {
        "score_breakdown_complete": breakdown.complete,
        "force_field_parameter_identity_bound": (
            diagnostics.parameter_source_sha256 == scorer.parameter_source_sha256
            and diagnostics.problem_fingerprint_sha256
            == scorer.problem.fingerprint_sha256
            and diagnostics.proposal_fingerprint_sha256 == proposal.fingerprint_sha256
        ),
        "supported_element_and_cofactor_scope": (
            supported_elements and receptor_polymer_only
        ),
        "formal_charge_within_declared_scope": formal_charge_in_scope,
        "partial_charge_parameter_match": partial_charge_match,
        "receptor_ligand_element_parameterized_clash_free": (
            diagnostics.receptor_ligand_contacts.clashing_pair_count == 0
        ),
        "ligand_internal_element_parameterized_clash_free": (
            diagnostics.ligand_internal_contacts.clashing_pair_count == 0
        ),
        "ligand_strain_within_declared_limit": (
            strain_delta <= config.maximum_ligand_strain_delta_kcal_per_mol
        ),
        "repulsive_screened_coulomb_within_declared_limit": (
            repulsive_coulomb <= config.maximum_repulsive_screened_coulomb_kcal_per_mol
        ),
        "aromatic_specific_interactions_covered": not has_aromatic,
        "declared_stereo_covered": not has_declared_stereo,
    }
    evaluated_checks = {name: True for name in checks}
    not_evaluated_reasons: dict[str, str] = {}
    if has_aromatic:
        evaluated_checks["aromatic_specific_interactions_covered"] = False
        not_evaluated_reasons["aromatic_specific_interactions_covered"] = (
            "reference_scorer_has_no_aromatic_specific_interaction_term"
        )
    if has_declared_stereo:
        evaluated_checks["declared_stereo_covered"] = False
        not_evaluated_reasons["declared_stereo_covered"] = (
            "reference_scorer_does_not_evaluate_declared_atom_or_bond_stereo"
        )

    blockers = list(
        dict.fromkeys(
            (
                *breakdown.blockers,
                "chemistry_aware_pose_validity_thresholds_caller_supplied_not_calibrated",
                "public_pose_validity_validation_missing",
            )
        )
    )
    failure_blockers = {
        "score_breakdown_complete": "reference_score_breakdown_incomplete",
        "force_field_parameter_identity_bound": "pose_parameter_identity_binding_failed",
        "supported_element_and_cofactor_scope": "unsupported_element_or_cofactor_scope",
        "formal_charge_within_declared_scope": "formal_charge_scope_failed",
        "partial_charge_parameter_match": "partial_charge_parameter_mismatch",
        "receptor_ligand_element_parameterized_clash_free": (
            "receptor_ligand_element_parameterized_clash_detected"
        ),
        "ligand_internal_element_parameterized_clash_free": (
            "ligand_internal_element_parameterized_clash_detected"
        ),
        "ligand_strain_within_declared_limit": "ligand_strain_limit_exceeded",
        "repulsive_screened_coulomb_within_declared_limit": (
            "repulsive_screened_coulomb_limit_exceeded"
        ),
    }
    for check_name, blocker in failure_blockers.items():
        if evaluated_checks[check_name] and not checks[check_name]:
            blockers.append(blocker)

    cross_contacts = diagnostics.receptor_ligand_contacts
    internal_contacts = diagnostics.ligand_internal_contacts
    charges = diagnostics.receptor_ligand_charges
    measurements: dict[str, float | int] = {
        "receptor_ligand_pair_count": cross_contacts.total_pair_count,
        "receptor_ligand_clashing_pair_count": cross_contacts.clashing_pair_count,
        "receptor_ligand_minimum_contact_ratio": float(
            cross_contacts.minimum_contact_ratio
        ),
        "receptor_ligand_maximum_overlap_angstrom": (
            cross_contacts.maximum_overlap_angstrom
        ),
        "ligand_internal_total_pair_count": internal_contacts.total_pair_count,
        "ligand_internal_excluded_pair_count": internal_contacts.excluded_pair_count,
        "ligand_internal_evaluated_pair_count": internal_contacts.evaluated_pair_count,
        "ligand_internal_clashing_pair_count": internal_contacts.clashing_pair_count,
        "receptor_ligand_signed_screened_coulomb_kcal_per_mol": (
            charges.signed_screened_coulomb_kcal_per_mol
        ),
        "receptor_ligand_attractive_screened_coulomb_kcal_per_mol": (
            charges.attractive_screened_coulomb_kcal_per_mol
        ),
        "receptor_ligand_repulsive_screened_coulomb_kcal_per_mol": (
            charges.repulsive_screened_coulomb_kcal_per_mol
        ),
        "receptor_ligand_like_charge_pair_count": charges.like_charge_pair_count,
        "receptor_ligand_opposite_charge_pair_count": (
            charges.opposite_charge_pair_count
        ),
        "receptor_ligand_neutral_charge_pair_count": charges.neutral_charge_pair_count,
        "ligand_internal_strain_delta_kcal_per_mol": strain_delta,
        "maximum_ligand_strain_delta_kcal_per_mol": (
            config.maximum_ligand_strain_delta_kcal_per_mol
        ),
        "maximum_repulsive_screened_coulomb_kcal_per_mol": (
            config.maximum_repulsive_screened_coulomb_kcal_per_mol
        ),
        "receptor_net_formal_charge_e": diagnostics.receptor_net_formal_charge_e,
        "ligand_net_formal_charge_e": diagnostics.ligand_net_formal_charge_e,
        "receptor_net_partial_charge_e": diagnostics.receptor_net_partial_charge_e,
        "ligand_net_partial_charge_e": diagnostics.ligand_net_partial_charge_e,
    }
    if internal_contacts.minimum_contact_ratio is not None:
        measurements["ligand_internal_minimum_contact_ratio"] = (
            internal_contacts.minimum_contact_ratio
        )
        measurements["ligand_internal_maximum_overlap_angstrom"] = (
            internal_contacts.maximum_overlap_angstrom
        )

    complete = all(evaluated_checks.values())
    valid_within_evaluated_scope = all(
        checks[name]
        for name, was_evaluated in evaluated_checks.items()
        if was_evaluated
    )
    return ChemistryAwarePoseValidityResult(
        checks=checks,
        evaluated_checks=evaluated_checks,
        complete=complete,
        valid_within_evaluated_scope=valid_within_evaluated_scope,
        measurements=measurements,
        blockers=tuple(dict.fromkeys(blockers)),
        not_evaluated_reasons=not_evaluated_reasons,
        validity_config_fingerprint_sha256=config.fingerprint_sha256,
        problem_fingerprint_sha256=scorer.problem.fingerprint_sha256,
        proposal_fingerprint_sha256=proposal.fingerprint_sha256,
        parameter_source_sha256=scorer.parameter_source_sha256,
        score_breakdown=breakdown,
        interaction_diagnostics=diagnostics,
    )


__all__ = [
    "CHEMISTRY_AWARE_POSE_VALIDITY_CONFIG_SCHEMA_ID",
    "CHEMISTRY_AWARE_POSE_VALIDITY_SCHEMA_ID",
    "ChemistryAwarePoseValidityConfig",
    "ChemistryAwarePoseValidityError",
    "ChemistryAwarePoseValidityResult",
    "evaluate_chemistry_aware_pose_validity",
]
