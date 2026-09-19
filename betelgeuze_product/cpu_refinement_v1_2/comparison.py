"""Candidate generation -> corrected extended refinement -> actual rescore -> Top-K."""
from __future__ import annotations

import time

from betelgeuze_engine_v2.docking.guided_placement import build_guided_placement_context
from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1, run_authenticated_scorer_v1_guided_search
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_product.cpu_refinement.refinement_comparison import (
    RefinementComparisonConfig, _pose, _search, plan_refinement_comparison,
)
from .evidence_contracts import REPORT_SCHEMA, POLICY_ID
from .evaluation import ExtendedEvaluator
from .minimization import SolverConfig
from .provenance import ResearchError, digest, source_manifest
from .refinement import ExtendedRefiner
from .selection import SelectionConfig, candidate_from_row, select_final_candidates, refinement_admissible
from .work import WorkMeter


class MeasuredScorer(ChemistryPoseScorerV1):
    """Observe the unchanged Python scorer, including exceptions, without global replacement."""

    def __init__(self, *args, work_meter: WorkMeter, **kwargs):
        self._work_meter = work_meter
        super().__init__(*args, **kwargs)

    def _score_terms_python(self, proposal):
        with self._work_meter.measure("score.evaluate"):
            return super()._score_terms_python(proposal)


def choose_variant(before: dict, after: dict, attempt: dict, require_convergence: bool) -> tuple[str, str]:
    fallback = "baseline" if before["succeeded"] and before["selection_eligible"] else "none"
    if attempt["status"] != "success" or not after["succeeded"]:
        return fallback, "refinement_or_rescoring_failed"
    if not after["selection_eligible"]:
        return fallback, "refined_pose_invalid_or_incomplete"
    if require_convergence and not attempt["converged"]:
        return fallback, "refinement_not_converged"
    if attempt["energy_delta"] > 0:
        return fallback, "internal_energy_increased"
    if not refinement_admissible(after, attempt, require_convergence):
        raise ResearchError("refinement admission policy disagreement")
    if fallback == "baseline" and after["score"] >= before["score"]:
        return fallback, "score_not_improved"
    return "refined", "valid_refinement_selected"


def run_comparison(authority, budget, *, receptor_system, ligand_system, parameters,
                   solver: SolverConfig, solvation=None, comparison=None, selection=None) -> dict:
    comparison = RefinementComparisonConfig() if comparison is None else comparison
    selection = SelectionConfig(budget.top_k) if selection is None else selection
    if type(solver) is not SolverConfig:
        raise ResearchError("explicit corrected solver required")
    if type(selection) is not SelectionConfig or selection.top_k != budget.top_k:
        raise ResearchError("final Top-K must match docking budget")
    before_budget, after_budget, force_bound = plan_refinement_comparison(budget, solver.minimization, comparison)
    if (canonical_system_sha256(receptor_system) != authority.receptor_system_sha256
            or canonical_system_sha256(ligand_system) != authority.ligand_system_sha256):
        raise ResearchError("comparison source identity mismatch")
    sources = source_manifest()
    implementation = digest(sources)
    evaluator = ExtendedEvaluator(parameters, solvation)
    refiner = ExtendedRefiner(authority, ligand_system, parameters, solver, solvation=solvation,
        implementation_source_sha256=implementation, max_attempts=after_budget.candidate_count)
    refiner.assert_ready()
    arms, searches, descriptors = {}, {}, {}
    for name, arm_budget, arm_refiner in (("baseline", before_budget, None), ("refined", after_budget, refiner)):
        start = time.perf_counter()
        meter = WorkMeter()
        with meter.measure("scorer.construct"):
            scorer = MeasuredScorer(authority, receptor_system, ligand_system,
                                   work_meter=meter, implementation_source_sha256=implementation)
        with meter.measure("context.construct"):
            context = build_guided_placement_context(authority, receptor_system, ligand_system)
        with meter.measure("search.execute"):
            result = run_authenticated_scorer_v1_guided_search(authority, arm_budget, scorer, context,
                receptor_system=receptor_system, ligand_system=ligand_system, refiner=arm_refiner,
                diversity_rmsd_angstrom=selection.diversity_rmsd_angstrom)
        elapsed = time.perf_counter() - start
        result.receipt_sha256
        search = _search(result)
        if len(search.rows) != arm_budget.candidate_count:
            raise ResearchError("comparison candidate denominator mismatch")
        rows = [_pose(row, scored.terms) for row, scored in zip(search.rows, result.rows, strict=True)]
        reserve_force = 0 if name == "baseline" else len(rows) * force_bound
        reserved = len(rows) * comparison.score_evaluation_weight + reserve_force * comparison.force_evaluation_weight
        if comparison.work_units_per_arm is not None and reserved > comparison.work_units_per_arm:
            raise ResearchError("arm exceeded reserved work")
        arms[name] = {"candidate_count": len(rows), "success_count": search.success_count,
            "failure_count": search.failure_count, "valid_pose_count": search.valid_pose_count,
            "valid_pose_fraction_all_candidates": search.valid_pose_count / len(rows),
            "work_units_reserved": reserved, "force_evaluations_reserved": reserve_force,
            "elapsed_seconds": elapsed, "execution_work": meter.snapshot(),
            "score_evaluation_calls": meter.counts("score.evaluate")["calls"],
            "failed_score_evaluation_calls": meter.counts("score.evaluate")["failed"], "rows": rows}
        searches[name], descriptors[name] = search, search.score_descriptor
    refiner.assert_ready()
    if descriptors["baseline"] != descriptors["refined"]:
        raise ResearchError("comparison score descriptor mismatch")
    attempts = [refiner.attempt_for(row.proposal_fingerprint_sha256).to_dict() for row in searches["refined"].rows]
    refinement_work = [refiner.attempt_for(row.proposal_fingerprint_sha256).work()
                       for row in searches["refined"].rows]
    if any(row["force_evaluation_calls"] > force_bound for row in refinement_work):
        raise ResearchError("actual force calls exceeded reserved work")
    arms["baseline"]["actual_force_evaluation_calls"] = 0
    arms["refined"]["actual_force_evaluation_calls"] = sum(row["force_evaluation_calls"] for row in refinement_work)
    arms["refined"]["failed_force_evaluation_calls"] = sum(row["failed_force_evaluation_calls"] for row in refinement_work)
    pairs, candidates = [], []
    if comparison.mode == "same_candidates":
        for before, after, attempt in zip(arms["baseline"]["rows"], arms["refined"]["rows"], attempts, strict=True):
            if (before["proposal_fingerprint_sha256"] != after["proposal_fingerprint_sha256"]
                    or before["proposal_fingerprint_sha256"] != attempt["source_proposal_fingerprint_sha256"]
                    or before["candidate_id"] != after["candidate_id"]
                    or before["proposal_index"] != after["proposal_index"]):
                raise ResearchError("same-candidate source mismatch")
            for row, key in ((before, "pre_coordinates_sha256"), (after, "post_coordinates_sha256")):
                if row["succeeded"] and row["coordinates_sha256"] != attempt.get(key):
                    raise ResearchError("scored coordinates do not match actual refinement coordinates")
            choice, reason = choose_variant(before, after, attempt, comparison.require_convergence_for_selection)
            pairs.append({"candidate_id": before["candidate_id"], "variant": choice, "reason": reason})
            if choice != "none":
                candidates.append(candidate_from_row(before if choice == "baseline" else after, choice))
        final = select_final_candidates(candidates, descriptors["baseline"], selection, ligand_system.atom_count)
    else:
        final = None  # Different source sets cannot masquerade as matched pairs.
    raw_per_arm = {name: select_final_candidates(
        [candidate_from_row(row, name) for row in arms[name]["rows"] if row["succeeded"] and row["selection_eligible"]],
        descriptors[name], selection, ligand_system.atom_count) for name in arms}
    per_arm = {"baseline": raw_per_arm["baseline"],
        "refined": select_final_candidates(
            [candidate_from_row(row, "refined") for row, attempt in
             zip(arms["refined"]["rows"], attempts, strict=True)
             if refinement_admissible(row, attempt, comparison.require_convergence_for_selection)],
            descriptors["refined"], selection, ligand_system.atom_count)}
    if (source_manifest() != sources
            or canonical_system_sha256(receptor_system) != authority.receptor_system_sha256
            or canonical_system_sha256(ligand_system) != authority.ligand_system_sha256):
        raise ResearchError("comparison input or implementation changed")
    report = {"schema_id": REPORT_SCHEMA, "mode": comparison.mode,
              "implementation_source_sha256": implementation,
              "authority_input_receipt_sha256": authority.input_receipt_sha256,
              "evaluator": evaluator.identity(), "solver": solver.to_dict(),
              "comparison": dict(vars(comparison)), "budget": budget.to_dict(),
              "atom_count": ligand_system.atom_count, "arms": arms, "attempts": attempts,
              "paired_decisions": pairs, "final_selection": final, "per_arm_selection": per_arm,
              "refinement_work": refinement_work,
              "selection_config": selection.to_dict(), "selection_policy_id": POLICY_ID,
              "raw_per_arm_selection": raw_per_arm, "request_binding": None,
              "force_evaluation_bound_per_candidate": force_bound,
              "timing_scope": "scorer_context_generation_refinement_scoring_validity_selection_per_arm",
              "timing_excludes": ["preflight", "source_verification", "final_cross_variant_selection", "publication"],
              "failure_rows_retained": True, "receptor_ligand_interaction_energy_minimized": False,
              "equal_elapsed_cpu_time_claimed": False, "scientifically_validated": False,
              "customer_execution_allowed": False, "claim_safe": False}
    report["report_sha256"] = digest(report)
    return report
