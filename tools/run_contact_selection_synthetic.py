#!/usr/bin/env python3
"""Run fixed synthetic selection cases; labels are evaluation-only, not docking truth."""
import argparse
import hashlib
import sys
import importlib.util
from pathlib import Path
# Fixed neighboring source, never a caller-supplied module or executable.
_spec = importlib.util.spec_from_file_location('contact_selection', Path(__file__).with_name('compare_contact_diversity_selection.py'))
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
InputError, array, canonical, digest, fields, load_bytes, need, select, text = (
    getattr(_module, name) for name in ('InputError','array','canonical','digest','fields','load_bytes','need','select','text'))


def run(protocol):
    fields(protocol, ('schema','protocol_id','tuning','claims','cases'))
    need(protocol['schema']=='contact_selection_synthetic_protocol/1','protocol_schema')
    text(protocol['protocol_id']); text(protocol['tuning'])
    need(protocol['claims']=={'molecular_evaluation':False,'docking_accuracy':False},'protocol_claims')
    cases=array(protocol['cases'],128); need(bool(cases),'empty_protocol')
    results=[]; seen=set()
    for case in cases:
        fields(case,('case_id','selection_input','evaluation'))
        cid=text(case['case_id']); need(cid not in seen,'duplicate_case'); seen.add(cid)
        # Selection finishes before the separate evaluator is read.
        selection=select(case['selection_input'])
        fields(case['evaluation'],('target_candidate_ids',))
        targets=[text(x) for x in array(case['evaluation']['target_candidate_ids'],256)]
        need(bool(targets) and len(targets)==len(set(targets)),'evaluation_targets')
        need(set(targets)<=set(case['selection_input']['expected_candidate_ids']),'unknown_target')
        evaluated={name:{'status':arm['status'],'selected_ids':arm['selected_ids'],
                         'selected_count':arm['selected_count'],'unfilled_slots':arm['unfilled_slots'],
                         'target_retained': bool(set(targets)&set(arm['selected_ids'])) if arm['status']=='observed' else None}
                   for name,arm in selection['arms'].items()}
        results.append({'case_id':cid,'selection_input_sha256':selection['input_canonical_sha256'],
                        'selection_report_sha256':hashlib.sha256(canonical(selection).encode('ascii')).hexdigest(),
                        'comparison_status':selection['comparison_status'],'arms':evaluated})
    summary={}
    for name in ('energy_only','energy_rmsd','energy_rmsd_contact'):
        rows=[r['arms'][name] for r in results]
        summary[name]={'expected_cases':len(cases),'observed_cases':sum(r['status']=='observed' for r in rows),
                       'unknown_cases':sum(r['status']=='unknown' for r in rows),
                       'target_retained_cases':sum(r['target_retained'] is True for r in rows),
                       'target_not_retained_cases':sum(r['target_retained'] is False for r in rows),
                       'underfilled_cases':sum(r['unfilled_slots']>0 for r in rows)}
    return {'schema':'contact_selection_synthetic_report/1','protocol_id':protocol['protocol_id'],
            'protocol_canonical_sha256':hashlib.sha256(canonical(protocol).encode('ascii')).hexdigest(),
            'cases':results,'summary':summary,'claims':{'molecular_evaluations':0,'docking_accuracy':False,
            'hand_constructed_case_frequency_is_performance_estimate':False,'reference_labels_used_by_selector':False}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('protocol'); parser.add_argument('--expected-sha256',required=True)
    args=parser.parse_args(argv)
    try:
        digest(args.expected_sha256)
        with open(args.protocol,'rb') as stream: raw=stream.read(4*1024*1024+1)
        need(hashlib.sha256(raw).hexdigest()==args.expected_sha256,'protocol_digest_mismatch')
        result=run(load_bytes(raw)); result['protocol_bytes_sha256']=args.expected_sha256
        output=canonical(result)+'\n'; need(len(output.encode('ascii'))<=4*1024*1024,'output_budget')
        sys.stdout.write(output); return 0
    except (InputError,OSError,ValueError,OverflowError,RecursionError):
        sys.stderr.write('synthetic contact experiment rejected: invalid, inaccessible, or over budget\n'); return 2


if __name__=='__main__':
    raise SystemExit(main())
