"""A new explicit comparison identity; no historical protocol is migrated."""
from dataclasses import dataclass

from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest

SCHEMA = 'cpu_prepared_shape_comparison/1.0.0'
PLAN_SCHEMA = 'cpu_prepared_shape_comparison_plan/1.0.0'
BASELINE_SCHEMA = 'cpu_unrefined_evaluation/1.0.0'
ARMS = {'B0': None, 'B1': 0., 'B2': 100., 'B3': 1000.}
BOUNDARY = {'scientifically_validated': False, 'claim_safe': False,
            'pose_selection_admitted': False, 'customer_execution_allowed': False,
            'source_authenticity_verified': False, 'defaults_changed': False}


def require(condition, message):
    if not condition:
        raise ResearchError(message)


@dataclass(frozen=True)
class ComparisonConfig:
    accepted_steps: int = 40
    restart_verifications: int = 0
    diagnostic_stride: int = 10
    diagnostic_maximum_records: int = 17

    def __post_init__(self):
        require(type(self.accepted_steps) is int and self.accepted_steps in (40, 80, 160),
                'explicit supported accepted-step tier required')
        require(type(self.restart_verifications) is int and self.restart_verifications == 0,
                'comparison v1 has no restart allowance')
        require(type(self.diagnostic_stride) is int and self.diagnostic_stride == 10,
                'frozen diagnostic stride required')
        require(type(self.diagnostic_maximum_records) is int
                and self.diagnostic_maximum_records == 17, 'frozen diagnostic capacity required')

    def to_dict(self):
        return {'accepted_steps': self.accepted_steps, 'restart_verifications': 0,
                'diagnostic_stride': 10, 'diagnostic_maximum_records': 17,
                'optimizer_objective_attempt_limit_per_arm': 1 + 4 * self.accepted_steps,
                'optimizer_actual_base_call_limit_per_arm': 1 + 4 * self.accepted_steps,
                'baseline_evaluation_limit': 1,
                'limits_are_equal_consumption_may_differ': True}

    @property
    def fingerprint_sha256(self):
        return digest(self.to_dict())
