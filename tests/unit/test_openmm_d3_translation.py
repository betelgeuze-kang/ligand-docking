"""Lossless supported potential translation and explicit source-term refusals."""
from dataclasses import replace
import math
from xml.etree import ElementTree as ET

import pytest
import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import Bond
from betelgeuze_engine_v2.physics.reference_forcefield import _bonded_topology_paths
from betelgeuze_product.cpu_refinement_v1_2.openmm_periodic_extension import evaluate_extension
from tools.product.openmm_d3_translation import (
    OpenMMD3TranslationError, TranslationSettings, convert_openmm_system,
)
from tests.unit.test_engine_v2_reference_forcefield_v2 import _star_system


SETTINGS = TranslationSettings("synthetic-source-translation", 12., 10.)


def source_fixture(*, star=False, amplitude=-4.184):
    system = _star_system()
    atoms = tuple(replace(a, mass_da=12., partial_charge_e=q)
        for a, q in zip(system.atoms, (.2, -.2, .3, -.3), strict=True))
    bonds = system.bonds if star else tuple(Bond(index=i, atom_i=i, atom_j=i+1,
        order=1., source="translation-fixture") for i in range(3))
    system = replace(system, atoms=atoms, bonds=bonds)
    graph = [(b.atom_i, b.atom_j) for b in bonds]
    angles, propers = _bonded_topology_paths(4, graph)
    root = ET.Element("System", type="System", version="1", openmmVersion="8.4")
    box = ET.SubElement(root, "PeriodicBoxVectors")
    for axis, xyz in zip(("A", "B", "C"), ((2,0,0),(0,2,0),(0,0,2)), strict=True):
        ET.SubElement(box, axis, **{key:str(v) for key,v in zip(("x","y","z"),xyz,strict=True)})
    particles = ET.SubElement(root, "Particles")
    for _ in atoms:
        ET.SubElement(particles, "Particle", mass="12")
    ET.SubElement(root, "Constraints")
    forces = ET.SubElement(root, "Forces")
    for kind, container, record, rows in (
        ("HarmonicBondForce", "Bonds", "Bond", [dict(p1=str(i),p2=str(j),d=".1",k="418.4") for i,j in graph]),
        ("HarmonicAngleForce", "Angles", "Angle", [dict(p1=str(i),p2=str(j),p3=str(k),a="1.5",k="4.184") for i,j,k in sorted(angles)]),
        ("PeriodicTorsionForce", "Torsions", "Torsion", [dict(p1=str(i),p2=str(j),p3=str(k),p4=str(l),periodicity="2",phase=".4",k=str(amplitude)) for i,j,k,l in sorted(propers)]),
    ):
        force=ET.SubElement(forces,"Force",type=kind,name=kind,forceGroup="0",usesPeriodic="0",version="2")
        table=ET.SubElement(force,container)
        for row in rows:
            ET.SubElement(table,record,**row)
        if star and kind == "PeriodicTorsionForce":
            for indices in ((1,0,2,3),(2,0,3,1),(3,0,1,2)):
                ET.SubElement(table,"Torsion",**{**{f"p{i+1}":str(v) for i,v in enumerate(indices)},
                    "periodicity":"2","phase":".4","k":str(amplitude)})
    nb = ET.SubElement(forces,"Force",type="NonbondedForce",name="NonbondedForce",forceGroup="0",version="4",
        alpha="0",cutoff=".9",dispersionCorrection="1",ewaldTolerance=".0005",exceptionsUsePeriodic="0",
        includeDirectSpace="1",ljAlpha="0",ljnx="0",ljny="0",ljnz="0",method="0",nx="0",ny="0",nz="0",
        recipForceGroup="-1",rfDielectric="78.3",switchingDistance=".8",useSwitchingFunction="1")
    for tag in ("GlobalParameters","ParticleOffsets","ExceptionOffsets"):
        ET.SubElement(nb,tag)
    table=ET.SubElement(nb,"Particles")
    for a in atoms:
        ET.SubElement(table,"Particle",eps=".4184",q=str(a.partial_charge_e),sig=".1")
    table=ET.SubElement(nb,"Exceptions")
    ET.SubElement(table,"Exception",p1="0",p2="1",eps="0",q="0",sig="1")
    ET.SubElement(table,"Exception",p1="0",p2="3",eps=".2092",q="-.05",sig=".1")
    ET.SubElement(forces,"Force",type="CMMotionRemover",name="CMMotionRemover",forceGroup="0",frequency="1",version="1")
    return root, system


def convert(root, system):
    return convert_openmm_system(ET.tostring(root), system, SETTINGS)


def force(root, name):
    return next(x for x in root.find("Forces") if x.attrib["type"] == name)


@pytest.mark.parametrize("star", [False, True])
@pytest.mark.parametrize("amplitude", [-4.184, 0., 4.184])
def test_complete_inventory_preserves_signed_torsions_and_units(star, amplitude):
    root, system = source_fixture(star=star, amplitude=amplitude)
    result = convert(root, system)
    assert result.base_parameters.bonds[0].equilibrium_angstrom == 1.
    assert result.base_parameters.bonds[0].force_constant_kcal_per_mol_angstrom2 == 1.
    assert result.base_parameters.angles[0].force_constant_kcal_per_mol_radian2 == 1.
    assert result.base_parameters.atom_parameters[0].epsilon_kcal_per_mol == pytest.approx(.1, abs=1e-16, rel=0)
    assert len(result.base_parameters.excluded_pairs) == len(result.base_parameters.scaled_pairs) == 1
    assert result.base_parameters.scaled_pairs[0].electrostatic_scale == pytest.approx(5/6)
    assert result.inventory["source_periodic_torsion_count"] == (3 if star else 1)
    assert result.inventory["periodic_improper_count"] == (3 if star else 0)
    assert result.parameters.constant_energy_offset_kcal_per_mol == (-2. if not star and amplitude<0 else 0.)
    assert not result.inventory["scientifically_validated"]
    assert "no_dynamics_equivalence" in result.inventory["cmmotion_remover_scope"]
    assert result.parameters.metadata["openmm_xml_sha256"] == result.inventory["source_xml_sha256"]
    if star:
        assert all(x.amplitude_kcal_per_mol == amplitude/4.184 for x in result.parameters.periodic_impropers)
    else:
        row = result.base_parameters.torsions[0]
        for theta in (.1,1.,2.4):
            mapped = row.amplitude_kcal_per_mol*(1+math.cos(row.periodicity*theta-row.phase_radians))
            assert mapped + result.parameters.constant_energy_offset_kcal_per_mol == pytest.approx(
                amplitude/4.184*(1+math.cos(2*theta-.4)), abs=1e-14)


@pytest.mark.parametrize("star", [False, True])
def test_source_openmm_reference_energy_and_force_match(star):
    openmm = pytest.importorskip("openmm")
    from openmm import unit
    root, system = source_fixture(star=star)
    result = convert(root, system)
    independent = openmm.XmlSerializer.deserialize(ET.tostring(root).decode())
    integrator = openmm.VerletIntegrator(.001)
    context = openmm.Context(independent, integrator, openmm.Platform.getPlatformByName("Reference"))
    neighbors = build_compact_radius_graph(system.coordinates, RadiusGraphConfig(
        cutoff_angstrom=SETTINGS.cutoff_angstrom,max_neighbors=4,max_atoms_per_cell=4))
    context.setPositions(system.coordinates[0].numpy()*.1*unit.nanometer)
    reference = context.getState(getEnergy=True,getForces=True)
    actual = evaluate_extension(system, neighbors, result.parameters)
    assert actual.term.energy.item() == pytest.approx(
        reference.getPotentialEnergy().value_in_unit(unit.kilocalorie_per_mole),abs=1e-8,rel=0)
    torch.testing.assert_close(actual.term.forces[0],torch.tensor(reference.getForces(asNumpy=True).value_in_unit(
        unit.kilocalorie_per_mole/unit.angstrom)),rtol=0,atol=1e-8)


@pytest.mark.parametrize("mutation,code", [
    ("unknown_force","unsupported_force_class"),
    ("duplicate_force","duplicate_force_class"),
    ("unknown_attribute","unsupported_xml_attributes"),
    ("periodic_bond","periodic_bonded_force_unsupported"),
    ("cutoff_source","only_nonperiodic_nocutoff_source_supported"),
    ("global_parameter","nonbonded_offsets_or_global_parameters_unsupported"),
    ("particle_offset","nonbonded_offsets_or_global_parameters_unsupported"),
    ("exception_offset","nonbonded_offsets_or_global_parameters_unsupported"),
    ("virtual_site","unsupported_xml_record"),
    ("bond_missing","harmonic_bond_coverage_mismatch"),
    ("angle_missing","harmonic_angle_coverage_mismatch"),
    ("proper_missing","periodic_proper_coverage_mismatch"),
    ("constraint_missing_bond","constrained_bond_terms_missing"),
    ("constraint_present","constrained_system_unsupported"),
    ("sigma_override","non_lorentz_berthelot_exception_sigma"),
    ("scale_above_one","exception_scaling_outside_supported_interval"),
    ("duplicate_exception","duplicate_nonbonded_exception"),
    ("mass_mismatch","source_particle_mass_order_mismatch"),
    ("charge_mismatch","source_particle_charge_order_mismatch"),
])
def test_unsupported_terms_and_source_mutations_refuse(mutation, code):
    root, system=source_fixture()
    nb=force(root,"NonbondedForce")
    if mutation == "unknown_force":
        ET.SubElement(root.find("Forces"),"Force",type="CustomBondForce")
    elif mutation == "duplicate_force":
        root.find("Forces").append(ET.fromstring(ET.tostring(nb)))
    elif mutation == "unknown_attribute":
        nb.set("futureSetting","1")
    elif mutation == "periodic_bond":
        force(root,"HarmonicBondForce").set("usesPeriodic","1")
    elif mutation == "cutoff_source":
        nb.set("method","1")
    elif mutation in ("global_parameter","particle_offset","exception_offset"):
        ET.SubElement(nb.find({"global_parameter":"GlobalParameters","particle_offset":"ParticleOffsets",
            "exception_offset":"ExceptionOffsets"}[mutation]),"Unsupported")
    elif mutation == "virtual_site":
        ET.SubElement(root.find("Particles")[0],"VirtualSite",type="TwoParticleAverageSite")
    elif mutation in ("bond_missing","angle_missing","proper_missing"):
        kind, table={"bond_missing":("HarmonicBondForce","Bonds"),"angle_missing":("HarmonicAngleForce","Angles"),
            "proper_missing":("PeriodicTorsionForce","Torsions")}[mutation]
        container=force(root,kind).find(table)
        container.remove(container[0])
    elif mutation.startswith("constraint"):
        ET.SubElement(root.find("Constraints"),"Constraint",p1="0",p2="1",d=".1")
        if mutation == "constraint_missing_bond":
            table=force(root,"HarmonicBondForce").find("Bonds")
            table.remove(table[0])
    elif mutation == "sigma_override":
        nb.find("Exceptions")[1].set("sig",".2")
    elif mutation == "scale_above_one":
        nb.find("Exceptions")[1].set("eps","4.184")
    elif mutation == "duplicate_exception":
        table=nb.find("Exceptions")
        table.append(ET.fromstring(ET.tostring(table[0])))
    elif mutation == "mass_mismatch":
        root.find("Particles")[0].set("mass","13")
    elif mutation == "charge_mismatch":
        nb.find("Particles")[0].set("q","0")
    with pytest.raises(OpenMMD3TranslationError) as caught:
        convert(root,system)
    assert caught.value.code == code


def test_nocutoff_domain_is_not_silently_truncated():
    root,system=source_fixture()
    with pytest.raises(OpenMMD3TranslationError,match="nocutoff_equivalence_domain_exceeded"):
        convert_openmm_system(ET.tostring(root),system,TranslationSettings("too-small",2.,1.))


@pytest.mark.parametrize("zero_base", ["charge", "epsilon"])
def test_nonzero_exception_cannot_be_reconstructed_from_a_zero_base(zero_base):
    root,system=source_fixture()
    nb=force(root,"NonbondedForce")
    if zero_base == "charge":
        nb.find("Particles")[0].set("q","0")
        system=replace(system,atoms=(replace(system.atoms[0],partial_charge_e=0.),*system.atoms[1:]))
    else:
        nb.find("Particles")[0].set("eps","0")
    with pytest.raises(OpenMMD3TranslationError,match="non_scalable_exception"):
        convert(root,system)


def test_zero_lj_exception_keeps_coulomb_without_requiring_an_active_sigma():
    root,system=source_fixture()
    row=force(root,"NonbondedForce").find("Exceptions")[1]
    row.set("eps","0")
    row.set("sig","7")
    result=convert(root,system)
    assert result.base_parameters.scaled_pairs[0].lj_scale == 0.
    assert result.base_parameters.scaled_pairs[0].electrostatic_scale == pytest.approx(5/6)


def test_xml_entities_are_refused_before_parsing():
    _,system=source_fixture()
    with pytest.raises(OpenMMD3TranslationError,match="xml_dtd_or_entities_unsupported"):
        convert_openmm_system(b'<!DOCTYPE x [<!ENTITY a "x">]><System/>',system,SETTINGS)


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-32-le"])
def test_alternate_encoding_cannot_hide_a_dtd(encoding):
    root,system=source_fixture()
    text = ('<?xml version="1.0" encoding="UTF-16"?>'
            '<!DOCTYPE System [<!ENTITY mass "12">]>'
            + ET.tostring(root).decode().replace('mass="12"','mass="&mass;"',1))
    with pytest.raises(OpenMMD3TranslationError,match="only_ascii_openmm_serialization_supported"):
        convert_openmm_system(text.encode(encoding),system,SETTINGS)
