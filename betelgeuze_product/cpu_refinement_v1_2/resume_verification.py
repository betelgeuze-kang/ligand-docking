"""Portable consistency verification of candidate-resume development summaries.

Does not read source inputs or reexecute scorer/physics. Hashes are not signatures;
coherently rewriting every retained observation is outside this verification.
"""

from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
from betelgeuze_engine_v2.docking.scorer_v1 import (
    ScorerV1Terms,
    SCORER_V1_SCORE_ID,
    SCORER_V1_APPLICABILITY_DOMAIN_ID,
)
from betelgeuze_engine_v2.docking.scoring import DockingScoreDescriptor, ScoreDirection
from .score_replay import _IDENTITIES, _VALUES, _COUNTS
from .provenance import (
    ResearchError,
    digest,
    exact_fields,
    decode_coordinates,
    integer,
    require_digest,
)
from .evidence_contracts import (
    execution_plan,
    selection_config,
    same,
    verify_pose_row,
    verify_attempt_execution,
    verify_work,
    count,
)
from .fixed_receptor import CrossParameters, FIXED_EVALUATOR_ID
from .evaluation import EVALUATOR_ID
import torch
from .comparison import choose_variant
from .selection import (
    select_final_candidates,
    candidate_from_row,
    refinement_admissible,
)


def verify_resume_summary(doc):
    try:
        _verify(doc)
    except ResearchError:
        raise
    except (KeyError, ValueError, TypeError, IndexError, OverflowError) as exc:
        raise ResearchError("malformed candidate comparison summary") from exc
    return {
        "structural_verification_passed": True,
        "scoring_reexecuted": False,
        "scientifically_validated": False,
        "summary_sha256": doc["summary_sha256"],
    }


def _verify(doc):
    exact_fields(
        doc,
        {
            "schema_id",
            "plan",
            "records",
            "score_descriptor",
            "execution_complete",
            "plan_sha256",
            "mode",
            "rows",
            "attempts",
            "paired_decisions",
            "final_selection",
            "raw_per_arm_selection",
            "per_arm_selection",
            "costs",
            "cost_scope",
            "scientifically_validated",
            "summary_sha256",
        },
    )
    same(doc["schema_id"], "cpu_candidate_comparison_summary/1.0.0", "summary schema")
    same(
        doc["summary_sha256"],
        digest({k: v for k, v in doc.items() if k != "summary_sha256"}),
        "summary digest",
    )
    same(doc["execution_complete"], True, "completed summary")
    same(doc["scientifically_validated"], False, "scientific boundary")
    same(
        doc["cost_scope"],
        "candidate score and force calls only; startup/replay/validity/publication overhead excluded",
        "cost scope",
    )
    plan = doc["plan"]
    exact_fields(
        plan,
        {
            "schema_id",
            "source",
            "environment",
            "external_request_sha256",
            "authority",
            "evaluator",
            "atom_count",
            "problem",
            "search_space",
            "validity_context",
            "coordinate_frame",
            "cross_parameters",
            "scorer",
            "solver",
            "budget",
            "comparison",
            "selection",
            "force_bound",
            "arms",
        },
    )
    same(plan["schema_id"], "cpu_candidate_comparison_plan/1.0.0", "plan schema")
    same(digest(plan), doc["plan_sha256"], "plan digest")
    if plan["external_request_sha256"] is not None:
        require_digest(plan["external_request_sha256"])
    for name in ("source", "authority", "problem", "search_space", "validity_context"):
        require_digest(plan[name])
    exact_fields(plan["scorer"], {"context", "config", "backend"})
    for value in plan["scorer"].values():
        require_digest(value)
    n = integer(plan["atom_count"], 1, 256)
    budget, solver, comparison, before, after, bound, effective = execution_plan(
        plan["budget"], plan["solver"], plan["comparison"]
    )
    same(doc["mode"], comparison.mode, "comparison mode")
    same(plan["force_bound"], bound, "force reservation")
    selection = selection_config(plan["selection"], budget.top_k)
    cross = (
        None
        if plan["cross_parameters"] is None
        else CrossParameters.from_dict(plan["cross_parameters"])
    )
    same(
        plan["evaluator"]["evaluator_id"],
        EVALUATOR_ID if cross is None else FIXED_EVALUATOR_ID,
        "objective identity",
    )
    if cross is not None:
        same(
            plan["coordinate_frame"],
            cross.coordinate_frame_id,
            "coordinate frame binding",
        )
        same(
            plan["evaluator"]["cross_parameters_sha256"],
            cross.fingerprint_sha256,
            "cross parameter binding",
        )
        same(
            plan["evaluator"]["receptor_system_sha256"],
            cross.receptor_system_sha256,
            "fixed receptor binding",
        )
    descriptor = DockingScoreDescriptor(
        SCORER_V1_SCORE_ID,
        ScoreDirection.MINIMIZE,
        None,
        "uncalibrated_dimensionless_chemistry_pose_ordering_score",
        False,
        applicability_domain_id=SCORER_V1_APPLICABILITY_DOMAIN_ID,
    )
    same(doc["score_descriptor"], descriptor.to_dict(), "score descriptor")
    for field in ("arms",):
        exact_fields(plan[field], {"baseline", "refined"})
    for field in (
        "records",
        "rows",
        "costs",
        "raw_per_arm_selection",
        "per_arm_selection",
    ):
        exact_fields(doc[field], {"baseline", "refined"})
    for name, arm_budget in (("baseline", before), ("refined", after)):
        arm = plan["arms"][name]
        exact_fields(arm, {"budget", "guidance", "proposals"})
        same(arm["budget"], arm_budget.to_dict(), "arm budget")
        require_digest(arm["guidance"])
        proposals, records = arm["proposals"], doc["records"][name]
        if (
            type(proposals) is not list
            or type(records) is not list
            or len(records) != arm_budget.candidate_count
            or len(proposals) != len(records)
        ):
            raise ResearchError("candidate denominator mismatch")
        if len(set(proposals)) != len(proposals):
            raise ResearchError("duplicate candidate plan")
        costs = doc["costs"][name]
        exact_fields(
            costs,
            {
                "reused_candidates",
                "new_candidates",
                "historical_force_calls",
                "new_force_calls",
                "historical_score_calls",
                "new_score_calls",
                "interrupted_attempts_unknown_cost",
                "intent_counts",
            },
        )
        for key, value in costs.items():
            if key != "intent_counts":
                count(value)
        if type(costs["intent_counts"]) is not list or len(
            costs["intent_counts"]
        ) != len(records):
            raise ResearchError("journal intent denominator mismatch")
        for value in costs["intent_counts"]:
            integer(value, 1, 64)
        same(
            costs["interrupted_attempts_unknown_cost"],
            sum(costs["intent_counts"]) - len(records),
            "unknown interrupted work",
        )
        prior = integer(costs["reused_candidates"], 0, len(records))
        same(costs["new_candidates"], len(records) - prior, "new candidate count")
        observed = {
            key: 0
            for key in (
                "historical_force_calls",
                "new_force_calls",
                "historical_score_calls",
                "new_score_calls",
            )
        }
        for index, (proposal, record) in enumerate(
            zip(proposals, records, strict=True)
        ):
            require_digest(proposal)
            exact_fields(
                record, {"row", "attempt", "refinement_work", "execution_work"}
            )
            row = record["row"]
            verify_pose_row(row, n)
            for field, value in (
                ("proposal_fingerprint_sha256", proposal),
                ("proposal_index", index),
                ("problem_fingerprint_sha256", plan["problem"]),
                ("search_space_fingerprint_sha256", plan["search_space"]),
                ("validity_context_fingerprint_sha256", plan["validity_context"]),
            ):
                same(row[field], value, "row identity")
            stages = verify_work(record["execution_work"])
            if (
                not set(stages) <= {"search.execute", "score.evaluate"}
                or record["execution_work"]["counters"]
            ):
                raise ResearchError("unexpected candidate work")
            for metric, expected in (("calls", 1), ("completed", 1), ("failed", 0)):
                same(
                    stages.get("search.execute", {}).get(metric),
                    expected,
                    "candidate execution",
                )
            attempt = record["attempt"]
            if name == "baseline":
                same(attempt, None, "baseline attempt")
                same(record["refinement_work"], None, "baseline refinement work")
                same(row["refined"], False, "baseline refinement flag")
                force_calls = 0
                scored = True
            else:
                verify_attempt_execution(
                    attempt,
                    record["refinement_work"],
                    solver=effective,
                    steps=budget.max_refinement_steps,
                    bound=bound,
                    cross=cross,
                )
                same(
                    attempt["receipt_sha256"],
                    digest({k: v for k, v in attempt.items() if k != "receipt_sha256"}),
                    "attempt digest",
                )
                for field, expected in (
                    ("source_proposal_fingerprint_sha256", proposal),
                    ("candidate_id", row["candidate_id"]),
                    ("proposal_index", index),
                    ("implementation_source_sha256", plan["source"]),
                    ("evaluator", plan["evaluator"]),
                ):
                    same(attempt[field], expected, "attempt identity")
                scored = attempt["status"] == "success"
                same(row["refined"], scored, "refinement outcome")
                for phase in ("pre", "post") if scored else ("pre",):
                    xyz = decode_coordinates(
                        attempt[phase + "_coordinates_binary64_hex"], n
                    )[0]
                    same(
                        coordinate_fingerprint(xyz),
                        attempt[phase + "_coordinates_sha256"],
                        "attempt coordinates",
                    )
                if scored:
                    same(
                        attempt["energy_delta"],
                        attempt["final_energy"] - attempt["initial_energy"],
                        "energy delta",
                    )
                    initial = decode_coordinates(
                        attempt["pre_coordinates_binary64_hex"], n
                    )[0]
                    final_xyz = decode_coordinates(
                        attempt["post_coordinates_binary64_hex"], n
                    )[0]
                    displacement = float(
                        torch.linalg.vector_norm(final_xyz - initial, dim=-1).max()
                    )
                    same(
                        attempt["maximum_displacement_angstrom"],
                        displacement,
                        "observed displacement",
                    )
                force_calls = record["refinement_work"]["force_evaluation_calls"]
            score_calls = stages.get("score.evaluate", {}).get("calls", 0)
            same(score_calls, int(scored), "score calls")
            if row["succeeded"]:
                if not scored:
                    raise ResearchError("failed refinement produced success")
                same(stages["score.evaluate"]["completed"], 1, "score completed")
                terms = row["terms"]
                restored = ScorerV1Terms(
                    **{k: terms[k] for k in _IDENTITIES + _COUNTS},
                    **{k: float.fromhex(terms[k + "_binary64_hex"]) for k in _VALUES},
                )
                same(restored.to_dict(), terms, "score terms")
                for field, expected in (
                    ("authority_input_receipt_sha256", plan["authority"]),
                    ("context_fingerprint_sha256", plan["scorer"]["context"]),
                    ("config_fingerprint_sha256", plan["scorer"]["config"]),
                    ("backend_receipt_sha256", plan["scorer"]["backend"]),
                    (
                        "proposal_fingerprint_sha256",
                        row["result_proposal_fingerprint_sha256"],
                    ),
                ):
                    same(terms[field], expected, "score identity")
                same(row["score"], restored.total_score, "score total")
                xyz = decode_coordinates(row["coordinates_binary64_hex"], n)[0]
                same(
                    coordinate_fingerprint(xyz),
                    row["coordinates_sha256"],
                    "scored coordinates",
                )
                if name == "refined":
                    same(
                        row["coordinates_sha256"],
                        attempt["post_coordinates_sha256"],
                        "optimized score",
                    )
            else:
                same(row["terms"], None, "failure terms")
                same(row["result_proposal_fingerprint_sha256"], "", "failure proposal")
                require_digest(row["private_error_sha256"])
                integer(row["private_error_byte_length"], 1, 2**63 - 1)
                if type(row["error_code"]) is not str or not row["error_code"]:
                    raise ResearchError("missing failure code")
                same(
                    row["error_message"],
                    "docking candidate execution failed",
                    "public error",
                )
            kind = "historical" if index < prior else "new"
            observed[kind + "_force_calls"] += force_calls
            observed[kind + "_score_calls"] += score_calls
        for key, value in observed.items():
            same(costs[key], value, "retained cost accounting")
        same(doc["rows"][name], [r["row"] for r in records], "summary rows")
    attempts = [r["attempt"] for r in doc["records"]["refined"]]
    same(doc["attempts"], attempts, "summary attempts")
    raw = {
        name: select_final_candidates(
            [
                candidate_from_row(row, name)
                for row in rows
                if row["succeeded"] and row["selection_eligible"]
            ],
            descriptor,
            selection,
            n,
        )
        for name, rows in doc["rows"].items()
    }
    same(doc["raw_per_arm_selection"], raw, "raw selection")
    admitted = {
        "baseline": raw["baseline"],
        "refined": select_final_candidates(
            [
                candidate_from_row(row, "refined")
                for row, attempt in zip(doc["rows"]["refined"], attempts, strict=True)
                if refinement_admissible(
                    row, attempt, comparison.require_convergence_for_selection
                )
            ],
            descriptor,
            selection,
            n,
        ),
    }
    same(doc["per_arm_selection"], admitted, "policy selection")
    pairs, candidates = [], []
    if comparison.mode == "same_candidates":
        same(
            plan["arms"]["baseline"]["proposals"],
            plan["arms"]["refined"]["proposals"],
            "paired plan",
        )
        for before_row, after_row, attempt in zip(
            doc["rows"]["baseline"], doc["rows"]["refined"], attempts, strict=True
        ):
            if before_row["succeeded"]:
                same(
                    before_row["coordinates_sha256"],
                    attempt["pre_coordinates_sha256"],
                    "original paired coordinates",
                )
            choice, reason = choose_variant(
                before_row,
                after_row,
                attempt,
                comparison.require_convergence_for_selection,
            )
            pairs.append(
                {
                    "candidate_id": before_row["candidate_id"],
                    "variant": choice,
                    "reason": reason,
                }
            )
            if choice != "none":
                candidates.append(
                    candidate_from_row(
                        before_row if choice == "baseline" else after_row, choice
                    )
                )
        final = select_final_candidates(candidates, descriptor, selection, n)
    else:
        final = None
    same(doc["paired_decisions"], pairs, "paired decisions")
    same(doc["final_selection"], final, "final selection")
