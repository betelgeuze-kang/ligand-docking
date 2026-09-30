"""Portable registered-input policy checks, without claiming source authenticity."""
from .evidence_contracts import same
from .registered_pose import require_registered_receipt


def verify_registered_evidence(document, *, atom_count, authority, seed, rows, attempts,
                               coordinate_frame, receptor_system_sha256, problem=None, search_space=None):
    receipt = require_registered_receipt(document)
    same(len(receipt['initial_coordinates_binary64_hex']), atom_count, 'registered atom count')
    same(receipt['authority_input_receipt_sha256'], authority, 'registered authority')
    same(receipt['seed'], seed, 'registered seed')
    same(receipt['coordinate_frame_id'], coordinate_frame, 'registered coordinate frame')
    same(receipt['authority_binding']['receptor_system_sha256'], receptor_system_sha256,
         'registered receptor identity')
    if problem is not None:
        same(receipt['problem_fingerprint_sha256'], problem, 'registered problem')
    if search_space is not None:
        same(receipt['search_space_fingerprint_sha256'], search_space, 'registered search space')
    for name in ('baseline', 'refined'):
        same(len(rows[name]), 1, 'registered candidate denominator')
        row = rows[name][0]
        for key in ('candidate_id', 'proposal_index', 'proposal_fingerprint_sha256',
                    'problem_fingerprint_sha256', 'search_space_fingerprint_sha256'):
            same(row[key], receipt[key], 'registered candidate identity')
        same(row['validity_context_fingerprint_sha256'],
             receipt['authority_binding']['validity_context_fingerprint_sha256'],
             'registered validity identity')
        if name == 'baseline' and row['succeeded']:
            same(row['coordinates_binary64_hex'], receipt['initial_coordinates_binary64_hex'],
                 'registered initial coordinates')
            same(row['coordinates_sha256'], receipt['initial_coordinate_fingerprint_sha256'],
                 'registered initial coordinate identity')
            same(row['result_proposal_fingerprint_sha256'], receipt['proposal_fingerprint_sha256'],
                 'registered baseline result identity')
    same(len(attempts), 1, 'registered refinement denominator')
    attempt = attempts[0]
    for field, expected in (
        ('candidate_id', receipt['candidate_id']),
        ('proposal_index', 0),
        ('source_proposal_fingerprint_sha256', receipt['proposal_fingerprint_sha256']),
        ('pre_coordinates_binary64_hex', receipt['initial_coordinates_binary64_hex']),
        ('pre_coordinates_sha256', receipt['initial_coordinate_fingerprint_sha256']),
    ):
        same(attempt[field], expected, 'registered refinement input')
    return receipt
