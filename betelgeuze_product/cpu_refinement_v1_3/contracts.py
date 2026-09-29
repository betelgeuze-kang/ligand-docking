"""Explicit Cartesian budgets and source identities, separate from projected 1.2."""
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path

from betelgeuze_product.cpu_refinement_v1_2.provenance import (
    ResearchError, canonical, exact_fields, finite, integer,
    source_manifest as previous_source_manifest,
)

CONFIG_SCHEMA = 'cpu_cartesian_solver_config/1.3.0'
STATE_SCHEMA = 'cpu_cartesian_solver_state/1.3.0'
RESULT_SCHEMA = 'cpu_cartesian_minimization_result/1.3.0'
ALGORITHMS = {'sd': 'cpu_cartesian_sd/1.3.0', 'lbfgs': 'cpu_cartesian_lbfgs/1.3.0'}


@dataclass(frozen=True)
class SolverConfig:
    algorithm: str = 'lbfgs'
    max_objective_attempts: int = 417
    max_accepted_steps: int = 416
    max_restart_verifications: int = 2
    initial_step_size: float = .001
    maximum_atom_displacement: float = .05
    force_tolerance: float = .001
    max_backtracks: int = 12
    armijo_constant: float = .0001
    backtrack_factor: float = .5
    history_size: int = 10
    curvature_relative_threshold: float = 1.e-12
    max_neighbors: int = 256
    max_atoms_per_cell: int = 256

    def __post_init__(self):
        if type(self.algorithm) is not str or self.algorithm not in ALGORITHMS:
            raise ResearchError('explicit Cartesian SD or L-BFGS required')
        integer(self.max_objective_attempts, 1, 8192)
        integer(self.max_accepted_steps, 0, 8191)
        integer(self.max_restart_verifications, 0, 32)
        integer(self.max_backtracks, 0, 64)
        integer(self.history_size, 1, 32)
        integer(self.max_neighbors, 1, 4096)
        integer(self.max_atoms_per_cell, 1, 4096)
        for name in ('initial_step_size', 'maximum_atom_displacement', 'force_tolerance'):
            if finite(getattr(self, name)) <= 0:
                raise ResearchError(name + ' must be positive')
        for name in ('armijo_constant', 'backtrack_factor', 'curvature_relative_threshold'):
            if not 0 < finite(getattr(self, name)) < 1:
                raise ResearchError(name + ' must be between zero and one')

    @property
    def algorithm_id(self):
        return ALGORITHMS[self.algorithm]

    @property
    def max_total_force_calls(self):
        return self.max_objective_attempts + self.max_restart_verifications

    def to_dict(self):
        return {'schema_id': CONFIG_SCHEMA, 'algorithm_id': self.algorithm_id, **asdict(self)}

    @classmethod
    def from_dict(cls, value):
        exact_fields(value, set(cls().to_dict()))
        result = cls(**{key: item for key, item in value.items()
                        if key not in {'schema_id', 'algorithm_id'}})
        if canonical(result.to_dict()) != canonical(value):
            raise ResearchError('noncanonical Cartesian solver configuration')
        return result


def source_manifest():
    """Bind the old numerical closure plus every new solver/validator/CLI module."""
    result = previous_source_manifest()
    folder = Path(__file__).resolve().parent
    for path in sorted(folder.glob('*.py')):
        result['betelgeuze_product/cpu_refinement_v1_3/' + path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result
