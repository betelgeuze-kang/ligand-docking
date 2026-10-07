import math
import unittest
from tests.unit.cpu_fourier_scalar_oracle import (
    ordered_dihedral,
    periodic_energy,
    finite_difference_forces,
    switched_pair,
    self_checks,
)


class OracleTests(unittest.TestCase):
    def test_known_angles_and_signed_constants(self):
        self.assertEqual(self_checks(), 195)

    def test_signed_torque(self):
        for phi in [-2.1, -0.4, 0.9, 2.3]:
            for k in [-1.7, 0.0, 2.3]:
                for n in [1, 2, 3, 6]:
                    phase = 0.43
                    x = [
                        [0, 1, 0],
                        [0, 0, 0],
                        [1, 0, 0],
                        [1, math.cos(phi), math.sin(phi)],
                    ]
                    f = finite_difference_forces(
                        lambda y: periodic_energy(y, (0, 1, 2, 3), k, n, phase), x
                    )
                    torque = f[3][1] * (-math.sin(phi)) + f[3][2] * math.cos(phi)
                    self.assertAlmostEqual(
                        torque, k * n * math.sin(n * phi - phase), delta=2e-8
                    )
                    for a in range(3):
                        self.assertAlmostEqual(
                            sum(row[a] for row in f), 0.0, delta=2e-8
                        )

    def test_zero_lj_retains_coulomb(self):
        lj, q = switched_pair(
            2.0,
            1.5,
            0.0,
            0.3,
            -0.2,
            cutoff=10.0,
            switch_start=8.0,
            dielectric=1.0,
            kappa=0.0,
        )
        self.assertEqual(lj, 0.0)
        self.assertAlmostEqual(q, 332.063713299 * 0.3 * (-0.2) / 2.0)

    def test_ordering_is_not_symmetric_atom_set(self):
        xyz = [[0.0, 1.0, 0.2], [0.0, 0.0, 0.0], [1.0, 0.1, 0.0], [1.2, 0.7, 0.9]]
        self.assertNotAlmostEqual(
            periodic_energy(xyz, (0, 1, 2, 3), -1.7, 3, 0.43),
            periodic_energy(xyz, (0, 2, 1, 3), -1.7, 3, 0.43),
        )

    def test_singular_rejected(self):
        with self.assertRaises(ValueError):
            ordered_dihedral([[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]], (0, 1, 2, 3))


if __name__ == "__main__":
    unittest.main(verbosity=2)
