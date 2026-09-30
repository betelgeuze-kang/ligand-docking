"""Boundary checks for independent serialized-derivation evidence only."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree as ET

import pytest

SOURCE = Path(__file__).resolve().parents[2] / 'docs/evidence/scripts/prepared_pair_independent_numerics_20260930.py'
spec = importlib.util.spec_from_file_location('pair_independent_audit', SOURCE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def fixture():
    original = ET.fromstring('''<System><Particles><Particle mass="12"/><Particle mass="12"/><Particle mass="1"/></Particles><Constraints><Constraint p1="1" p2="2" d=".1"/></Constraints><Forces><Force type="HarmonicBondForce"><Bonds><Bond p1="0" p2="1" d=".15" k="100"/></Bonds></Force><Force type="HarmonicAngleForce"><Angles><Angle p1="0" p2="1" p3="2" a="1.5" k="20"/></Angles></Force><Force type="PeriodicTorsionForce"><Torsions/></Force><Force type="NonbondedForce"><Particles><Particle q="-.1" sig=".2" eps=".3"/></Particles></Force><Force type="CMMotionRemover"/></Forces></System>''')
    derived = ET.fromstring(ET.tostring(original))
    derived.find('Constraints').clear()
    ET.SubElement(derived.find('Forces/Force/Bonds'),'Bond',p1='1',p2='2',d='.1',k='200')
    ligand = SimpleNamespace(bonds=[SimpleNamespace(atom_i=0,atom_j=1),SimpleNamespace(atom_i=1,atom_j=2)])
    return original,derived,ligand


def evaluate(rows):
    old,new,ligand=rows
    return audit.derivation_check(ET.tostring(old),ET.tostring(new),ligand)


def test_separate_declared_model_preserves_terms_and_restores_exact_constraint_pair():
    result=evaluate(fixture())
    assert result['passed']
    assert result['original_constraint_count']==1
    assert result['restored_harmonic_pair_count']==1
    assert result['constrained_dynamics_equivalence_claimed'] is False


@pytest.mark.parametrize('mutation',['remaining_constraint','missing_restored_bond','old_bond_changed','equilibrium_length_changed','charge_changed','mass_changed','angle_changed','graph_bond_omitted'])
def test_resealed_derivation_cannot_hide_different_source_terms(mutation):
    rows=fixture()
    old,new,ligand=rows
    if mutation=='remaining_constraint':
        ET.SubElement(new.find('Constraints'),'Constraint',p1='1',p2='2',d='.1')
    elif mutation=='missing_restored_bond':
        new.find('Forces/Force/Bonds').remove(new.find('Forces/Force/Bonds')[1])
    elif mutation=='old_bond_changed':
        new.find('Forces/Force/Bonds')[0].set('k','101')
    elif mutation=='equilibrium_length_changed':
        new.find('Forces/Force/Bonds')[1].set('d','.11')
    elif mutation=='charge_changed':
        new.find("Forces/Force[@type='NonbondedForce']/Particles/Particle").set('q','-.2')
    elif mutation=='mass_changed':
        new.find('Particles/Particle').set('mass','13')
    elif mutation=='angle_changed':
        new.find("Forces/Force[@type='HarmonicAngleForce']/Angles/Angle").set('k','21')
    else:
        ligand.bonds.pop()
    with pytest.raises(ValueError,match='unconstrained_derivation_term_correspondence_failed'):
        evaluate(rows)


def test_duplicate_restored_bond_is_rejected():
    rows=fixture()
    new=rows[1]
    ET.SubElement(new.find('Forces/Force/Bonds'),'Bond',p1='2',p2='1',d='.1',k='200')
    with pytest.raises(ValueError,match='duplicate_source_pair'):
        evaluate(rows)


@pytest.mark.parametrize('wrong_field',['sha256','bytes'])
def test_input_hash_and_size_bindings_are_required(tmp_path,wrong_field):
    p=tmp_path/'immutable'
    p.write_bytes(b'source')
    binding=audit.ref(p)
    binding[wrong_field]='0'*64 if wrong_field=='sha256' else 1
    with pytest.raises(ValueError,match='immutable_input_binding_mismatch'):
        audit.checked(binding)
