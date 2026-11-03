"""Synthetic geometry contract; no chemical/native packages or real molecules."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tools/check_declared_geometry.py"
FIXTURE = ROOT / "tests/fixtures/declared_geometry_synthetic.json"
spec = importlib.util.spec_from_file_location("declared_geometry", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    return json.loads(FIXTURE.read_text())


class GeometryTests(unittest.TestCase):
    def test_synthetic(self):
        out = m.evaluate(fixture())
        self.assertEqual(out["counts"], {"requested": 2, "satisfied": 2, "violated": 0, "unknown": 0})
        self.assertTrue(out["all_declared_constraints_satisfied"])
        self.assertFalse(out["whole_molecule_validity_assessed"])
        self.assertFalse(out["chemical_identity_verified"])
        self.assertEqual(out["rows"][0]["measurement"], 90)
        self.assertEqual(out["rows"][1]["measurement"]["rms_angstrom"], 0)

    def test_angle_violation_and_boundary_abstention(self):
        data = fixture()
        data["expected_checks"][0]["bounds"] = [91, 100]
        self.assertEqual(m.evaluate(data)["rows"][0]["status"], "VIOLATED")
        data["expected_checks"][0]["bounds"] = [90, 100]
        self.assertEqual(m.evaluate(data)["rows"][0]["reason"], "NUMERIC_BOUNDARY")

    def test_linear_and_zero_angles_measured_not_inferred(self):
        angle, reason = m._angle([[1, 0, 0], [0, 0, 0], [-1, 0, 0]])
        self.assertEqual((angle, reason), (180, None))
        angle, reason = m._angle([[1, 0, 0], [0, 0, 0], [2, 0, 0]])
        self.assertEqual((angle, reason), (0, None))

    def test_degenerate_arm(self):
        data = fixture()
        data["atoms"][0]["xyz"] = [0, 0, 0]
        self.assertEqual(m.evaluate(data)["rows"][0]["reason"], "DEGENERATE_ANGLE")

    def test_missing_and_no_policy_preserve_denominator(self):
        data = fixture()
        data["atoms"].pop(0)
        out = m.evaluate(data)
        self.assertEqual(out["counts"]["unknown"], 2)
        self.assertFalse(out["coverage_complete"])
        data = fixture()
        del data["expected_checks"][0]["policy"]
        out = m.evaluate(data)
        self.assertEqual(out["rows"][0]["reason"], "MISSING_POLICY_OR_THRESHOLD")
        self.assertEqual(out["counts"]["requested"], 2)

    def test_empty_is_not_pass(self):
        data = fixture()
        data["expected_checks"] = []
        out = m.evaluate(data)
        self.assertFalse(out["all_declared_constraints_satisfied"])
        self.assertFalse(out["coverage_complete"])

    def test_tetrahedron_repeated_eigenvalues(self):
        points = [[1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1]]
        value, reason = m._plane(points)
        self.assertIsNone(reason)
        self.assertAlmostEqual(value["rms_angstrom"], 1, places=14)
        data = fixture()
        for atom, point in zip(data["atoms"], points):
            atom["xyz"] = point
        self.assertEqual(m.evaluate(data)["rows"][1]["status"], "VIOLATED")
        data["expected_checks"][1]["max_rms_angstrom"] = 1
        self.assertEqual(m.evaluate(data)["rows"][1]["reason"], "NUMERIC_BOUNDARY")

    def test_plane_coincident_collinear_and_ill_conditioned(self):
        for points in ([[0, 0, 0]] * 4, [[i, 0, 0] for i in range(4)],
                       [[-1, 0, 0], [1, 0, 0], [0, 1e-8, 0], [0, -1e-8, 0]]):
            self.assertEqual(m._plane(points)[1], "DEGENERATE_PLANAR_GROUP")

    def test_rigid_transform_and_atom_permutation(self):
        points = [[1, 0, 0.2], [-1, 0, 0.2], [0, 2, -0.2], [0, -2, -0.2]]
        first = m._plane(points)[0]["rms_angstrom"]
        angle = 0.321
        c, s = math.cos(angle), math.sin(angle)
        transformed = [[c*x-s*y+11, s*x+c*y-7, z+3] for x, y, z in reversed(points)]
        self.assertAlmostEqual(first, m._plane(transformed)[0]["rms_angstrom"], places=13)
        self.assertAlmostEqual(first * 12, m._plane([[12*v for v in p] for p in points])[0]["rms_angstrom"], places=12)

    def test_small_plane_large_translation_regression(self):
        u = math.ulp(1e6)
        points = [[0, 0, 0], [u, 0, u], [0, 2*u, 2*u], [0, 0, 0]]
        shifted = [[v+999999 for v in p] for p in points]
        a, reason_a = m._plane(points)
        b, reason_b = m._plane(shifted)
        self.assertIsNone(reason_a)
        self.assertIsNone(reason_b)
        self.assertLess(abs(a["rms_angstrom"]-b["rms_angstrom"]), 1e-20)
        data = fixture()
        for atom, point in zip(data["atoms"], shifted):
            atom["xyz"] = point
        data["expected_checks"][1]["max_rms_angstrom"] = 1e-11
        self.assertEqual(m.evaluate(data)["rows"][1]["status"], "SATISFIED")

    def test_cli_io_error_does_not_expose_path(self):
        path = "/nonexistent/private-input-identity.json"
        result = subprocess.run([sys.executable, "-I", "-S", str(SOURCE), path], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(path.encode(), result.stderr)
        self.assertEqual(json.loads(result.stderr)["reason"], "INPUT_IO_ERROR")

    def test_known_anisotropic_covariance(self):
        points = [[1, 0, 0], [-1, 0, 0], [0, 2, 0], [0, -2, 0], [0, 0, 3], [0, 0, -3]]
        self.assertAlmostEqual(m._plane(points)[0]["rms_angstrom"], 1/math.sqrt(3), places=14)

    def test_solver_failure_abstains(self):
        with patch.object(m, "_eigenvalues", return_value=(None, None)):
            self.assertEqual(m.evaluate(fixture())["rows"][1]["reason"], "NUMERIC_UNRESOLVED")

    def test_negative_eigenvalue_abstains(self):
        with patch.object(m, "_eigenvalues", return_value=([-0.1, 0.2, 1], 0)):
            self.assertEqual(m.evaluate(fixture())["rows"][1]["reason"], "NUMERIC_UNRESOLVED")

    def test_bad_policy_or_input(self):
        mutations = [
            lambda d: d["atoms"][0].update(xyz=[True, 0, 0]),
            lambda d: d["atoms"][0].update(xyz=[float("nan"), 0, 0]),
            lambda d: d["atoms"][0].update(xyz=[1e7, 0, 0]),
            lambda d: d["atoms"].append(copy.deepcopy(d["atoms"][0])),
            lambda d: d["expected_checks"][0].update(bounds=[91, 90]),
            lambda d: d["expected_checks"][0].update(bounds=[0, 181]),
            lambda d: d["expected_checks"][0].update(atoms=["a", "a", "c"]),
            lambda d: d["expected_checks"][1].update(atoms=["a", "b", "c"]),
            lambda d: d["expected_checks"][1].update(max_rms_angstrom=-1),
            lambda d: d["expected_checks"][0].update(max_rms_angstrom=1),
            lambda d: d.update(units={"coordinates": "nm", "angles": "degree"}),
            lambda d: d.update(cell=[10, 10, 10]),
            lambda d: d["expected_checks"].append(copy.deepcopy(d["expected_checks"][0])),
        ]
        for mutate in mutations:
            data = fixture()
            mutate(data)
            with self.subTest(mutate=mutate), self.assertRaises(m.InputError):
                m.evaluate(data)

    def test_strict_parser_and_budget(self):
        for data in (b'{"a":1,"a":2}', b'{"a":NaN}', b'\xff', b'['*50+b'0'+b']'*50,
                     b' '* (m.MAX_BYTES + 1)):
            with self.subTest(data=data[:30]), self.assertRaises(m.InputError):
                m.parse_bytes(data)

    def test_order_and_no_input_mutation(self):
        data = fixture()
        before = copy.deepcopy(data)
        a = m.evaluate(data)
        b = m.evaluate(data)
        self.assertEqual(a, b)
        self.assertEqual(data, before)
        data["atoms"].append({"id": "unassessed", "xyz": [99, 99, 99]})
        self.assertEqual(m.evaluate(data), a)

    def test_cli_success_is_report_not_validity(self):
        data = fixture()
        data["expected_checks"][0]["bounds"] = [1, 2]
        raw = json.dumps(data).encode()
        result = subprocess.run([sys.executable, "-I", "-S", str(SOURCE), "-"], input=raw, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out["counts"]["violated"], 1)
        self.assertFalse(out["all_declared_constraints_satisfied"])
        self.assertEqual(len(out["input_sha256"]), 64)

    def test_cli_invalid(self):
        result = subprocess.run([sys.executable, "-I", "-S", str(SOURCE), "-"], input=b'{"x":NaN}', capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(json.loads(result.stderr)["status"], "INPUT_ERROR")


if __name__ == "__main__":
    unittest.main()
