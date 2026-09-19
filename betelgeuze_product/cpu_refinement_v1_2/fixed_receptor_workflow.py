"""Explicit fixed-receptor refinement with durable candidate-level restart.

Only fully committed candidates are reused. Work interrupted before commit may
repeat and is reported as unknown; no exact-once execution or total retry-cost
bound is claimed. Historical 1.2 CLI output/checkpoints are not migrated.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import re

from betelgeuze_engine_v2.docking.guided_placement import build_guided_placement_context, generate_guided_docking_proposals
from betelgeuze_engine_v2.docking.scorer_v1 import ChemistryPoseScorerV1
from betelgeuze_engine_v2.docking.scoring import DockingScoreDescriptor, ScoreDirection
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_product.reference_minimization_workflow import _read, _bound, _publish, _directory
from betelgeuze_product.local_research_workflow import _decode, _json
from .workflow import load_request
from .cross_interaction import CrossParameters, FixedReceptorEvaluator
from .provenance import ResearchError, digest, environment, source_manifest, coordinates_hex, finite, integer, require_digest
from .evidence_contracts import exact_fields, same, request_binding, execution_plan
from .selection import SelectionConfig
from .receptor_candidates import evaluate_candidate, verify_candidate, final_selection
from .work import verify_admitted_bytes

SCHEMA = "fixed_receptor_workflow_request/1.0.0"


def prepare(request):
    exact_fields(request, {"schema_id", "prepared", "cross_parameters", "maximum_internal_increase_kcal_per_mol"})
    if request["schema_id"] != SCHEMA:
        raise ResearchError("explicit fixed-receptor request required")
    finite(request["maximum_internal_increase_kcal_per_mol"], nonnegative=True)
    request_binding(request["prepared"])
    sources = source_manifest()
    implementation = digest(sources)
    authority, receptor, ligand, parameters, budget, solver, solvent, comparison, selection = load_request(request["prepared"], implementation)
    if comparison.mode != "same_candidates" or comparison.work_units_per_arm is not None:
        raise ResearchError("initial fixed-receptor workflow supports same candidates without legacy work-unit weights")
    if not 1 <= budget.max_refinement_steps <= solver.minimization.max_iterations:
        raise ResearchError("explicit positive refinement budget required")
    cross = CrossParameters.from_dict(_bound(request["cross_parameters"]))
    objective = FixedReceptorEvaluator(receptor, parameters, cross,
        coordinate_frame_id=request["prepared"]["pocket"]["coordinate_frame_id"], solvation=solvent)
    objective.validate_ligand(ligand)
    context = build_guided_placement_context(authority, receptor, ligand)
    proposals, receipt = generate_guided_docking_proposals(authority, budget, context,
        receptor_system=receptor, ligand_system=ligand)
    solver = replace(solver, minimization=replace(solver.minimization, max_iterations=budget.max_refinement_steps))
    scorer = ChemistryPoseScorerV1(authority, receptor, ligand, implementation_source_sha256=implementation)
    plan = {"schema_id": "fixed_receptor_execution_plan/1.0.0", "request": request,
            "implementation_sources": sources, "implementation_sha256": implementation, "environment": environment(),
            "objective": objective.identity(), "solver": solver.to_dict(), "atom_count": ligand.atom_count,
            "authority_sha256": authority.input_receipt_sha256, "guidance_sha256": receipt.receipt_sha256,
            "proposals": [p.fingerprint_sha256 for p in proposals],
            "candidate_systems": [canonical_system_sha256(ligand.with_coordinates(p.coordinates.unsqueeze(0),
                                   operation="fixed_receptor_candidate")) for p in proposals],
            "candidate_coordinates": [digest(coordinates_hex(p.coordinates)) for p in proposals],
            "selection": selection.to_dict(), "score_descriptor": scorer.score_descriptor.to_dict(),
            "policy": {"require_convergence": comparison.require_convergence_for_selection,
                       "maximum_internal_increase_kcal_per_mol": request["maximum_internal_increase_kcal_per_mol"]},
            "force_calls_reserved_per_candidate": 3 + budget.max_refinement_steps * (solver.minimization.max_backtracks + 1),
            "reservation_scope": "committed_attempt_including_two_component_evaluations;interrupted_work_unknown"}
    verify_plan(plan)
    return plan, authority, ligand, objective, solver, proposals, scorer, selection


def verify_plan(plan):
    """Check the executable plan against retained request semantics, not just hashes."""
    exact_fields(plan, {"schema_id", "request", "implementation_sources", "implementation_sha256", "environment",
        "objective", "solver", "atom_count", "authority_sha256", "guidance_sha256", "proposals",
        "candidate_systems", "candidate_coordinates", "selection", "score_descriptor", "policy",
        "force_calls_reserved_per_candidate", "reservation_scope"})
    same(plan["schema_id"], "fixed_receptor_execution_plan/1.0.0", "plan schema")
    req = plan["request"]
    exact_fields(req, {"schema_id", "prepared", "cross_parameters", "maximum_internal_increase_kcal_per_mol"})
    same(req["schema_id"], SCHEMA, "request schema")
    request_binding(req["prepared"])
    exact_fields(req["cross_parameters"], {"path", "sha256"})
    require_digest(req["cross_parameters"]["sha256"])
    if type(req["cross_parameters"]["path"]) is not str or not Path(req["cross_parameters"]["path"]).is_absolute():
        raise ResearchError("absolute cross-parameter path required")
    budget, solver, comparison, _, _, bound, effective = execution_plan(
        req["prepared"]["budget"], req["prepared"]["solver"], req["prepared"]["comparison"])
    if comparison.mode != 'same_candidates' or comparison.work_units_per_arm is not None:
        raise ResearchError("unsupported fixed-receptor comparison plan")
    finite(req["maximum_internal_increase_kcal_per_mol"], nonnegative=True)
    same(plan["policy"], {"require_convergence": comparison.require_convergence_for_selection,
        "maximum_internal_increase_kcal_per_mol": req["maximum_internal_increase_kcal_per_mol"]}, "admission policy")
    same(plan["solver"], effective.to_dict(), "effective solver")
    same(plan["force_calls_reserved_per_candidate"], bound + 2, "component-inclusive reservation")
    same(plan["selection"], req["prepared"]["selection"], "selection settings")
    integer(plan["atom_count"], 1, 256)
    for name in ("proposals", "candidate_systems", "candidate_coordinates"):
        if type(plan[name]) is not list or len(plan[name]) != budget.candidate_count:
            raise ResearchError("execution plan candidate denominator mismatch")
        for value in plan[name]:
            require_digest(value)
    if len(set(plan["proposals"])) != budget.candidate_count:
        raise ResearchError("duplicate candidate identities")
    for name in ("implementation_sha256", "authority_sha256", "guidance_sha256"):
        require_digest(plan[name])
    if type(plan["implementation_sources"]) is not dict or not plan["implementation_sources"]:
        raise ResearchError("complete source manifest required")
    for value in plan["implementation_sources"].values():
        require_digest(value)
    same(plan["implementation_sha256"], digest(plan["implementation_sources"]), "source manifest")
    from .cross_interaction import OBJECTIVE_ID
    exact_fields(plan["objective"], {"evaluator_id", "internal", "receptor_system_sha256", "cross_parameters_sha256", "coordinate_frame_id"})
    same(plan["objective"]["evaluator_id"], OBJECTIVE_ID, "objective method")
    same(plan["objective"]["coordinate_frame_id"], req["prepared"]["pocket"]["coordinate_frame_id"], "common frame")
    for name in ("receptor_system_sha256", "cross_parameters_sha256"):
        require_digest(plan["objective"][name])
    from betelgeuze_engine_v2.docking.scorer_v1 import SCORER_V1_SCORE_ID, SCORER_V1_APPLICABILITY_DOMAIN_ID
    expected = DockingScoreDescriptor(SCORER_V1_SCORE_ID, ScoreDirection.MINIMIZE, None,
        "uncalibrated_dimensionless_chemistry_pose_ordering_score", False,
        applicability_domain_id=SCORER_V1_APPLICABILITY_DOMAIN_ID)
    same(plan["score_descriptor"], expected.to_dict(), "uncalibrated scorer")


def _envelope(payload):
    return {"payload": payload, "sha256": digest(payload)}


def _verified(path):
    doc = _decode(_read(path))
    exact_fields(doc, {"payload", "sha256"})
    same(doc["sha256"], digest(doc["payload"]), "journal checksum")
    return doc["payload"]


def _commit_candidate(directory, index, record, plan_sha, intent):
    _publish(directory / f"candidate-{index:05d}.json",
             _envelope({"plan_sha256": plan_sha, "intent": intent, "record": record}))


def _recheck(request, sources, objective):
    for key in ("receptor", "ligand", "parameters", "extensions", "solvation"):
        ref = request["prepared"][key]
        if ref is not None:
            verify_admitted_bytes(ref)
    verify_admitted_bytes(request["cross_parameters"])
    if source_manifest() != sources:
        raise ResearchError("implementation changed during workflow")
    objective.identity()


def _recover_partials(directory):
    """Archive only recognized interrupted atomic writes under the held lock."""
    for path in sorted(directory.glob('*.partial')):
        if not re.fullmatch(r'(candidate-\d{5}\.json|intent-\d{5}-\d{5}\.json|report\.json|complete\.json)\.partial', path.name):
            raise ResearchError("unrecognized partial output; recovery refused")
        raw = _read(path)
        for index in range(10000):
            target = directory / f"abandoned-{index:05d}.bin"
            try:
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                break
            except FileExistsError:
                continue
        else:
            raise ResearchError("partial recovery capacity exceeded")
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        path.unlink()
        fd = os.open(str(directory) + "/.", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _records(directory, plan):
    plan_sha = digest(plan)
    records, intents = [], []
    missing = False
    for index in range(len(plan["proposals"])):
        paths = sorted(directory.glob(f"intent-{index:05d}-*.json"))
        if len(paths) > 64:
            raise ResearchError("retry history capacity exceeded")
        for ordinal, path in enumerate(paths):
            same(path.name, f"intent-{index:05d}-{ordinal:05d}.json", "intent sequence")
            same(_verified(path), {"plan_sha256": plan_sha, "index": index, "ordinal": ordinal}, "intent binding")
        intents.append(paths)
        path = directory / f"candidate-{index:05d}.json"
        if not path.exists() and not path.is_symlink():
            missing = True
            continue
        if missing:
            raise ResearchError("noncontiguous committed candidates")
        stored = _verified(path)
        exact_fields(stored, {"plan_sha256", "intent", "record"})
        same(stored["plan_sha256"], plan_sha, "candidate plan")
        if not paths or stored["intent"] != paths[-1].name:
            raise ResearchError("candidate commit/intent mismatch")
        verify_candidate(stored["record"], plan, index)
        records.append(stored["record"])
    known_intents = {p.name for paths in intents for p in paths}
    if {p.name for p in directory.glob("intent-*.json")} != known_intents:
        raise ResearchError("unexpected intent files")
    expected = {f"candidate-{i:05d}.json" for i in range(len(records))}
    if {p.name for p in directory.glob('candidate-*.json')} != expected:
        raise ResearchError("unexpected candidate files")
    return records, intents


def _summary(records, plan, descriptor, selection, unknown_attempts):
    final = final_selection(records, plan, descriptor, selection)
    numerical = {"candidate_numerical_sha256": [r["numerical_sha256"] for r in records], "final_selection": final}
    force_calls = sum(r["execution"]["solver"]["force_evaluation_calls"] +
                      r["execution"]["component_evaluations"]["stages"].get('force.evaluate', {}).get('calls', 0)
                      for r in records)
    return {"schema_id": "fixed_receptor_workflow_result/1.0.0", "plan_sha256": digest(plan),
            "candidate_count": len(records), "refinement_failure_count": sum(r["numerical"]["attempt"]["status"] != 'success' for r in records),
            "numerical_result": numerical, "numerical_sha256": digest(numerical),
            "converged_candidates": sum(r["numerical"]["attempt"].get("checkpoint", {}).get("status") == "converged" for r in records),
            "selected_refined_candidates": sum(r["variant"] == "refined" for r in final["selected_candidates"]),
            "committed_force_calls_observed": force_calls,
            "committed_score_calls_observed": sum(r["execution"]["scoring"]["stages"].get("score.evaluate", {}).get("calls", 0) for r in records),
            "interrupted_attempts_unknown_cost": unknown_attempts,
            "cost_scope": "committed_candidate_solver_and_component_force_calls;startup_verification_and_lost_work_excluded",
            "scientifically_validated": False, "customer_execution_allowed": False, "claim_safe": False}


def run_request(request, output, *, resume=False, stop_after=None):
    if type(resume) is not bool:
        raise ResearchError("exact resume flag required")
    request = _decode(_json(request))
    plan, authority, ligand, objective, solver, proposals, scorer, selection = prepare(request)
    if stop_after is not None:
        integer(stop_after, 0, len(proposals))
    with _directory(output, resume=resume) as directory:
        if resume:
            same(_verified(directory / 'plan.json'), plan, "resume input/source/environment plan")
            same(_decode(_read(directory / 'request.json')), request, "retained request")
            _recover_partials(directory)
        else:
            _publish(directory / 'request.json', request)
            _publish(directory / 'plan.json', _envelope(plan))
        records, intents = _records(directory, plan)
        if stop_after is not None and stop_after < len(records):
            raise ResearchError("stop point precedes committed progress")
        if (directory / 'complete.json').exists():
            return verify_output(directory)
        unknown = sum(max(0, len(paths) - int(index < len(records))) for index, paths in enumerate(intents))
        for index in range(len(records), len(proposals)):
            if stop_after is not None and index >= stop_after:
                return {"status": "checkpointed", "completed_candidates": len(records), "execution_complete": False}
            _recheck(request, plan["implementation_sources"], objective)
            ordinal = len(intents[index])
            if ordinal >= 64:
                raise ResearchError("candidate retry capacity exceeded")
            name = f"intent-{index:05d}-{ordinal:05d}.json"
            _publish(directory / name, _envelope({"plan_sha256": digest(plan), "index": index, "ordinal": ordinal}))
            record = evaluate_candidate(authority, scorer, proposals[index], ligand, objective, solver,
                                        plan["policy"], plan["implementation_sha256"])
            verify_candidate(record, plan, index)
            _recheck(request, plan["implementation_sources"], objective)
            _commit_candidate(directory, index, record, digest(plan), name)
            records.append(record)
        _recheck(request, plan["implementation_sources"], objective)
        report = _summary(records, plan, scorer.score_descriptor, selection, unknown)
        _publish(directory / 'report.json', report)
        _publish(directory / 'complete.json', {"report_sha256": hashlib.sha256((_json(report)+'\n').encode()).hexdigest(),
                                               "execution_complete": True, "scientifically_validated": False})
        return report


def verify_output(directory):
    """Portable structural read-only verification; no input files or scoring."""
    directory = Path(directory).absolute()
    plan = _verified(directory / 'plan.json')
    verify_plan(plan)
    same(_decode(_read(directory / 'request.json')), plan["request"], "retained request")
    same(plan["implementation_sha256"], digest(plan["implementation_sources"]), "source manifest")
    records, intents = _records(directory, plan)
    if len(records) != len(plan["proposals"]):
        raise ResearchError("incomplete workflow cannot verify as complete")
    descriptor = DockingScoreDescriptor(**{**plan["score_descriptor"], 'direction': ScoreDirection(plan["score_descriptor"]["direction"])})
    selection = SelectionConfig(plan["selection"]["top_k"], plan["selection"]["diversity_rmsd_angstrom"])
    expected = _summary(records, plan, descriptor, selection, sum(len(paths)-1 for paths in intents))
    raw = _read(directory / 'report.json')
    same(_decode(raw), expected, "completed report")
    same(_decode(_read(directory / 'complete.json')), {"report_sha256": hashlib.sha256(raw).hexdigest(),
          "execution_complete": True, "scientifically_validated": False}, "completion marker")
    return expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run')
    run.add_argument('request', type=Path)
    run.add_argument('--output', required=True, type=Path)
    run.add_argument('--resume', action='store_true')
    run.add_argument('--stop-after', type=int)
    verify = commands.add_parser('verify')
    verify.add_argument('directory', type=Path)
    preflight = commands.add_parser('preflight')
    preflight.add_argument('request', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'verify':
        report = verify_output(args.directory)
    elif args.command == 'preflight':
        plan, *_ = prepare(_decode(_read(args.request.absolute())))
        report = {"admitted": True, "plan_sha256": digest(plan), "candidate_count": len(plan["proposals"]),
                  "objective": plan["objective"], "scientifically_validated": False}
    else:
        report = run_request(_decode(_read(args.request.absolute())), args.output,
                             resume=args.resume, stop_after=args.stop_after)
    print(_json({key: value for key, value in report.items() if key not in {'numerical_result'}}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
