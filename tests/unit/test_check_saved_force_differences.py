"""Synthetic contract tests only; no molecular engine is run or imported."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "tools/check_saved_force_differences.py"
spec = importlib.util.spec_from_file_location("saved_force_checker", SOURCE)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def fixture():
    return json.loads((ROOT / "tests/fixtures/saved_force_differences_synthetic.json").read_text())


def synthetic(coords=None, energy=None, force=None):
    """Analytic test function is independent of the production FD calculation."""
    coords = coords or [[0.5, -0.75, 1.25]]
    energy = energy or (lambda xyz: sum((j + 1) * v * v / 2 for row in xyz for j, v in enumerate(row)))
    force = force or [[-(j + 1) * v for j, v in enumerate(row)] for row in coords]
    data = {"schema": checker.SCHEMA,
            "units": {"energy": "kcal/mol", "length": "angstrom", "force": "kcal/mol/angstrom"},
            "force_convention": "minus_energy_gradient",
            "context": {key: "synthetic-" + key for key in sorted(checker.CONTEXT_KEYS)},
            "atom_ids": ["atom-%d" % i for i in range(len(coords))], "expected_terms": ["quadratic"],
            "steps": [2**-12, 2**-13, 2**-14],
            "policy": {"force_atol": 1e-8, "force_rtol": 1e-8, "stability_atol": 1e-3,
                       "stability_rtol": 1e-8, "roundoff_fraction": 0.25,
                       "energy_resolution": 0.0, "domain": "smooth"},
            "baseline": {"coordinates": copy.deepcopy(coords), "geometry_sha256": checker.geometry_sha256(coords),
                         "energies": {"quadratic": energy(coords)}, "forces": {"quadratic": force}},
            "samples": []}
    data["context_sha256"] = checker.canonical_sha256(data["context"])
    for i in range(len(coords)):
        for axis in range(3):
            for h in data["steps"]:
                for sign in (-1, 1):
                    shifted = copy.deepcopy(coords)
                    shifted[i][axis] += sign * h
                    data["samples"].append({"atom_index": i, "axis": axis, "h": h, "sign": sign,
                                            "status": "ok", "context_sha256": data["context_sha256"],
                                            "coordinates": shifted,
                                            "geometry_sha256": checker.geometry_sha256(shifted),
                                            "energies": {"quadratic": energy(shifted)}})
    return data


class SavedForceDifferencesTests(unittest.TestCase):
    def test_fixed_fixture_and_analytic_quadratic(self):
        self.assertEqual(fixture(), synthetic())
        result = checker.analyze(fixture())
        self.assertEqual(result["status"], "consistent_under_supplied_policy")
        self.assertEqual(result["expected_axes"], 3)
        self.assertEqual(result["expected_samples"], 18)
        self.assertEqual(result["informative_axis_channels"], 3)
        self.assertTrue(result["coverage_complete"])
        self.assertFalse(result["scientific_validation"])
        self.assertEqual(result["engine_evaluations_performed"], 0)

    def test_coupled_quadratic_detects_axis_permutation(self):
        coords = [[.5, -.75, 1.25], [.25, .5, -.5]]
        energy = lambda c: sum(v*v/2 for row in c for v in row) + c[0][0]*c[1][1]
        force = [[-v for v in row] for row in coords]
        force[0][0] -= coords[1][1]
        force[1][1] -= coords[0][0]
        data = synthetic(coords, energy, force)
        self.assertEqual(checker.analyze(data)["status"], "consistent_under_supplied_policy")
        force[0][0], force[0][2] = force[0][2], force[0][0]
        self.assertEqual(checker.analyze(data)["status"], "inconsistent_under_supplied_policy")

    def test_wrong_sign_and_one_bad_axis(self):
        for mode in ("sign", "one"):
            data = fixture()
            values = data["baseline"]["forces"]["quadratic"][0]
            if mode == "sign":
                values[:] = [-v for v in values]
            else:
                values[2] += 0.1
            result = checker.analyze(data)
            self.assertEqual(result["status"], "inconsistent_under_supplied_policy")
            self.assertGreater(result["axis_channel_counts"]["inconsistent_under_supplied_policy"], 0)

    def test_missing_axis_failed_and_missing_channel_preserve_denominator(self):
        for mode in ("axis", "failed", "channel", "baseline"):
            data = fixture()
            if mode == "axis":
                data["samples"] = [row for row in data["samples"] if row["axis"] != 2]
            elif mode == "failed":
                row = data["samples"][0]
                row["status"] = "failed"
                for key in ("coordinates", "geometry_sha256", "energies"):
                    row.pop(key)
            elif mode == "channel":
                data["samples"][0]["energies"] = {}
            else:
                data["baseline"]["forces"] = {}
            result = checker.analyze(data)
            self.assertEqual(result["status"], "unknown")
            self.assertEqual(result["expected_samples"], 18)
            self.assertEqual(result["expected_axis_channels"], 3)
            self.assertFalse(result["coverage_complete"])

    def test_nonuniform_float64_offsets(self):
        data = synthetic([[1.0, .3, -.7]])
        # Decimal steps produce unequal representable +/- offsets near x=1.
        newsteps = [1e-4, 5e-5, 2.5e-5]
        data["steps"] = newsteps
        for row in data["samples"]:
            old_steps = [2**-12, 2**-13, 2**-14]
            row["h"] = newsteps[old_steps.index(row["h"])]
            c = copy.deepcopy(data["baseline"]["coordinates"])
            c[row["atom_index"]][row["axis"]] += row["sign"] * row["h"]
            row["coordinates"] = c
            row["geometry_sha256"] = checker.geometry_sha256(c)
            row["energies"] = {"quadratic": sum((j+1)*v*v/2 for r in c for j, v in enumerate(r))}
        self.assertEqual(checker.analyze(data)["status"], "consistent_under_supplied_policy")

    def test_geometry_context_and_convention_mismatches_rejected(self):
        for mode in ("hash", "geometry", "context", "convention", "units"):
            data = fixture()
            if mode == "hash":
                data["baseline"]["geometry_sha256"] = "0"*64
            elif mode == "geometry":
                row = data["samples"][0]
                row["coordinates"][0][2] += .01
                row["geometry_sha256"] = checker.geometry_sha256(row["coordinates"])
            elif mode == "context":
                data["samples"][0]["context_sha256"] = "0"*64
            elif mode == "convention":
                data["force_convention"] = "energy_gradient"
            else:
                data["units"]["length"] = "nm"
            with self.assertRaises(checker.EvidenceError):
                checker.analyze(data)

    def test_duplicate_or_undeclared_samples_rejected(self):
        for mode in ("duplicate", "step", "axis", "bool"):
            data = fixture()
            if mode == "duplicate":
                data["samples"].append(copy.deepcopy(data["samples"][0]))
            elif mode == "step":
                data["samples"][0]["h"] *= 3
            elif mode == "axis":
                data["samples"][0]["axis"] = 3
            else:
                data["samples"][0]["sign"] = True
            with self.assertRaises(checker.EvidenceError):
                checker.analyze(data)

    def test_large_energy_offset_and_declared_energy_resolution_are_unknown(self):
        data = synthetic(energy=lambda c: 1e16 + sum((j+1)*v*v/2 for row in c for j, v in enumerate(row)))
        self.assertEqual(checker.analyze(data)["status"], "unknown")
        data = fixture()
        data["policy"]["energy_resolution"] = 1e-6
        self.assertEqual(checker.analyze(data)["status"], "unknown")

    def test_zero_signal_does_not_qualify(self):
        data = synthetic(energy=lambda c: 0.0, force=[[0.0, 0.0, 0.0]])
        result = checker.analyze(data)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["informative_axis_channels"], 0)
        self.assertEqual(result["axis_channel_counts"]["consistent_under_supplied_policy"], 3)

    def test_cusp_and_domain_not_smooth(self):
        data = synthetic([[0.0, 0.5, 0.75]], energy=lambda c: abs(c[0][0]), force=[[0.0, 0.0, 0.0]])
        result = checker.analyze(data)
        self.assertEqual(result["status"], "unknown")
        self.assertIn("one_sided_slopes_unresolved", result["axes"][0]["reasons"])
        for domain in ("unknown", "nonsmooth"):
            data = fixture()
            data["policy"]["domain"] = domain
            self.assertEqual(checker.analyze(data)["status"], "unknown")

    def test_unresolved_coordinate_step(self):
        data = synthetic([[1e16, 2e16, 3e16]], energy=lambda c: 1.0, force=[[1., 2., 3.]])
        result = checker.analyze(data)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["axes"][0]["stencils"][0]["reason"], "unresolved_displacement")

    def test_quartic_ladder_reports_truncation_without_best_h(self):
        data = synthetic([[.5, .75, 1.25]], energy=lambda c: sum(v**4 for row in c for v in row),
                         force=[[-4*.5**3, -4*.75**3, -4*1.25**3]])
        data["policy"]["stability_atol"] = 1e-12
        data["policy"]["stability_rtol"] = 0.0
        result = checker.analyze(data)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(len(result["axes"][0]["stencils"]), 3)
        self.assertEqual(result["required_h_count"], 3)

    def test_bad_policy_and_denominator(self):
        for key, value in (("force_rtol", 1.0), ("roundoff_fraction", 0.0),
                           ("force_atol", 0), ("stability_atol", float("nan"))):
            data = fixture()
            data["policy"][key] = value
            with self.assertRaises(checker.EvidenceError):
                checker.analyze(data)
        data = fixture()
        data["expected_terms"].append("missing-term")
        result = checker.analyze(data)
        self.assertEqual(result["expected_axis_channels"], 6)
        self.assertEqual(result["axis_channel_counts"]["unknown"], 3)

    def test_component_defect_cannot_hide_in_total(self):
        data = fixture()
        data["expected_terms"] = ["total", "component_a", "component_b"]
        base = data["baseline"]
        e = base["energies"].pop("quadratic")
        f = base["forces"].pop("quadratic")
        base["energies"] = {"total": e, "component_a": 2*e, "component_b": -e}
        base["forces"] = {"total": f, "component_a": [[2*v for v in row] for row in f],
                          "component_b": [[-v for v in row] for row in f]}
        base["forces"]["component_a"][0][0] += .1
        base["forces"]["component_b"][0][0] -= .1
        for sample in data["samples"]:
            e = sample["energies"].pop("quadratic")
            sample["energies"] = {"total": e, "component_a": 2*e, "component_b": -e}
        result = checker.analyze(data)
        self.assertEqual(result["status"], "inconsistent_under_supplied_policy")
        self.assertEqual(result["axis_channel_counts"]["inconsistent_under_supplied_policy"], 2)

    def test_nonfinite_derived_slope_gap_is_unknown(self):
        policy = fixture()["policy"]
        result = checker._stencil(0.0, 1e-12, 1e-12, 1e-320, 1e-320, 0.0, policy)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason"], "unresolved_arithmetic")
        json.dumps(result, allow_nan=False)

    def test_all_exported_numbers_finite_under_extreme_arithmetic(self):
        policy = fixture()["policy"]
        for args in ((0., 1e308, 1e308, 1., 1., 0.),
                     (0., 1., -1., float("inf"), 1., 0.),
                     (-1e308, 1e308, -1e308, 1., 1., 0.),
                     (0., 1e-12, 1e-12, 1e-320, 1e-320, 0.)):
            result = checker._stencil(*args, policy)
            json.dumps(result, allow_nan=False)
            self.assertTrue(all(math.isfinite(v) for v in result.values() if type(v) is float))
        json.dumps(checker.analyze(fixture()), allow_nan=False)

    def test_single_lucky_h_does_not_hide_bad_sample(self):
        data = fixture()
        data["samples"][1]["energies"]["quadratic"] += .001
        result = checker.analyze(data)
        self.assertEqual(result["status"], "unknown")
        self.assertIn("finite_differences_not_stable", result["axes"][0]["reasons"])
        self.assertEqual(len(result["axes"][0]["stencils"]), 3)

    def test_malformed_sample_and_loose_policy_do_not_qualify(self):
        data = fixture()
        data["policy"]["force_atol"] = 1e20
        self.assertEqual(checker.analyze(data)["status"], "unknown")
        data = fixture()
        data["samples"][0]["status"] = "failed"
        with self.assertRaises(checker.EvidenceError):
            checker.analyze(data)
        data = fixture()
        data["baseline"]["coordinates"][0][0] = True
        with self.assertRaises(checker.EvidenceError):
            checker.analyze(data)

    def test_json_rejects_duplicates_nonfinite_and_deep_input(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'['*33+b'0'+b']'*33, b'\xff'):
            with self.assertRaises(checker.EvidenceError):
                checker.load_bytes(raw)
        with self.assertRaises(checker.EvidenceError):
            checker.load_bytes(b' '*(checker.MAX_BYTES+1))

    def test_output_deterministic_and_no_private_label_echo(self):
        data = fixture()
        data["context"]["engine"] = "private-label"
        data["context_sha256"] = checker.canonical_sha256(data["context"])
        for row in data["samples"]:
            row["context_sha256"] = data["context_sha256"]
        a = checker.analyze(data)
        self.assertEqual(a, checker.analyze(copy.deepcopy(data)))
        self.assertNotIn("private-label", json.dumps(a))

    def test_cli_digest_exit_and_no_writes(self):
        path = ROOT / "tests/fixtures/saved_force_differences_synthetic.json"
        with tempfile.TemporaryDirectory() as tmp:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            command = [sys.executable, "-I", "-S", str(SOURCE), str(path), "--expected-sha256", digest]
            process = subprocess.run(command, cwd=tmp, capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(json.loads(process.stdout)["status"], "consistent_under_supplied_policy")
            self.assertEqual(list(Path(tmp).iterdir()), [])
            process = subprocess.run(command[:-1]+["0"*64], cwd=tmp, capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 2)
            self.assertEqual(process.stdout, "")
            self.assertNotIn(str(path), process.stderr)


if __name__ == "__main__":
    unittest.main()
