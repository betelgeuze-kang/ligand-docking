"""Fresh synthetic source observations; no protected data or assay fitting."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import itertools
import math
from pathlib import Path

import pytest

from betelgeuze_engine.product import mmcif_ligand_observation as module
from tools.product.observe_mmcif_ligand_coordinates import evaluate_request


def source_text(*, coords=((0, 0, 0), (1.2, 0, 0), (0, 0.9, 0)), order=(0, 1, 2), charge="?", occupancy="1"):
    header = """data_9ZZZ
_entry.id 9ZZZ
loop_
_entity.id
_entity.type
1 non-polymer
loop_
_struct_asym.id
_struct_asym.entity_id
L 1
loop_
_pdbx_entity_nonpoly.entity_id
_pdbx_entity_nonpoly.comp_id
_pdbx_entity_nonpoly.name
1 TST
;A long descriptive name
retained without use in an identity join
;
loop_
_pdbx_nonpoly_scheme.asym_id
_pdbx_nonpoly_scheme.entity_id
_pdbx_nonpoly_scheme.mon_id
_pdbx_nonpoly_scheme.pdb_seq_num
_pdbx_nonpoly_scheme.pdb_strand_id
_pdbx_nonpoly_scheme.pdb_ins_code
L 1 TST 42 A .
loop_
_chem_comp_atom.comp_id
_chem_comp_atom.atom_id
_chem_comp_atom.type_symbol
TST C1 C
TST O1 O
TST N1 N
TST H1 H
loop_
_chem_comp_bond.comp_id
_chem_comp_bond.atom_id_1
_chem_comp_bond.atom_id_2
_chem_comp_bond.value_order
_chem_comp_bond.pdbx_aromatic_flag
_chem_comp_bond.pdbx_stereo_config
TST C1 O1 doub N N
TST C1 N1 sing N N
TST N1 H1 sing N N
loop_
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_entity_id
_atom_site.auth_seq_id
_atom_site.auth_asym_id
_atom_site.label_alt_id
_atom_site.pdbx_PDB_model_num
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
_atom_site.pdbx_formal_charge
_atom_site.occupancy
_atom_site.pdbx_PDB_ins_code
"""
    atoms = [('C', 'C1'), ('O', 'O1'), ('N', 'N1')]
    return header + "".join(f"{i+1} {atoms[i][0]} {atoms[i][1]} TST L 1 42 A . 1 {' '.join(map(str,coords[i]))} {charge} {occupancy} .\n" for i in order)


def case(tmp_path, text=None):
    path = tmp_path / 'synthetic.cif'
    path.write_text(source_text() if text is None else text)
    return {"case_id": "invented", "source": {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
            "selection": {"entry_id": "9ZZZ", "label_asym_id": "L", "component_id": "TST", "auth_seq_id": "42", "model_number": "1"},
            "provenance": {"role": "fit", "split": "development_source", "dataset_split": "fit", "evaluation_only": False}}


def observe(c):
    return module.observe_mmcif_ligand(source=c['source'], selection=c['selection'])


def test_new_source_profile_preserves_missing_charge_atoms_and_bonds(tmp_path):
    r = observe(case(tmp_path))
    assert [a['name'] for a in r['atoms']] == ['C1', 'O1', 'N1']
    assert all(a['formal_charge'] is None and a['component_formal_charge'] is None for a in r['atoms'])
    assert [a['name'] for a in r['component_atoms_without_source_coordinates']] == ['H1']
    assert r['counts']['missing_hydrogen_coordinates'] == 1
    assert r['counts']['missing_heavy_atom_coordinates'] == 0
    assert len(r['bonds']) == 2 and len(r['component_bonds_without_source_coordinates']) == 1
    assert r['bonds'][0]['order'] == 2 and r['bonds'][0]['distance_angstrom'] == pytest.approx(1.2)
    assert r['geometry']['pair_count'] == 1
    assert r['potential_energy'] is None and r['forces'] is None
    assert not any(r[k] for k in ['all_atom_prepared', 'receptor_prepared', 'training_admitted', 'scientifically_validated', 'customer_execution'])


def _distances(r):
    return {tuple(sorted((r['atoms'][b['atom_i']]['name'], r['atoms'][b['atom_j']]['name']))): b['distance_angstrom'] for b in r['bonds']}


@pytest.mark.parametrize('order', list(itertools.permutations(range(3))))
def test_source_permutation_keeps_named_bonds_and_distances(tmp_path, order):
    r = observe(case(tmp_path, source_text(order=order)))
    assert [a['source_atom_id'] for a in r['atoms']] == [str(i+1) for i in order]
    assert _distances(r) == pytest.approx({('C1', 'O1'): 1.2, ('C1', 'N1'): 0.9})


def test_rigid_transform_and_independent_distance_reference(tmp_path):
    coords = [(0, 0, 0), (1.2, 0, 0), (0, 0.9, 0)]
    transformed = [(8-y, -3+x, 2+z) for x, y, z in coords]
    r = observe(case(tmp_path, source_text(coords=transformed)))
    assert _distances(r) == pytest.approx({('C1', 'O1'): 1.2, ('C1', 'N1'): 0.9})
    reference = {(i, j): math.dist(a, b) for i, a in enumerate(transformed) for j, b in enumerate(transformed) if i < j and math.dist(a, b) <= 1}
    assert {(p['atom_i'], p['atom_j']): p['distance_angstrom'] for p in r['geometry']['pairs']} == pytest.approx(reference)


def test_measured_zero_charge_and_zero_occupancy_are_not_missing(tmp_path):
    r = observe(case(tmp_path, source_text(charge='0', occupancy='0')))
    assert all(a['formal_charge'] == 0 and a['occupancy'] == 0 for a in r['atoms'])
    assert r['counts']['missing_atom_site_formal_charges'] == 0
    assert r['counts']['zero_occupancy_atoms'] == 3
    assert not r['all_atom_prepared']


@pytest.mark.parametrize(('old', 'new', 'message'), [
    ('TST C1 C\n', 'TST C1 C\nTST C1 C\n', 'duplicate_component_atom'),
    ('TST C1 O1 doub N N\n', 'TST C1 O1 doub N N\nTST O1 C1 doub N N\n', 'duplicate_component_bond'),
    ('L 1 TST 42 A .', 'L 1 TST 43 A .', 'instance_scheme_mismatch'),
    ('1 non-polymer', '1 polymer', 'not_nonpolymer'),
    ('L 1\n', 'L 2\n', 'asym_entity_mismatch'),
    ('1 TST\n', '1 OTHER\n', 'nonpolymer_component_mismatch'),
    ('TST C1 C\n', 'TST C1 O\n', 'component_atom_mismatch'),
    ('TST C1 O1 doub N N', 'TST C1 O1 unsupported N N', 'bond_semantics'),
    ('42 A . 1', '42 A B 1', 'alternate_locations'),
    ('0 0 0 ? 1 .', 'nan 0 0 ? 1 .', 'nonfinite_number'),
    ('0 0 0 ? 1 .', '0 0 0 ? 1.1 .', 'occupancy_outside'),
])
def test_invalid_sources_are_rejected_without_repair(tmp_path, old, new, message):
    text = source_text()
    assert old in text
    with pytest.raises(ValueError, match=message):
        observe(case(tmp_path, text.replace(old, new)))



def test_duplicate_selected_atoms_are_not_last_row_wins(tmp_path):
    text = source_text()
    text += text.splitlines()[-1] + '\n'
    with pytest.raises(ValueError, match='duplicate_source_atom'):
        observe(case(tmp_path, text))


def test_hash_mismatch_rejected_before_observation(tmp_path):
    c = case(tmp_path)
    Path(c['source']['path']).write_text(source_text().replace('1.2', '1.4'))
    with pytest.raises(ValueError, match='source_hash_or_size_mismatch'):
        observe(c)


def test_quoted_unknown_marker_is_not_assumed_missing(tmp_path):
    with pytest.raises(ValueError, match='invalid_formal_charge'):
        observe(case(tmp_path, source_text(charge="'?'") ))


def test_consumer_retains_failures_and_policy(tmp_path):
    c = case(tmp_path)
    bad = deepcopy(c)
    bad['case_id'] = 'wrong'
    bad['selection']['entry_id'] = '9ZZY'
    request = {'schema_version': 'mmcif_ligand_observation_request_v1', 'cases': [c, bad]}
    result = evaluate_request(request)
    assert result['denominator'] == {'requested': 2, 'observed': 1, 'failed': 1, 'skipped': 0, 'physical_evaluations': 0}
    assert all(row['provenance'] == c['provenance'] for row in result['rows'])
    assert result['rows'][1]['observation'] is None
    request['cases'] = [c, deepcopy(c)]
    assert evaluate_request(request)['denominator']['failed'] == 2


def test_existing_strict_identity_guard_still_rejects_same_synthetic_source(tmp_path):
    from betelgeuze_engine_v2.molecular.mmcif_nonpoly_identity import parse_mmcif_nonpoly_identity
    # The old identity profile is unchanged. The new observer uses the existing
    # lexical parser and a narrower explicit instance join; it grants no state.
    with pytest.raises(ValueError):
        parse_mmcif_nonpoly_identity(source_text())
    assert observe(case(tmp_path))['all_atom_prepared'] is False


def test_neighbor_overflow_remains_unavailable(monkeypatch, tmp_path):
    original = module.build_compact_radius_graph
    def low_capacity(coordinates, config):
        return original(coordinates, module.RadiusGraphConfig(1, max_neighbors=1, max_atoms_per_cell=1))
    monkeypatch.setattr(module, 'build_compact_radius_graph', low_capacity)
    r = observe(case(tmp_path, source_text(coords=((0, 0, 0), (.2, 0, 0), (0, .3, 0)))))
    assert r['geometry']['status'] == 'unavailable'
    assert r['geometry']['pair_count'] is None and r['geometry']['pairs'] is None
    assert r['all_atom_prepared'] is False
