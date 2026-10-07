"""Versioned augmented observations around one unchanged base dispatch.

No molecular evaluation occurs on replay. Base observations retain the exact
unpenalized values; lambda zero never adds even a floating point zero to them.
"""
from dataclasses import dataclass
import time
import torch

from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, canonical, coordinates_hex, decode_coordinates, exact_fields,
    finite, integer,
)
from betelgeuze_product.cpu_refinement_v1_3 import minimization as execution
from betelgeuze_product.cpu_refinement_v1_3.kernel import (
    validate_observation as validate_base, require_array, scalar, maximum_atom_norm,
)

from .reference import ShapeDomainError

OBSERVATION_SCHEMA = 'cpu_parent_shape_observation/1.0.0'
COMPONENTS = {'ligand_internal', 'cross_lennard_jones', 'cross_screened_coulomb',
              'parent_shape_restraint', 'unpenalized_total', 'total'}
SHAPE_WORK = {'base_force_calls', 'failed_base_force_calls', 'shape_calls',
              'failed_shape_calls', 'augmented_observation_failures'}


def make_shape_observation(base, penalty, shape_forces, strength):
    n = len(base['coordinates'])
    base = validate_base(base, n)
    penalty = finite(penalty, nonnegative=True)
    shape = require_array(shape_forces, n)
    original = decode_coordinates(base['forces'], n)
    if strength == 0:
        if penalty != 0 or bool((shape != 0).any()):
            raise ResearchError('zero-strength observation has nonzero restraint')
        combined = original
        energy = scalar(base['energy'])
    else:
        combined = require_array(original + shape, n)
        energy = finite(scalar(base['energy']) + penalty)
    maximum = finite(maximum_atom_norm(combined), nonnegative=True)
    parts = {k: v for k, v in base['components'].items() if k != 'total'}
    parts.update(parent_shape_restraint=penalty.hex(),
                 unpenalized_total=base['energy'], total=energy.hex())
    return {**base, 'schema_id': OBSERVATION_SCHEMA,
            'energy': energy.hex(),
            'forces': base['forces'] if strength == 0 else coordinates_hex(combined),
            'components': parts, 'maximum_raw_atom_force': maximum.hex(),
            'maximum_unpenalized_atom_force': base['maximum_raw_atom_force'],
            'maximum_augmented_atom_force': maximum.hex(),
            'base_observation': base, 'restraint_forces': coordinates_hex(shape)}


@dataclass(frozen=True)
class ShapeProfile:
    reference: object
    strength: float
    identity_for_system: object
    calculate: object
    max_internal_increase: float = 0.
    state_schema = 'cpu_parent_shape_solver_state/1.0.0'
    journal_schema = 'cpu_parent_shape_trial_journal/1.0.0'
    checkpoint_schema = 'cpu_parent_shape_checkpoint/1.0.0'

    def __post_init__(self):
        if type(self.strength) is not float or self.strength not in (0., 100., 1000.):
            raise ResearchError('predeclared shape strength required')
        finite(self.max_internal_increase, nonnegative=True)

    def validate_observation(self, value, atom_count):
        exact_fields(value, {'attempt', 'coordinates', 'energy', 'forces', 'components',
                            'maximum_raw_atom_force', 'schema_id',
                            'maximum_unpenalized_atom_force', 'maximum_augmented_atom_force', 'base_observation',
                            'restraint_forces'})
        exact_fields(value['components'], COMPONENTS)
        if value['schema_id'] != OBSERVATION_SCHEMA:
            raise ResearchError('shape observation schema mismatch')
        base = validate_base(value['base_observation'], atom_count)
        rebuilt = make_shape_observation(base, scalar(value['components']['parent_shape_restraint']),
                                         decode_coordinates(value['restraint_forces'], atom_count),
                                         self.strength)
        if canonical(rebuilt) != canonical(value):
            raise ResearchError('augmented observation energy/force accounting mismatch')
        return rebuilt

    def invoke(self, system, evaluator, config, intent):
        # Dispatch exactly once through the unchanged base path, including failures.
        receipt = execution._invoke(system, evaluator, config, intent)
        extra_started = time.perf_counter_ns()
        work = {'base_force_calls': receipt['work']['force_calls'],
                'failed_base_force_calls': receipt['work']['failed_force_calls'],
                'shape_calls': 0, 'failed_shape_calls': 0,
                'augmented_observation_failures': 0}
        if receipt['observation'] is not None:
            try:
                base = receipt['observation']
                if self.strength == 0:
                    # No trial pair-distance checks and no redundant base call.
                    penalty, force = 0., torch.zeros((1, system.atom_count, 3), dtype=torch.float64)
                else:
                    xyz = decode_coordinates(intent['coordinates'], system.atom_count)
                    trial = system.with_coordinates(xyz, operation=config.algorithm_id)
                    ids = self.identity_for_system(trial)
                    work['shape_calls'] = 1
                    try:
                        penalty, rows = self.calculate(self.reference, xyz[0].tolist(), self.strength, **ids)
                    except Exception:
                        work['failed_shape_calls'] = 1
                        raise
                    force = torch.tensor([rows], dtype=torch.float64)
                receipt['observation'] = make_shape_observation(base, penalty, force, self.strength)
            except Exception as exc:
                work['augmented_observation_failures'] = 1
                receipt.update(observation=None,
                    failure='retryable' if isinstance(exc, (ShapeDomainError, FloatingPointError)) else 'fatal',
                    error_type=type(exc).__name__[:128])
                receipt['work']['failed_force_calls'] = receipt['work']['force_calls']
        extra_elapsed = time.perf_counter_ns() - extra_started
        if receipt['work']['force_calls']:
            receipt['timings_ns']['force'] += extra_elapsed
        receipt['timings_ns']['objective'] += extra_elapsed
        receipt['shape_work'] = work
        return receipt

    def work(self, config):
        return {prefix + '_' + key: 0 for prefix in ('optimizer', 'restart') for key in SHAPE_WORK}

    def completed_work(self, payload, work, prefix):
        row = payload['shape_work']
        exact_fields(row, SHAPE_WORK)
        for value in row.values():
            integer(value, 0, 1)
        base, failed_base, shape, failed_shape, failed_aug = (row[k] for k in
            ('base_force_calls', 'failed_base_force_calls', 'shape_calls', 'failed_shape_calls',
             'augmented_observation_failures'))
        if (base != payload['work']['force_calls'] or failed_base > base or shape > base
                or failed_shape > shape or failed_aug > base or (failed_base and shape)
                or (self.strength == 0 and shape) or (failed_shape and not failed_aug)):
            raise ResearchError('shape/base work denominator inconsistent')
        if payload['observation'] is not None:
            if failed_base or failed_shape or failed_aug or base != 1 or shape != int(self.strength != 0):
                raise ResearchError('successful shape observation work inconsistent')
        elif base and not (failed_base or failed_aug):
            raise ResearchError('failed combined call lacks failed base or augmentation')
        for key, value in row.items():
            work[prefix + '_' + key] += value

    def result_fields(self, state, config):
        current = state['current']
        base_stationary = bool(current is not None and
            scalar(current['maximum_unpenalized_atom_force']) <= config.force_tolerance)
        restrained_stationary = bool(current is not None and
            scalar(current['maximum_raw_atom_force']) <= config.force_tolerance)
        initial = state.get('initial')
        increase = None if current is None or initial is None else finite(
            scalar(current['base_observation']['components']['ligand_internal']) -
            scalar(initial['base_observation']['components']['ligand_internal']))
        return {'converged': state['status'] == 'force_converged',
                'status': ('restrained_force_converged' if self.strength > 0 and state['status'] == 'force_converged'
                           else 'checkpointed' if state['status'] == 'running' else state['status']),
                'convergence_basis': 'augmented_force_maximum_atom_euclidean_norm',
                'restrained_stationary': restrained_stationary,
                'unpenalized_stationary': base_stationary,
                'internal_energy_gate_basis': 'unpenalized_ligand_internal_only',
                'unpenalized_internal_energy_increase': increase,
                'maximum_allowed_internal_increase': self.max_internal_increase,
                'internal_energy_gate_passed': None if increase is None else increase <= self.max_internal_increase,
                'chirality_enforced_by_restraint': False,
                'pose_selection_admitted': False}
