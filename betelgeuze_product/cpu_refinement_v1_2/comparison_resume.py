"""Source-bound candidate scheduling for both existing comparison budget modes.

This API returns a development summary, not the published comparison report.
CLI publication and portable report verification remain separate integration.
"""

from betelgeuze_engine_v2.docking.guided_placement import (
    build_guided_placement_context,
    generate_guided_docking_proposals,
)
from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_product.cpu_refinement.refinement_comparison import (
    RefinementComparisonConfig,
    plan_refinement_comparison,
)
from betelgeuze_product.reference_minimization_workflow import _directory, _publish
from .candidate_journal import open_journal, _load, _envelope
from .candidate_execution import CandidateExecution
from .comparison import choose_variant
from .evaluation import ExtendedEvaluator
from .fixed_receptor import FixedReceptorEvaluator
from .refinement import ExtendedRefiner
from .selection import (
    SelectionConfig,
    candidate_from_row,
    select_final_candidates,
    refinement_admissible,
)
from .provenance import (
    ResearchError,
    canonical,
    digest,
    source_manifest,
    environment,
    integer,
    require_digest,
)


def run_candidate_comparison(
    authority,
    budget,
    *,
    receptor_system,
    ligand_system,
    parameters,
    solver,
    output,
    resume=False,
    stop_after=None,
    solvation=None,
    comparison=None,
    selection=None,
    fixed_environment=None,
    request_sha256=None,
):
    if request_sha256 is not None:
        require_digest(request_sha256)
    comparison = RefinementComparisonConfig() if comparison is None else comparison
    selection = SelectionConfig(budget.top_k) if selection is None else selection
    if type(resume) is not bool or selection.top_k != budget.top_k:
        raise ResearchError("invalid resume flag or selection budget")
    before, after, bound = plan_refinement_comparison(
        budget, solver.minimization, comparison
    )
    total = before.candidate_count + after.candidate_count
    if stop_after is not None:
        integer(stop_after, 0, total)
    sources = source_manifest()
    source = digest(sources)
    runtime = environment()
    evaluator = ExtendedEvaluator(parameters, solvation)
    if fixed_environment is not None:
        if (
            fixed_environment.cross.receptor_system_sha256
            != authority.receptor_system_sha256
            or fixed_environment.cross.coordinate_frame_id
            != authority.pocket.coordinate_frame_id
        ):
            raise ResearchError("fixed receptor/frame authority mismatch")
        fixed_environment.validate_ligand(ligand_system, parameters.base_parameters)
        evaluator = FixedReceptorEvaluator(evaluator, fixed_environment)

    def check():
        if (
            source_manifest() != sources
            or environment() != runtime
            or canonical_system_sha256(receptor_system)
            != authority.receptor_system_sha256
            or canonical_system_sha256(ligand_system) != authority.ligand_system_sha256
        ):
            raise ResearchError("comparison source/input/environment changed")
        evaluator.fingerprint_sha256

    check()
    context = build_guided_placement_context(authority, receptor_system, ligand_system)
    plans = []
    for name, arm_budget in (("baseline", before), ("refined", after)):
        proposals, receipt = generate_guided_docking_proposals(
            authority,
            arm_budget,
            context,
            receptor_system=receptor_system,
            ligand_system=ligand_system,
        )
        plans.append((name, arm_budget, proposals, receipt))
    bound_scorer = ChemistryPoseScorerV1(
        authority, receptor_system, ligand_system, implementation_source_sha256=source
    )
    plan = {
        "schema_id": "cpu_candidate_comparison_plan/1.0.0",
        "source": source,
        "environment": runtime,
        "external_request_sha256": request_sha256,
        "authority": authority.input_receipt_sha256,
        "evaluator": evaluator.identity(),
        "atom_count": ligand_system.atom_count,
        "problem": authority.problem.fingerprint_sha256,
        "search_space": authority.search_space.fingerprint_sha256,
        "validity_context": authority.validity_context.fingerprint_sha256,
        "coordinate_frame": authority.pocket.coordinate_frame_id,
        "cross_parameters": None
        if fixed_environment is None
        else fixed_environment.cross.to_dict(),
        "scorer": {
            "context": bound_scorer.context.fingerprint_sha256,
            "config": bound_scorer.config.fingerprint_sha256,
            "backend": bound_scorer.backend_receipt_sha256,
        },
        "solver": solver.to_dict(),
        "budget": budget.to_dict(),
        "comparison": dict(vars(comparison)),
        "selection": selection.to_dict(),
        "force_bound": bound,
        "arms": {
            name: {
                "budget": arm.to_dict(),
                "guidance": receipt.receipt_sha256,
                "proposals": [p.fingerprint_sha256 for p in proposals],
            }
            for name, arm, proposals, receipt in plans
        },
    }
    records = {}
    costs = {}
    offset = 0
    with _directory(output, resume=resume) as directory:
        if resume:
            if canonical(_load(directory / "plan.json")) != canonical(plan):
                raise ResearchError("comparison resume plan changed")
        else:
            _publish(directory / "plan.json", _envelope(plan))
        if {p.name for p in directory.iterdir()} - {
            "plan.json",
            ".minimization.lock",
            "baseline",
            "refined",
        }:
            raise ResearchError("unexpected comparison journal files")
        for name, arm_budget, proposals, _ in plans:
            scorer = ChemistryPoseScorerV1(
                authority,
                receptor_system,
                ligand_system,
                implementation_source_sha256=source,
            )
            refiner = (
                None
                if name == "baseline"
                else ExtendedRefiner(
                    authority,
                    ligand_system,
                    parameters,
                    solver,
                    implementation_source_sha256=source,
                    solvation=solvation,
                    max_attempts=arm_budget.candidate_count,
                    fixed_environment=fixed_environment,
                )
            )
            engine = CandidateExecution(
                authority, arm_budget, scorer, proposals, refiner=refiner
            )
            keys = [digest([name, p.fingerprint_sha256]) for p in proposals]
            indices = {key: i for i, key in enumerate(keys)}
            binding = {
                "schema_id": "cpu_comparison_candidate_journal/1.0.0",
                "request_sha256": digest(plan),
                "implementation_sha256": source,
                "environment_sha256": digest(runtime),
                "candidate_keys": keys,
            }

            def validate(key, record):
                engine.validate(indices[key], record)

            arm_path = directory / name
            with open_journal(
                arm_path,
                binding,
                validate_record=validate,
                resume=resume and arm_path.exists(),
            ) as journal:
                prior = len(journal.records)
                if stop_after is not None and stop_after < offset + prior:
                    raise ResearchError("pause precedes committed progress")
                records[name] = []
                costs[name] = {
                    "reused_candidates": prior,
                    "new_candidates": 0,
                    "historical_force_calls": 0,
                    "new_force_calls": 0,
                    "historical_score_calls": 0,
                    "new_score_calls": 0,
                }
                for index in range(len(proposals)):
                    if stop_after is not None and offset + index >= stop_after:
                        check()
                        costs[name]["interrupted_attempts_unknown_cost"] = (
                            journal.unknown_attempts
                        )
                        return {
                            "execution_complete": False,
                            "committed_candidates": offset + index,
                            "costs": costs,
                            "scientifically_validated": False,
                        }
                    check()
                    _, record = engine.execute(journal, index)
                    records[name].append(record)
                    kind = "historical" if index < prior else "new"
                    costs[name][kind + "_force_calls"] += (
                        0
                        if record["refinement_work"] is None
                        else record["refinement_work"]["force_evaluation_calls"]
                    )
                    costs[name][kind + "_score_calls"] += (
                        record["execution_work"]["stages"]
                        .get("score.evaluate", {})
                        .get("calls", 0)
                    )
                    costs[name]["new_candidates"] += int(index >= prior)
                costs[name]["interrupted_attempts_unknown_cost"] = (
                    journal.unknown_attempts
                )
                costs[name]["intent_counts"] = [
                    len(values) for values in journal.intents
                ]
            offset += len(proposals)
        check()
    arms = {
        name: [record["row"] for record in values] for name, values in records.items()
    }
    attempts = [record["attempt"] for record in records["refined"]]
    descriptor = scorer.score_descriptor
    raw = {
        name: select_final_candidates(
            [
                candidate_from_row(row, name)
                for row in rows
                if row["succeeded"] and row["selection_eligible"]
            ],
            descriptor,
            selection,
            ligand_system.atom_count,
        )
        for name, rows in arms.items()
    }
    admitted = {
        "baseline": raw["baseline"],
        "refined": select_final_candidates(
            [
                candidate_from_row(row, "refined")
                for row, attempt in zip(arms["refined"], attempts, strict=True)
                if refinement_admissible(
                    row, attempt, comparison.require_convergence_for_selection
                )
            ],
            descriptor,
            selection,
            ligand_system.atom_count,
        ),
    }
    pairs, candidates = [], []
    if comparison.mode == "same_candidates":
        for baseline, refined, attempt in zip(
            arms["baseline"], arms["refined"], attempts, strict=True
        ):
            if (
                baseline["proposal_fingerprint_sha256"]
                != refined["proposal_fingerprint_sha256"]
            ):
                raise ResearchError("comparison pairing changed")
            choice, reason = choose_variant(
                baseline, refined, attempt, comparison.require_convergence_for_selection
            )
            pairs.append(
                {
                    "candidate_id": baseline["candidate_id"],
                    "variant": choice,
                    "reason": reason,
                }
            )
            if choice != "none":
                candidates.append(
                    candidate_from_row(
                        baseline if choice == "baseline" else refined, choice
                    )
                )
        final = select_final_candidates(
            candidates, descriptor, selection, ligand_system.atom_count
        )
    else:
        final = None
    summary = {
        "schema_id": "cpu_candidate_comparison_summary/1.0.0",
        "plan": plan,
        "records": records,
        "score_descriptor": descriptor.to_dict(),
        "execution_complete": True,
        "plan_sha256": digest(plan),
        "mode": comparison.mode,
        "rows": arms,
        "attempts": attempts,
        "paired_decisions": pairs,
        "final_selection": final,
        "raw_per_arm_selection": raw,
        "per_arm_selection": admitted,
        "costs": costs,
        "cost_scope": "candidate score and force calls only; startup/replay/validity/publication overhead excluded",
        "scientifically_validated": False,
    }

    from .resume_verification import verify_resume_summary

    summary["summary_sha256"] = digest(summary)
    verify_resume_summary(summary)
    return summary
