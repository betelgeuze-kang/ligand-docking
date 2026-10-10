"""Synthetic contracts only: geometry measurements do not validate chemistry."""
from dataclasses import replace
import json
import math

import pytest
import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, Atom, Bond, Chain, Residue, StructureProvenance,
    canonical_topology_sha256,
)
from betelgeuze_engine_v2.physics.reference_forcefield import _torsion_angle
from betelgeuze_engine_v2.physics.reference_parameters import HarmonicAngleParameter, HarmonicBondParameter
from betelgeuze_product.cpu_refinement_diagnostics_v1.geometry import geometry_changes
from betelgeuze_product.cpu_refinement_fourier_v1.parameters import (
    FourierParameters, NonbondedParameter, SignedPeriodicTorsionParameter,
    OrderedPeriodicImproperParameter,
)
from betelgeuze_product.cpu_refinement_linear_angle_v1.parameters import (
    LinearAngleParameters, LinearHarmonicAngleParameter,
)
from betelgeuze_product.cpu_refinement_v1_2.provenance import ResearchError, canonical


def fixture(phi=0.7):
    xyz = [[0., 1., 0.], [0., 0., 0.], [1., 0., 0.],
           [1., math.cos(phi), math.sin(phi)], [-1., 0., 0.]]
    ligand = AllAtomSystem(
        system_id="diagnostic-synthetic",
        atoms=tuple(Atom(index=i, name=f"C{i}", element="C", atomic_number=6,
                         residue_index=0, partial_charge_e=0.) for i in range(5)),
        bonds=tuple(Bond(index=n, atom_i=1, atom_j=i) for n, i in enumerate((0, 2, 3, 4))),
        residues=(Residue(index=0, name="LIG", chain_index=0, sequence_number=1,
                          atom_indices=tuple(range(5)), entity_type="non_polymer", hetero=True),),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=torch.tensor([xyz], dtype=torch.float64),
        provenance=StructureProvenance(source_format="unit", source_id="diagnostic-synthetic",
                                      source_sha256="a"*64, parser_name="unit", parser_version="1"),
    )
    base = FourierParameters("diagnostic", "1", canonical_topology_sha256(ligand),
        tuple(NonbondedParameter(i, 1., 0., 0.) for i in range(5)),
        bonds=(HarmonicBondParameter(0, 1, 1.1, 100.),),
        angles=(HarmonicAngleParameter(0, 1, 2, 1.4, 20.),),
        torsions=(SignedPeriodicTorsionParameter(0, 1, 2, 3, 1, .2, -1.5),
                  SignedPeriodicTorsionParameter(0, 1, 2, 3, 3, -.4, 2.)),
        periodic_impropers=(OrderedPeriodicImproperParameter(0, 1, 2, 3, 2, .1, -3., 1),))
    return ligand, LinearAngleParameters(base, (LinearHarmonicAngleParameter(2, 1, 4, math.pi, 40.),))


def value(row, label):
    return float.fromhex(row[label]["value_hex"])


def test_all_source_rows_equilibrium_changes_and_no_mutation():
    ligand, parameters = fixture()
    before_xyz = ligand.coordinates.clone()
    before_parameters = canonical(parameters.to_dict())
    xyz = ligand.coordinates.clone()
    xyz[0, 0] *= 1.2
    xyz[0, 4] = torch.tensor([-math.cos(.2), math.sin(.2), 0.])
    trial = ligand.with_coordinates(xyz, operation="synthetic-change")
    result = geometry_changes(ligand, trial, parameters)
    assert [len(result[k]) for k in ("bonds", "ordinary_angles", "linear_angles", "proper_torsions", "periodic_impropers")] == [1, 1, 1, 2, 1]
    bond = result["bonds"][0]
    assert value(bond, "parent") == 1.
    assert value(bond, "trial") == pytest.approx(1.2)
    assert float.fromhex(bond["change_from_parent_hex"]) == pytest.approx(.2)
    assert float.fromhex(bond["parent_deviation_from_equilibrium_hex"]) == pytest.approx(-.1)
    assert float.fromhex(bond["trial_deviation_from_equilibrium_hex"]) == pytest.approx(.1)
    linear = result["linear_angles"][0]
    assert value(linear, "parent") == math.pi
    assert value(linear, "trial") == pytest.approx(math.pi-.2)
    assert float.fromhex(linear["trial_deviation_from_equilibrium_hex"]) == pytest.approx(-.2)
    assert value(result["ordinary_angles"][0], "trial") == pytest.approx(math.pi/2)
    assert result["proper_torsions"][1]["source_row_index"] == 1
    assert result["proper_torsions"][0]["source_parameter_row"]["amplitude_kcal_per_mol"] == (-1.5).hex()
    assert result["periodic_impropers"][0]["source_parameter_row"]["star_center"] == 1
    assert "equilibrium_hex" not in result["proper_torsions"][0]
    assert result["parameter_fingerprint_sha256"] == parameters.fingerprint_sha256
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    assert canonical(result) == canonical(geometry_changes(ligand, trial, parameters))
    assert torch.equal(ligand.coordinates, before_xyz)
    assert torch.equal(trial.coordinates, xyz)
    assert canonical(parameters.to_dict()) == before_parameters


@pytest.mark.parametrize("start,end,delta", [(170., -170., 20.), (-170., 170., -20.), (30., -40., -70.)])
def test_signed_proper_improper_and_wrapped_changes(start, end, delta):
    parent, parameters = fixture(math.radians(start))
    target, _ = fixture(math.radians(end))
    trial = parent.with_coordinates(target.coordinates, operation="synthetic-change")
    result = geometry_changes(parent, trial, parameters)
    for row in result["proper_torsions"] + result["periodic_impropers"]:
        assert value(row, "parent") == pytest.approx(math.radians(start))
        assert value(row, "trial") == pytest.approx(math.radians(end))
        assert value(row, "trial") == _torsion_angle(trial.coordinates, trial, 0, 1, 2, 3).item()
        assert float.fromhex(row["change_from_parent_hex"]) == pytest.approx(math.radians(delta))


@pytest.mark.parametrize("endpoint", ["parent", "trial"])
@pytest.mark.parametrize("degeneracy", ["central_bond", "first_plane", "second_plane"])
def test_degenerate_torsions_explicit_unavailable_without_row_loss(endpoint, degeneracy):
    ligand, parameters = fixture()
    xyz = ligand.coordinates.clone()
    if degeneracy == "central_bond":
        xyz[0, 2] = xyz[0, 1]
    elif degeneracy == "first_plane":
        xyz[0, 0] = torch.tensor([-1., 0., 0.])
    else:
        xyz[0, 3] = torch.tensor([2., 0., 0.])
    degenerate = ligand.with_coordinates(xyz, operation="synthetic-degenerate")
    parent, trial = (degenerate, ligand) if endpoint == "parent" else (ligand, degenerate)
    result = geometry_changes(parent, trial, parameters)
    assert len(result["proper_torsions"]) == 2
    for row in result["proper_torsions"] + result["periodic_impropers"]:
        assert row[endpoint] == {"available": False, "value_hex": None,
                                 "unavailable_reason": "degenerate_torsion_geometry"}
        assert row["change_available"] is False
        assert row["change_from_parent_hex"] is None
        assert row["change_unavailable_reason"] == "parent_or_trial_geometry_unavailable"
    json.dumps(result, allow_nan=False)


def test_exact_parallel_angle_and_zero_length_unavailability():
    ligand, parameters = fixture()
    xyz = ligand.coordinates.clone()
    xyz[0, 4] = xyz[0, 2]
    trial = ligand.with_coordinates(xyz, operation="synthetic-parallel")
    assert value(geometry_changes(ligand, trial, parameters)["linear_angles"][0], "trial") == 0.
    xyz[0, 4] = xyz[0, 1]
    trial = ligand.with_coordinates(xyz, operation="synthetic-zero")
    row = geometry_changes(ligand, trial, parameters)["linear_angles"][0]
    assert row["trial"]["unavailable_reason"] == "zero_length_angle_vector"
    assert row["trial_deviation_from_equilibrium_hex"] is None


def test_rigid_motion_preserves_geometry_and_fourier_only_empty_linear_collection():
    ligand, parameters = fixture()
    rotation = torch.tensor([[.36, -.48, .8], [.8, .6, 0.], [-.48, .64, .6]], dtype=torch.float64)
    trial = ligand.with_coordinates(ligand.coordinates @ rotation.T + .25, operation="synthetic-rigid")
    result = geometry_changes(ligand, trial, parameters.base_parameters)
    assert result["linear_angles"] == []
    for name in ("bonds", "ordinary_angles", "proper_torsions", "periodic_impropers"):
        for row in result[name]:
            assert float.fromhex(row["change_from_parent_hex"]) == pytest.approx(0., abs=1.e-14)


def test_rejects_unbound_models_indices_and_nonfinite_arithmetic():
    ligand, parameters = fixture()
    with pytest.raises(ResearchError, match="explicit Fourier"):
        geometry_changes(ligand, ligand, object())
    with pytest.raises(ResearchError, match="topology mismatch"):
        geometry_changes(ligand, ligand, replace(parameters.base_parameters, topology_sha256="b"*64))
    bad_row = replace(parameters.base_parameters.bonds[0], atom_i=7)
    with pytest.raises(ResearchError, match="index outside"):
        geometry_changes(ligand, ligand, replace(parameters.base_parameters, bonds=(bad_row,)))
    xyz = ligand.coordinates.clone()
    xyz[0, 0, 0] = 1.e308
    huge = ligand.with_coordinates(xyz, operation="synthetic-overflow")
    with pytest.raises(ResearchError):
        geometry_changes(ligand, huge, parameters)


def test_changed_atom_identity_and_nonfinite_input_rejected():
    ligand, parameters = fixture()
    altered = replace(ligand, atoms=(replace(ligand.atoms[0], name="OTHER"),) + ligand.atoms[1:])
    with pytest.raises(ResearchError, match="topology mismatch"):
        geometry_changes(ligand, altered, parameters)
    ligand.coordinates[0, 0, 0] = float("nan")
    with pytest.raises(ResearchError, match="finite|float64"):
        geometry_changes(ligand, ligand, parameters)


def test_zero_change_retains_every_empty_and_nonempty_collection():
    ligand, parameters = fixture()
    result = geometry_changes(ligand, ligand, parameters)
    for name in ("bonds", "ordinary_angles", "linear_angles", "proper_torsions", "periodic_impropers"):
        for row in result[name]:
            assert row["change_from_parent_hex"] == 0.0.hex()
            assert row["parent"] == row["trial"]
    empty = replace(parameters.base_parameters, bonds=(), angles=(), torsions=(), periodic_impropers=())
    result = geometry_changes(ligand, ligand, empty)
    for name in ("bonds", "ordinary_angles", "linear_angles", "proper_torsions", "periodic_impropers"):
        assert result[name] == []
