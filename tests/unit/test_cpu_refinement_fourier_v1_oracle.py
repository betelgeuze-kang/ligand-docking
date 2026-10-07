"""Independent scalar components/all-coordinate FD against additive proposal."""

import math
from dataclasses import replace
import pytest
import torch
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Residue,
    Chain,
    StructureProvenance,
    canonical_topology_sha256,
    canonical_system_sha256,
)
from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.physics.reference_parameters import (
    HarmonicBondParameter,
    HarmonicAngleParameter,
)
from betelgeuze_product.cpu_refinement_fourier_v1 import (
    FourierParameters,
    NonbondedParameter,
    SignedPeriodicTorsionParameter,
    OrderedPeriodicImproperParameter,
    FourierInternalEvaluator,
    FourierCrossParameters,
    FourierEnvironment,
)
from tests.unit.cpu_fourier_scalar_oracle import (
    distance,
    periodic_energy,
    bond_energy,
    angle_energy,
    finite_difference_forces,
)

torch.set_num_threads(1)


def system(xyz, bonds, charges=None):
    charges = charges or [0.0] * len(xyz)
    return AllAtomSystem(
        "independent-synthetic",
        tuple(
            Atom(i, "C" + str(i), "C", 6, 0, partial_charge_e=charges[i])
            for i in range(len(xyz))
        ),
        tuple(Bond(n, *sorted(p)) for n, p in enumerate(bonds)),
        (
            Residue(
                0,
                "LIG",
                0,
                1,
                tuple(range(len(xyz))),
                entity_type="non_polymer",
                hetero=True,
            ),
        ),
        (Chain(0, "L", (0,)),),
        torch.tensor([xyz], dtype=torch.float64),
        StructureProvenance(
            source_format="synthetic",
            source_id="independent-scalar-fixture",
            parser_name="test",
            parser_version="1",
        ),
    )


def fixture(kind, phi, k, n, phase):
    xyz = [
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [1.0, math.cos(phi), math.sin(phi)],
    ]
    bonds = [(0, 1), (1, 2), (2, 3)] if kind == "proper" else [(0, 1), (1, 2), (1, 3)]
    angles = (
        [(0, 1, 2), (1, 2, 3)]
        if kind == "proper"
        else [(0, 1, 2), (0, 1, 3), (2, 1, 3)]
    )
    s = system(xyz, bonds)
    bp = tuple(
        HarmonicBondParameter(*b, distance(xyz[b[0]], xyz[b[1]]) * 0.97, 2.1)
        for b in bonds
    )
    ap = tuple(HarmonicAngleParameter(*a, 1.23, 1.8) for a in angles)
    args = (
        {"torsions": (SignedPeriodicTorsionParameter(0, 1, 2, 3, n, phase, k),)}
        if kind == "proper"
        else {
            "periodic_impropers": (
                OrderedPeriodicImproperParameter(
                    0, 1, 2, 3, n, phase, k, star_center=1
                ),
            )
        }
    )
    p = FourierParameters(
        "independent-synthetic",
        "1",
        canonical_topology_sha256(s),
        tuple(NonbondedParameter(i, 1.0, 0.0, 0.0) for i in range(4)),
        bonds=bp,
        angles=ap,
        excluded_pairs=tuple((i, j) for i in range(4) for j in range(i + 1, 4)),
        **args,
    )

    def components(x):
        return {
            "harmonic_bond": math.fsum(
                bond_energy(
                    x,
                    (b.atom_i, b.atom_j),
                    b.equilibrium_angstrom,
                    b.force_constant_kcal_per_mol_angstrom2,
                )
                for b in bp
            ),
            "harmonic_angle": math.fsum(
                angle_energy(
                    x,
                    (a.atom_i, a.atom_j, a.atom_k),
                    a.equilibrium_radians,
                    a.force_constant_kcal_per_mol_radian2,
                )
                for a in ap
            ),
            "periodic_torsion"
            if kind == "proper"
            else "ordered_periodic_improper": periodic_energy(
                x, (0, 1, 2, 3), k, n, phase
            ),
        }

    return s, p, components


def eval_internal(s, p):
    return FourierInternalEvaluator(p).evaluate(
        s,
        build_compact_radius_graph(
            s.coordinates,
            RadiusGraphConfig(10.0, max_neighbors=256, max_atoms_per_cell=256),
        ),
    )


@pytest.mark.parametrize("kind", ["proper", "improper"])
@pytest.mark.parametrize("phi", [-2.7, -1.2, 0.0, 0.6, 2.4])
def test_signed_components_and_all_coordinates(kind, phi):
    for k in [-1.7, 0.0, 2.3]:
        for n in [1, 2, 3, 6]:
            for phase in [-0.43, 0.0, math.pi]:
                s, p, oracle = fixture(kind, phi, k, n, phase)
                r = eval_internal(s, p)
                xyz = s.coordinates[0].tolist()
                components = oracle(xyz)
                for name, value in components.items():
                    assert float(r.component_energies[name][0]) == pytest.approx(
                        value, abs=1e-9, rel=1e-10
                    )
                assert float(r.term.energy[0]) == pytest.approx(
                    math.fsum(components.values()), abs=1e-9, rel=1e-10
                )
                force = finite_difference_forces(
                    lambda x: math.fsum(oracle(x).values()), xyz
                )
                torch.testing.assert_close(
                    r.term.forces[0],
                    torch.tensor(force, dtype=torch.float64),
                    atol=2e-5,
                    rtol=2e-6,
                )


def test_multiple_signed_terms_and_offset_not_lost():
    s, p, oracle = fixture("proper", 0.6, -1.7, 3, 0.4)
    p = replace(
        p,
        torsions=(
            *p.torsions,
            SignedPeriodicTorsionParameter(0, 1, 2, 3, 2, -0.3, 0.8),
        ),
    )
    r = eval_internal(s, p)
    expected = periodic_energy(
        s.coordinates[0].tolist(), (0, 1, 2, 3), -1.7, 3, 0.4
    ) + periodic_energy(s.coordinates[0].tolist(), (0, 1, 2, 3), 0.8, 2, -0.3)
    assert float(r.component_energies["periodic_torsion"][0]) == pytest.approx(
        expected, abs=1e-10
    )


def test_cross_zero_lj_preserves_charged_atom():
    rec = system([[0.0, 0.0, 0.0]], [], [-0.2])
    lig = system([[2.0, 0.0, 0.0]], [], [0.3])
    p = FourierParameters(
        "zero-lj",
        "1",
        canonical_topology_sha256(lig),
        (NonbondedParameter(0, 3.0, 0.4, 0.3),),
    )
    cross = FourierCrossParameters(
        "zero-lj",
        "a" * 64,
        canonical_system_sha256(rec),
        canonical_topology_sha256(lig),
        p.fingerprint_sha256,
        "test",
        (NonbondedParameter(0, 0.0, 0.0, -0.2),),
        10.0,
        8.0,
        0.35,
        1.0,
        0.0,
        128,
        0.0,
    )
    terms, force, count = FourierEnvironment(rec, cross).evaluate_cross(lig, p)
    expected = 332.063713299 * 0.3 * (-0.2) / 2.0
    assert count == 1 and float(terms["cross_lennard_jones"][0]) == 0.0
    assert float(terms["cross_screened_coulomb"][0]) == pytest.approx(
        expected, abs=1e-12
    )
    assert float(force[0, 0, 0]) == pytest.approx(expected / 2.0, abs=1e-12)
    assert cross.receptor_atoms[0].sigma_angstrom == 0.0
    with pytest.raises(ValueError):
        NonbondedParameter(0, 0.0, 0.1, -0.2)


@pytest.mark.parametrize("r", [2.0, 4.5, 12.0])
def test_listed_override_unswitched_excluded_once(r):
    from betelgeuze_product.cpu_refinement_fourier_v1 import ListedPairParameter
    from tests.unit.cpu_fourier_scalar_oracle import plain_listed_pair

    s = system([[0.0, 0.0, 0.0], [r, 0.0, 0.0]], [], [0.3, -0.2])
    p = FourierParameters(
        "listed",
        "1",
        canonical_topology_sha256(s),
        (NonbondedParameter(0, 3.0, 0.5, 0.3), NonbondedParameter(1, 4.0, 0.7, -0.2)),
        excluded_pairs=((0, 1),),
        listed_pairs=(ListedPairParameter(0, 1, 2.0, 0.2, 0.83333),),
    )
    row = eval_internal(s, p)
    lj, q = plain_listed_pair(r, 2.0, 0.2, 0.3, -0.2, 0.83333)
    assert float(
        row.component_energies["listed_pair_lennard_jones"][0]
    ) == pytest.approx(lj, abs=1e-11)
    assert float(row.component_energies["listed_pair_coulomb"][0]) == pytest.approx(
        q, abs=1e-11
    )
    assert float(row.component_energies["lennard_jones"][0]) == 0.0
    assert float(row.component_energies["screened_coulomb"][0]) == 0.0
    assert float(row.term.energy[0]) == pytest.approx(lj + q, abs=1e-11)
    expected = finite_difference_forces(
        lambda x: sum(
            plain_listed_pair(distance(x[0], x[1]), 2.0, 0.2, 0.3, -0.2, 0.83333)
        ),
        s.coordinates[0].tolist(),
    )
    torch.testing.assert_close(
        row.term.forces[0],
        torch.tensor(expected, dtype=torch.float64),
        atol=2e-5,
        rtol=2e-6,
    )
    # Neither dielectric/screening nor ordinary cutoff modifiers affect listed pairs.
    changed = eval_internal(
        s, replace(p, dielectric=7.0, screening_kappa_per_angstrom=0.2)
    )
    assert torch.equal(row.term.energy, changed.term.energy)
    assert torch.equal(row.term.forces, changed.term.forces)
    with pytest.raises(ValueError):
        replace(p, excluded_pairs=())


def test_override_cannot_be_replaced_by_uniform_lj_scaling():
    from tests.unit.cpu_fourier_scalar_oracle import plain_listed_pair

    def lj(r, sigma, eps):
        return plain_listed_pair(r, sigma, eps, 0.0, 0.0)[0]

    factor = lj(3.0, 2.0, 0.2) / lj(3.0, 3.5, math.sqrt(0.5 * 0.7))
    assert abs(lj(5.0, 2.0, 0.2) - factor * lj(5.0, 3.5, math.sqrt(0.5 * 0.7))) > 1e-4
