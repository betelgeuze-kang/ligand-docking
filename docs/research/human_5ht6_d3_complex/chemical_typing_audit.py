"""Read-only source-bound receptor chemistry audit; no scorer execution or repair.

Uses the original OpenMM 8.4 environment to match the pinned receptor templates.
Output is a new external receipt, never a replacement preparation or admission.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import sys
import time

BASE = Path('/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs')
PACKET = BASE / 'engine-v2-pr49-d3-complex-20260929-final2'
RECEPTOR = BASE / 'engine-v2-7xtb-openmm-projection-20260929'
PACKET_MANIFEST_SHA = '95128a77c3dd416371371966b9d7cbd2ca22dbfbff4499cce70bd14d6899af33'
RECEPTOR_MANIFEST_SHA = 'a761368e162a3ce5b502702d9ba689451386e0dd424619da371df8e4d0a16f12'


def ref(path):
    path = path.resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}


def pinned_json(path, expected):
    if ref(path)['sha256'] != expected:
        raise ValueError('PINNED_MANIFEST_HASH_MISMATCH')
    return json.loads(path.read_text())


def audit(packet=PACKET, receptor_root=RECEPTOR):
    import openmm
    from openmm import app
    from betelgeuze_engine_v2.molecular import serialization
    from betelgeuze_engine_v2.docking import scorer_v1
    start = time.perf_counter()
    manifest = pinned_json(packet/'manifest.v1.json', PACKET_MANIFEST_SHA)
    source = pinned_json(receptor_root/'manifest.v1.json', RECEPTOR_MANIFEST_SHA)
    canonical = packet/'receptor-canonical.json'
    if ref(canonical)['sha256'] != manifest['files']['receptor-canonical.json']['sha256']:
        raise ValueError('CANONICAL_RECEPTOR_HASH_MISMATCH')
    for name, identity in source['files'].items():
        observed = ref(receptor_root/name)
        if observed['sha256'] != identity['sha256'] or observed['bytes'] != identity['bytes']:
            raise ValueError('ORIGINAL_RECEPTOR_ARTIFACT_CHANGED:'+name)
    system = serialization.all_atom_system_from_canonical_json(canonical.read_bytes())
    if serialization.canonical_system_sha256(system) != manifest['receptor_system_sha256']:
        raise ValueError('CANONICAL_SEMANTIC_HASH_MISMATCH')
    forcefield_data = Path(app.__file__).parent/'data'
    forcefield_sources = {}
    for name, expected in source['method']['forcefield_source_sha256'].items():
        observed = ref(forcefield_data/name)
        if observed['sha256'] != expected:
            raise ValueError('ORIGINAL_FORCEFIELD_SOURCE_CHANGED:'+name)
        forcefield_sources[name] = observed
    pdb = app.PDBFile(str(receptor_root/'receptor-prepared.pdb'))
    templates = app.ForceField('amber14-all.xml').getMatchingTemplates(pdb.topology)
    residues = list(pdb.topology.residues())
    if len(residues) != len(templates) or len(residues) != len(system.residues):
        raise ValueError('TEMPLATE_RESIDUE_COVERAGE_MISMATCH')
    residue_partial = defaultdict(Decimal)
    for atom in system.atoms:
        printed = atom.metadata['prepared_gromacs_source']['source_row']['tokens'][6]
        residue_partial[atom.residue_index] += Decimal(printed)
    template_rows = []
    for index, (residue, template) in enumerate(zip(residues, templates)):
        canonical_residue = system.residues[index]
        if residue.id != str(canonical_residue.sequence_number) or residue.name != canonical_residue.name:
            raise ValueError('TEMPLATE_CANONICAL_RESIDUE_ORDER_CHANGED')
        template_rows.append({'residue_index': index, 'chain': residue.chain.id, 'residue_number': residue.id,
            'residue_name': residue.name, 'matched_template': template.name,
            'printed_itp_partial_charge_sum_e': str(residue_partial[index]),
            'formal_charge_sum_e': sum(system.atoms[i].formal_charge for i in canonical_residue.atom_indices)})
    donors, acceptors, hydrophobic = scorer_v1._features(system, set(range(system.atom_count)))
    suspect = Counter()
    for index in acceptors:
        atom = system.atoms[index]
        residue = system.residues[atom.residue_index]
        if atom.name == 'N':
            suspect['backbone_N'] += 1
        if residue.name == 'TRP' and atom.name == 'NE1':
            suspect['TRP_NE1'] += 1
        if residue.name == 'HIS' and atom.name == 'NE2':
            suspect['HIE_NE2'] += 1
    partial = [float(atom.partial_charge_e) for atom in system.atoms]
    report = {
        'schema_version': 'pr49_7xtb_receptor_chemical_typing_blocker_audit_v1',
        'status': 'BLOCKED_COMPLETE_SOURCE_BOUND_RECEPTOR_CHEMICAL_GRAPH_REQUIRED',
        'source_refs': {'packet_manifest': ref(packet/'manifest.v1.json'), 'receptor_manifest': ref(receptor_root/'manifest.v1.json'),
            'receptor_canonical': ref(canonical), 'receptor_openmm_xml': ref(receptor_root/'openmm-system.xml'),
            'receptor_pdb': ref(receptor_root/'receptor-prepared.pdb'), 'scorer_source': ref(Path(scorer_v1.__file__)),
            'audit_source': ref(Path(__file__))},
        'canonical_receptor_system_sha256': serialization.canonical_system_sha256(system),
        'forcefield_sources_all_match_pinned_preparation': True, 'forcefield_source_refs': forcefield_sources,
        'atoms': system.atom_count, 'residues': len(residues), 'templates_matched': len(templates),
        'template_counts': dict(sorted(Counter(template.name for template in templates).items())),
        'residue_name_counts': dict(sorted(Counter(residue.name for residue in residues).items())),
        'residue_template_and_charge_rows': template_rows,
        'charged_residue_rows': [row for row in template_rows if abs(Decimal(row['printed_itp_partial_charge_sum_e'])) > Decimal('0.01')],
        'formal_charge_annotation_status_counts': dict(Counter(atom.metadata['prepared_gromacs_source']['formal_charge_annotation_status'] for atom in system.atoms)),
        'partial_charge_ordered_float_sum_e': sum(partial), 'partial_charge_fsum_e': math.fsum(partial),
        'printed_itp_decimal_partial_charge_sum_e': str(sum(residue_partial.values())),
        'formal_charge_sum_e': sum(atom.formal_charge for atom in system.atoms),
        'expected_declared_microstate_net_charge_e': 14+4-6-1+2-2,
        'expected_charge_accounting': {'ARG_positive':14, 'LYS_positive':4, 'ASP_negative':6,
            'GLU_negative':1, 'N_termini_positive':2, 'C_termini_negative':2},
        'bonds': len(system.bonds), 'bond_order_counts': dict(Counter(str(bond.order) for bond in system.bonds)),
        'aromatic_atoms': sum(atom.aromatic for atom in system.atoms), 'aromatic_bonds': sum(bond.aromatic for bond in system.bonds),
        'feature_function_diagnostic': {'scope': 'private feature helper with all receptor atoms; no authenticated scorer or comparison executed',
            'donor_pairs': len(donors), 'acceptors': len(acceptors), 'hydrophobic_atoms': len(hydrophobic),
            'acceptor_classes_requiring_chemical_review': dict(suspect)},
        'interpretation': 'Formal-only patch not sufficient. AMBER templates provide partial charges and adjacency, while canonical bond orders and aromatic flags remain absent. Derive a separate source-bound chemical graph and verify scorer typing before whole-product comparison.',
        'required_work': ['reviewed residue and terminal chemical graph with complete atom map, bond order, aromaticity and formal charge',
            'preserve coordinates, partial charges, masses and LJ; bind parent canonical hash and chemical source/version',
            'verify per-residue valence and charge, HIE/CYX, termini, peptide carbonyl and guanidinium donor/acceptor semantics',
            'keep direct explicit-parameter D3 numerical evidence separate from ScorerV1 or biological accuracy'],
        'prohibited_shortcuts': ['put +11 formal charge on one atom', 'relax charge-conservation criterion', 'silently change AMBER partial charges', 'claim full chemical typing after correcting only the total'],
        'scope': {'product_code_modified':False, 'prepared_sources_modified':False, 'scorer_or_whole_comparison_executed':False,
            'chemical_typing_repaired':False, 'protected_outcomes_read':False, 'fit_calibration_evaluation_roles_assigned':False},
        'runtime': {'python':sys.version, 'openmm':openmm.version.version, 'audit_wall_seconds':time.perf_counter()-start}}
    if not (report['atoms']==4376 and report['templates_matched']==278 and report['bonds']==4431
            and report['bond_order_counts']=={'1.0':4431} and report['formal_charge_sum_e']==0
            and report['aromatic_atoms']==report['aromatic_bonds']==0
            and Decimal(report['printed_itp_decimal_partial_charge_sum_e'])==11
            and dict(suspect)=={'backbone_N':278,'TRP_NE1':7,'HIE_NE2':2}):
        raise ValueError('PINNED_CHEMICAL_TYPING_BLOCKER_OBSERVATION_CHANGED')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    with args.output.open('xb') as stream:
        stream.write(raw)
    print(json.dumps({'output':str(args.output.resolve()), 'sha256':hashlib.sha256(raw).hexdigest(),
                      'status':result['status'], 'atom_count':result['atoms']}, sort_keys=True))
