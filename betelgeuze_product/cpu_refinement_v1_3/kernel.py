"""Deterministic Cartesian SD/L-BFGS state machine, without an evaluator or I/O.

The next intent is a pure function of completed observations. Replay rebuilds
curvature pairs from accepted coordinates and full forces, never from a trusted
checkpoint history. Rejected evaluations consume the same bounded attempt budget.
"""
from __future__ import annotations

from copy import deepcopy
import math

import torch

from ..cpu_refinement_v1_2.fixed_receptor import validate_components
from ..cpu_refinement_v1_2.provenance import (
    ResearchError, canonical, coordinates_hex, decode_coordinates, exact_fields,
    finite, integer,
)
from .contracts import SolverConfig, STATE_SCHEMA


def require_array(value, atom_count=None):
    if (not isinstance(value, torch.Tensor) or value.device.type != 'cpu'
            or value.dtype != torch.float64 or value.ndim != 3 or value.shape[0] != 1
            or value.shape[2] != 3 or not 1 <= value.shape[1] <= 256
            or (atom_count is not None and value.shape[1] != atom_count)
            or not bool(torch.isfinite(value).all())):
        raise ResearchError('finite 1xNx3 CPU binary64 array required')
    return value.detach().clone()


def scalar(value):
    if type(value) is not str or len(value) > 32:
        raise ResearchError('canonical finite binary64 scalar required')
    try:
        result = float.fromhex(value)
    except ValueError as exc:
        raise ResearchError('invalid binary64 scalar') from exc
    if not math.isfinite(result) or result.hex() != value:
        raise ResearchError('noncanonical or nonfinite binary64 scalar')
    return result


def maximum_atom_norm(value):
    return float(torch.linalg.vector_norm(value, dim=-1).max())


def make_observation(attempt, coordinates, energy, forces, components):
    integer(attempt, 1, 8192)
    xyz = require_array(coordinates)
    force = require_array(forces, xyz.shape[1])
    energy = finite(energy)
    validate_components(components, energy)
    maximum = maximum_atom_norm(force)
    finite(maximum, nonnegative=True)
    return {'attempt': attempt, 'coordinates': coordinates_hex(xyz),
            'energy': energy.hex(), 'forces': coordinates_hex(force),
            'components': {key: finite(value).hex() for key, value in components.items()},
            'maximum_raw_atom_force': maximum.hex()}


def validate_observation(value, atom_count):
    exact_fields(value, {'attempt', 'coordinates', 'energy', 'forces', 'components',
                         'maximum_raw_atom_force'})
    exact_fields(value['components'], {'total', 'ligand_internal', 'cross_lennard_jones',
                                      'cross_screened_coulomb'})
    rebuilt = make_observation(value['attempt'], decode_coordinates(value['coordinates'], atom_count),
                               scalar(value['energy']), decode_coordinates(value['forces'], atom_count),
                               {key: scalar(item) for key, item in value['components'].items()})
    if canonical(rebuilt) != canonical(value):
        raise ResearchError('observation does not match its complete energy/force arrays')
    return rebuilt


def _two_loop(gradient, history, initial_scale):
    q, terms = gradient.clone(), []
    for s, y in reversed(history):
        rho = 1.0 / float((s * y).sum())
        alpha = rho * float((s * q).sum())
        terms.append((rho, alpha))
        q = q - alpha * y
    scale = initial_scale
    if history:
        s, y = history[-1]
        scale = float((s * y).sum()) / float((y * y).sum())
    r = scale * q
    for (s, y), (rho, alpha) in zip(history, reversed(terms)):
        r = r + (alpha - rho * float((y * r).sum())) * s
    return r


class CartesianMachine:
    """Only validated completed observations advance the logical solver state."""

    def __init__(self, coordinates, config):
        if type(config) is not SolverConfig:
            raise ResearchError('explicit Cartesian solver configuration required')
        xyz = require_array(coordinates)
        self.config = config
        self._state = {'schema_id': STATE_SCHEMA, 'config': config.to_dict(),
                       'atom_count': xyz.shape[1], 'original_coordinates': coordinates_hex(xyz),
                       'attempts': 0, 'accepted': 0, 'status': 'running',
                       'initial': None, 'current': None, 'history': [], 'line_search': None,
                       'restarts': 0, 'skipped_curvature': 0, 'failed_evaluations': 0}

    def snapshot(self):
        return deepcopy(self._state)

    def _decode(self, rows):
        return decode_coordinates(rows, self._state['atom_count'])

    def next_intent(self):
        state, config = self._state, self.config
        if state['status'] != 'running':
            return None
        if state['current'] is None:
            return {'attempt': 1, 'iteration': 0, 'trial': 0,
                    'coordinates': deepcopy(state['original_coordinates']), 'step': 0.0.hex(),
                    'direction': coordinates_hex(torch.zeros((1, state['atom_count'], 3), dtype=torch.float64)),
                    'restarted': None}
        current = state['current']
        x, force = self._decode(current['coordinates']), self._decode(current['forces'])
        line = state['line_search']
        if line is None:
            restart = None
            if config.algorithm == 'sd':
                direction = force.clone()
                maximum = maximum_atom_norm(force)
                if config.initial_step_size * maximum > config.maximum_atom_displacement:
                    direction *= config.maximum_atom_displacement / (config.initial_step_size * maximum)
                step = config.initial_step_size
            else:
                history = [(self._decode(row['s']), self._decode(row['y'])) for row in state['history']]
                try:
                    direction = -_two_loop(-force, history, config.initial_step_size)
                    if (not bool(torch.isfinite(direction).all())
                            or float((force * direction).sum()) <= 0.0):
                        restart = 'nonfinite_or_non_descent_direction'
                except (ZeroDivisionError, OverflowError):
                    restart = 'invalid_curvature_arithmetic'
                if restart is not None:
                    direction = config.initial_step_size * force
                largest = maximum_atom_norm(direction)
                direction = direction * min(1.0, config.maximum_atom_displacement / max(largest, 1e-300))
                step = 1.0
            trial = 0
        else:
            direction, step = self._decode(line['direction']), scalar(line['step'])
            trial, restart = line['trial'], line['restarted']
        proposed = require_array(x + step * direction, state['atom_count'])
        return {'attempt': state['attempts'] + 1, 'iteration': state['accepted'] + 1,
                'trial': trial, 'coordinates': coordinates_hex(proposed),
                'step': float(step).hex(), 'direction': coordinates_hex(direction), 'restarted': restart}

    def commit(self, intent, observation, *, failure=None):
        expected = self.next_intent()
        if expected is None or canonical(expected) != canonical(intent):
            raise ResearchError('objective intent differs from deterministic next trial')
        if failure not in {None, 'retryable', 'fatal'}:
            raise ResearchError('explicit evaluation failure class required')
        if (observation is None) != (failure is not None):
            raise ResearchError('an objective must have exactly one observation or failure')
        state, config = self._state, self.config
        if observation is not None:
            observation = validate_observation(observation, state['atom_count'])
            if (observation['attempt'] != intent['attempt']
                    or observation['coordinates'] != intent['coordinates']):
                raise ResearchError('returned observation belongs to another objective intent')
        first = state['current'] is None
        outcome, curvature = ('initial' if first else 'accepted'), 'none'
        if failure is not None:
            outcome = 'rejected_evaluation'
        elif not first:
            current = state['current']
            displacement = self._decode(intent['coordinates']) - self._decode(current['coordinates'])
            old_force = self._decode(current['forces'])
            slope = -float((old_force * displacement).sum())
            if maximum_atom_norm(displacement) > config.maximum_atom_displacement + 1e-12:
                outcome = 'rejected_displacement'
            elif slope >= 0.0:
                outcome = 'rejected_non_descent'
            elif scalar(observation['energy']) > scalar(current['energy']) + config.armijo_constant * slope:
                outcome = 'rejected_armijo'
        # All validation above precedes mutation so an invalid receipt is atomic.
        state['attempts'] += 1
        if intent['trial'] == 0 and intent['restarted'] is not None:
            state['history'] = []
            state['restarts'] += 1
        if failure is not None:
            state['failed_evaluations'] += 1
        if outcome in {'initial', 'accepted'}:
            if first:
                state['initial'] = deepcopy(observation)
            else:
                if config.algorithm == 'lbfgs':
                    y = old_force - self._decode(observation['forces'])
                    sy = float((displacement * y).sum())
                    norms = float(torch.linalg.vector_norm(displacement)) * float(torch.linalg.vector_norm(y))
                    valid = (math.isfinite(sy) and math.isfinite(norms) and norms > 0.0
                             and sy > config.curvature_relative_threshold * norms)
                    if valid:
                        state['history'].append({'source_attempt': current['attempt'],
                                                 'target_attempt': observation['attempt'],
                                                 's': coordinates_hex(displacement), 'y': coordinates_hex(y)})
                        state['history'] = state['history'][-config.history_size:]
                        curvature = 'retained'
                    else:
                        state['skipped_curvature'] += 1
                        curvature = 'skipped'
                state['accepted'] += 1
            state['current'], state['line_search'] = deepcopy(observation), None
        elif not first:
            state['line_search'] = {'direction': deepcopy(intent['direction']),
                                    'step': (scalar(intent['step']) * config.backtrack_factor).hex(),
                                    'trial': intent['trial'] + 1, 'restarted': intent['restarted']}
        if failure == 'fatal' or (first and failure is not None):
            state['status'] = 'evaluation_failed'
        elif scalar(state['current']['maximum_raw_atom_force']) <= config.force_tolerance:
            state['status'] = 'force_converged'
        elif state['accepted'] >= config.max_accepted_steps:
            state['status'] = 'max_accepted_steps_reached'
        elif state['attempts'] >= config.max_objective_attempts:
            state['status'] = 'objective_budget_exhausted'
        elif state['line_search'] is not None and state['line_search']['trial'] > config.max_backtracks:
            state['status'] = 'line_search_failed'
        return {'outcome': outcome, 'curvature': curvature, 'status': state['status']}
