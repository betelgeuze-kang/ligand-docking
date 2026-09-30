"""Opt-in single proposal copied exactly from the authenticated registered pose.

No conformer rebuilding, centering, rotation sampling, search or chemistry
inference occurs here. This first CPU policy supports one binary64 model only.
The same proposal/receipt is shared by baseline and refined arms; refinement
budgets remain in their arm plans rather than changing the initial pose identity.
"""
from dataclasses import dataclass
import json

import torch

from betelgeuze_engine_v2.docking.authority import AuthenticatedDockingProblem, AUTHENTICATED_DOCKING_INPUT_SCHEMA_ID
from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
from betelgeuze_engine_v2.docking.proposals import DockingBudget, bind_docking_proposal_state
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from .provenance import (
    ResearchError, canonical, coordinates_hex, decode_coordinates, digest,
    exact_fields, integer, require_digest,
)
from .scoring_profile import REGISTERED_PROPOSAL_POLICY

REGISTERED_RECEIPT_SCHEMA = 'cpu_registered_input_single_pose_receipt/1.0.0'
_FIELDS = {'schema_id', 'policy_id', 'authority_binding', 'source_ligand_system_sha256',
    'authority_input_receipt_sha256', 'problem_fingerprint_sha256',
    'search_space_fingerprint_sha256', 'coordinate_frame_id', 'candidate_count',
    'top_k', 'max_torsions', 'translation_radius_angstrom', 'seed', 'proposal_index',
    'candidate_id', 'coordinate_dtype', 'initial_coordinates_binary64_hex',
    'initial_coordinate_fingerprint_sha256', 'proposal_fingerprint_sha256', 'receipt_sha256'}
_DIGEST_FIELDS = {'source_ligand_system_sha256', 'authority_input_receipt_sha256',
    'problem_fingerprint_sha256', 'search_space_fingerprint_sha256',
    'initial_coordinate_fingerprint_sha256', 'proposal_fingerprint_sha256', 'receipt_sha256'}

_AUTHORITY_FLAGS = {'caller_supplied_receptor_coordinates_allowed', 'caller_supplied_ligand_reference_coordinates_allowed',
    'caller_supplied_exclusions_allowed', 'caller_supplied_chirality_allowed', 'caller_supplied_search_space_allowed',
    'caller_supplied_validity_context_allowed', 'chemically_validated', 'scientifically_validated', 'claim_safe'}
_AUTHORITY_DIGESTS = {'problem_fingerprint_sha256', 'receptor_system_sha256', 'ligand_system_sha256',
    'pocket_definition_sha256', 'search_space_fingerprint_sha256', 'search_space_derivation_receipt_sha256',
    'validity_context_fingerprint_sha256', 'validity_policy_sha256', 'authority_policy_sha256'}
_AUTHORITY_FIELDS = _AUTHORITY_FLAGS | _AUTHORITY_DIGESTS | {'schema_id', 'scope', 'receptor_atom_indices',
    'receptor_model_index', 'ligand_model_index'}


def _bind(xyz, *, seed, problem, search_space):
    return bind_docking_proposal_state(coordinates=xyz,
        torsion_angles=torch.zeros(xyz.shape[0], dtype=torch.float64),
        rotation=torch.eye(3, dtype=torch.float64), translation=torch.zeros(3, dtype=torch.float64),
        proposal_index=0, seed=seed, problem_fingerprint_sha256=problem,
        search_space_fingerprint_sha256=search_space)


def require_registered_receipt(document):
    """Validate a portable receipt and recompute its exact initial proposal.

    Callers must also compare the retained authority/source/coordinate identities
    with their request, report rows, and refinement pre-coordinate evidence.
    """
    try:
        row = dict(exact_fields(document, _FIELDS))
        if (row['schema_id'] != REGISTERED_RECEIPT_SCHEMA or row['policy_id'] != REGISTERED_PROPOSAL_POLICY
                or row['coordinate_dtype'] != 'float64'):
            raise ResearchError('unsupported registered pose receipt policy/schema/dtype')
        for name in _DIGEST_FIELDS:
            require_digest(row[name])
        binding = dict(exact_fields(row['authority_binding'], _AUTHORITY_FIELDS))
        if (binding['schema_id'] != AUTHENTICATED_DOCKING_INPUT_SCHEMA_ID
                or binding['scope'] != 'known_pocket_docking'
                or any(binding[name] is not False for name in _AUTHORITY_FLAGS)):
            raise ResearchError('registered pose authority declaration mismatch')
        for name in _AUTHORITY_DIGESTS:
            require_digest(binding[name])
        integer(binding['ligand_model_index'], 0, 0)
        integer(binding['receptor_model_index'], 0, 8192)
        indices = binding['receptor_atom_indices']
        if type(indices) is not list or not indices or len(indices) > 8192:
            raise ResearchError('registered pose receptor index coverage mismatch')
        for index in indices:
            integer(index, 0, 8191)
        if len(set(indices)) != len(indices):
            raise ResearchError('registered pose duplicate receptor index')
        if (digest(binding) != row['authority_input_receipt_sha256']
                or binding['ligand_system_sha256'] != row['source_ligand_system_sha256']
                or binding['problem_fingerprint_sha256'] != row['problem_fingerprint_sha256']
                or binding['search_space_fingerprint_sha256'] != row['search_space_fingerprint_sha256']):
            raise ResearchError('registered pose authority/source binding mismatch')
        for name, value in (('candidate_count', 1), ('top_k', 1), ('max_torsions', 0), ('proposal_index', 0)):
            integer(row[name], value, value)
        integer(row['seed'], 0, 2**63 - 1)
        if (type(row['translation_radius_angstrom']) is not float
                or row['translation_radius_angstrom'].hex() != 0.0.hex()
                or type(row['coordinate_frame_id']) is not str or not row['coordinate_frame_id'].strip()):
            raise ResearchError('registered pose receipt placement/frame mismatch')
        coordinates = row['initial_coordinates_binary64_hex']
        if type(coordinates) is not list:
            raise ResearchError('registered pose coordinates must be a list')
        xyz = decode_coordinates(coordinates, len(coordinates))[0]
        if coordinate_fingerprint(xyz) != row['initial_coordinate_fingerprint_sha256']:
            raise ResearchError('registered pose coordinate fingerprint mismatch')
        proposal = _bind(xyz, seed=row['seed'], problem=row['problem_fingerprint_sha256'],
                         search_space=row['search_space_fingerprint_sha256'])
        if (proposal.fingerprint_sha256 != row['proposal_fingerprint_sha256']
                or proposal.candidate_id != row['candidate_id']):
            raise ResearchError('registered pose proposal identity mismatch')
        if digest({k: v for k, v in row.items() if k != 'receipt_sha256'}) != row['receipt_sha256']:
            raise ResearchError('registered pose receipt digest mismatch')
        return json.loads(canonical(row))
    except ResearchError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
        raise ResearchError('malformed registered pose receipt') from exc


@dataclass(frozen=True)
class RegisteredPoseReceipt:
    _document_json: str

    def __post_init__(self):
        row = require_registered_receipt(json.loads(self._document_json))
        object.__setattr__(self, '_document_json', canonical(row))

    @property
    def receipt_sha256(self):
        return self.to_dict()['receipt_sha256']

    def to_dict(self):
        return json.loads(self._document_json)


def generate_registered_pose(authority, budget, ligand_system):
    """Copy the one authenticated initial binary64 coordinate model exactly."""
    if not isinstance(authority, AuthenticatedDockingProblem) or not isinstance(budget, DockingBudget):
        raise ResearchError('registered pose requires authenticated authority and docking budget')
    authority.input_receipt_sha256
    authority.search_space.assert_integrity()
    if (budget.candidate_count != 1 or budget.top_k != 1 or budget.max_torsions != 0
            or budget.translation_radius_angstrom != 0):
        raise ResearchError('registered pose requires one candidate, top_k=1 and zero placement perturbations')
    if canonical_system_sha256(ligand_system) != authority.ligand_system_sha256:
        raise ResearchError('registered pose ligand source identity mismatch')
    source = ligand_system.coordinates
    if (source.dtype is not torch.float64 or source.device.type != 'cpu'
            or source.ndim != 3 or source.shape[0] != 1 or authority.ligand_model_index != 0):
        raise ResearchError('registered pose requires one CPU float64 coordinate model')
    if not 1 <= source.shape[1] <= 256 or source.shape[1] != authority.search_space.atom_count:
        raise ResearchError('registered pose atom count mismatch')
    xyz = source[0].detach().clone().contiguous()
    if coordinates_hex(xyz) != coordinates_hex(authority.validity_context.reference_coordinates):
        raise ResearchError('registered pose differs from authenticated reference coordinates')
    proposal = _bind(xyz, seed=budget.seed, problem=authority.problem.fingerprint_sha256,
                     search_space=authority.search_space.fingerprint_sha256)
    if coordinates_hex(proposal.coordinates) != coordinates_hex(source[0]):
        raise ResearchError('registered pose coordinates changed during binding')
    authority_binding = {k: v for k, v in authority.to_dict().items()
                         if k not in {'input_receipt_sha256', 'pocket', 'search_space_derivation'}}
    row = {'schema_id': REGISTERED_RECEIPT_SCHEMA, 'policy_id': REGISTERED_PROPOSAL_POLICY,
        'authority_binding': authority_binding,
        'source_ligand_system_sha256': authority.ligand_system_sha256,
        'authority_input_receipt_sha256': authority.input_receipt_sha256,
        'problem_fingerprint_sha256': authority.problem.fingerprint_sha256,
        'search_space_fingerprint_sha256': authority.search_space.fingerprint_sha256,
        'coordinate_frame_id': authority.pocket.coordinate_frame_id,
        'candidate_count': 1, 'top_k': 1, 'max_torsions': 0, 'translation_radius_angstrom': 0.0,
        'seed': budget.seed, 'proposal_index': 0, 'candidate_id': proposal.candidate_id,
        'coordinate_dtype': 'float64', 'initial_coordinates_binary64_hex': coordinates_hex(xyz),
        'initial_coordinate_fingerprint_sha256': proposal.coordinate_fingerprint_sha256,
        'proposal_fingerprint_sha256': proposal.fingerprint_sha256}
    receipt = RegisteredPoseReceipt(canonical({**row, 'receipt_sha256': digest(row)}))
    proposal.assert_integrity()
    authority.input_receipt_sha256
    if canonical_system_sha256(ligand_system) != authority.ligand_system_sha256:
        raise ResearchError('registered pose source changed during generation')
    return (proposal,), receipt
