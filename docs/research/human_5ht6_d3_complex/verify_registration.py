"""Independently verify the declared rigid placement, source bytes and reader.

This verifies a computational coordinate transform, not a biological pose.
It does not import the preparation builder or consume protected outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

SOURCE_SHA = 'e81b271ee863340c0e1e65101be7695849bdd56f408c887b03b89929cc4e9cb7'
PROTOCOL_SHA = '01c1f5f2c0fa8e253a997565e64c4d319d2025a1f49a1221976bc9fde730af8b'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bound(reference):
    raw = Path(reference['path']).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == reference['sha256'], 'BOUND_SOURCE_HASH_MISMATCH')
    return raw


def sdf(raw):
    lines = raw.decode('ascii').splitlines(keepends=True)
    count = int(lines[3][:3])
    coordinates = np.array([[float(line[a:b]) for a,b in ((0,10),(10,20),(20,30))] for line in lines[4:4+count]])
    noncoordinates = lines.copy()
    for i in range(count):
        noncoordinates[i+4] = noncoordinates[i+4][30:]
    return coordinates, [line[31:34].strip() for line in lines[4:4+count]], ''.join(noncoordinates)


def verify_geometry(receptor_coordinates, receptor_elements, original_sdf, registered_sdf, registration, protocol):
    protocol_raw = (json.dumps(protocol, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
    require(hashlib.sha256(protocol_raw).hexdigest() == PROTOCOL_SHA, 'FROZEN_GEOMETRY_PROTOCOL_CHANGED')
    old, old_elements, old_noncoordinates = sdf(original_sdf)
    new, elements, new_noncoordinates = sdf(registered_sdf)
    require(old_noncoordinates == new_noncoordinates and elements == old_elements, 'NONCOORDINATE_LIGAND_BYTES_CHANGED')
    matrix = np.array(registration['rotation_matrix'])
    shift = np.array(registration['translation_angstrom'])
    require(matrix.shape == (3,3) and shift.shape == (3,) and np.isfinite(matrix).all() and np.isfinite(shift).all(), 'INVALID_TRANSFORM_DIMENSIONS')
    require(np.max(np.abs(matrix.T @ matrix-np.eye(3))) < 1e-12 and abs(np.linalg.det(matrix)-1) < 1e-12,
            'TRANSFORM_IS_NOT_PROPER_RIGID')
    exact = old @ matrix.T + shift
    require(np.array_equal(new, np.round(exact,4)), 'WRITTEN_COORDINATES_DO_NOT_MATCH_TRANSFORM')
    before = np.sqrt(((old[:,None]-old[None,:])**2).sum(axis=2))
    after = np.sqrt(((new[:,None]-new[None,:])**2).sum(axis=2))
    drift = float(np.max(np.abs(before-after)))
    require(drift <= 0.00018, 'INTRALIGAND_DISTANCE_CHANGED_BEYOND_ROUNDING')
    expected_mapping = [{'prepared_index_zero_based': i, 'source_index_zero_based': i, 'element': element} for i, element in enumerate(elements)]
    require(registration['source_atom_mapping'] == expected_mapping, 'ATOM_MAP_NOT_COMPLETE_IDENTITY_ORDER')
    heavy_l = np.array([element != 'H' for element in elements])
    heavy_r = np.array([element != 'H' for element in receptor_elements])
    distances = np.sqrt(((new[:,None]-receptor_coordinates[None,:])**2).sum(axis=2))
    radii = protocol['radius_table_angstrom']
    sums = np.array([radii[e] for e in elements])[:,None]+np.array([radii[e] for e in receptor_elements])[None,:]
    center = np.array(registration['pocket_center_angstrom'])
    metrics = {
        'minimum_all_atom_distance_angstrom': float(distances.min()),
        'minimum_heavy_atom_distance_angstrom': float(distances[np.ix_(heavy_l,heavy_r)].min()),
        'minimum_all_atom_radius_sum_ratio': float((distances/sums).min()),
        'minimum_heavy_atom_radius_sum_ratio': float((distances/sums)[np.ix_(heavy_l,heavy_r)].min()),
        'maximum_ligand_heavy_radius_angstrom': float(np.sqrt(((new[heavy_l]-center)**2).sum(axis=1)).max()),
    }
    for observed, limit in (
        ('minimum_all_atom_distance_angstrom','all_atom_minimum_distance_angstrom'),
        ('minimum_heavy_atom_distance_angstrom','heavy_atom_minimum_distance_angstrom'),
        ('minimum_all_atom_radius_sum_ratio','all_atom_minimum_radius_sum_ratio'),
        ('minimum_heavy_atom_radius_sum_ratio','heavy_atom_minimum_radius_sum_ratio')):
        require(metrics[observed] >= protocol[limit], 'GEOMETRIC_OVERLAP_LIMIT_VIOLATED:'+observed)
    require(metrics['maximum_ligand_heavy_radius_angstrom'] <= protocol['pocket_all_heavy_maximum_radius_angstrom'], 'OUTSIDE_DECLARED_POCKET')
    attempts = registration['attempts']
    require(registration['selected_ordinal'] == len(attempts)-1 and sum(row['accepted'] for row in attempts) == 1
            and attempts[-1]['accepted'] is True, 'SELECTED_POSE_NOT_FIRST_RECORDED_ACCEPTANCE')
    for key, value in metrics.items():
        require(abs(attempts[-1][key]-value) <= 1e-12, 'SAVED_GEOMETRY_METRIC_MISMATCH:'+key)
    return {'metrics': metrics, 'intraligand_maximum_distance_change_angstrom': drift,
            'registered_atoms': len(new), 'receptor_atoms': len(receptor_coordinates), 'recorded_attempts': len(attempts)}


def verify(root):
    from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components
    from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes, canonical_system_sha256
    manifest = json.loads((root/'manifest.v1.json').read_text())
    for name, identity in manifest['files'].items():
        raw = (root/name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == identity['sha256'] and len(raw) == identity['bytes'], 'PACKET_FILE_HASH_MISMATCH:'+name)
    request = json.loads(bound(manifest['prepared_input']))
    registration = json.loads(bound(manifest['registration']))
    protocol = json.loads(bound(registration['protocol']))
    source_raw = bound(registration['source'])
    require(hashlib.sha256(source_raw).hexdigest() == SOURCE_SHA, 'PINNED_7XTB_SOURCE_MISMATCH')
    from betelgeuze_engine_v2.molecular.mmcif_syntax import parse_cif_block
    block = parse_cif_block(source_raw.decode('ascii'))
    anchors = []
    for loop in block.loops:
        if '_atom_site' not in loop.categories:
            continue
        for tokens in loop.rows:
            row = {key: token.value for key, token in zip(loop.tags, tokens)}
            if row['_atom_site.label_asym_id'] == 'F':
                require(row['_atom_site.label_comp_id'] == 'SRO' and row['_atom_site.auth_seq_id'] == '501'
                    and row['_atom_site.pdbx_pdb_model_num'] == '1', 'SOURCE_ANCHOR_IDENTITY_CHANGED')
                anchors.append({'atom_site_id': row['_atom_site.id'], 'atom_name': row['_atom_site.label_atom_id'],
                    'xyz_angstrom': [float(row['_atom_site.cartn_'+axis]) for axis in 'xyz']})
    require(len(anchors) == 13 and anchors == registration['public_source_anchor_rows'], 'SOURCE_ANCHOR_ROWS_CHANGED')
    require(np.array_equal(np.mean([row['xyz_angstrom'] for row in anchors], axis=0), registration['pocket_center_angstrom']), 'POCKET_CENTER_NOT_SOURCE_CENTROID')
    receptor, ligand, receptor_parameters, ligand_parameters, evidence = load_prepared_gromacs_components(request)
    rows = bound(request['protein_pdb']).decode('ascii').splitlines()
    elements = [row[76:78].strip() for row in rows if row.startswith(('ATOM  ','HETATM'))]
    result = verify_geometry(receptor.coordinates[0].numpy(), elements, bound(registration['ligand_source']),
        bound(request['ligand_sdf']), registration, protocol)
    require((root/'receptor-canonical.json').read_bytes() == canonical_system_json_bytes(receptor), 'RECEPTOR_CANONICAL_READER_ROUNDTRIP_MISMATCH')
    require((root/'ligand-canonical.json').read_bytes() == canonical_system_json_bytes(ligand), 'LIGAND_CANONICAL_READER_ROUNDTRIP_MISMATCH')
    require(manifest['receptor_system_sha256'] == canonical_system_sha256(receptor)
            and manifest['ligand_system_sha256'] == canonical_system_sha256(ligand), 'CANONICAL_HASH_MISMATCH')
    require(json.loads((root/'cross-parameters.json').read_text()) == {'receptor': receptor_parameters, 'ligand': ligand_parameters}, 'READER_PARAMETERS_CHANGED')
    require(manifest['scientific_authority'] == {'observed_PR49_pose': False, 'redocking_reference': False,
        'assay_state_equivalence': False, 'affinity_or_ranking_validation': False,
        'fit_calibration_or_evaluation_admission': False, 'protected_outcomes_read': False}, 'SCIENTIFIC_AUTHORITY_PROMOTION')
    result.update({'status': 'PASS_COMPUTATIONAL_REGISTRATION_ONLY', 'reader_ingestion_registration_performed': evidence['coordinate_registration_performed'],
                   'upstream_rigid_transform_verified': True, 'biological_pose_validated': False})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.packet.resolve()), sort_keys=True, indent=2))
