"""Explicit prepared-request entry for numerical diagnostics, without scoring.

Accept the unchanged Cartesian 1.3 prepared CPU request. Preserve its request and
numerical input guards. This is not a replacement for native source admission,
pose/scoring comparison, selection, or the frozen SRO campaign controller.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from pathlib import Path

import torch

from ..cpu_refinement_v1_2.provenance import ResearchError, digest
from ..cpu_refinement_v1_3 import workflow as parent
from .contracts import source_manifest
from . import minimization

AUDIT_SCHEMA = "cpu_cartesian_diagnostic_prepared_audit/1.4.0"
PREPARED_BINDING_SCHEMA = "cpu_cartesian_diagnostic_prepared_binding/1.4.0"


def _seal(value, name="receipt_sha256"):
    return {**value, name: digest(value)}


def audit_request(request):
    """Validate request shape and authenticate raw prepared files; no physics.

    This does not admit chemical state, source role, a native protocol, or training.
    The numerical runner additionally parses the same complete canonical inputs.
    """
    request, _, _ = parent._request(request)
    sources = source_manifest()
    records = []
    for role in parent.FILE_FIELDS:
        ref = request[role]
        raw = parent._read(Path(ref['path']))
        if hashlib.sha256(raw).hexdigest() != ref['sha256']:
            raise ResearchError('prepared input SHA-256 changed')
        # Preserve the parent's JSON input format check, without molecular parsing.
        parent._decode(raw)
        records.append({'role': role, 'sha256': ref['sha256'], 'bytes': len(raw),
                        'path_utf8_sha256': hashlib.sha256(ref['path'].encode('utf-8')).hexdigest()})
    if source_manifest() != sources:
        raise ResearchError('diagnostic implementation changed during request audit')
    return _seal({'schema_id': AUDIT_SCHEMA, 'request_sha256': digest(request),
                  'backend': request['backend'], 'prepared_files': records,
                  'implementation_sources': sources, 'implementation_sha256': digest(sources),
                  'scope': 'request_structure_and_raw_prepared_file_identity_only',
                  'source_role_admission_verified': False, 'chemical_state_admission_verified': False,
                  'graph_dispatches': 0, 'force_dispatches': 0, 'score_dispatches': 0,
                  'scientifically_validated': False, 'training_admitted': False, 'claim_safe': False})


@dataclass
class _Prepared:
    request: dict
    audit: dict
    config: object
    ligand: object
    parameters: object
    fixed: object
    binding: dict


def _admit_numeric(request):
    request, config, _ = parent._request(request)
    audit = audit_request(request)
    receptor = parent.all_atom_system_from_canonical_json(parent._json(parent._bound(request['receptor'])))
    ligand = parent.all_atom_system_from_canonical_json(parent._json(parent._bound(request['ligand'])))
    for system, maximum in ((receptor, 8192), (ligand, 256)):
        if (system.model_count != 1 or not 1 <= system.atom_count <= maximum or system.cell is not None
                or system.coordinates.dtype != torch.float64 or system.coordinates.device.type != 'cpu'):
            raise ResearchError('bounded single-model nonperiodic CPU float64 inputs required')
    base = parent._parameters(parent._bound(request['parameters']))
    parameters = parent._extension(parent._bound(request['extensions']), base)
    if parameters.constraints:
        raise ResearchError('Cartesian workflow does not support projected constraints')
    fixed = parent.FixedReceptorEnvironment(receptor, parent.CrossParameters.from_dict(
        parent._bound(request['cross_parameters'])))
    fixed.validate_ligand(ligand, base)
    if fixed.cross.coordinate_frame_id != request['pocket']['coordinate_frame_id']:
        raise ResearchError('fixed receptor and prepared pocket coordinate frame changed')
    if fixed.cross.max_internal_increase_kcal_per_mol > 5.:
        raise ResearchError('Cartesian workflow cannot weaken ligand strain cap')
    binding = _seal({'schema_id': PREPARED_BINDING_SCHEMA, 'request_sha256': digest(request),
                     'audit_receipt_sha256': audit['receipt_sha256'],
                     'implementation_sha256': audit['implementation_sha256'],
                     'source_role_admission_verified': False, 'scientifically_validated': False,
                     'scoring_and_selection_performed': False})
    return _Prepared(deepcopy(request), audit, config, ligand, parameters, fixed, binding)


def _intact(prepared):
    observed = audit_request(prepared.request)
    if observed != prepared.audit:
        raise ResearchError('prepared request or implementation changed')


def run_minimization(request, run_dir, *, pause_after_objective_attempts=None, resume=False):
    """Explicit prepared CPU execution through the diagnostic runner and journal."""
    prepared = _admit_numeric(request)
    try:
        numerical = minimization.minimize(prepared.ligand, prepared.parameters, prepared.config,
            fixed_environment=prepared.fixed, run_dir=Path(run_dir).absolute(), binding=prepared.binding,
            pause_after_objective_attempts=pause_after_objective_attempts, resume=resume)
    finally:
        _intact(prepared)
    return _seal({'schema_id': 'cpu_cartesian_diagnostic_prepared_result/1.4.0',
                  'audit': prepared.audit, 'prepared_binding': prepared.binding, 'numerical_result': numerical,
                  'score_dispatches': 0, 'selection_performed': False, 'source_role_admission_verified': False,
                  'scientifically_validated': False, 'training_admitted': False, 'claim_safe': False}, 'result_sha256')


def verify_run(request, run_dir):
    """Parse authenticated inputs and replay evidence; no scorer, graph or force."""
    prepared = _admit_numeric(request)
    inspection = minimization.inspect_run(prepared.ligand, prepared.parameters, prepared.config,
        fixed_environment=prepared.fixed, run_dir=Path(run_dir).absolute(), binding=prepared.binding)
    _intact(prepared)
    return _seal({'schema_id': 'cpu_cartesian_diagnostic_prepared_verification/1.4.0',
                  'audit_receipt_sha256': prepared.audit['receipt_sha256'],
                  'prepared_binding_sha256': prepared.binding['receipt_sha256'], 'inspection': inspection,
                  'graph_dispatches': 0, 'force_dispatches': 0, 'score_dispatches': 0,
                  'continuation_authorized': False, 'source_role_admission_verified': False,
                  'scientifically_validated': False, 'training_admitted': False, 'claim_safe': False})
