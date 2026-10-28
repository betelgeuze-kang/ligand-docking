#!/usr/bin/env python3
"""Compare fixed-cohort selection policies using supplied evidence, not an engine."""
import argparse
import hashlib
import json
import math
import re
import sys

MAX_BYTES = 4 * 1024 * 1024
MAX_OUTPUT = 4 * 1024 * 1024
MAX_CANDIDATES = 256
MAX_RESIDUES = 10000
MAX_CONTACT_IDS = 100000


class InputError(ValueError):
    """Safe fixed-code input failure."""


def need(ok, message):
    if not ok:
        raise InputError(message)


def fields(value, required, optional=()):
    need(type(value) is dict and not (set(value)-set(required)-set(optional))
         and set(required) <= set(value), 'invalid_fields')


def text(value):
    need(type(value) is str and 0 < len(value) <= 128 and
         all(ord(c) >= 32 and not 0xD800 <= ord(c) <= 0xDFFF for c in value), 'invalid_identifier')
    return value


def digest(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None, 'invalid_digest')
    return value


def number(value, low=-1e100, high=1e100):
    need(type(value) in (int, float), 'invalid_number')
    need(low <= value <= high, 'number_out_of_range')
    return float(value)


def integer(value, low, high):
    need(type(value) is int and low <= value <= high, 'invalid_integer')
    return value


def array(value, maximum):
    need(type(value) is list and len(value) <= maximum, 'array_budget_or_type')
    return value


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise InputError('noncanonical_value') from None


def sha(value):
    return hashlib.sha256(canonical(value).encode('ascii')).hexdigest()


def pairs(items):
    result = {}
    for k, v in items:
        need(k not in result, 'duplicate_json_key')
        result[k] = v
    return result


def load_bytes(raw):
    need(type(raw) is bytes and len(raw) <= MAX_BYTES, 'input_byte_budget')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(InputError('nonfinite_json')))
    except (UnicodeError, ValueError, RecursionError):
        raise InputError('invalid_json') from None
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        need(depth <= 24, 'depth_budget')
        if isinstance(item, dict):
            stack.extend((v, depth+1) for v in item.values())
        elif isinstance(item, list):
            stack.extend((v, depth+1) for v in item)
    return value


def validate(data):
    fields(data, ('schema', 'context', 'score_descriptor', 'policy', 'expected_candidate_ids',
                  'candidates', 'rmsd', 'contact_report', 'contact_report_sha256', 'contact_bindings'))
    need(data['schema'] == 'contact_selection_input/1', 'schema')
    ctx = data['context']
    fields(ctx, ('chemical_state', 'frame', 'atom_mapping_sha256', 'receptor_sha256'))
    text(ctx['chemical_state']); text(ctx['frame'])
    digest(ctx['atom_mapping_sha256']); digest(ctx['receptor_sha256'])
    score = data['score_descriptor']
    fields(score, ('model', 'units', 'direction'))
    text(score['model']); text(score['units'])
    need(score['direction'] in ('minimize', 'maximize'), 'score_direction')
    policy = data['policy']
    fields(policy, ('id', 'source', 'top_k', 'rmsd_min_angstrom', 'contact_distance_min'))
    text(policy['id']); text(policy['source'])
    integer(policy['top_k'], 1, MAX_CANDIDATES)
    number(policy['rmsd_min_angstrom'], 0, 1000)
    number(policy['contact_distance_min'], 0, 1)
    expected = [text(x) for x in array(data['expected_candidate_ids'], MAX_CANDIDATES)]
    need(len(expected) == len(set(expected)), 'duplicate_expected_candidate')
    candidates = {}
    for row in array(data['candidates'], MAX_CANDIDATES):
        fields(row, ('candidate_id', 'status'), ('score', 'proposal_index', 'variant', 'coordinates_sha256',
                                               'selection_eligible', 'pose_valid', 'validity_complete'))
        cid = text(row['candidate_id'])
        need(cid in expected and cid not in candidates, 'candidate_identity')
        need(row['status'] in ('eligible', 'ineligible', 'failed', 'unknown'), 'candidate_status')
        if row['status'] == 'eligible':
            need(set(row) == {'candidate_id', 'status', 'score', 'proposal_index', 'variant', 'coordinates_sha256',
                              'selection_eligible', 'pose_valid', 'validity_complete'}, 'eligible_fields')
            need(all(row[x] is True for x in ('selection_eligible', 'pose_valid', 'validity_complete')), 'admission_not_true')
            number(row['score']); integer(row['proposal_index'], 0, 1000000)
            need(row['variant'] in ('baseline', 'refined'), 'variant')
            digest(row['coordinates_sha256'])
        else:
            need(set(row) == {'candidate_id', 'status'}, 'noneligible_fields')
        candidates[cid] = row
    eligible = [r for r in candidates.values() if r['status'] == 'eligible']
    sign = 1 if score['direction'] == 'minimize' else -1
    eligible.sort(key=lambda r: (sign*r['score'], r['proposal_index'], r['candidate_id'], r['variant']))
    ids = {r['candidate_id'] for r in eligible}
    rmsd = data['rmsd']
    fields(rmsd, ('metric', 'frame', 'atom_mapping_sha256', 'pairs'))
    need(rmsd['metric'] == 'direct_rmsd_in_receptor_frame' and rmsd['frame'] == ctx['frame']
         and rmsd['atom_mapping_sha256'] == ctx['atom_mapping_sha256'], 'rmsd_context')
    distances = {}
    for row in array(rmsd['pairs'], 32640):
        fields(row, ('left', 'right', 'left_coordinates_sha256', 'right_coordinates_sha256', 'distance_angstrom'))
        a, b = text(row['left']), text(row['right'])
        need(a in ids and b in ids and a != b, 'rmsd_candidate')
        key = tuple(sorted((a, b)))
        need(key not in distances, 'duplicate_rmsd_pair')
        need(row['left_coordinates_sha256'] == candidates[a]['coordinates_sha256'] and
             row['right_coordinates_sha256'] == candidates[b]['coordinates_sha256'], 'rmsd_geometry_binding')
        d = number(row['distance_angstrom'], 0, 1e10)
        if candidates[a]['coordinates_sha256'] == candidates[b]['coordinates_sha256']:
            need(d == 0, 'duplicate_geometry_nonzero_rmsd')
        distances[key] = d
    report = data['contact_report']
    need(type(report) is dict, 'contact_report_type')
    need(sha(report) == digest(data['contact_report_sha256']), 'contact_report_digest')
    required = {'schema_version', 'input_sha256', 'coordinate_frame', 'units', 'settings', 'residues', 'poses'}
    need(required <= set(report), 'contact_report_fields')
    need(report['schema_version'] == 'residue_contacts_output.v1' and report['coordinate_frame'] == ctx['frame']
         and report['units'] == 'angstrom', 'contact_context')
    digest(report['input_sha256'])
    settings = report['settings']
    need(type(settings) is dict and {'cutoff', 'bin_edges', 'all_supplied_atoms', 'periodic', 'alignment'} <= set(settings), 'contact_settings')
    number(settings['cutoff'], 0, 1e100)
    edges = [number(x, 0, 1e100) for x in array(settings['bin_edges'], 32)]
    need(bool(edges) and all(a < b for a,b in zip(edges,edges[1:])), 'contact_bins')
    need(settings['all_supplied_atoms'] is True and settings['periodic'] is False and settings['alignment'] is False, 'contact_semantics')
    residues = set()
    for row in array(report['residues'], MAX_RESIDUES):
        need(type(row) is dict and 'residue_id' in row, 'residue_fields')
        rid = text(row['residue_id']); need(rid not in residues, 'duplicate_residue'); residues.add(rid)
    poses = {}; contact_total = 0
    for row in array(report['poses'], 1000):
        need(type(row) is dict and {'pose_id', 'fingerprint_state', 'contact_residue_ids', 'contact_count', 'geometry_state'} <= set(row), 'contact_pose_fields')
        pid = text(row['pose_id']); need(pid not in poses, 'duplicate_contact_pose')
        state = row['fingerprint_state']
        need(state in ('complete', 'unavailable'), 'contact_state')
        need(row['geometry_state'] in ('observed', 'missing', 'null', 'empty'), 'geometry_state')
        if state == 'complete':
            need(row['geometry_state'] == 'observed', 'complete_fingerprint_without_observed_geometry')
            contacts = [text(x) for x in array(row['contact_residue_ids'], MAX_RESIDUES)]
            need(len(contacts) == len(set(contacts)) and set(contacts) <= residues, 'contact_residue_identity')
            need(type(row['contact_count']) is int and row['contact_count'] == len(contacts), 'contact_count')
            poses[pid] = frozenset(contacts); contact_total += len(contacts)
        else:
            need(row['contact_residue_ids'] is None and row['contact_count'] is None, 'unavailable_not_null')
            poses[pid] = None
    need(contact_total <= MAX_CONTACT_IDS, 'contact_budget')
    contacts = {}; used_poses = set(); by_geometry = {}
    for row in array(data['contact_bindings'], MAX_CANDIDATES):
        fields(row, ('candidate_id', 'pose_id', 'coordinates_sha256'))
        cid, pid = text(row['candidate_id']), text(row['pose_id'])
        need(cid in ids and cid not in contacts and pid in poses and pid not in used_poses, 'contact_binding_identity')
        need(row['coordinates_sha256'] == candidates[cid]['coordinates_sha256'], 'contact_geometry_binding')
        contacts[cid] = poses[pid]; used_poses.add(pid)
        h = row['coordinates_sha256']
        if h in by_geometry and by_geometry[h] is not None and poses[pid] is not None:
            need(by_geometry[h] == poses[pid], 'duplicate_geometry_conflicting_contacts')
        if poses[pid] is not None:
            by_geometry[h] = poses[pid]
    missing_candidates = sorted(set(expected)-set(candidates))
    unknown_candidates = sorted(k for k,v in candidates.items() if v['status'] == 'unknown')
    return eligible, distances, contacts, missing_candidates, unknown_candidates


def select(data):
    """No evaluator labels accepted; all metrics and admissions are supplied evidence."""
    eligible, distances, contacts, missing, unknown = validate(data)
    ids = [r['candidate_id'] for r in eligible]
    pair_complete = len(distances) == len(ids)*(len(ids)-1)//2
    contact_complete = all(cid in contacts and contacts[cid] is not None for cid in ids)
    policy = data['policy']; k = policy['top_k']; arms = {}
    for name in ('energy_only', 'energy_rmsd', 'energy_rmsd_contact'):
        selected = []; selected_hashes = set(); decisions = []
        unavailable = (name != 'energy_only' and not pair_complete) or (name == 'energy_rmsd_contact' and not contact_complete)
        uncertain = bool(missing or unknown or unavailable)
        for row in eligible:
            cid = row['candidate_id']
            if unavailable:
                reason = 'arm_evidence_incomplete'
            elif row['coordinates_sha256'] in selected_hashes:
                reason = 'duplicate_coordinates'
            elif name != 'energy_only' and any(distances[tuple(sorted((cid, old)))] < policy['rmsd_min_angstrom'] for old in selected):
                reason = 'within_diversity_distance'
            elif len(selected) >= k:
                reason = 'outside_top_k'
            elif name == 'energy_rmsd_contact':
                pair_contacts = [(contacts[cid], contacts[old]) for old in selected]
                if any(not (a | b) for a,b in pair_contacts):
                    reason = 'contact_comparison_unknown_empty_union'; uncertain = True
                elif any(1-len(a & b)/len(a | b) < policy['contact_distance_min'] for a,b in pair_contacts):
                    reason = 'within_contact_diversity_distance'
                else:
                    reason = 'selected'
            else:
                reason = 'selected'
            if reason == 'selected':
                selected.append(cid); selected_hashes.add(row['coordinates_sha256'])
            decisions.append({'candidate_id':cid, 'reason':reason})
        arms[name] = {'status':'unknown' if uncertain else 'observed', 'selected_ids':selected,
                      'selected_count':len(selected), 'requested_capacity':k, 'unfilled_slots':k-len(selected),
                      'admissible_candidate_ids':ids, 'decisions':decisions}
    counts = {s: sum(r['status']==s for r in data['candidates']) for s in ('eligible','ineligible','failed','unknown')}
    counts.update(expected=len(data['expected_candidate_ids']), supplied=len(data['candidates']), missing=len(missing))
    return {'schema':'contact_selection_report/1', 'input_canonical_sha256':sha(data), 'policy_sha256':sha(policy),
            'context_sha256':sha(data['context']), 'contact_report_sha256':data['contact_report_sha256'],
            'candidate_counts':counts, 'missing_candidate_ids':missing, 'unknown_candidate_ids':unknown,
            'pair_evidence_complete':pair_complete, 'contact_evidence_complete':contact_complete,
            'comparison_status':'observed' if ids and all(a['status']=='observed' for a in arms.values()) else 'unknown',
            'arms':arms, 'claims':{'actual_engine_evaluations':0, 'scientific_validation':False,
              'producer_authenticity_verified':False, 'rmsd_recomputed':False, 'upstream_admission_recomputed':False,
              'chemical_interactions':False, 'whole_selector_integration_equivalence':False, 'receptor_identity_independently_verified':False,
              'contact_geometry_recomputed':False, 'full_contact_report_validated':False}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input'); parser.add_argument('--expected-sha256',required=True)
    args=parser.parse_args(argv)
    try:
        digest(args.expected_sha256)
        with open(args.input,'rb') as stream: raw=stream.read(MAX_BYTES+1)
        need(hashlib.sha256(raw).hexdigest()==args.expected_sha256,'input_digest_mismatch')
        result=select(load_bytes(raw)); result['input_bytes_sha256']=args.expected_sha256
        out=canonical(result)+'\n'; need(len(out.encode('ascii'))<=MAX_OUTPUT,'output_budget')
        sys.stdout.write(out); return 0
    except (InputError,OSError,ValueError,OverflowError,RecursionError):
        sys.stderr.write('contact selection rejected: invalid, inaccessible, or over budget\n'); return 2


if __name__=='__main__':
    raise SystemExit(main())
