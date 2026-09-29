"""One registered Cartesian refinement, explicit scoring and durable score receipts.

Numerical history belongs to the 1.3 minimizer. This layer preserves the original
pose, scores at most one baseline and one terminal proposal, and replays saved
score terms plus live geometry without rescoring. No source-role admission occurs.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields
import os
import re
import stat
import time
from pathlib import Path, PurePosixPath

import torch

from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.docking import (
    DockingBudget, DockingScope, PocketDefinition,
    build_element_aware_authenticated_known_pocket_docking_problem,
)
from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
from betelgeuze_engine_v2.docking.search import DockingSearchRow
from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_product.cpu_refinement.refinement_comparison import RefinementComparisonConfig, _pose
from betelgeuze_product.cpu_refinement_v1_2.comparison import choose_variant
from betelgeuze_product.cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from betelgeuze_product.cpu_refinement_v1_2.evidence_contracts import same, verify_pose_row
from betelgeuze_product.cpu_refinement_v1_2.failure_replay import restore_failure_row
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import (
    CrossParameters, FixedReceptorEnvironment, FixedReceptorEvaluator, ENERGY_BASIS,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, coordinates_hex, decode_coordinates, digest,
    environment, exact_fields, finite, integer, require_digest,
)
from betelgeuze_product.cpu_refinement_v1_2.registered_pose import generate_registered_pose
from betelgeuze_product.cpu_refinement_v1_2.score_replay import restore_score_terms
from betelgeuze_product.cpu_refinement_v1_2.scoring_profile import (
    EXPLICIT_MODEL, REGISTERED_REQUEST_SCHEMA, descriptor, scorer_class,
)
from betelgeuze_product.cpu_refinement_v1_2.selection import (
    SelectionConfig, candidate_from_row, refinement_admissible, select_final_candidates,
)
from betelgeuze_product.cpu_refinement_v1_2.work import WorkMeter, verify_admitted_bytes
from betelgeuze_product.cpu_refinement_v1_2.workflow import _extension
from betelgeuze_product.local_research_workflow import _decode, _json
from betelgeuze_product.reference_minimization_workflow import (
    _bound, _directory, _parameters, _publish, _read,
)
from .contracts import SolverConfig, source_manifest


REQUEST_SCHEMA = 'cpu_cartesian_registered_pose_request/1.3.0'
RESULT_SCHEMA = 'cpu_cartesian_registered_pose_result/1.3.0'
BINDING_SCHEMA = 'cpu_cartesian_registered_pose_binding/1.3.0'
SCORE_SCHEMA = 'cpu_cartesian_registered_score_receipt/1.3.0'
SCORE_QUANTITY = 'uncalibrated_explicit_graph_scorer_dimensionless_minimize'
FILE_FIELDS = ('receptor', 'ligand', 'parameters', 'extensions', 'cross_parameters')
POSE_FIELDS = {'candidate_count', 'top_k', 'max_torsions', 'translation_radius_angstrom', 'seed'}
REQUEST_FIELDS = set(FILE_FIELDS) | {'schema_id', 'backend', 'pocket', 'receptor_margin_angstrom',
                                   'budget', 'solver', 'solvation', 'comparison', 'selection'}
TERMINAL = {'force_converged', 'objective_budget_exhausted', 'max_accepted_steps_reached',
            'line_search_failed', 'evaluation_failed'}
CALL_FIELDS = ('optimizer_objective_attempts', 'optimizer_graph_calls', 'optimizer_force_calls',
               'failed_optimizer_force_calls', 'restart_verification_attempts', 'restart_graph_calls', 'restart_force_calls',
               'failed_restart_force_calls', 'actual_force_calls')


def _sealed(value, field='receipt_sha256'):
    return {**value, field: digest(value)}


def _check_seal(value, field='receipt_sha256'):
    same(value.get(field), digest({k: v for k, v in value.items() if k != field}), field)


def _read_json(path):
    return _decode(_read(Path(path).absolute()))


def _request(request):
    exact_fields(request, REQUEST_FIELDS)
    if request['schema_id'] != REQUEST_SCHEMA or request['backend'] != 'python_cpu_reference':
        raise ResearchError('explicit Cartesian registered CPU request required')
    if request['solvation'] is not None:
        raise ResearchError('Cartesian fixed receptor requires null solvation')
    solver = SolverConfig.from_dict(request['solver'])
    if solver.force_tolerance > .001:
        raise ResearchError('Cartesian workflow cannot weaken raw force tolerance')
    for name in FILE_FIELDS:
        ref = exact_fields(request[name], {'path', 'sha256'})
        require_digest(ref['sha256'])
        if type(ref['path']) is not str or not PurePosixPath(ref['path']).is_absolute():
            raise ResearchError('absolute prepared input path required')
    budget = exact_fields(request['budget'], POSE_FIELDS)
    for name, value in (('candidate_count', 1), ('top_k', 1), ('max_torsions', 0)):
        integer(budget[name], value, value)
    integer(budget['seed'], 0, 2**63 - 1)
    if finite(budget['translation_radius_angstrom']) != 0:
        raise ResearchError('registered pose cannot have placement perturbations')
    comp = exact_fields(request['comparison'], {f.name for f in fields(RefinementComparisonConfig)})
    comparison = RefinementComparisonConfig(**comp)
    if comparison.mode != 'same_candidates' or comparison.require_convergence_for_selection is not True:
        raise ResearchError('Cartesian registered comparison requires convergence and same candidates')
    if comparison.work_units_per_arm is not None:
        raise ResearchError('Cartesian work budget belongs to the explicit solver')
    selected = exact_fields(request['selection'], set(SelectionConfig(1).to_dict()))
    selection = SelectionConfig(selected['top_k'], selected['diversity_rmsd_angstrom'])
    same(selection.to_dict(), selected, 'Cartesian selection configuration')
    same(selection.top_k, 1, 'registered Top-K')
    pocket = exact_fields(request['pocket'], {'center_angstrom', 'radius_angstrom', 'coordinate_frame_id',
                                            'source_artifact_sha256', 'method_id', 'method_version'})
    if type(pocket['center_angstrom']) is not list or len(pocket['center_angstrom']) != 3:
        raise ResearchError('explicit three-coordinate pocket required')
    for value in pocket['center_angstrom']:
        finite(value)
    for value in (pocket['radius_angstrom'], request['receptor_margin_angstrom']):
        if finite(value) <= 0:
            raise ResearchError('positive pocket radius and receptor margin required')
    require_digest(pocket['source_artifact_sha256'])
    for name in ('coordinate_frame_id', 'method_id', 'method_version'):
        if type(pocket[name]) is not str or not pocket[name].strip():
            raise ResearchError('explicit pocket identity required')
    return deepcopy(request), solver, selection


def prepare_cartesian_request(old_request, config):
    """Explicit conversion only; never execute/reinterpret the old solver."""
    if type(config) is not SolverConfig:
        raise ResearchError('explicit Cartesian SolverConfig required')
    from betelgeuze_product.cpu_refinement_v1_2.evidence_contracts import request_binding
    if type(old_request) is not dict or old_request.get('schema_id') != REGISTERED_REQUEST_SCHEMA:
        raise ResearchError('conversion requires an original registered-pose request')
    request_binding(old_request)  # Validate the old document; no solver execution.
    result = deepcopy(old_request)
    result['schema_id'] = REQUEST_SCHEMA
    result['solver'] = config.to_dict()
    result['budget'] = {k: v for k, v in result['budget'].items() if k != 'max_refinement_steps'}
    _request(result)
    return result


@dataclass
class _Admitted:
    request: dict
    config: SolverConfig
    selection: SelectionConfig
    authority: object
    receptor: object
    ligand: object
    parameters: object
    fixed: object
    scorer: object
    proposal: object
    binding: dict
    sources: dict


def _admit(request, meter):
    request, config, selection = _request(request)
    with meter.measure('implementation.verify'):
        sources = source_manifest()
        implementation = digest(sources)
    with meter.measure('inputs.parse'):
        receptor = all_atom_system_from_canonical_json(_json(_bound(request['receptor'])))
        ligand = all_atom_system_from_canonical_json(_json(_bound(request['ligand'])))
        for system, maximum in ((receptor, 8192), (ligand, 256)):
            if (system.model_count != 1 or not 1 <= system.atom_count <= maximum or system.cell is not None
                    or system.coordinates.dtype != torch.float64 or system.coordinates.device.type != 'cpu'):
                raise ResearchError('bounded single-model nonperiodic CPU float64 inputs required')
        base = _parameters(_bound(request['parameters']))
        parameters = _extension(_bound(request['extensions']), base)
        if parameters.constraints:
            raise ResearchError('Cartesian workflow does not support projected constraints')
        fixed = FixedReceptorEnvironment(receptor, CrossParameters.from_dict(_bound(request['cross_parameters'])))
        fixed.validate_ligand(ligand, base)
        if fixed.cross.max_internal_increase_kcal_per_mol > 5.:
            raise ResearchError('Cartesian workflow cannot weaken ligand strain cap')
        pocket = request['pocket']
        definition = PocketDefinition(scope=DockingScope.KNOWN_POCKET,
            center=torch.tensor(pocket['center_angstrom'], dtype=torch.float64),
            radius_angstrom=pocket['radius_angstrom'], coordinate_frame_id=pocket['coordinate_frame_id'],
            source_artifact_sha256=pocket['source_artifact_sha256'], method_id=pocket['method_id'],
            method_version=pocket['method_version'], implementation_source_sha256=implementation)
        authority = build_element_aware_authenticated_known_pocket_docking_problem(
            receptor, ligand, definition, receptor_margin_angstrom=request['receptor_margin_angstrom'])
        same(fixed.cross.coordinate_frame_id, authority.pocket.coordinate_frame_id, 'fixed coordinate frame')
        same(authority.validity_context.config.bond_length_tolerance_angstrom, .15, 'unchanged bond tolerance')
        proposals, receipt = generate_registered_pose(authority, DockingBudget(**request['budget']), ligand)
    with meter.measure('scorer.construct'):
        scorer = scorer_class(EXPLICIT_MODEL)(authority, receptor, ligand,
                                              implementation_source_sha256=implementation)
    evaluator = FixedReceptorEvaluator(ExtendedEvaluator(parameters), fixed)
    binding = _sealed({'schema_id': BINDING_SCHEMA, 'request_sha256': digest(request),
        'input_files': {name: request[name] for name in FILE_FIELDS},
        'implementation_sources': sources, 'implementation_source_sha256': implementation,
        'environment': environment(),
        'authority_input_receipt_sha256': authority.input_receipt_sha256,
        'proposal_policy': receipt.to_dict(), 'solver': config.to_dict(),
        'evaluator': evaluator.identity(), 'cross_parameters': fixed.cross.to_dict(),
        'scorer': {'feature_model_id': EXPLICIT_MODEL, 'context': scorer.context.fingerprint_sha256,
                   'config': scorer.config.fingerprint_sha256, 'backend': scorer.backend_receipt_sha256},
        'score_quantity': SCORE_QUANTITY, 'score_descriptor': descriptor(EXPLICIT_MODEL).to_dict(),
        'candidate_source_admission_verified': False, 'scientifically_validated': False})
    return _Admitted(request, config, selection, authority, receptor, ligand, parameters, fixed,
                     scorer, proposals[0], binding, sources)


def _intact(admitted, meter):
    for name in FILE_FIELDS:
        verify_admitted_bytes(admitted.request[name], meter)
    admitted.fixed.assert_intact()
    admitted.authority.input_receipt_sha256
    same(canonical_system_sha256(admitted.ligand), admitted.authority.ligand_system_sha256,
         'original ligand object unchanged')
    same(canonical_system_sha256(admitted.receptor), admitted.authority.receptor_system_sha256,
         'original receptor object unchanged')
    with meter.measure('implementation.verify'):
        same(source_manifest(), admitted.sources, 'Cartesian implementation unchanged')


def input_binding(request):
    """No score/force calls; scorer construction includes reference arithmetic."""
    meter = WorkMeter()
    admitted = _admit(request, meter)
    _intact(admitted, meter)
    return admitted.binding


def _row(admitted, current, terms):
    proposal, authority = admitted.proposal, admitted.authority
    validity = authority.validity_context.evaluate(current)
    return DockingSearchRow(candidate_id=proposal.candidate_id, proposal_index=proposal.proposal_index,
        proposal_fingerprint_sha256=proposal.fingerprint_sha256,
        result_proposal_fingerprint_sha256=current.fingerprint_sha256,
        problem_fingerprint_sha256=proposal.problem_fingerprint_sha256,
        search_space_fingerprint_sha256=proposal.search_space_fingerprint_sha256,
        status='success', score=terms.total_score, proposal=current, pose_validity=validity,
        validity_context_fingerprint_sha256=authority.validity_context.fingerprint_sha256,
        selection_eligible=validity.valid, refined=current.refined, score_evidence=terms)


def _failure(admitted, current, exc):
    receipt = failure_receipt(exc, public_message='docking candidate execution failed')
    proposal, authority = admitted.proposal, admitted.authority
    return DockingSearchRow(candidate_id=proposal.candidate_id, proposal_index=proposal.proposal_index,
        proposal_fingerprint_sha256=proposal.fingerprint_sha256, result_proposal_fingerprint_sha256='',
        problem_fingerprint_sha256=proposal.problem_fingerprint_sha256,
        search_space_fingerprint_sha256=proposal.search_space_fingerprint_sha256,
        status='failure', score=None, proposal=None,
        validity_context_fingerprint_sha256=authority.validity_context.fingerprint_sha256,
        selection_eligible=False, refined=current.refined, error_code=receipt.public_error_code,
        error_message=receipt.public_message, private_error_sha256=receipt.private_error_sha256,
        private_error_byte_length=receipt.private_error_byte_length)


def _restore_score(admitted, arm, current, record, intent):
    exact_fields(record, {'schema_id', 'arm', 'binding_sha256', 'proposal_fingerprint_sha256',
                          'intent_sha256', 'row', 'score_calls', 'work', 'receipt_sha256'})
    _check_seal(record)
    same(record['schema_id'], SCORE_SCHEMA, 'score receipt schema')
    same(record['arm'], arm, 'score receipt arm')
    same(record['binding_sha256'], admitted.binding['receipt_sha256'], 'score request binding')
    same(record['proposal_fingerprint_sha256'], current.fingerprint_sha256, 'score proposal binding')
    same(record['intent_sha256'], digest(intent), 'score intent binding')
    same(record['score_calls'], 1, 'score call denominator')
    from betelgeuze_product.cpu_refinement_v1_2.evidence_contracts import verify_work
    stages = verify_work(record['work'])
    if set(stages) != {'score.evaluate'} or record['work']['counters']:
        raise ResearchError('unexpected saved score work')
    same(stages['score.evaluate']['calls'], 1, 'actual saved score calls')
    saved = record['row']
    verify_pose_row(saved, admitted.ligand.atom_count)
    if saved['succeeded']:
        same(stages['score.evaluate']['completed'], 1, 'successful score completion')
        terms = restore_score_terms(admitted.scorer, current, saved['terms'])
        row = _row(admitted, current, terms)
    else:
        reduced = {k: v for k, v in saved.items() if k not in {'terms', 'coordinates_sha256', 'coordinates_binary64_hex'}}
        row = restore_failure_row(admitted.authority, admitted.proposal, reduced, refined=current.refined)
        terms = None
    same(_pose(row, terms), saved, 'saved score and current geometry')
    return saved


def _score_start_allowed(directory, arm, counters, prior_indices):
    """A missing reservation is not evidence that this score has never run."""
    if (counters['new_score_calls_by_arm'][arm] != 0 or
            (arm == 'baseline' and ((directory / 'numerical-start-intent.json').exists()
                                    or (directory / 'numerical').exists()))):
        counters['unknown_pending_score_attempts'] += 1
        raise ResearchError('current score work without reservation; automatic rescore is forbidden')
    for index in prior_indices:
        path = directory / f'invocation-{index:06d}.end.json'
        if not path.exists():
            counters['unknown_pending_score_attempts'] += 1
            raise ResearchError('unfinished invocation without score reservation; automatic rescore is forbidden')
        work = _read_json(path).get('score_work', {})
        per_arm = work.get('new_score_calls_by_arm')
        if (type(per_arm) is not dict or set(per_arm) != {'baseline', 'refined'}
                or any(type(value) is not int or value < 0 for value in per_arm.values())
                or type(work.get('new_score_calls')) is not int
                or type(work.get('unknown_pending_score_attempts')) is not int
                or sum(per_arm.values()) != work.get('new_score_calls')
                or per_arm[arm] != 0 or work.get('unknown_pending_score_attempts') != 0):
            counters['unknown_pending_score_attempts'] += 1
            raise ResearchError('prior score work without reservation; automatic rescore is forbidden')


def _score(admitted, directory, arm, current, *, execute, counters, prior_indices=()):
    intent_path, path = directory / f'{arm}-score-intent.json', directory / f'{arm}-score.json'
    expected_intent = {'schema_id': SCORE_SCHEMA + '/intent', 'arm': arm,
        'binding_sha256': admitted.binding['receipt_sha256'],
        'proposal_fingerprint_sha256': current.fingerprint_sha256, 'reserved_score_calls': 1}
    if intent_path.exists():
        intent = _read_json(intent_path)
        same(intent, expected_intent, 'saved score intent')
        if not path.exists():
            counters['unknown_pending_score_attempts'] += 1
            raise ResearchError('uncommitted score attempt; automatic rescore is forbidden')
        record = _read_json(path)
        row = _restore_score(admitted, arm, current, record, intent)
        counters['reused_score_receipts'] += 1
        return row, record
    if path.exists() or not execute:
        raise ResearchError('score receipt or intent is missing')
    _score_start_allowed(directory, arm, counters, prior_indices)
    _publish(intent_path, expected_intent)
    meter = WorkMeter()
    counters['new_score_calls'] += 1
    counters['new_score_calls_by_arm'][arm] += 1
    terms = None
    try:
        with meter.measure('score.evaluate'):
            terms = admitted.scorer.score_terms(current)
        row = _row(admitted, current, terms)
    except Exception as exc:
        row, terms = _failure(admitted, current, exc), None
    except BaseException:
        counters['unknown_pending_score_attempts'] += 1
        raise
    record = _sealed({'schema_id': SCORE_SCHEMA, 'arm': arm,
        'binding_sha256': admitted.binding['receipt_sha256'],
        'proposal_fingerprint_sha256': current.fingerprint_sha256,
        'intent_sha256': digest(expected_intent), 'row': _pose(row, terms),
        'score_calls': 1, 'work': meter.snapshot()})
    _publish(path, record)
    return _restore_score(admitted, arm, current, record, expected_intent), record


def _attempt(admitted, numerical):
    state = numerical['checkpoint']['state']
    current, initial = state['current'], state['initial']
    same(state['original_coordinates'], coordinates_hex(admitted.proposal.coordinates), 'numerical original coordinates')
    same(state['config'], admitted.config.to_dict(), 'numerical solver configuration')
    status = numerical['status']
    if status not in TERMINAL:
        raise ResearchError('terminal Cartesian result required for selection')
    same(numerical['converged'], status == 'force_converged', 'terminal convergence status')
    failed = status == 'evaluation_failed' or initial is None or current is None
    attempt = {'schema_id': 'cpu_cartesian_registered_attempt/1.3.0',
        'candidate_id': admitted.proposal.candidate_id, 'proposal_index': admitted.proposal.proposal_index,
        'source_proposal_fingerprint_sha256': admitted.proposal.fingerprint_sha256,
        'pre_coordinates_binary64_hex': coordinates_hex(admitted.proposal.coordinates),
        'pre_coordinates_sha256': admitted.proposal.coordinate_fingerprint_sha256,
        'status': 'failure' if failed else 'success', 'minimization_status': status,
        'converged': numerical['converged'], 'numerical_state_sha256': digest(state)}
    if not failed:
        force = decode_coordinates(current['forces'], admitted.ligand.atom_count)
        maximum = float(torch.linalg.vector_norm(force, dim=-1).max())
        same(maximum.hex(), current['maximum_raw_atom_force'], 'raw force observation')
        same(numerical['converged'], maximum <= admitted.config.force_tolerance, 'raw force convergence')
        attempt.update(energy_basis=ENERGY_BASIS,
            max_internal_increase_kcal_per_mol=admitted.fixed.cross.max_internal_increase_kcal_per_mol,
            initial_energy=float.fromhex(initial['energy']), final_energy=float.fromhex(current['energy']),
            energy_delta=float.fromhex(current['energy']) - float.fromhex(initial['energy']),
            initial_components={k: float.fromhex(v) for k, v in initial['components'].items()},
            final_components={k: float.fromhex(v) for k, v in current['components'].items()},
            maximum_raw_atom_force=maximum, post_coordinates_binary64_hex=current['coordinates'],
            post_coordinates_sha256=coordinate_fingerprint(decode_coordinates(current['coordinates'], admitted.ligand.atom_count)[0]))
    return _sealed(attempt)


def _refined(admitted, attempt):
    return admitted.proposal.with_refined_coordinates(
        decode_coordinates(attempt['post_coordinates_binary64_hex'], admitted.ligand.atom_count)[0],
        refiner_id='cpu_cartesian_registered_refiner', refiner_version='1.3.0',
        refinement_receipt_sha256=attempt['receipt_sha256'])


def _report(admitted, numerical, baseline, baseline_record, refined, refined_record, attempt):
    choice, reason = choose_variant(baseline, refined, attempt, True)
    candidate = baseline if choice == 'baseline' else refined
    candidates = [] if choice == 'none' else [candidate_from_row(candidate, choice)]
    desc = descriptor(EXPLICIT_MODEL)
    selection = select_final_candidates(candidates, desc, admitted.selection, admitted.ligand.atom_count)
    raw, admitted_arms = {}, {}
    for name, row in (('baseline', baseline), ('refined', refined)):
        rows = [candidate_from_row(row, name)] if row['succeeded'] and row['selection_eligible'] else []
        raw[name] = select_final_candidates(rows, desc, admitted.selection, admitted.ligand.atom_count)
        if name == 'refined' and not refinement_admissible(row, attempt, True):
            rows = []
        admitted_arms[name] = select_final_candidates(rows, desc, admitted.selection, admitted.ligand.atom_count)
    return _sealed({'schema_id': RESULT_SCHEMA, 'execution_complete': True,
        'binding': admitted.binding, 'numerical_result': numerical, 'attempt': attempt,
        'rows': {'baseline': baseline, 'refined': refined},
        'score_receipts': {'baseline': baseline_record, 'refined': refined_record},
        'paired_decision': {'candidate_id': admitted.proposal.candidate_id, 'variant': choice, 'reason': reason},
        'raw_per_arm_selection': raw, 'per_arm_selection': admitted_arms, 'final_selection': selection,
        'score_quantity': SCORE_QUANTITY, 'score_calls': 1 + int(refined_record is not None),
        'force_work': numerical['work'], 'candidate_count': 1,
        'refined_cartesian_torsion_metadata': 'original_registered_angles_retained_not_a_torsion_reconstruction',
        'physical_affinity_computed': False, 'candidate_source_admission_verified': False,
        'scientifically_validated': False, 'claim_safe': False}, 'result_sha256')


def _assemble(admitted, directory, numerical, *, execute, counters, prior_indices=()):
    baseline, before_record = _score(admitted, directory, 'baseline', admitted.proposal,
                                     execute=execute, counters=counters, prior_indices=prior_indices)
    attempt = _attempt(admitted, numerical)
    if attempt['status'] == 'failure':
        refined = _pose(_failure(admitted, admitted.proposal, ResearchError('Cartesian minimization failed')), None)
        after_record = None
    else:
        current = _refined(admitted, attempt)
        refined, after_record = _score(admitted, directory, 'refined', current, execute=execute,
                                      counters=counters, prior_indices=prior_indices)
    return _report(admitted, numerical, baseline, before_record, refined, after_record, attempt)


def _numerical_verify(admitted, directory):
    from .minimization import verify_run
    result = verify_run(admitted.ligand, admitted.parameters, admitted.config, fixed_environment=admitted.fixed,
                        run_dir=directory / 'numerical', binding=admitted.binding)
    indices, _, problems = _invocation_inventory(directory)
    _validate_invocation_history(directory, admitted.request, indices, problems)
    _retained_numerical_floor(directory, indices, result['work'])
    return result


def _numerical_reservation(admitted, directory, *, create=False, prior_indices=()):
    """Reserve the one nested run durably; missing history cannot reset its budget."""
    path = directory / 'numerical-start-intent.json'
    expected = {'schema_id': RESULT_SCHEMA + '/numerical-start-intent',
                'binding_sha256': admitted.binding['receipt_sha256'],
                'numerical_directory': 'numerical', 'reserved_numerical_runs': 1}
    exists = (directory / 'numerical').exists()
    if path.exists():
        same(_read_json(path), expected, 'saved numerical start intent')
        if not exists:
            raise ResearchError('reserved numerical history is missing; automatic restart is forbidden')
        return True
    if exists or not create:
        raise ResearchError('numerical start intent is missing; automatic restart is forbidden')
    for index in prior_indices:
        prior = directory / f'invocation-{index:06d}.end.json'
        if not prior.exists():
            raise ResearchError('unfinished invocation without numerical reservation; work is unknown')
        receipt = _read_json(prior)
        if (receipt.get('numerical_entrypoint_invoked') is not False
                or receipt.get('new_force_calls') != 0
                or receipt.get('numerical_work_before') is not None
                or receipt.get('numerical_work_after') is not None):
            raise ResearchError('prior numerical work without reservation; automatic restart is forbidden')
    _publish(path, expected)  # Immutable file publication fsyncs both file and directory.
    return False


def _verify(admitted, directory, counters, *, numerical_root=None):
    same(_read_json(directory / 'request.json'), admitted.request, 'retained Cartesian request')
    same(_read_json(directory / 'binding.json'), admitted.binding, 'retained Cartesian binding')
    stored = _read_json(directory / 'result.json')
    _check_seal(stored, 'result_sha256')
    _numerical_reservation(admitted, directory)
    numerical = _numerical_verify(admitted, directory if numerical_root is None else numerical_root)
    reconstructed = _assemble(admitted, directory, numerical, execute=False, counters=counters)
    same(stored, reconstructed, 'reconstructed Cartesian selection result')
    return stored


def _counters():
    return {'new_score_calls': 0, 'new_score_calls_by_arm': {'baseline': 0, 'refined': 0},
            'reused_score_receipts': 0, 'unknown_pending_score_attempts': 0}


def _directory_identity(locked, actual):
    """Keep the outer locked fd bound to the non-/proc path used by TrialJournal."""
    held, visible = os.stat(locked), os.stat(actual, follow_symlinks=False)
    if (not stat.S_ISDIR(visible.st_mode) or visible.st_uid != os.geteuid()
            or visible.st_mode & 0o077
            or (held.st_dev, held.st_ino) != (visible.st_dev, visible.st_ino)):
        raise ResearchError('Cartesian output directory path identity changed')


def _work_delta(before, after):
    if before is None or after is None:
        return None
    result = {key: after[key] - before[key] for key in CALL_FIELDS}
    if any(type(value) is not int or value < 0 for value in result.values()):
        raise ResearchError('cumulative numerical work decreased')
    return result


def _invocation_inventory(directory):
    """Include surviving ends; a missing start must never hide recorded work."""
    pairs, problems = {}, []
    for path in directory.glob('invocation-*'):
        match = re.fullmatch(r'invocation-([0-9]{6})\.(start|end)\.json', path.name)
        if match is None:
            problems.append('unrecognized invocation filename')
            continue
        pairs.setdefault(int(match[1]), set()).add(match[2])
    indices = sorted(pairs)
    if indices != list(range(len(indices))):
        problems.append('invocation index sequence has gaps')
    if any('start' not in kinds for kinds in pairs.values()):
        problems.append('invocation end has no corresponding start')
    unfinished = sum(kinds == {'start'} for kinds in pairs.values())
    return indices, unfinished, problems


def _validate_invocation_history(directory, request, indices, problems):
    if problems:
        raise ResearchError('; '.join(problems))
    for index in indices:
        start = _read_json(directory / f'invocation-{index:06d}.start.json')
        same(start.get('schema_id'), RESULT_SCHEMA + '/invocation', 'prior invocation schema')
        same(start.get('request_sha256'), digest(request), 'prior invocation request')
        if type(start.get('resume')) is not bool:
            raise ResearchError('prior invocation resume flag is invalid')
        end_path = directory / f'invocation-{index:06d}.end.json'
        if not end_path.exists():
            continue  # Interrupted outer bookkeeping; nested durable evidence still governs reuse.
        end = _read_json(end_path)
        same(end.get('schema_id'), RESULT_SCHEMA + '/invocation', 'prior invocation end schema')
        if type(end.get('index')) is not int or end['index'] != index:
            raise ResearchError('prior invocation end index is inconsistent')
        same(end.get('resume'), start['resume'], 'prior invocation start/end mode')
        work = end.get('score_work')
        per_arm = work.get('new_score_calls_by_arm') if type(work) is dict else None
        if (type(per_arm) is not dict or set(per_arm) != {'baseline', 'refined'}
                or any(type(value) is not int or value not in (0, 1) for value in per_arm.values())
                or type(work.get('new_score_calls')) is not int
                or sum(per_arm.values()) != work['new_score_calls']
                or type(work.get('unknown_pending_score_attempts')) is not int
                or work['unknown_pending_score_attempts'] < 0):
            raise ResearchError('prior invocation score work is inconsistent')
        invoked, calls = end.get('numerical_entrypoint_invoked'), end.get('new_force_calls')
        if (type(invoked) is not bool or (calls is not None and (type(calls) is not int or calls < 0))
                or (not invoked and calls != 0)):
            raise ResearchError('prior invocation numerical work is inconsistent')


def _retained_numerical_floor(directory, indices, work):
    """A self-consistent older journal cannot erase work still recorded outside it."""
    for index in indices:
        path = directory / f'invocation-{index:06d}.end.json'
        if not path.exists():
            continue
        receipt = _read_json(path)
        for field in ('numerical_work_before', 'numerical_work_after'):
            previous = receipt.get(field)
            if previous is None:
                continue
            if type(previous) is not dict:
                raise ResearchError('retained numerical work is invalid')
            for key in (*CALL_FIELDS, 'known_completed_force_calls'):
                value = previous.get(key)
                if value is None:
                    continue  # Unknown work is not converted to a known zero.
                if type(value) is not int or value < 0 or work[key] < value:
                    raise ResearchError('numerical history is behind retained invocation work')


def _unresolved_numerical_invocations(directory, indices):
    """Unknown outer calls cannot be cleared by replaying an older complete prefix."""
    unresolved = []
    for index in indices:
        path = directory / f'invocation-{index:06d}.end.json'
        if not path.exists():
            unresolved.append({'index': index, 'reason': 'invocation_end_missing'})
            continue
        receipt = _read_json(path)
        after = receipt.get('numerical_work_after')
        if receipt['numerical_entrypoint_invoked'] and (
                receipt['new_force_calls'] is None or type(after) is not dict
                or after.get('actual_force_calls') is None
                or after.get('unknown_pending_attempts') != 0):
            unresolved.append({'index': index, 'reason': 'numerical_return_work_unknown'})
    return unresolved


def _require_known_continuation(numerical, pause, unresolved):
    if numerical['status'] != 'checkpointed':
        return  # A verified terminal journal requires no new objective or restart verification.
    attempts = numerical['checkpoint']['state']['attempts']
    advancing = pause is None or pause > attempts
    if advancing and unresolved:
        raise ResearchError('prior numerical invocation work is unresolved; automatic continuation is forbidden')


def evaluate(request, run_dir, *, pause_after_objective_attempts=None, resume=False):
    """Run once or resume explicit durable work; completed resume has no new score/force calls."""
    from .minimization import minimize
    if type(resume) is not bool:
        raise ResearchError('explicit resume boolean required')
    if pause_after_objective_attempts is not None:
        integer(pause_after_objective_attempts, 1, 8192)
    meter, counters = WorkMeter(), _counters()
    start = time.perf_counter_ns()
    actual_directory = Path(run_dir).absolute()
    with _directory(actual_directory, resume=resume) as directory:
        _directory_identity(directory, actual_directory)
        indices, prior_unfinished, history_problems = _invocation_inventory(directory)
        index = max(indices, default=-1) + 1
        prefix = directory / f'invocation-{index:06d}'
        _publish(Path(str(prefix) + '.start.json'), {'schema_id': RESULT_SCHEMA + '/invocation',
            'request_sha256': digest(request), 'resume': resume, 'prior_unfinished_invocations': prior_unfinished})
        outcome, error, admitted = None, None, None
        numerical_before, numerical_after = None, None
        numerical_invoked = False
        unresolved_numerical = None
        try:
            _validate_invocation_history(directory, request, indices, history_problems)
            unresolved_numerical = _unresolved_numerical_invocations(directory, indices)
            admitted = _admit(request, meter)
            if resume:
                same(_read_json(directory / 'request.json'), admitted.request, 'resume request')
                same(_read_json(directory / 'binding.json'), admitted.binding, 'resume binding')
            else:
                _publish(directory / 'request.json', admitted.request)
                _publish(directory / 'binding.json', admitted.binding)
            if (directory / 'result.json').exists():
                outcome = _verify(admitted, directory, counters, numerical_root=actual_directory)
                numerical_before = numerical_after = outcome['numerical_result']['work']
            else:
                _score(admitted, directory, 'baseline', admitted.proposal, execute=True,
                       counters=counters, prior_indices=indices)
                numerical_exists = _numerical_reservation(admitted, directory, create=True, prior_indices=indices)
                if numerical_exists:
                    retained = _numerical_verify(admitted, actual_directory)
                    numerical_before = retained['work']
                    _require_known_continuation(retained, pause_after_objective_attempts, unresolved_numerical)
                else:
                    numerical_before = {key: 0 for key in CALL_FIELDS}
                _directory_identity(directory, actual_directory)
                numerical_invoked = True
                numerical = minimize(admitted.ligand, admitted.parameters, admitted.config,
                    fixed_environment=admitted.fixed, run_dir=actual_directory / 'numerical', binding=admitted.binding,
                    pause_after_objective_attempts=pause_after_objective_attempts, resume=numerical_exists)
                numerical_after = numerical['work']
                if numerical['status'] == 'checkpointed':
                    outcome = {'schema_id': RESULT_SCHEMA, 'execution_complete': False,
                               'status': 'checkpointed', 'numerical_result': numerical,
                               'binding': admitted.binding, 'final_selection': None,
                               'scientifically_validated': False}
                else:
                    outcome = _assemble(admitted, directory, numerical, execute=True,
                                        counters=counters, prior_indices=indices)
            _intact(admitted, meter)
            _directory_identity(directory, actual_directory)
            _work_delta(numerical_before, numerical_after)
            if outcome['execution_complete'] and not (directory / 'result.json').exists():
                _publish(directory / 'result.json', outcome)
        except BaseException as exc:
            if isinstance(getattr(exc, 'work', None), dict):
                numerical_after = deepcopy(exc.work)
            error = {'type': type(exc).__name__, 'receipt': failure_receipt(
                exc, public_message='Cartesian workflow execution interrupted or failed').to_dict()}
            raise
        finally:
            finalization_error, delta = None, None
            try:
                _directory_identity(directory, actual_directory)
                delta = _work_delta(numerical_before, numerical_after)
            except Exception as exc:
                finalization_error = exc
            invocation = {'schema_id': RESULT_SCHEMA + '/invocation', 'index': index,
                'resume': resume, 'prior_unfinished_invocations': prior_unfinished, 'error': error,
                'score_work': counters, 'setup_and_verification_work': meter.snapshot(),
                'whole_wall_ns_before_receipt_publication': time.perf_counter_ns() - start,
                'durations_are_inclusive_do_not_sum': True,
                'completed_result_sha256': None if outcome is None else outcome.get('result_sha256'),
                'numerical_entrypoint_invoked': numerical_invoked,
                'prior_unresolved_numerical_invocations': unresolved_numerical,
                'numerical_work_before': numerical_before, 'numerical_work_after': numerical_after,
                'new_numerical_call_counts': delta,
                'new_force_calls': (0 if not numerical_invoked else None if delta is None else delta['actual_force_calls']),
                'finalization_error': None if finalization_error is None else failure_receipt(finalization_error).to_dict(),
                'numerical_work_retained_in_nested_run': True, 'scientifically_validated': False}
            _publish(Path(str(prefix) + '.end.json'), invocation)
            if error is None and finalization_error is not None:
                raise finalization_error
    return {'result': outcome, 'invocation': invocation}


def verify_output(request, run_dir):
    """Rebind original files, replay terms/geometry and selection; no force or score evaluation."""
    meter, counters = WorkMeter(), _counters()
    start = time.perf_counter_ns()
    admitted = _admit(request, meter)
    result = _verify(admitted, Path(run_dir).absolute(), counters)
    _intact(admitted, meter)
    return {'structural_verification_passed': True, 'result_sha256': result['result_sha256'],
            'score_work': counters, 'setup_and_verification_work': meter.snapshot(),
            'wall_ns': time.perf_counter_ns() - start, 'scoring_reexecuted': False,
            'numerical_evaluation_reexecuted': False, 'scientifically_validated': False}
