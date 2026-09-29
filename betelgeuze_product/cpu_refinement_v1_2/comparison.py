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
from .fixed_receptor import FixedReceptorEvaluator, FIXED_REPORT_SCHEMA, FIXED_POLICY_ID
from .minimization import SolverConfig
from .provenance import ResearchError, digest, source_manifest
from .refinement import ExtendedRefiner
from .selection import SelectionConfig, candidate_from_row, select_final_candidates, refinement_admissible
from .work import WorkMeter
from .scoring_profile import (LEGACY_MODEL, EXPLICIT_MODEL, EXPLICIT_REPORT_SCHEMA,
    REGISTERED_REPORT_SCHEMA, DEFAULT_PROPOSAL_POLICY, REGISTERED_PROPOSAL_POLICY,
    scorer_class, require_model, validate_proposal_settings)
from .registered_pose import generate_registered_pose
from .candidate_search import _evaluate_candidate_rows


class MeasuredScorer(ChemistryPoseScorerV1):
    """Observe the unchanged Python scorer, including exceptions, without global replacement."""

    def __init__(self, *args, work_meter: WorkMeter, **kwargs):
        self._work_meter = work_meter
        super().__init__(*args, **kwargs)

    def _score_terms_python(self, proposal):
        with self._work_meter.measure("score.evaluate"):
            return super()._score_terms_python(proposal)


def measured_scorer(scoring_model, *args, work_meter, **kwargs):
    if scoring_model == LEGACY_MODEL:
        return MeasuredScorer(*args, work_meter=work_meter, **kwargs)
    class MeasuredExplicit(scorer_class(scoring_model)):
        def _score_terms_python(self, proposal):
            with work_meter.measure("score.evaluate"):
                return super()._score_terms_python(proposal)
    return MeasuredExplicit(*args, **kwargs)


def choose_variant(before: dict, after: dict, attempt: dict, require_convergence: bool) -> tuple[str, str]:
    fallback = "baseline" if before["succeeded"] and before["selection_eligible"] else "none"
    if attempt["status"] != "success" or not after["succeeded"]:
        return fallback, "refinement_or_rescoring_failed"
    if not after["selection_eligible"]:
        return fallback, "refined_pose_invalid_or_incomplete"
    if require_convergence and not attempt["converged"]:
        return fallback, "refinement_not_converged"
    if attempt["energy_delta"] > 0:
        return fallback, "total_objective_increased" if "energy_basis" in attempt else "internal_energy_increased"
    if not refinement_admissible(after, attempt, require_convergence):
        if "max_internal_increase_kcal_per_mol" in attempt:
            return fallback, "ligand_internal_strain_limit_exceeded"
        raise ResearchError("refinement admission policy disagreement")
    if fallback == "baseline" and after["score"] >= before["score"]:
        return fallback, "score_not_improved"
    return "refined", "valid_refinement_selected"


def run_comparison(authority, budget, *, receptor_system, ligand_system, parameters,
                   solver: SolverConfig, solvation=None, comparison=None, selection=None, fixed_environment=None, scoring_model=LEGACY_MODEL,
                   proposal_policy=DEFAULT_PROPOSAL_POLICY) -> dict:
    require_model(scoring_model)
    if scoring_model == EXPLICIT_MODEL and fixed_environment is None:
        raise ResearchError("explicit chemical features require fixed-receptor comparison")
    comparison = RefinementComparisonConfig() if comparison is None else comparison
    selection = SelectionConfig(budget.top_k) if selection is None else selection
    validate_proposal_settings(proposal_policy, budget, comparison)
    registered = proposal_policy == REGISTERED_PROPOSAL_POLICY
    if registered and (scoring_model != EXPLICIT_MODEL or fixed_environment is None):
        raise ResearchError("registered pose requires explicit chemical features and fixed receptor")
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
    if fixed_environment is not None:
        if fixed_environment.cross.receptor_system_sha256 != authority.receptor_system_sha256:
            raise ResearchError("fixed environment does not match docking receptor")
        if fixed_environment.cross.coordinate_frame_id != authority.pocket.coordinate_frame_id:
            raise ResearchError("fixed interaction coordinate frame does not match docking pocket")
        fixed_environment.validate_ligand(ligand_system, parameters.base_parameters)
        evaluator = FixedReceptorEvaluator(evaluator, fixed_environment)
    refiner = ExtendedRefiner(authority, ligand_system, parameters, solver, solvation=solvation,
        implementation_source_sha256=implementation, max_attempts=after_budget.candidate_count,
        **({} if fixed_environment is None else {"fixed_environment": fixed_environment}))
    refiner.assert_ready()
    arms, searches, descriptors = {}, {}, {}
    scorer_binding = None
    registered_receipt = None
    for name, arm_budget, arm_refiner in (("baseline", before_budget, None), ("refined", after_budget, refiner)):
        start = time.perf_counter()
        meter = WorkMeter()
        with meter.measure("scorer.construct"):
            scorer = measured_scorer(scoring_model, authority, receptor_system, ligand_system,
                                   work_meter=meter, implementation_source_sha256=implementation)
        if scoring_model == EXPLICIT_MODEL:
            observed_binding = {"feature_model_id": EXPLICIT_MODEL,
                "context": scorer.context.fingerprint_sha256,
                "config": scorer.config.fingerprint_sha256,
                "backend": scorer.backend_receipt_sha256}
            if scorer_binding is not None and scorer_binding != observed_binding:
                raise ResearchError("comparison arms have different scorer identity")
            scorer_binding = observed_binding
        if registered:
            with meter.measure("context.construct"):
                proposals, receipt = generate_registered_pose(authority, arm_budget, ligand_system)
                observed_receipt = receipt.to_dict()
                if registered_receipt is not None and registered_receipt != observed_receipt:
                    raise ResearchError("registered comparison arms have different initial pose receipts")
                registered_receipt = observed_receipt
            # Use the same authenticated candidate executor as resumable runs.
            # A registered pose is never presented as a guided placement receipt.
            with meter.measure("search.execute"):
                search_rows = _evaluate_candidate_rows(proposals, search_space=authority.search_space,
                    budget=arm_budget, scorer=scorer, refiner=arm_refiner,
                    problem_fingerprint=authority.problem.fingerprint_sha256,
                    context=authority.validity_context,
                    validity_fingerprint=authority.validity_context.fingerprint_sha256,
                    unbound_validity_compatibility=False)
            elapsed = time.perf_counter() - start
            rows = [_pose(row, row.score_evidence) for row in search_rows]
            score_descriptor = scorer.score_descriptor
        else:
            with meter.measure("context.construct"):
                context = build_guided_placement_context(authority, receptor_system, ligand_system)
            with meter.measure("search.execute"):
                result = run_authenticated_scorer_v1_guided_search(authority, arm_budget, scorer, context,
                    receptor_system=receptor_system, ligand_system=ligand_system, refiner=arm_refiner,
                    diversity_rmsd_angstrom=selection.diversity_rmsd_angstrom)
            elapsed = time.perf_counter() - start
            result.receipt_sha256
            search = _search(result)
            search_rows, score_descriptor = search.rows, search.score_descriptor
            rows = [_pose(row, scored.terms) for row, scored in zip(search_rows, result.rows, strict=True)]
        if len(search_rows) != arm_budget.candidate_count:
            raise ResearchError("comparison candidate denominator mismatch")
        success_count = sum(row.succeeded for row in search_rows)
        valid_pose_count = sum(row.succeeded and row.pose_valid for row in search_rows)
        reserve_force = 0 if name == "baseline" else len(rows) * force_bound
        reserved = len(rows) * comparison.score_evaluation_weight + reserve_force * comparison.force_evaluation_weight
        if comparison.work_units_per_arm is not None and reserved > comparison.work_units_per_arm:
            raise ResearchError("arm exceeded reserved work")
        arms[name] = {"candidate_count": len(rows), "success_count": success_count,
            "failure_count": len(search_rows) - success_count, "valid_pose_count": valid_pose_count,
            "valid_pose_fraction_all_candidates": valid_pose_count / len(rows),
            "work_units_reserved": reserved, "force_evaluations_reserved": reserve_force,
            "elapsed_seconds": elapsed, "execution_work": meter.snapshot(),
            "score_evaluation_calls": meter.counts("score.evaluate")["calls"],
            "failed_score_evaluation_calls": meter.counts("score.evaluate")["failed"], "rows": rows}
        searches[name], descriptors[name] = search_rows, score_descriptor
    refiner.assert_ready()
    if descriptors["baseline"] != descriptors["refined"]:
        raise ResearchError("comparison score descriptor mismatch")
    attempts = [refiner.attempt_for(row.proposal_fingerprint_sha256).to_dict() for row in searches["refined"]]
    refinement_work = [refiner.attempt_for(row.proposal_fingerprint_sha256).work()
                       for row in searches["refined"]]
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
    if fixed_environment is not None:
        fixed_environment.assert_intact()
        report.update(schema_id=EXPLICIT_REPORT_SCHEMA if scoring_model == EXPLICIT_MODEL else FIXED_REPORT_SCHEMA, selection_policy_id=FIXED_POLICY_ID,
                      cross_parameters=fixed_environment.cross.to_dict(),
                      receptor_ligand_interaction_energy_minimized=True)
    if scoring_model == EXPLICIT_MODEL:
        report["scorer"] = scorer_binding
    if registered:
        report["schema_id"] = REGISTERED_REPORT_SCHEMA
        report["proposal_policy"] = registered_receipt
    report["report_sha256"] = digest(report)
    return report
