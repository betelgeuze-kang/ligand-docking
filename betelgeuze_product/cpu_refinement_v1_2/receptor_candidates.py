"""Paired original/fixed-environment refinement with explicit component policy.

Reuse authenticated proposals, scorer, validity and projected descent. Total
objective reduction and ligand-internal increase are NOT the same criterion.
"""
from __future__ import annotations


from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.docking.search import DockingSearchRow
from betelgeuze_engine_v2.docking.scorer_v1 import _sha256 as score_digest
from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import _constraint_observations
from betelgeuze_product.cpu_refinement.refinement_comparison import _pose
from .refinement import ExtendedRefiner
from .minimization import minimize_objective, require_checkpoint
from .provenance import ResearchError, digest, finite, decode_coordinates
from .evidence_contracts import same, exact_fields, verify_pose_row, verify_work, calls
from .selection import candidate_from_row, select_final_candidates
from .work import WorkMeter

COMPONENT_ORDER = ("ligand_internal", "cross_lennard_jones", "cross_screened_coulomb")
COMPONENTS = set(COMPONENT_ORDER)

def _total(components):
    total = 0.0
    for name in COMPONENT_ORDER:
        total += components[name]
    return total


def _error(exc):
    receipt = failure_receipt(exc, public_message="fixed-receptor candidate operation failed")
    return {"public_error_code": receipt.public_error_code,
            "private_error_sha256": receipt.private_error_sha256,
            "private_error_byte_length": receipt.private_error_byte_length}


def _score(authority, scorer, original, current, refined, meter):
    common = dict(candidate_id=original.candidate_id, proposal_index=original.proposal_index,
        proposal_fingerprint_sha256=original.fingerprint_sha256,
        problem_fingerprint_sha256=original.problem_fingerprint_sha256,
        search_space_fingerprint_sha256=original.search_space_fingerprint_sha256,
        validity_context_fingerprint_sha256=authority.validity_context.fingerprint_sha256, refined=refined)
    try:
        original.assert_integrity()
        with meter.measure("score.evaluate"):
            terms = scorer.score_terms(current)
        validity = authority.validity_context.evaluate(current)
        original.assert_integrity()
        current.assert_integrity()
        row = DockingSearchRow(**common, result_proposal_fingerprint_sha256=current.fingerprint_sha256,
            status="success", score=terms.total_score, proposal=current, pose_validity=validity,
            selection_eligible=validity.valid, score_evidence=terms)
        return _pose(row, terms)
    except Exception as exc:
        error = _error(exc)
        row = DockingSearchRow(**common, result_proposal_fingerprint_sha256="", status="failure", score=None,
            proposal=None, error_code=error["public_error_code"], error_message="candidate scoring failed",
            private_error_sha256=error["private_error_sha256"], private_error_byte_length=error["private_error_byte_length"])
        return _pose(row, None)


def _components(objective, system, config, meter):
    with meter.measure("geometry.build"):
        graph = build_compact_radius_graph(system.coordinates, RadiusGraphConfig(
            cutoff_angstrom=objective.parameters.base_parameters.cutoff_angstrom,
            max_neighbors=config.minimization.max_neighbors, max_atoms_per_cell=config.minimization.max_atoms_per_cell))
    with meter.measure("force.evaluate"):
        value = objective.evaluate(system, graph)
    return {key: float(tensor[0]) for key, tensor in value.component_energies.items()}


def decision(before, after, attempt, policy):
    fallback = "baseline" if before["succeeded"] and before["selection_eligible"] else "none"
    if attempt["status"] != "success" or after is None or not after["succeeded"]:
        return fallback, "refinement_or_rescoring_failed"
    if not after["selection_eligible"]:
        return fallback, "refined_pose_invalid"
    cp = attempt["checkpoint"]
    if policy["require_convergence"] and cp["status"] != "converged":
        return fallback, "refinement_not_converged"
    delta = attempt["energy_changes"]
    if delta["total_objective"] > 0:
        return fallback, "total_objective_increased"
    if delta["ligand_internal"] > policy["maximum_internal_increase_kcal_per_mol"]:
        return fallback, "internal_strain_limit_exceeded"
    if fallback == "baseline" and after["score"] >= before["score"]:
        return fallback, "ranking_score_not_improved"
    return "refined", "valid_refinement_selected"


def evaluate_candidate(authority, scorer, proposal, ligand, objective, solver, policy, implementation):
    meter, breakdown_meter, score_meter = WorkMeter(), WorkMeter(), WorkMeter()
    before = _score(authority, scorer, proposal, proposal, False, score_meter)
    attempt, after = {}, None
    try:
        adapter = ExtendedRefiner(authority, ligand, objective.parameters, solver,
            implementation_source_sha256=implementation, solvation=objective.internal.solvation, max_attempts=1)
        adapter._assert_inputs(proposal, solver.minimization.max_iterations)
        source = ligand.with_coordinates(proposal.coordinates.unsqueeze(0), operation="fixed_receptor_candidate")
        observations = _constraint_observations(source.coordinates, source, objective.parameters.constraints)
        if not all(row.satisfied for row in observations):
            raise ResearchError("candidate must already satisfy declared distance constraints")
        pre = _components(objective, source, solver, breakdown_meter)
        result = minimize_objective(source, objective, solver, meter=meter)
        post = _components(objective, result.system, solver, breakdown_meter)
        delta = {key: post[key] - pre[key] for key in COMPONENTS}
        delta["total_objective"] = _total(post) - _total(pre)
        same(_total(pre), result.checkpoint.to_dict()["initial_energy"], "initial component total")
        same(_total(post), result.checkpoint.to_dict()["current_energy"], "final component total")
        attempt = {"status": "success", "checkpoint": result.checkpoint.to_dict(),
                   "initial_components": pre, "final_components": post, "energy_changes": delta}
        receipt = digest(attempt)
        current = proposal.with_refined_coordinates(result.system.coordinates[0],
            refiner_id="fixed_receptor_projected_refiner", refiner_version="1.0.0", refinement_receipt_sha256=receipt,
            torsion_angles=adapter._torsion_angles_for(result.system.coordinates[0]))
        after = _score(authority, scorer, proposal, current, True, score_meter)
    except Exception as exc:
        attempt = {"status": "failure", "error": _error(exc)}
    choice, reason = decision(before, after, attempt, policy)
    numerical = {"candidate_id": proposal.candidate_id, "proposal_index": proposal.proposal_index,
                 "source_proposal_sha256": proposal.fingerprint_sha256, "baseline": before, "refined": after,
                 "attempt": attempt, "selected_variant": choice, "selection_reason": reason}
    execution = {"solver": meter.numerical_calls(), "component_evaluations": breakdown_meter.snapshot(),
                 "scoring": score_meter.snapshot()}
    return {"numerical": numerical, "numerical_sha256": digest(numerical), "execution": execution}


def verify_candidate(record, plan, index):
    exact_fields(record, {"numerical", "numerical_sha256", "execution"})
    numerical = record["numerical"]
    exact_fields(numerical, {"candidate_id", "proposal_index", "source_proposal_sha256", "baseline", "refined",
                              "attempt", "selected_variant", "selection_reason"})
    same(record["numerical_sha256"], digest(numerical), "candidate numerical digest")
    same(numerical["proposal_index"], index, "candidate index")
    same(numerical["source_proposal_sha256"], plan["proposals"][index], "candidate source")
    before, after, attempt = numerical["baseline"], numerical["refined"], numerical["attempt"]
    for row, expected_refined in ((before, False), (after, True)):
        if row is None:
            continue
        verify_pose_row(row, plan["atom_count"])
        same(row["proposal_index"], index, "row candidate index")
        same(row["refined"], expected_refined, "row refinement flag")
        same(row["candidate_id"], numerical["candidate_id"], "row candidate identity")
        same(row["proposal_fingerprint_sha256"], numerical["source_proposal_sha256"], "row source")
        if row["succeeded"]:
            from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
            xyz = decode_coordinates(row["coordinates_binary64_hex"], plan["atom_count"])[0]
            same(coordinate_fingerprint(xyz), row["coordinates_sha256"], "scored coordinates")
            if not expected_refined:
                same(digest(row["coordinates_binary64_hex"]), plan["candidate_coordinates"][index], "original scored coordinates")
            terms = row["terms"]
            same(float(row["score"]).hex(), terms["total_score_binary64_hex"], "score value")
            same(terms["receipt_sha256"], score_digest({k: v for k, v in terms.items() if k != "receipt_sha256"}), "score receipt")
            same(terms["proposal_fingerprint_sha256"], row["result_proposal_fingerprint_sha256"], "score pose binding")
            same(terms["authority_input_receipt_sha256"], plan["authority_sha256"], "score authority")
    if attempt["status"] == "success":
        exact_fields(attempt, {"status", "checkpoint", "initial_components", "final_components", "energy_changes"})
        cp = require_checkpoint(attempt["checkpoint"]).to_dict()
        if cp["status"] not in {"converged", "max_iterations_reached", "line_search_failed"}:
            raise ResearchError("candidate cannot commit a paused solver state")
        same(cp["evaluator"], plan["objective"], "candidate objective")
        same(cp["config"], plan["solver"], "candidate solver")
        same(cp["implementation_sha256"], plan["implementation_sha256"], "candidate implementation")
        same(cp["environment"], plan["environment"], "candidate environment")
        same(cp["source_system_sha256"], plan["candidate_systems"][index], "candidate input state")
        same(cp["observations"][0]["coordinates_sha256"], plan["candidate_coordinates"][index], "initial candidate coordinates")
        for components in (attempt["initial_components"], attempt["final_components"]):
            exact_fields(components, COMPONENTS)
            for value in components.values():
                finite(value)
        pre, post = attempt["initial_components"], attempt["final_components"]
        same(_total(pre), cp["initial_energy"], "initial energy sum")
        same(_total(post), cp["current_energy"], "final energy sum")
        expected = {key: post[key] - pre[key] for key in COMPONENTS}
        expected["total_objective"] = _total(post) - _total(pre)
        same(expected, attempt["energy_changes"], "energy changes")
        if after is not None and after["succeeded"]:
            same(after["coordinates_binary64_hex"], cp["coordinates"], "actual returned coordinates")
    elif attempt["status"] == "failure":
        exact_fields(attempt, {"status", "error"})
        if after is not None:
            raise ResearchError("failed refinement cannot have a returned pose")
    else:
        raise ResearchError("unknown candidate attempt status")
    choice, reason = decision(before, after, attempt, plan["policy"])
    same((choice, reason), (numerical["selected_variant"], numerical["selection_reason"]), "candidate selection")
    execution = record["execution"]
    exact_fields(execution, {"solver", "component_evaluations", "scoring"})
    from .evidence_contracts import verify_numerical_work
    bound = 1 + plan["solver"]["minimization"]["max_iterations"] * (1 + plan["solver"]["minimization"]["max_backtracks"])
    verify_numerical_work(execution["solver"], bound)
    component_stages = verify_work(execution["component_evaluations"])
    scoring_stages = verify_work(execution["scoring"])
    if not set(component_stages) <= {"geometry.build", "force.evaluate"} or not set(scoring_stages) <= {"score.evaluate"}:
        raise ResearchError("unexpected candidate observation stage")
    same(calls(component_stages, "force.evaluate"), calls(component_stages, "geometry.build", "completed"),
         "component graph/force calls")
    if calls(component_stages, "geometry.build") > 2:
        raise ResearchError("component evaluation count exceeds pre/post bound")
    rows = [row for row in (before, after) if row is not None]
    successful_rows = sum(row["succeeded"] for row in rows)
    if not successful_rows <= calls(scoring_stages, "score.evaluate", "completed") <= calls(scoring_stages, "score.evaluate") <= len(rows):
        raise ResearchError("scoring calls do not support returned rows")
    if attempt["status"] == "success":
        same(calls(component_stages, "force.evaluate", "completed"), 2, "successful breakdown calls")
        if not cp["accepted_iterations"] + 1 <= execution["solver"]["force_evaluation_calls"] <= cp["evaluation_count"]:
            raise ResearchError("solver work does not support accepted iterations")
        same(execution["solver"]["constraint_projection_calls"], cp["evaluation_count"], "solver logical calls")
    return numerical


def final_selection(records, plan, descriptor, selection):
    candidates = []
    for record in records:
        n = record["numerical"]
        variant = n["selected_variant"]
        if variant != "none":
            candidates.append(candidate_from_row(n[variant], variant))
    return select_final_candidates(candidates, descriptor, selection, plan["atom_count"])
