"""Bounded source-driven OpenMM audit: actual contexts, errors and provenance."""
from dataclasses import replace
import hashlib
import json

import numpy as np
import pytest
import torch

openmm = pytest.importorskip("openmm")

from betelgeuze_engine_v2.molecular import canonical_system_sha256, canonical_topology_sha256
from betelgeuze_engine_v2.molecular.serialization import canonical_system_json_bytes
from betelgeuze_engine_v2.physics.reference_parameters import AtomNonbondedParameter
from betelgeuze_product.cpu_refinement_v1_2.fixed_receptor import CrossParameters
from tools.analysis import openmm_d3_numerical_audit as audit_tool
from tools.product.openmm_d3_translation import TranslationSettings, convert_openmm_system
from tests.unit.test_engine_v2_reference_forcefield_v2 import _star_system, _star_base_parameters
from tests.unit.test_cpu_fixed_receptor import system as simple_system
from tests.unit.test_cpu_fixed_receptor_pipeline import request_fixture


def _write(path, value):
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    path.write_bytes(raw)
    return {"path": str(path.absolute()), "sha256": hashlib.sha256(raw).hexdigest()}


def packet(tmp_path):
    request = request_fixture(tmp_path)
    ligand = _star_system()
    charges = (.1, -.2, .15, -.05)
    ligand = replace(ligand, atoms=tuple(replace(atom, mass_da=12., partial_charge_e=charges[i])
                                       for i, atom in enumerate(ligand.atoms)))
    base = _star_base_parameters(ligand)
    system = openmm.System()
    bonds, angles, torsions, nb = (openmm.HarmonicBondForce(), openmm.HarmonicAngleForce(),
                                  openmm.PeriodicTorsionForce(), openmm.NonbondedForce())
    nb.setNonbondedMethod(openmm.NonbondedForce.NoCutoff)
    for q in charges:
        system.addParticle(12.)
        nb.addParticle(q, .12, .25)
    for row in base.bonds:
        bonds.addBond(row.atom_i, row.atom_j, row.equilibrium_angstrom/10,
                      row.force_constant_kcal_per_mol_angstrom2*418.4)
    for row in base.angles:
        angles.addAngle(row.atom_i, row.atom_j, row.atom_k, row.equilibrium_radians,
                        row.force_constant_kcal_per_mol_radian2*4.184)
    torsions.addTorsion(1, 0, 2, 3, 3, .47, -1.7*4.184)
    for i in range(4):
        for j in range(i+1, 4):
            if (i, j) == (1, 2):
                nb.addException(i, j, charges[i]*charges[j]*.8333333333333, .12, .125)
            else:
                nb.addException(i, j, 0., 1., 0.)
    for force in (bonds, angles, torsions, nb):
        system.addForce(force)
    raw_xml = openmm.XmlSerializer.serialize(system).encode()
    xml_ref = _write(tmp_path/"source-ligand.xml", raw_xml)
    conversion = convert_openmm_system(raw_xml, ligand, TranslationSettings("synthetic-source-audit", 10., 8.))
    receptor = simple_system([[2., 2., 2.], [4.6, .3, .2], [10., 10., 10.]], [.2, -.2, .1], "audit-receptor")
    rsource, rnb = openmm.System(), openmm.NonbondedForce()
    rnb.setNonbondedMethod(openmm.NonbondedForce.NoCutoff)
    for atom in receptor.atoms:
        rsource.addParticle(12.)
        rnb.addParticle(atom.partial_charge_e, .14, .3)
    rsource.addForce(rnb)
    receptor_ref = _write(tmp_path/"source-receptor.xml", openmm.XmlSerializer.serialize(rsource).encode())
    frame = "synthetic_source_audit_frame"
    cross = CrossParameters("synthetic-source-cross", receptor_ref["sha256"], canonical_system_sha256(receptor),
        canonical_topology_sha256(ligand), conversion.base_parameters.fingerprint_sha256, frame,
        tuple(AtomNonbondedParameter(i, 1.4, .3/4.184, atom.partial_charge_e) for i, atom in enumerate(receptor.atoms)),
        6., 4., .35, 4., .1, 2, 5.)
    for key, raw in {
        "ligand": canonical_system_json_bytes(ligand), "receptor": canonical_system_json_bytes(receptor),
        "parameters": conversion.base_parameters.to_dict(), "extensions": conversion.parameters.to_dict(),
        "cross_parameters": cross.to_dict(),
    }.items():
        request[key] = _write(tmp_path/(key+"-source-audit.json"), raw)
    request["pocket"]["coordinate_frame_id"] = frame
    request["pocket"]["source_artifact_sha256"] = xml_ref["sha256"]
    request_path = tmp_path/"request-source-audit.json"
    _write(request_path, request)
    return request_path, tmp_path/"source-ligand.xml", tmp_path/"source-receptor.xml"


def test_full_independent_audit_keeps_original_delta_and_all_denominators(tmp_path):
    paths = packet(tmp_path)
    result = audit_tool.audit(*paths, perturbations=1)
    assert result["all_same_math_checks_passed"]
    assert result["denominator"] == {"requested": 2, "evaluated": 2, "rejected": 0, "passed": 2}
    assert not result["source_XML_equivalence_claimed"]
    assert not result["scientifically_validated"]
    assert not result["intrareceptor_energy_evaluated"]
    assert result["cross_interaction_group_pair_capacity"] == 12
    assert result["coulomb_constants_kcal_angstrom_per_mol_e2"]["native_minus_builtin"] != 0.
    for row in result["snapshots"]:
        assert row["same_math_checks"]["total"]["passed"]
        assert row["original_XML"]["original_minus_same_math_energy_kcal_per_mol"] != 0.
        assert len(row["native"]["internal_forces"]) == 4
        assert len(row["reference_same_math"]["cross_forces"]) == 4


@pytest.mark.parametrize("which", ["ligand", "receptor"])
def test_changed_source_XML_is_rejected_before_contexts(tmp_path, monkeypatch, which):
    paths = packet(tmp_path)
    path = paths[1 if which == "ligand" else 2]
    path.write_bytes(path.read_bytes()+b"\n")
    monkeypatch.setattr(audit_tool, "_reference_context", lambda *args: pytest.fail("context opened before source admission"))
    with pytest.raises(audit_tool.NumericalAuditError, match="not_bound"):
        audit_tool.audit(*paths, perturbations=0)


def test_final_domain_rejection_is_preserved_not_removed(tmp_path):
    paths = packet(tmp_path)
    document = json.loads(paths[0].read_text())
    ligand = audit_tool.load_request({**{k: v for k, v in document.items() if k != "cross_parameters"},
                                     "schema_id": audit_tool.REQUEST_SCHEMA}, "a"*64)[2]
    xyz = ligand.coordinates[0].tolist()
    xyz[0][0] = 100.
    final = tmp_path/"final.json"
    _write(final, {"coordinates_angstrom": xyz})
    result = audit_tool.audit(*paths, perturbations=0, final_coordinates_path=final)
    assert result["denominator"] == {"requested": 2, "evaluated": 1, "rejected": 1, "passed": 1}
    assert not result["all_same_math_checks_passed"]
    assert result["snapshots"][1]["error_type"] == "OpenMMPeriodicApplicabilityError"


def test_independent_same_math_reference_retains_nonexception_pairs():
    state = openmm.System()
    bonds, angles, torsions, nb = (openmm.HarmonicBondForce(), openmm.HarmonicAngleForce(),
                                  openmm.PeriodicTorsionForce(), openmm.NonbondedForce())
    nb.setNonbondedMethod(openmm.NonbondedForce.NoCutoff)
    for q in (.3, -.2):
        state.addParticle(12.)
        nb.addParticle(q, .2, .4)
    for force in (bonds, angles, torsions, nb):
        state.addForce(force)
    reference = audit_tool.same_math_internal_system(openmm.XmlSerializer.serialize(state).encode(), openmm)
    context, integrator = audit_tool._reference_context(reference, openmm)
    energy, force = audit_tool._observe(context, [[0., 0., 0.], [3., 0., 0.]], openmm)
    r, sigma, epsilon, q = 3., 2., .4/4.184, -.06
    c = audit_tool.COULOMB_KCAL_ANGSTROM_PER_MOL_E2
    sr6 = (sigma/r)**6
    expected = 4*epsilon*(sr6**2-sr6)+c*q/r
    derivative = 24*epsilon*(sr6-2*sr6**2)/r-c*q/(r*r)
    assert energy == pytest.approx(expected, abs=1e-12)
    assert force[1, 0] == pytest.approx(-derivative, abs=1e-12)
    del context, integrator


def test_fixed_error_tolerances_do_not_relax_with_large_values():
    result = audit_tool._metrics(1e5, 1e5+1e-5, np.zeros((1, 3)), np.zeros((1, 3)))
    assert not result["passed"]
    result = audit_tool._metrics(0., 0., np.zeros((1, 3)), np.array([[1e-7, 0., 0.]]))
    assert not result["passed"]
