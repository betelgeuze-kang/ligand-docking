"""Explicit source-bound analytic controls for subprocess integration tests.

Only a P3 plan independently verified as synthetic_control is admitted. These
mock objectives and diagnostic components are not molecular or scientific evidence.
"""
from contextlib import ExitStack
from dataclasses import asdict
from unittest.mock import patch

import torch

from betelgeuze_engine_v2 import geometry
from betelgeuze_engine_v2.molecular import canonical_topology_sha256
from betelgeuze_product.cpu_prepared_shape_comparison_v1.contracts import require
from betelgeuze_product.cpu_refinement_diagnostics_v1 import evaluation as diagnostic_evaluation
from betelgeuze_product.cpu_refinement_diagnostics_v1 import workflow as diagnostic_workflow
from betelgeuze_product.cpu_refinement_diagnostics_v1.contracts import RECORD_SCHEMA, empty_work
from betelgeuze_product.cpu_refinement_diagnostics_v1.geometry import geometry_changes
from betelgeuze_product.cpu_refinement_fourier_v1.evaluation import (
    FourierEnvironment, FourierFixedEvaluator, FourierInternalEvaluator,
)
from betelgeuze_product.cpu_refinement_linear_angle_v1.evaluation import (
    LinearAngleFixedEvaluator, LinearAngleInternalEvaluator,
)
from betelgeuze_product.cpu_refinement_v1_2 import evaluation, fixed_receptor
from betelgeuze_product.cpu_refinement_v1_2.provenance import decode_coordinates, digest
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.kernel import make_observation
from . import worker


class ForbiddenMolecularEvaluation(BaseException):
    """Cannot be swallowed as a failed/retryable molecular objective."""


def _forbidden(*args, **kwargs):
    raise ForbiddenMolecularEvaluation('molecular execution forbidden in analytic control')


def _diagnose(original, evaluator, config, observation, *, observation_ref,
              diagnostic_config=None, shape_profile=None):
    observed = (execution.validate_observation(observation, original.atom_count)
                if shape_profile is None else
                shape_profile.validate_observation(observation, original.atom_count))
    base = observed if shape_profile is None else observed['base_observation']
    force = decode_coordinates(base['forces'], original.atom_count)
    xyz = decode_coordinates(observed['coordinates'], original.atom_count)
    atoms = [{'source_index': atom.index, 'element': atom.element,
              'atom_metadata_sha256': digest(asdict(atom))} for atom in original.atoms]
    component = diagnostic_evaluation._component
    zero = torch.zeros_like(force)
    work = empty_work()
    work.update(graph_calls=1, internal_evaluator_calls=1, cross_passes=1,
                cross_blocks_visited=1, cross_blocks_active=1,
                cross_component_gradient_calls=2,
                retained_shape_reuses=int(shape_profile is not None))
    record = {'schema_id': RECORD_SCHEMA, 'observation_ref': observation_ref,
        'observation_sha256': digest(observed), 'coordinates_sha256': digest(observed['coordinates']),
        'topology_sha256': canonical_topology_sha256(original), 'atoms': atoms,
        'evaluator': evaluator.identity(), 'source_evidence_verified': False,
        'status': 'evaluated', 'components': {
            'ligand_internal': component(float.fromhex(base['energy']), force, atoms),
            'cross_lennard_jones': component(0., zero, atoms),
            'cross_screened_coulomb': component(0., zero, atoms)},
        'internal_component_energies': {'analytic_quadratic': base['energy']},
        'internal_component_energy_semantics': 'subdivision_of_ligand_internal_not_additional_terms',
        'internal_component_forces_available': False,
        'unpenalized_total': component(float.fromhex(base['energy']), force, atoms),
        'parity': {'unpenalized_forces': diagnostic_evaluation._parity(force, force)},
        'geometry': geometry_changes(original,
            original.with_coordinates(xyz, operation='synthetic_retained_diagnostic'), evaluator.parameters),
        'failure_code': None, 'work': work, 'wall_ns': 7}
    if shape_profile is not None:
        shape_force = decode_coordinates(observed['restraint_forces'], original.atom_count)
        record['components']['parent_shape_restraint'] = component(
            float.fromhex(observed['components']['parent_shape_restraint']), shape_force, atoms)
        record['augmented_total'] = component(float.fromhex(observed['energy']),
            decode_coordinates(observed['forces'], original.atom_count), atoms)
    return {**record, 'record_sha256': digest(record)}


def execute_analytic(plan_path, plan_sha256, arm, output_dir):
    """Run the real P3 journal/worker with an explicit bounded analytic objective."""
    plan, _, _, _ = worker._load(plan_path, plan_sha256, arm)
    require(plan['preflight']['evidence_kind'] == 'synthetic_control',
            'analytic controls require verified synthetic-only preparation')
    base_calls, diagnostic_calls = 0, 0

    def receipt(system, evaluator, config, intent):
        nonlocal base_calls
        require(base_calls < 256, 'analytic base-dispatch capacity exceeded')
        base_calls += 1
        xyz = decode_coordinates(intent['coordinates'], system.atom_count)
        gradient = xyz - (system.coordinates + .1)
        energy = float(.5 * gradient.square().sum())
        observation = make_observation(intent['attempt'], xyz, energy, -gradient,
            {'total': energy, 'ligand_internal': energy,
             'cross_lennard_jones': 0., 'cross_screened_coulomb': 0.})
        return {'observation': observation, 'failure': None, 'error_type': None,
                'work': {'graph_calls': 1, 'force_calls': 1, 'failed_force_calls': 0},
                'timings_ns': {'graph': 2, 'force': 3, 'objective': 7}}

    def diagnose(*args, **kwargs):
        nonlocal diagnostic_calls
        require(diagnostic_calls < 32, 'analytic diagnostic capacity exceeded')
        diagnostic_calls += 1
        return _diagnose(*args, **kwargs)

    with ExitStack() as stack:
        for evaluator in (FourierFixedEvaluator, FourierInternalEvaluator,
                          LinearAngleFixedEvaluator, LinearAngleInternalEvaluator,
                          evaluation.ExtendedEvaluator, fixed_receptor.FixedReceptorEvaluator):
            stack.enter_context(patch.object(evaluator, 'evaluate', _forbidden))
        stack.enter_context(patch.object(FourierEnvironment, 'evaluate_cross', _forbidden))
        stack.enter_context(patch.object(geometry, 'build_compact_radius_graph', _forbidden))
        stack.enter_context(patch.object(execution, 'build_compact_radius_graph', _forbidden))
        stack.enter_context(patch.object(diagnostic_evaluation, 'build_compact_radius_graph', _forbidden))
        stack.enter_context(patch.object(execution, '_invoke', receipt))
        stack.enter_context(patch.object(diagnostic_evaluation, 'diagnose_observation', diagnose))
        stack.enter_context(patch.object(diagnostic_workflow, 'diagnose_observation', diagnose))
        row = worker.execute_arm(plan_path, plan_sha256, arm, output_dir)
    if row['result_sha256'] is not None:
        recorded = (row['work']['evaluation_work']['force_calls'] if arm == 'B0'
                    else row['work']['actual_force_calls'])
        require(recorded == base_calls, 'analytic base-dispatch accounting mismatch')
    if 'diagnostic_work' in row:
        require(row['diagnostic_work']['internal_evaluator_calls'] == diagnostic_calls,
                'analytic diagnostic accounting mismatch')
    return row
