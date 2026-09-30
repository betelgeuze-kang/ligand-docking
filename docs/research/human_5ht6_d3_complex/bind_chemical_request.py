"""Bind the separately derived receptor chemistry to an explicit CPU scorer run.

The original request and force parameters are retained. Only receptor chemical
annotations/lineage, its cross identity, and the explicit scorer identity change.
"""
from __future__ import annotations
import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time

import torch
from betelgeuze_engine_v2.molecular import canonical_system_sha256
from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json
from betelgeuze_product.reference_minimization_workflow import _bound
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import CrossParameters, FixedReceptorEnvironment, FIXED_REQUEST_SCHEMA
from betelgeuze_product.cpu_refinement_v1_2.workflow import load_request, REQUEST_SCHEMA
from betelgeuze_product.cpu_refinement_v1_2.provenance import source_manifest, digest
from betelgeuze_product.cpu_refinement_v1_2.chemical_features import derive_explicit_chemical_features, feature_model_document
from betelgeuze_product.cpu_refinement_v1_2.scoring_profile import EXPLICIT_REQUEST_SCHEMA, EXPLICIT_MODEL, scorer_class


def ref(path):
    return {'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, doc):
    with path.open('x') as stream:
        json.dump(doc,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')


def bind(source_request, packet, output):
    started=time.perf_counter()
    request=json.loads(source_request.read_bytes())
    if request['schema_id'] != FIXED_REQUEST_SCHEMA:
        raise ValueError('original fixed-receptor development request required')
    manifest=json.loads((packet/'manifest.v1.json').read_bytes())
    if manifest['schema_id'] != 'human_5ht6_7xtb_source_bound_receptor_chemical_graph_v1':
        raise ValueError('explicit receptor chemical graph packet required')
    for name, row in manifest['files'].items():
        path=packet/name
        if ref(path)['sha256']!=row['sha256'] or path.stat().st_size!=row['bytes']:
            raise ValueError('chemical graph packet changed')
    if manifest['parent_refs']['canonical']['sha256']!=request['receptor']['sha256']:
        raise ValueError('derived receptor parent does not match source request')
    old=all_atom_system_from_canonical_json(json.dumps(_bound(request['receptor'])))
    new=all_atom_system_from_canonical_json((packet/'receptor-canonical.json').read_bytes())
    if not torch.equal(old.coordinates,new.coordinates) or old.atom_count!=new.atom_count:
        raise ValueError('coordinate or atom coverage changed')
    for before,after in zip(old.atoms,new.atoms,strict=True):
        for name in ('index','name','element','atomic_number','residue_index','partial_charge_e','mass_da','stereo'):
            if getattr(before,name)!=getattr(after,name):
                raise ValueError('force-bearing atom field changed: '+name)
    if [(b.atom_i,b.atom_j) for b in old.bonds]!=[(b.atom_i,b.atom_j) for b in new.bonds]:
        raise ValueError('adjacency changed')
    new_hash=canonical_system_sha256(new)
    if new_hash!=manifest['receptor_system_sha256']:
        raise ValueError('new receptor identity mismatch')
    cross=CrossParameters.from_dict(_bound(request['cross_parameters']))
    FixedReceptorEnvironment(old,cross).assert_intact()
    cross=replace(cross,receptor_system_sha256=new_hash)
    features=derive_explicit_chemical_features(new)
    classes=Counter()
    for i in features.acceptors:
        atom=new.atoms[i];residue=new.residues[atom.residue_index]
        if atom.name=='N': classes['backbone_N']+=1
        if residue.name=='TRP' and atom.name=='NE1': classes['TRP_NE1']+=1
        if residue.name=='HIS' and atom.name=='NE2': classes['HIE_NE2']+=1
        if residue.name=='ARG' and atom.name in ('NE','NH1','NH2'): classes['ARG_sidechain_N']+=1
    if any(classes.values()):
        raise ValueError('known nonaccepting prepared nitrogens classified as acceptors')
    output.mkdir(parents=True,exist_ok=False)
    write(output/'cross-parameters.json',cross.to_dict())
    request={**request,'schema_id':EXPLICIT_REQUEST_SCHEMA,'receptor':ref(packet/'receptor-canonical.json'),
        'cross_parameters':ref(output/'cross-parameters.json')}
    # Exercise the exact authenticated scorer input contract before publication.
    implementation=digest(source_manifest())
    prepared={k:v for k,v in request.items() if k!='cross_parameters'};prepared['schema_id']=REQUEST_SCHEMA
    authority,receptor,ligand,parameters,*_=load_request(prepared,implementation)
    FixedReceptorEnvironment(receptor,cross).validate_ligand(ligand,parameters.base_parameters)
    scorer=scorer_class(EXPLICIT_MODEL)(authority,receptor,ligand,implementation_source_sha256=implementation)
    write(output/'request.json',request)
    report={'schema_id':'pr49_explicit_chemistry_request_binding/1.0.0',
        'original_request':ref(source_request),'request':ref(output/'request.json'),
        'receptor_chemical_manifest':ref(packet/'manifest.v1.json'),'parent_receptor_system_sha256':canonical_system_sha256(old),
        'derived_receptor_system_sha256':new_hash,'coordinates_atom_order_parameters_preserved':True,
        'feature_model':feature_model_document(),'receptor_complete_graph_features':{'donor_pairs':len(features.donors),
            'acceptors':len(features.acceptors),'hydrophobic':len(features.hydrophobic),
            'unexpected_acceptors_in_declared_backbone_ARG_TRP_HIE':dict(classes)},
        'authenticated_scorer_constructed':True,'scorer_context_sha256':scorer.context.fingerprint_sha256,
        'score_descriptor':scorer.score_descriptor.to_dict(),'budget_changed':False,'solver_changed':False,
        'convergence_or_strain_limits_changed':False,'partial_charge_sum':sum(a.partial_charge_e for a in new.atoms),
        'formal_charge_sum':sum(a.formal_charge for a in new.atoms),'preflight_wall_seconds':time.perf_counter()-started,
        'comparison_executed':False,'scientifically_validated':False,'product_qualified':False}
    write(output/'binding.json',report)
    return {'output':str(output),'authenticated_scorer_constructed':True,'feature_counts':report['receptor_complete_graph_features']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-request',required=True,type=Path)
    parser.add_argument('--receptor-packet',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(bind(args.source_request.resolve(),args.receptor_packet.resolve(),args.output.resolve()),sort_keys=True))
