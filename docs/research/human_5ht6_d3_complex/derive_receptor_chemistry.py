"""Derive a new 7XTB receptor chemical state without changing its preparation.

Run with the pinned external OpenMM/OpenFF environment. All generated artifacts
are written exclusively to a new directory on the external data volume.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

from tools.product.receptor_chemical_graph import derive_receptor_chemical_graph, digest, json_bytes

BASE = Path('/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs')
PACKET = BASE / 'engine-v2-pr49-d3-complex-20260929-final2'
RECEPTOR = BASE / 'engine-v2-7xtb-openmm-projection-20260929'
CIF = BASE / 'engine-v2-7xtb-source-observation-20260929T031420Z/7XTB.cif'
PACKET_MANIFEST_SHA = '95128a77c3dd416371371966b9d7cbd2ca22dbfbff4499cce70bd14d6899af33'
RECEPTOR_MANIFEST_SHA = 'a761368e162a3ce5b502702d9ba689451386e0dd424619da371df8e4d0a16f12'


def ref(path):
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'sha256': digest(raw), 'bytes': len(raw)}


def checked_json(path, sha256):
    raw = path.read_bytes()
    if digest(raw) != sha256:
        raise ValueError('PINNED_SOURCE_CHANGED:' + str(path))
    return json.loads(raw)


def validate_rdkit(canonical_bytes):
    """Independently sanitize an index-preserving copy; never rewrite source."""
    from rdkit import Chem, rdBase
    topology = json.loads(canonical_bytes)['system']['topology']
    molecule = Chem.RWMol()
    for row in topology['atoms']:
        atom = Chem.Atom(row['atomic_number'])
        atom.SetFormalCharge(row['formal_charge'])
        atom.SetIsAromatic(row['aromatic'])
        atom.SetNoImplicit(True)
        if molecule.AddAtom(atom) != row['index']:
            raise ValueError('RDKIT_ATOM_ORDER_CHANGED')
    for row in topology['bonds']:
        order = float.fromhex(row['order']['$float_hex'])
        molecule.AddBond(row['atom_i'], row['atom_j'], {1: Chem.BondType.SINGLE, 2: Chem.BondType.DOUBLE, 3: Chem.BondType.TRIPLE}[order])
        molecule.GetBondBetweenAtoms(row['atom_i'], row['atom_j']).SetIsAromatic(row['aromatic'])
    graph = molecule.GetMol()
    Chem.SanitizeMol(graph)
    if graph.GetNumAtoms() != len(topology['atoms']) or graph.GetNumBonds() != len(topology['bonds']):
        raise ValueError('RDKIT_GRAPH_SIZE_CHANGED')
    for row, atom in zip(topology['atoms'], graph.GetAtoms()):
        if (atom.GetAtomicNum(), atom.GetFormalCharge(), atom.GetIsAromatic(), atom.GetNumImplicitHs()) != (row['atomic_number'], row['formal_charge'], row['aromatic'], 0):
            raise ValueError('RDKIT_CHEMICAL_ANNOTATION_DISAGREEMENT:' + str(row['index']))
    return {'rdkit_version': rdBase.rdkitVersion, 'all_atom_sanitize': 'PASS', 'implicit_hydrogens': 0,
            'ring_count': graph.GetRingInfo().NumRings(), 'source_coordinates_or_stereo_modified': False}


def derive(output):
    import openmm
    from openmm import app
    from betelgeuze_engine_v2.molecular.serialization import all_atom_system_from_canonical_json, canonical_system_json_bytes
    from tools.product import receptor_chemical_graph as implementation
    output = output.resolve()
    if not output.is_relative_to(BASE.resolve()):
        raise ValueError('EXTERNAL_VOLUME_NEW_PACKET_REQUIRED')
    if output.exists():
        raise FileExistsError('NEW_OUTPUT_DIRECTORY_REQUIRED:' + str(output))
    packet = checked_json(PACKET / 'manifest.v1.json', PACKET_MANIFEST_SHA)
    preparation = checked_json(RECEPTOR / 'manifest.v1.json', RECEPTOR_MANIFEST_SHA)
    input_refs = {'packet_manifest': ref(PACKET / 'manifest.v1.json'), 'preparation_manifest': ref(RECEPTOR / 'manifest.v1.json')}
    for name, expected in preparation['files'].items():
        observed = ref(RECEPTOR / name)
        if (observed['sha256'], observed['bytes']) != (expected['sha256'], expected['bytes']):
            raise ValueError('PREPARATION_SOURCE_CHANGED:' + name)
        input_refs['preparation/' + name] = observed
    canonical = (PACKET / 'receptor-canonical.json').read_bytes()
    cif = CIF.read_bytes()
    if digest(canonical) != packet['files']['receptor-canonical.json']['sha256'] or digest(cif) != preparation['source']['cif_sha256']:
        raise ValueError('CANONICAL_OR_CIF_SOURCE_CHANGED')
    ff_data = Path(app.__file__).parent / 'data'
    for name, sha in preparation['method']['forcefield_source_sha256'].items():
        observed = ref(ff_data / name)
        if observed['sha256'] != sha:
            raise ValueError('PINNED_FORCEFIELD_CHANGED:' + name)
        input_refs['forcefield/' + name] = observed
    forcefield = (ff_data / 'amber14/protein.ff14SB.xml').read_bytes()
    topology = json.loads(canonical)['system']['topology']
    residues = topology['residues']
    pdb = app.PDBFile(str(RECEPTOR / 'receptor-prepared.pdb'))
    matches = app.ForceField('amber14-all.xml').getMatchingTemplates(pdb.topology)
    pdb_residues = list(pdb.topology.residues())
    if len(matches) != len(residues) or len(residues) != 278:
        raise ValueError('RESIDUE_TEMPLATE_COVERAGE')
    assignments, index_by_identity = [], {}
    for residue, pdb_residue, match in zip(residues, pdb_residues, matches):
        chain = topology['chains'][residue['chain_index']]['chain_id']
        if (chain, str(residue['sequence_number']), residue['name']) != (pdb_residue.chain.id, pdb_residue.id, pdb_residue.name):
            raise ValueError('PREPARED_CANONICAL_RESIDUE_ORDER_CHANGED')
        identity = chain + ':' + str(residue['sequence_number'])
        index_by_identity[identity] = residue['index']
        declared = residue['name']
        if declared == 'HIS':
            declared = preparation['method']['histidine_requested_variants'].get(identity)
            if declared != 'HIE':
                raise ValueError('UNDECLARED_HISTIDINE_MICROSTATE')
        if identity in ('A:99', 'A:180'):
            if declared != 'CYS':
                raise ValueError('DECLARED_DISULFIDE_RESIDUE_MISMATCH')
            declared = 'CYX'
        if identity in ('A:26', 'B:263'):
            declared = 'N' + declared
        if identity in ('A:227', 'B:338'):
            declared = 'C' + declared
        if match.name != declared:
            raise ValueError('DECLARED_MATCHED_AMBER_TEMPLATE_MISMATCH:' + identity)
        aliases = {'H': 'H1'} if declared in ('NSER', 'NALA') else {}
        assignments.append({'residue_index': residue['index'], 'amber_template': declared, 'atom_name_map': aliases})
    if preparation['method']['disulfide'] != 'Cys99-Cys180 inferred by OpenMM from source SG geometry' or preparation['method']['termini'] != 'standard charged AMBER N/C termini at A26/A227 and B263/B338':
        raise ValueError('PREPARATION_MICROSTATE_DECLARATION_CHANGED')
    derived, receipt = derive_receptor_chemical_graph(canonical, cif_bytes=cif, forcefield_xml_bytes=forcefield,
        assignments=assignments, disulfide_residue_pairs=[(index_by_identity['A:99'], index_by_identity['A:180'])],
        expected_source_hashes={'canonical': digest(canonical), 'cif': preparation['source']['cif_sha256'],
                               'forcefield': preparation['method']['forcefield_source_sha256']['amber14/protein.ff14SB.xml']},
        expected_net_charge=11)
    # This independent comparison verifies declared integer charges; it never
    # selects a microstate or locates formal charge using printed partial charge.
    for row in receipt['chemical_graph']['residue_microstates']:
        residue = residues[row['residue_index']]
        partial = sum(Decimal(topology['atoms'][i]['metadata']['prepared_gromacs_source']['source_row']['tokens'][6]) for i in residue['atom_indices'])
        if partial != Decimal(row['formal_charge']):
            raise ValueError('DECLARED_RESIDUE_CHARGE_VS_EXACT_AMBER_PRINTED_SUM_MISMATCH')
    decoded = all_atom_system_from_canonical_json(derived)
    if canonical_system_json_bytes(decoded) != derived:
        raise ValueError('DERIVED_CANONICAL_ROUND_TRIP_MISMATCH')
    independent = validate_rdkit(derived)
    input_refs['canonical'] = ref(PACKET / 'receptor-canonical.json')
    input_refs['cif'] = ref(CIF)
    for source in input_refs.values():
        if ref(Path(source['path'])) != source:
            raise ValueError('SOURCE_CHANGED_DURING_DERIVATION')
    receipt['independent_validation'] = independent
    receipt['exact_printed_AMBER_residue_partial_charge_sums_match_declared_integers'] = True
    receipt['source_refs'] = input_refs
    receipt['runtime'] = {'python': sys.version, 'openmm': openmm.version.version}
    files = {'receptor-canonical.json': derived, 'chemical-graph-receipt.json': json_bytes(receipt),
             'microstate-assignments.json': json_bytes(assignments), 'derive-receptor-chemistry-source.py': Path(__file__).read_bytes(),
             'receptor-chemical-graph-source.py': Path(implementation.__file__).read_bytes()}
    manifest = {'schema_id': 'human_5ht6_7xtb_source_bound_receptor_chemical_graph_v1',
        'status': receipt['status'], 'files': {name: {'sha256': digest(raw), 'bytes': len(raw)} for name, raw in files.items()},
        'parent_refs': input_refs, 'receptor_system_sha256': receipt['derived_canonical_system_sha256'],
        'chemical_graph_sha256': receipt['lineage']['chemical_graph_sha256'],
        'counts': {key: receipt[key] for key in ('atom_count', 'bond_count', 'residue_count', 'formal_charge_sum', 'aromatic_atoms', 'aromatic_bonds')},
        'scope': {'input_preparation_modified': False, 'coordinates_modified': False, 'parameterization_modified': False,
                  'scorer_or_D3_executed': False, 'protected_outcomes_read': False, 'scientifically_validated': False, 'product_qualified': False}}
    files['manifest.v1.json'] = json_bytes(manifest)
    output.mkdir()
    for name, raw in files.items():
        with (output / name).open('xb') as stream:
            stream.write(raw)
    return {'output': str(output), 'manifest_sha256': digest(files['manifest.v1.json']), 'status': manifest['status'],
            'counts': manifest['counts'], 'bond_order_counts': receipt['bond_order_counts'], 'independent_validation': independent}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(derive(parser.parse_args().output), sort_keys=True))
