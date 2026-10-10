"""Independent sidecar identity, frozen tolerances, and bounded selection."""
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path

from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, digest

SCHEMA = 'cpu_prepared_force_geometry_diagnostics/1.0.0'
RECORD_SCHEMA = 'cpu_prepared_force_geometry_diagnostic_record/1.0.0'
CONFIG_SCHEMA = 'cpu_prepared_force_geometry_diagnostic_config/1.0.0'
COMPONENTS = ('ligand_internal', 'cross_lennard_jones', 'cross_screened_coulomb')
BOUNDARY = {'scientifically_validated': False, 'claim_safe': False,
            'pose_selection_admitted': False, 'customer_execution_allowed': False,
            'stationarity_criterion_changed': False, 'source_authenticity_verified': False}
WORK_KEYS = ('graph_calls', 'internal_evaluator_calls', 'cross_passes',
             'cross_blocks_visited', 'cross_blocks_active', 'cross_component_gradient_calls',
             'failed_evaluations', 'retained_shape_reuses')


def require(condition, message):
    if not condition:
        raise ResearchError(message)


@dataclass(frozen=True)
class DiagnosticConfig:
    accepted_stride: int = 10
    maximum_records: int = 256
    schema_id: str = CONFIG_SCHEMA

    def __post_init__(self):
        require(self.schema_id == CONFIG_SCHEMA, 'diagnostic config schema mismatch')
        require(type(self.accepted_stride) is int and 1 <= self.accepted_stride <= 8192,
                'bounded integer accepted stride required')
        require(type(self.maximum_records) is int and 1 <= self.maximum_records <= 1024,
                'bounded integer diagnostic record capacity required')

    def to_dict(self):
        return {**asdict(self), 'energy_atol_kcal_per_mol': 1.e-9,
                'force_atol_kcal_per_mol_angstrom': 1.e-9, 'parity_rtol': 1.e-10,
                'selection': 'initial_plus_accepted_stride_plus_terminal_or_checkpoint_endpoint',
                'force_components': list(COMPONENTS),
                'internal_leaf_forces_available': False}

    @property
    def fingerprint_sha256(self):
        return digest(self.to_dict())


def implementation_sources():
    return {'betelgeuze_product/cpu_refinement_diagnostics_v1/' + path.name:
            hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).resolve().parent.glob('*.py'))}


def empty_work():
    return dict.fromkeys(WORK_KEYS, 0)
