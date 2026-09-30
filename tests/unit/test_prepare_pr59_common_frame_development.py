"""Boundaries of explicit constraint-to-bond model derivation."""
from copy import deepcopy
import xml.etree.ElementTree as ET

import pytest

from tools.analysis.prepare_pr59_common_frame_development import (
    FORCES, unconstrained_difference,
)


def source_pair():
    original = ET.Element('System')
    particles = ET.SubElement(original, 'Particles')
    for mass in ('12', '1', '1'):
        ET.SubElement(particles, 'Particle', mass=mass)
    constraints = ET.SubElement(original, 'Constraints')
    ET.SubElement(constraints, 'Constraint', p1='0', p2='1', d='.1')
    ET.SubElement(constraints, 'Constraint', p1='0', p2='2', d='.1')
    forces = ET.SubElement(original, 'Forces')
    for name in sorted(FORCES):
        force = ET.SubElement(forces, 'Force', type=name)
        if name == 'HarmonicBondForce':
            ET.SubElement(force, 'Bonds')
        else:
            ET.SubElement(force, 'RetainedParameters', value='exact')
    derived = deepcopy(original)
    derived.find('Constraints').clear()
    bonds = next(f for f in derived.find('Forces') if f.get('type') == 'HarmonicBondForce').find('Bonds')
    ET.SubElement(bonds, 'Bond', p1='0', p2='1', d='.1', k='123')
    ET.SubElement(bonds, 'Bond', p1='0', p2='2', d='.1', k='456')
    return original, derived


def verify(original, derived):
    return unconstrained_difference(ET.tostring(original), ET.tostring(derived), 2)


def test_declared_derivation_restores_each_original_constraint_pair():
    original, derived = source_pair()
    result = verify(original, derived)
    assert result['new_harmonic_bond_pairs_zero_based'] == [[0, 1], [0, 2]]
    assert result['original_constraint_count'] == 2
    assert result['new_constraint_count'] == 0
    assert result['constrained_dynamics_equivalence_claimed'] is False


@pytest.mark.parametrize('inventory', [None, 0, -1, 2.0, True])
def test_explicit_positive_integer_original_inventory_required(inventory):
    original, derived = source_pair()
    with pytest.raises(ValueError, match='explicit_positive_original_constraint_inventory_required'):
        unconstrained_difference(ET.tostring(original), ET.tostring(derived), inventory)


def test_mass_order_change_rejected():
    original, derived = source_pair()
    derived.find('Particles')[0].set('mass', '13')
    with pytest.raises(ValueError, match='particle_masses_or_order_changed'):
        verify(original, derived)


@pytest.mark.parametrize('name', sorted(FORCES - {'HarmonicBondForce'}))
def test_all_other_force_parameters_must_remain_exact(name):
    original, derived = source_pair()
    next(f for f in derived.find('Forces') if f.get('type') == name)[0].set('value', 'different')
    with pytest.raises(ValueError, match='nonbond_force_or_parameter_changed'):
        verify(original, derived)


@pytest.mark.parametrize('duplicate', [False, True])
def test_unknown_or_duplicate_force_rejected(duplicate):
    original, derived = source_pair()
    ET.SubElement(derived.find('Forces'), 'Force', type='NonbondedForce' if duplicate else 'CustomBondForce')
    with pytest.raises(ValueError, match='unsupported_or_duplicate_force_class'):
        verify(original, derived)


def test_retained_constraint_rejected():
    original, derived = source_pair()
    ET.SubElement(derived.find('Constraints'), 'Constraint', p1='0', p2='1', d='.1')
    with pytest.raises(ValueError, match='original_or_derived_constraint_inventory_changed'):
        verify(original, derived)


def test_restored_constraint_pair_omission_rejected():
    original, derived = source_pair()
    bonds = next(f for f in derived.find('Forces') if f.get('type') == 'HarmonicBondForce').find('Bonds')
    bonds.remove(bonds[0])
    with pytest.raises(ValueError, match='restored_bonds_do_not_equal_original_constraint_pairs'):
        verify(original, derived)


def test_preexisting_bond_cannot_be_changed():
    original, derived = source_pair()
    old_bonds = next(f for f in original.find('Forces') if f.get('type') == 'HarmonicBondForce').find('Bonds')
    new_bonds = next(f for f in derived.find('Forces') if f.get('type') == 'HarmonicBondForce').find('Bonds')
    ET.SubElement(old_bonds, 'Bond', p1='1', p2='2', d='.15', k='789')
    ET.SubElement(new_bonds, 'Bond', p1='1', p2='2', d='.15', k='790')
    with pytest.raises(ValueError, match='preexisting_harmonic_bond_changed'):
        verify(original, derived)


def test_duplicate_constraint_pair_rejected():
    original, derived = source_pair()
    original.find('Constraints')[1].set('p2', '1')
    with pytest.raises(ValueError, match='duplicate_constraint_pair'):
        verify(original, derived)


def test_virtual_site_rejected():
    original, derived = source_pair()
    ET.SubElement(ET.SubElement(derived, 'VirtualSites'), 'TwoParticleAverageSite', index='2')
    with pytest.raises(ValueError, match='virtual_sites_unsupported'):
        verify(original, derived)
