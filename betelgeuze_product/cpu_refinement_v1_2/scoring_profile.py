"""Explicit opt-in feature identities; historical ScorerV1 remains unchanged."""
from betelgeuze_engine_v2.docking.scorer_v1 import (
    ChemistryPoseScorerV1, ScorerV1Terms, SCORER_V1_SCORE_ID,
    SCORER_V1_APPLICABILITY_DOMAIN_ID,
)
from betelgeuze_engine_v2.docking.scoring import DockingScoreDescriptor, ScoreDirection
from .fixed_receptor import FIXED_REQUEST_SCHEMA, FIXED_REPORT_SCHEMA
from .provenance import ResearchError

LEGACY_MODEL = 'legacy_scorer_v1'
EXPLICIT_MODEL = 'explicit_graph_hbond_features/1.0.0'
EXPLICIT_REQUEST_SCHEMA = 'cpu_explicit_chemistry_fixed_receptor_request/1.0.0'
EXPLICIT_REPORT_SCHEMA = 'cpu_explicit_chemistry_fixed_receptor_comparison/1.0.0'
EXPLICIT_PLAN_SCHEMA = 'cpu_explicit_chemistry_candidate_comparison_plan/1.0.0'
FIXED_REQUEST_SCHEMAS = {FIXED_REQUEST_SCHEMA, EXPLICIT_REQUEST_SCHEMA}
FIXED_REPORT_SCHEMAS = {FIXED_REPORT_SCHEMA, EXPLICIT_REPORT_SCHEMA}


def require_model(model):
    if type(model) is not str or model not in {LEGACY_MODEL, EXPLICIT_MODEL}:
        raise ResearchError('unsupported chemical feature model')
    return model


def request_model(request):
    return EXPLICIT_MODEL if request['schema_id'] == EXPLICIT_REQUEST_SCHEMA else LEGACY_MODEL


def report_model(report):
    return EXPLICIT_MODEL if report['schema_id'] == EXPLICIT_REPORT_SCHEMA else LEGACY_MODEL


def scorer_class(model):
    require_model(model)
    if model == LEGACY_MODEL:
        return ChemistryPoseScorerV1
    from .chemical_features import ExplicitGraphScorer
    return ExplicitGraphScorer


def terms_class(model):
    require_model(model)
    if model == LEGACY_MODEL:
        return ScorerV1Terms
    from .chemical_features import ExplicitGraphTerms
    return ExplicitGraphTerms


def descriptor(model):
    require_model(model)
    if model == EXPLICIT_MODEL:
        from .chemical_features import explicit_graph_score_descriptor
        return explicit_graph_score_descriptor()
    return DockingScoreDescriptor(SCORER_V1_SCORE_ID, ScoreDirection.MINIMIZE, None,
        'uncalibrated_dimensionless_chemistry_pose_ordering_score', False,
        applicability_domain_id=SCORER_V1_APPLICABILITY_DOMAIN_ID)


def plan_model(plan):
    if plan['schema_id'] == 'cpu_candidate_comparison_plan/1.0.0':
        if set(plan['scorer']) != {'context', 'config', 'backend'}:
            raise ResearchError('legacy scorer plan fields changed')
        return LEGACY_MODEL
    if plan['schema_id'] == EXPLICIT_PLAN_SCHEMA:
        if (set(plan['scorer']) != {'context', 'config', 'backend', 'feature_model_id'}
                or plan['scorer']['feature_model_id'] != EXPLICIT_MODEL
                or plan['cross_parameters'] is None):
            raise ResearchError('explicit scorer plan binding mismatch')
        return EXPLICIT_MODEL
    raise ResearchError('unsupported scorer plan schema')


def outer_report_schema(inner):
    if inner == EXPLICIT_REPORT_SCHEMA:
        return 'local_cpu_explicit_chemistry_fixed_receptor_comparison/1.0.0'
    if inner == FIXED_REPORT_SCHEMA:
        return 'local_cpu_fixed_receptor_comparison/1.0.0'
    return 'local_cpu_extended_comparison/1.2.1'
