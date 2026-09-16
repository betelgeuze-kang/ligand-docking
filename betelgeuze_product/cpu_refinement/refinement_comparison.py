"""Bounded CPU research comparison using the existing authenticated search paths.

This is ligand-internal relaxation, not receptor/ligand energy minimization.
Equal work means an explicit weighted evaluation reservation, NOT equal elapsed
CPU time. Failed evaluations remain in the denominator and are never free.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
import time

from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_system_sha256
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import ReferenceMinimizationConfig
from betelgeuze_engine_v2.physics.reference_parameters import ReferenceForceFieldParameters
from betelgeuze_engine_v2.docking.authority import AuthenticatedDockingProblem
from .energy_refinement_v1_1 import (
    EnergyBasedLocalRefiner, EnergyLocalRefinementConfig,
)
from betelgeuze_engine_v2.docking.guided_placement import build_guided_placement_context
from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
from betelgeuze_engine_v2.docking.proposals import DockingBudget
from betelgeuze_engine_v2.docking.scorer_v1 import (
    ChemistryPoseScorerV1, ScorerV1Config,
    run_authenticated_scorer_v1_guided_search,
)

from betelgeuze_engine_v2.docking.energy_refinement import run_authenticated_energy_refined_scorer_v1_guided_search

SCHEMA_ID = "betelgeuze.cpu_refinement_comparison/1.0.0"
MAX_COMPARISON_CANDIDATES = 256


@dataclass(frozen=True)
class RefinementComparisonConfig:
    mode: str = "same_candidates"
    work_units_per_arm: int | None = None
    score_evaluation_weight: int = 1
    force_evaluation_weight: int = 1
    require_convergence_for_selection: bool = True

    def __post_init__(self) -> None:
        if self.mode not in {"same_candidates", "equal_work_budget"}:
            raise ValueError("unsupported comparison mode")
        for name in ("score_evaluation_weight", "force_evaluation_weight"):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 1_000_000:
                raise ValueError(f"{name} must be an integer in [1,1000000]")
        if self.work_units_per_arm is not None and (
            type(self.work_units_per_arm) is not int
            or not 1 <= self.work_units_per_arm <= 1_000_000_000
        ):
            raise ValueError("work_units_per_arm must be a positive bounded integer")
        if self.mode == "equal_work_budget" and self.work_units_per_arm is None:
            raise ValueError("equal work comparison requires an explicit budget")
        if type(self.require_convergence_for_selection) is not bool:
            raise ValueError("require_convergence_for_selection must be boolean")


def plan_refinement_comparison(
    budget: DockingBudget,
    minimization: ReferenceMinimizationConfig,
    comparison: RefinementComparisonConfig,
) -> tuple[DockingBudget, DockingBudget, int]:
    """Reserve worst-case calls before executing any candidate, without refunds."""
    if not isinstance(budget, DockingBudget) or not isinstance(minimization, ReferenceMinimizationConfig):
        raise TypeError("explicit docking budget and minimization configuration required")
    if not isinstance(comparison, RefinementComparisonConfig):
        raise TypeError("comparison must be RefinementComparisonConfig")
    if not 1 <= budget.candidate_count <= MAX_COMPARISON_CANDIDATES:
        raise ValueError("comparison candidate capacity exceeded")
    if not 1 <= budget.max_refinement_steps <= minimization.max_iterations:
        raise ValueError("refinement step budget must be positive and within minimization bounds")
    # Initial evaluation plus every accepted/rejected backtracking trial.
    force_bound = 1 + budget.max_refinement_steps * (minimization.max_backtracks + 1)
    baseline_unit = comparison.score_evaluation_weight
    refined_unit = baseline_unit + comparison.force_evaluation_weight * force_bound
    baseline_count = refined_count = budget.candidate_count
    limit = comparison.work_units_per_arm
    if comparison.mode == "equal_work_budget":
        assert limit is not None
        baseline_count = min(baseline_count, limit // baseline_unit)
        refined_count = min(refined_count, limit // refined_unit)
    elif limit is not None and refined_count * refined_unit > limit:
        raise ValueError("same-candidate comparison exceeds the work budget")
    if min(baseline_count, refined_count) < 1:
        raise ValueError("work budget cannot reserve one complete refined candidate")
    return (
        replace(budget, candidate_count=baseline_count, top_k=min(budget.top_k, baseline_count),
                max_refinement_steps=0),
        replace(budget, candidate_count=refined_count, top_k=min(budget.top_k, refined_count)),
        force_bound,
    )


def _search(result):
    return result.guided_search_result.authenticated_search_result.search_result


def _pose(row, terms) -> dict:
    """Bind the exported coordinates to the coordinates actually scored."""
    value = row.to_dict()
    value["coordinates_sha256"] = None
    value["coordinates_binary64_hex"] = None
    value["terms"] = None if terms is None else terms.to_dict()
    if row.succeeded:
        row.proposal.assert_integrity()
        if terms is None or terms.proposal_fingerprint_sha256 != row.proposal.fingerprint_sha256:
            raise ValueError("score terms are not bound to the returned pose")
        value["coordinates_sha256"] = coordinate_fingerprint(row.proposal.coordinates)
        value["coordinates_binary64_hex"] = [
            [float(v).hex() for v in xyz] for xyz in row.proposal.coordinates.tolist()
        ]
    return value


def _arm(search, scorer_rows, seconds, comparison, force_bound, attempts=None) -> dict:
    rows = [_pose(row, scored.terms) for row, scored in zip(search.rows, scorer_rows, strict=True)]
    attempts = None if attempts is None else tuple(attempts)
    if attempts is not None and len(attempts) != len(rows):
        raise ValueError("refinement attempt denominator mismatch")
    unknown = 0 if attempts is None else sum(a.status != "success" for a in attempts)
    observed_force = 0 if attempts is None else sum(
        a.evaluation_count for a in attempts if a.status == "success"
    )
    if attempts is not None and any(
        a.status == "success" and a.evaluation_count > force_bound for a in attempts
    ):
        raise ValueError("refinement exceeded its reserved force evaluation budget")
    force_reserved = 0 if attempts is None else len(rows) * force_bound
    reserved = (len(rows) * comparison.score_evaluation_weight
                + force_reserved * comparison.force_evaluation_weight)
    if comparison.work_units_per_arm is not None and reserved > comparison.work_units_per_arm:
        raise ValueError("comparison arm exceeded its reserved budget")
    return {
        "candidate_count": len(rows),
        "success_count": search.success_count,
        "failure_count": search.failure_count,
        "valid_pose_count": search.valid_pose_count,
        "selection_eligible_count": search.selection_eligible_count,
        "valid_pose_fraction_all_candidates": search.valid_pose_count / len(rows),
        "budget": search.budget.to_dict(),
        "top_candidate_ids": [r.candidate_id for r in search.top_rows],
        "search_fingerprint_sha256": search.search_fingerprint_sha256,
        "elapsed_seconds": seconds,
        "score_slots_reserved": len(rows),
        "successful_score_evaluations": search.success_count,
        "force_evaluations_reserved": force_reserved,
        "force_evaluations_observed_lower_bound": observed_force,
        "force_evaluations_exact": None if unknown else observed_force,
        "failed_attempts_with_unknown_work": unknown,
        "work_units_reserved": reserved,
        "unreserved_work_units": (None if comparison.work_units_per_arm is None
                                  else comparison.work_units_per_arm - reserved),
        "rows": rows,
        "attempts": None if attempts is None else [a.to_dict() for a in attempts],
    }


def _selection(before, after, attempt, require_convergence):
    """Select at most one variant; invalid/failing refinement cannot erase input."""
    fallback = "baseline" if before.succeeded and before.selection_eligible else "none"
    if attempt.status != "success" or not after.succeeded:
        return fallback, "refinement_or_rescoring_failed"
    if not after.selection_eligible:
        return fallback, "refined_pose_invalid_or_incomplete"
    if require_convergence and not attempt.converged:
        return fallback, "refinement_not_converged"
    if attempt.energy_delta_kcal_per_mol > 0.0:
        return fallback, "internal_energy_increased"
    if fallback == "baseline" and after.score >= before.score:
        return fallback, "score_not_improved"
    return "refined", "valid_refinement_selected"


def run_cpu_refinement_comparison(
    authority: AuthenticatedDockingProblem,
    budget: DockingBudget,
    *,
    receptor_system: AllAtomSystem,
    ligand_system: AllAtomSystem,
    parameters: ReferenceForceFieldParameters,
    implementation_source_sha256: str,
    minimization: ReferenceMinimizationConfig,
    comparison: RefinementComparisonConfig | None = None,
    scorer_config: ScorerV1Config | None = None,
) -> dict:
    """Run two real CPU search paths, retaining coordinates, failures and costs.

    same_candidates asserts exact source proposal identity, not merely equal
    seeds. equal_work_budget intentionally uses separate candidate counts and
    does not pretend that independent arm rows form matched pairs.
    """
    comparison = RefinementComparisonConfig() if comparison is None else comparison
    before_budget, after_budget, force_bound = plan_refinement_comparison(
        budget, minimization, comparison
    )
    if not isinstance(authority, AuthenticatedDockingProblem):
        raise TypeError("authenticated docking problem required")
    if (canonical_system_sha256(receptor_system) != authority.receptor_system_sha256
            or canonical_system_sha256(ligand_system) != authority.ligand_system_sha256):
        raise ValueError("comparison source systems are cross-wired")
    if (ligand_system.model_count != 1 or receptor_system.model_count != 1
            or ligand_system.cell is not None or receptor_system.cell is not None):
        raise ValueError("comparison supports single-model nonperiodic systems only")
    # Validate both configurations and parameter topology before executing either arm.
    refiner = EnergyBasedLocalRefiner(
        authority, ligand_system, parameters,
        implementation_source_sha256=implementation_source_sha256,
        config=EnergyLocalRefinementConfig(minimization=minimization,
                                          max_attempts=after_budget.candidate_count),
    )
    refiner.assert_ready()
    scorer_args = dict(implementation_source_sha256=implementation_source_sha256,
                       config=scorer_config)
    start = time.perf_counter()
    before_scorer = ChemistryPoseScorerV1(authority, receptor_system, ligand_system, **scorer_args)
    before_context = build_guided_placement_context(authority, receptor_system, ligand_system)
    before = run_authenticated_scorer_v1_guided_search(
        authority, before_budget, before_scorer, before_context,
        receptor_system=receptor_system, ligand_system=ligand_system,
    )
    before_seconds = time.perf_counter() - start
    start = time.perf_counter()
    after_scorer = ChemistryPoseScorerV1(authority, receptor_system, ligand_system, **scorer_args)
    after_context = build_guided_placement_context(authority, receptor_system, ligand_system)
    after = run_authenticated_energy_refined_scorer_v1_guided_search(
        authority, after_budget, after_scorer, after_context, refiner,
        receptor_system=receptor_system, ligand_system=ligand_system,
    )
    after_seconds = time.perf_counter() - start
    # Revalidate the retained receipt chain; this also detects mutated coordinates.
    before.receipt_sha256
    after.receipt_sha256
    refiner.assert_ready()
    bsearch, asearch = _search(before), _search(after.scorer_v1_result)
    if len(bsearch.rows) != before_budget.candidate_count or len(asearch.rows) != after_budget.candidate_count:
        raise ValueError("comparison search denominator mismatch")
    if (canonical_system_sha256(receptor_system) != authority.receptor_system_sha256
            or canonical_system_sha256(ligand_system) != authority.ligand_system_sha256):
        raise ValueError("comparison mutated an input system")
    attempts = tuple(row.attempt for row in after.rows)
    paired = []
    selected = []
    if comparison.mode == "same_candidates":
        for b, a, attempt in zip(bsearch.rows, asearch.rows, attempts, strict=True):
            if (b.proposal_index != a.proposal_index or b.candidate_id != a.candidate_id
                    or b.proposal_fingerprint_sha256 != a.proposal_fingerprint_sha256
                    or attempt.source_proposal_fingerprint_sha256 != b.proposal_fingerprint_sha256):
                raise ValueError("same-candidate comparison source identity mismatch")
            if b.succeeded and coordinate_fingerprint(b.proposal.coordinates) != attempt.pre_coordinates_sha256:
                raise ValueError("baseline was not scored at the pre-refinement coordinates")
            if a.succeeded and coordinate_fingerprint(a.proposal.coordinates) != attempt.post_coordinates_sha256:
                raise ValueError("refinement was not scored at the post-refinement coordinates")
            choice, reason = _selection(b, a, attempt, comparison.require_convergence_for_selection)
            chosen = b if choice == "baseline" else a if choice == "refined" else None
            paired.append({
                "candidate_id": b.candidate_id,
                "source_proposal_fingerprint_sha256": b.proposal_fingerprint_sha256,
                "pre_coordinates_sha256": attempt.pre_coordinates_sha256,
                "post_coordinates_sha256": attempt.post_coordinates_sha256 or None,
                "baseline_score": b.score,
                "refined_score": a.score,
                "score_delta": None if b.score is None or a.score is None else a.score - b.score,
                "energy_delta_kcal_per_mol": (attempt.energy_delta_kcal_per_mol
                                              if attempt.status == "success" else None),
                "converged": attempt.converged if attempt.status == "success" else None,
                "baseline_pose_valid": b.pose_valid,
                "refined_pose_valid": a.pose_valid,
                "selected_variant": choice,
                "selection_reason": reason,
            })
            if chosen is not None:
                selected.append({
                    "candidate_id": chosen.candidate_id, "variant": choice,
                    "score": chosen.score,
                    "coordinates_sha256": coordinate_fingerprint(chosen.proposal.coordinates),
                    "coordinates_binary64_hex": [[float(v).hex() for v in row]
                                                  for row in chosen.proposal.coordinates.tolist()],
                })
    report = {
        "schema_id": SCHEMA_ID,
        "mode": comparison.mode,
        "implementation_source_sha256": implementation_source_sha256,
        "authority_input_receipt_sha256": authority.input_receipt_sha256,
        "parameter_fingerprint_sha256": parameters.fingerprint_sha256,
        "minimization": minimization.to_dict(),
        "comparison": dict(vars(comparison)),
        "candidate_count_cap": budget.candidate_count,
        "force_evaluation_upper_bound_per_candidate": force_bound,
        "baseline": _arm(bsearch, before.rows, before_seconds, comparison, force_bound),
        "refined": _arm(asearch, after.scorer_v1_result.rows, after_seconds,
                        comparison, force_bound, attempts),
        "paired_rows": paired,
        "selected_candidates": selected,
        "selected_candidates_are_globally_ranked_or_clustered": False,
        "timing_scope": "arm_scorer_context_construction_generation_refinement_scoring_validity_selection",
        "timing_excludes": ["input_preparation", "common_preflight", "refiner_construction", "report_publication"],
        "equal_elapsed_compute_time_claimed": False,
        "failure_rows_retained": True,
        "receptor_ligand_interaction_energy_minimized": False,
        "scientifically_validated": False,
        "customer_execution_allowed": False,
        "claim_safe": False,
    }
    if not all(math.isfinite(v) and v >= 0. for v in (before_seconds, after_seconds)):
        raise ValueError("non-finite elapsed time")
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    report["report_sha256"] = hashlib.sha256(encoded).hexdigest()
    return report
