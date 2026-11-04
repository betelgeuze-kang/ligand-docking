"""Pure failure-path tests; these do not qualify molecular equivalence."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import check_posebusters_subset_inputs as probe

try:
    import numpy as np
except ImportError:
    np = None


class _Mol:
    def __init__(self, payload, atoms=4, bonds=2):
        self.payload, self.atoms, self.bonds = payload, atoms, bonds

    def ToBinary(self, flags):
        return self.payload

    def GetNumAtoms(self):
        return self.atoms

    def GetNumBonds(self):
        return self.bonds


class _Delegate:
    def __init__(self, result):
        self.result = result
        self.action = None
        self.stats = dict.fromkeys(("calls", "identity_calls", "fast_path_calls", "fallback_calls",
                                  "bonded_fast_path_calls", "bondless_fast_path_calls"), 0)

    def document(self):
        return dict(self.stats)

    def __call__(self, mol, mask):
        for key in ("calls", "fast_path_calls", "bonded_fast_path_calls"):
            self.stats[key] += 1
        return self.action(mol, mask) if self.action is not None else self.result


@unittest.skipIf(np is None, "numpy unavailable")
class AuditorFailureTests(unittest.TestCase):
    def setUp(self):
        self.source = _Mol(b"source")
        self.expected = _Mol(b"same-subset", atoms=2, bonds=1)
        self.observed = _Mol(b"same-subset", atoms=2, bonds=1)
        self.mask = np.array([True, False, True, False], dtype=bool)
        self.reference = Mock(return_value=self.expected)
        self.runtime = SimpleNamespace(
            Chem=SimpleNamespace(PropertyPickleOptions=SimpleNamespace(AllProps=1, CoordsAsDouble=2)),
            volume=SimpleNamespace(_filter_by_mask=self.reference),
        )
        self.delegate = _Delegate(self.observed)
        self.rows = []
        for patcher in (
            patch.object(probe.subset, "ExactSubsetFilter", return_value=self.delegate),
            patch.object(probe, "molecule_inventory", side_effect=lambda mol, chem: {
                "atoms": mol.GetNumAtoms(), "bonds": mol.GetNumBonds()}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.auditor = probe.AuditedSubsetFilter(self.runtime, self.rows)

    def test_success_binds_exact_binary_mask_and_routing(self):
        self.assertIs(self.auditor(self.source, self.mask), self.observed)
        row = self.rows[0]
        self.assertEqual(row["status"], "passed")
        self.assertEqual(row["retained_atom_indices"], [0, 2])
        self.assertEqual(row["source_binary_sha256"], probe.sha(b"source"))
        self.assertEqual(row["reference_binary_sha256"], row["candidate_binary_sha256"])
        self.assertEqual(row["mask_sha256"], probe.sha(self.mask.tobytes()))
        self.assertEqual(row["routing_delta"]["bonded_fast_path_calls"], 1)
        self.assertEqual(row["retained_bonds"], 1)
        self.assertGreaterEqual(row["reference_filter_ns"], 0)
        self.assertGreaterEqual(row["candidate_filter_ns"], 0)

    def test_binary_mismatch_is_recorded_and_propagated(self):
        self.observed.payload = b"different"
        with self.assertRaisesRegex(Exception, "binary differs"):
            self.auditor(self.source, self.mask)
        self.assertEqual(self.rows[0]["status"], "failed")
        self.assertNotEqual(self.rows[0]["reference_binary_sha256"], self.rows[0]["candidate_binary_sha256"])

    def test_both_reference_and_candidate_source_mutation_fail(self):
        for branch in ("reference", "candidate"):
            with self.subTest(branch=branch):
                self.source.payload = b"source"
                self.reference.side_effect = None
                self.delegate.action = None
                def mutate(mol, mask):
                    mol.payload = b"mutated"
                    return self.observed
                if branch == "reference":
                    self.reference.side_effect = mutate
                else:
                    self.delegate.action = mutate
                with self.assertRaisesRegex(Exception, branch + " subset mutated source"):
                    self.auditor(self.source, self.mask)
                self.assertEqual(self.rows[-1]["status"], "failed")
        self.assertEqual(self.delegate.stats["calls"], 1)

    def test_both_reference_and_candidate_mask_mutation_fail(self):
        for branch in ("reference", "candidate"):
            with self.subTest(branch=branch):
                self.mask[:] = [True, False, True, False]
                self.reference.side_effect = None
                self.delegate.action = None
                def mutate(mol, mask):
                    mask[0] = not bool(mask[0])
                    return self.observed
                if branch == "reference":
                    self.reference.side_effect = mutate
                else:
                    self.delegate.action = mutate
                with self.assertRaisesRegex(Exception, branch + " subset mutated distance mask"):
                    self.auditor(self.source, self.mask)
                self.assertEqual(self.rows[-1]["status"], "failed")

    def test_reference_and_candidate_exceptions_propagate_without_retry(self):
        for branch in ("reference", "candidate"):
            with self.subTest(branch=branch):
                self.reference.side_effect = None
                self.delegate.action = None
                error = RuntimeError(branch + " sentinel")
                def fail(mol, mask):
                    raise error
                if branch == "reference":
                    self.reference.side_effect = fail
                else:
                    self.delegate.action = fail
                with self.assertRaises(RuntimeError) as caught:
                    self.auditor(self.source, self.mask)
                self.assertIs(caught.exception, error)
                self.assertEqual(self.rows[-1]["error"], {"type": "RuntimeError", "message": str(error)})
        self.assertEqual(self.reference.call_count, 2)
        self.assertEqual(self.delegate.stats["calls"], 1)

    def test_candidate_mask_shape_and_dtype_mutation_cannot_pass_as_unchanged(self):
        for field, value in (("shape", (2, 2)), ("dtype", np.dtype("uint8"))):
            with self.subTest(field=field):
                self.mask = np.array([True, False, True, False], dtype=bool)
                original_bytes = self.mask.tobytes()
                def mutate_metadata(mol, mask):
                    setattr(mask, field, value)
                    self.assertEqual(mask.tobytes(), original_bytes)
                    return self.observed
                self.delegate.action = mutate_metadata
                with self.assertRaises(Exception):
                    self.auditor(self.source, self.mask)
                self.assertEqual(self.rows[-1]["status"], "failed")


class AdmissionGateTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"status": "passed", "binary_equal": True, "source_unchanged": True,
                      "mask_unchanged": True} for _ in range(20)]
        self.stats = {
            "calls": 20, "identity_calls": 0, "fast_path_calls": 20, "fallback_calls": 0,
            "bonded_fast_path_calls": 20, "bondless_fast_path_calls": 0,
            "fast_path_errors": 0, "fallback_errors": 0,
            "source_atoms_fast_path": 80, "retained_atoms_fast_path": 40, "removed_atoms_fast_path": 40,
            "source_bonds_fast_path": 40, "retained_bonds_fast_path": 20, "removed_bonds_fast_path": 20,
            "fallback_reasons": {},
        }

    def test_valid_pure_accounting_fixture(self):
        probe.validate_audit(self.rows, self.stats)

    def test_missing_rows_failed_rows_and_non_boolean_equality_fail(self):
        mutations = (
            lambda rows: rows.pop(), lambda rows: rows[0].update(status="failed"),
            lambda rows: rows[0].update(binary_equal=1),
            lambda rows: rows[0].update(source_unchanged=False),
            lambda rows: rows[0].pop("mask_unchanged"),
        )
        for mutate in mutations:
            rows = deepcopy(self.rows)
            mutate(rows)
            with self.assertRaises(Exception):
                probe.validate_audit(rows, self.stats)

    def test_missing_actual_bonded_work_and_bad_accounting_fail(self):
        mutations = (
            {"bonded_fast_path_calls": 0}, {"retained_bonds_fast_path": 0},
            {"bonded_fast_path_calls": True}, {"retained_bonds_fast_path": True},
            {"fast_path_errors": 1}, {"fallback_errors": 1}, {"calls": 19},
            {"bondless_fast_path_calls": 1}, {"removed_atoms_fast_path": 0},
            {"removed_bonds_fast_path": 0}, {"fallback_reasons": {"unsupported": 1}},
        )
        for changed in mutations:
            with self.subTest(changed=changed), self.assertRaises(Exception):
                probe.validate_audit(self.rows, {**self.stats, **changed})


class AdmissionCliTests(unittest.TestCase):
    def invoke(self, root, output):
        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            return probe.main(["--input-root", str(root / "inputs"), "--bundle-sha256", "0" * 64,
                               "--runtime-root", str(root / "runtime"), "--output", str(output)])

    def test_probe_failure_writes_atomic_failed_report_and_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "reports" / "failure.json"
            with patch.object(probe, "run_probe", side_effect=RuntimeError("admission sentinel")) as run:
                self.assertEqual(self.invoke(root, output), 1)
            run.assert_called_once()
            report = json.loads(output.read_text())
            self.assertEqual(report["status"], "failed")
            self.assertIs(report["all_passed"], False)
            self.assertFalse(report["performance_claim_eligible"])
            self.assertEqual(report["error"]["message"], "admission sentinel")
            self.assertEqual(list(output.parent.glob("*.pending")), [])

    def test_existing_report_is_not_overwritten_and_probe_is_not_started(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "existing.json"
            output.write_bytes(b"existing evidence\n")
            with patch.object(probe, "run_probe") as run:
                self.assertEqual(self.invoke(root, output), 1)
            run.assert_not_called()
            self.assertEqual(output.read_bytes(), b"existing evidence\n")
            self.assertEqual(list(root.glob("*.pending")), [])

    def test_rejected_output_inside_input_never_creates_a_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / "inputs"
            inputs.mkdir()
            output = inputs / "forbidden.json"
            with patch.object(probe, "run_probe") as run:
                self.assertEqual(self.invoke(root, output), 1)
            run.assert_not_called()
            self.assertFalse(output.exists(), "an invalid output must not modify immutable inputs")
            self.assertEqual(list(inputs.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
