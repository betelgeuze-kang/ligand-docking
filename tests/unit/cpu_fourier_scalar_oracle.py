"""Independent scalar mechanics oracle: no Torch or product numerical imports.

Periodic convention: GROMACS IUPAC cis=0, ordered i,j,k,l plane normals.
Reference: https://manual.gromacs.org/documentation/2022/reference-manual/functions/bonded-interactions.html
"""

from copy import deepcopy
import math


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return math.fsum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(a):
    return math.sqrt(dot(a, a))


def distance(a, b):
    return norm(sub(a, b))


def ordered_dihedral(xyz, atoms):
    a, b, c, d = [xyz[i] for i in atoms]
    u, v, w = sub(b, a), sub(c, b), sub(d, c)
    n1, n2 = cross(u, v), cross(v, w)
    lv = norm(v)
    if lv <= 1e-12 or norm(n1) <= 1e-12 or norm(n2) <= 1e-12:
        raise ValueError("singular ordered dihedral")
    return math.atan2(dot(v, cross(n1, n2)) / lv, dot(n1, n2))


def periodic_energy(xyz, atoms, amplitude, periodicity, phase):
    return amplitude * (
        1 + math.cos(periodicity * ordered_dihedral(xyz, atoms) - phase)
    )


def angle_energy(xyz, atoms, equilibrium, k):
    a, b, c = [xyz[i] for i in atoms]
    u, v = sub(a, b), sub(c, b)
    angle = math.atan2(norm(cross(u, v)), dot(u, v))
    return 0.5 * k * (angle - equilibrium) ** 2


def bond_energy(xyz, atoms, equilibrium, k):
    return 0.5 * k * (distance(xyz[atoms[0]], xyz[atoms[1]]) - equilibrium) ** 2


def switched_pair(
    r,
    sigma,
    epsilon,
    qi,
    qj,
    *,
    cutoff,
    switch_start,
    dielectric,
    kappa,
    lj_scale=1.0,
    q_scale=1.0,
):
    if r <= 0:
        raise ValueError("overlap")
    if r >= cutoff:
        return (0.0, 0.0)
    sr6 = (sigma / r) ** 6
    lj = lj_scale * 4 * epsilon * (sr6 * sr6 - sr6)
    q = q_scale * 332.063713299 * qi * qj * math.exp(-kappa * r) / (dielectric * r)
    sw = 1.0
    if r > switch_start:
        t = (r - switch_start) / (cutoff - switch_start)
        sw = 1 - 10 * t**3 + 15 * t**4 - 6 * t**5
    return lj * sw, q * sw


def finite_difference_forces(energy, xyz, h=1e-6):
    forces = []
    for i in range(len(xyz)):
        row = []
        for a in range(3):
            plus, minus = deepcopy(xyz), deepcopy(xyz)
            plus[i][a] += h
            minus[i][a] -= h
            row.append(-(energy(plus) - energy(minus)) / (2 * h))
        forces.append(row)
    return forces


def self_checks():
    checks = 0
    for angle in [-2.7, -1.2, 0.0, 0.6, 2.4]:
        xyz = [[0, 1, 0], [0, 0, 0], [1, 0, 0], [1, math.cos(angle), math.sin(angle)]]
        assert abs(ordered_dihedral(xyz, (0, 1, 2, 3)) - angle) < 1e-14
        assert abs(ordered_dihedral(xyz, (3, 2, 1, 0)) - angle) < 1e-14
        checks += 2
        for k in [-1.7, 0.0, 2.3]:
            for n in [1, 2, 3, 6]:
                for phase in [-0.43, 0.0, math.pi]:
                    observed = periodic_energy(xyz, (0, 1, 2, 3), k, n, phase)
                    assert abs(observed - k * (1 + math.cos(n * angle - phase))) < 1e-13
                    checks += 1
        a = 1.7
        old = periodic_energy(xyz, (0, 1, 2, 3), -a, 3, 0.4)
        wrong = periodic_energy(xyz, (0, 1, 2, 3), a, 3, 0.4 + math.pi)
        assert abs((wrong - old) - 2 * a) < 1e-13
        checks += 1
    return checks


if __name__ == "__main__":
    print({"scalar_oracle_self_checks": self_checks()})


def plain_listed_pair(r, sigma, epsilon, qi, qj, qscale=0.83333):
    if r <= 0:
        raise ValueError("overlap")
    sr6 = (sigma / r) ** 6
    return 4 * epsilon * (sr6 * sr6 - sr6), 332.063713299 * qscale * qi * qj / r


def fixed_cross_analytic(
    ligand_xyz,
    receptor_xyz,
    ligand_parameters,
    receptor_parameters,
    *,
    cutoff=10.0,
    switch_start=8.0,
    dielectric=1.0,
    kappa=0.0,
    minimum=0.35,
):
    """Scalar independent pair derivative; no graph/Torch/product helpers."""
    energies = [[], []]
    force = [[[] for _ in range(3)] for _ in ligand_xyz]
    active = 0
    for i, x in enumerate(ligand_xyz):
        a = ligand_parameters[i]
        for j, y in enumerate(receptor_xyz):
            b = receptor_parameters[j]
            d = sub(x, y)
            r = norm(d)
            if r < minimum:
                raise ValueError("cross minimum distance")
            if r >= cutoff:
                continue
            active += 1
            sigma = 0.5 * (a["sigma_angstrom"] + b["sigma_angstrom"])
            epsilon = math.sqrt(a["epsilon_kcal_per_mol"] * b["epsilon_kcal_per_mol"])
            s6 = (sigma / r) ** 6
            lj = 4 * epsilon * (s6 * s6 - s6)
            dl = 24 * epsilon * (s6 - 2 * s6 * s6) / r
            q = (
                332.063713299
                * a["charge_e"]
                * b["charge_e"]
                * math.exp(-kappa * r)
                / (dielectric * r)
            )
            dq = -q * (kappa + 1 / r)
            sw = 1.0
            ds = 0.0
            if r > switch_start:
                t = (r - switch_start) / (cutoff - switch_start)
                sw = 1 - 10 * t**3 + 15 * t**4 - 6 * t**5
                ds = (-30 * t * t + 60 * t**3 - 30 * t**4) / (cutoff - switch_start)
            energies[0].append(lj * sw)
            energies[1].append(q * sw)
            radial = -((dl + dq) * sw + (lj + q) * ds) / r
            for axis in range(3):
                force[i][axis].append(radial * d[axis])
    return (
        {
            "cross_lennard_jones": math.fsum(energies[0]),
            "cross_screened_coulomb": math.fsum(energies[1]),
        },
        [[math.fsum(values) for values in row] for row in force],
        active,
    )
