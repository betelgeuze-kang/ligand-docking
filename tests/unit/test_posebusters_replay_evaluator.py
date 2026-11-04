"""Cache/serialization tests plus mandatory-in-cloud frozen-runtime equivalence.

PB_REPLAY_REQUIRE_FROZEN_RUNTIME=1 turns missing dependencies into a test failure.
The fake molecules below test cache isolation/control flow only; scientific
equivalence is separately checked with the real pinned RDKit/PoseBusters runtime.
"""

from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import posebusters_replay_evaluator as replay

try:
    import numpy as np
    import pandas as pd
except ImportError:
    np = None
    pd = None


class _FakeMol:
    def __init__(self, atoms_or_mol, coords=None):
        if isinstance(atoms_or_mol, _FakeMol):
            self.atoms = list(atoms_or_mol.atoms)
            self.coords = atoms_or_mol.coords.copy()
            self.props = deepcopy(atoms_or_mol.props)
        else:
            self.atoms = list(atoms_or_mol)
            self.coords = np.array(coords, dtype=float).reshape((-1, 3))
            self.props = {"_Name": "pose"}

    def ToBinary(self, flags):
        return json.dumps([self.atoms, self.coords.tolist(), self.props], sort_keys=True).encode()

    def GetNumAtoms(self):
        return len(self.atoms)

    def GetConformer(self):
        return self

    def GetPositions(self):
        return self.coords.copy()


def _fake_dependencies():
    calls = {"mask": 0, "filter": 0, "shape": []}

    def get_atom_type_mask(mol, ignore_types):
        calls["mask"] += 1
        if "unsupported" in ignore_types:
            raise ValueError("unsupported category")
        return [atom not in ignore_types for atom in mol.atoms]

    def filter_by_mask(mol, mask):
        calls["filter"] += 1
        if mask.sum() == len(mask):
            return mol
        result = _FakeMol([atom for atom, keep in zip(mol.atoms, mask) if keep], mol.coords[mask])
        result.props = deepcopy(mol.props)
        return result

    def pairwise(x, y):
        return np.linalg.norm(x[:, None, :] - y[None, :, :], axis=-1)

    def shape(pred, cond, **kwargs):
        calls["shape"].append((cond.GetNumAtoms(), dict(kwargs)))
        return 0.075

    volume = SimpleNamespace(
        np=np, Mol=_FakeMol, get_atom_type_mask=get_atom_type_mask,
        _filter_by_mask=filter_by_mask, _pairwise_distance=pairwise, ShapeTverskyIndex=shape,
    )
    Chem = SimpleNamespace(Mol=_FakeMol, PropertyPickleOptions=SimpleNamespace(AllProps=65535, CoordsAsDouble=65536))
    return Chem, volume, calls


class AdmissionAndSourceTests(unittest.TestCase):
    def test_invalid_inputs_fail_before_loading_runtime(self):
        valid = dict(records=(b"pose\n$$$$\n",), native_payload=b"native", receptor_payload=b"receptor", mode="baseline")
        for changed in ({"mode": "search"}, {"records": []}, {"records": ()},
                        {"records": (b"x",) * 65}, {"records": (bytearray(b"x"),)},
                        {"native_payload": b""}, {"receptor_payload": "pdb"}):
            with self.subTest(changed=changed), patch.object(replay, "_load_runtime") as load:
                with self.assertRaises(replay.ReplayEvaluationError):
                    replay.run_evaluation(**(valid | changed))
                load.assert_not_called()

    def test_changed_source_bytes_rejected_without_fallback(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "private.py").write_bytes(b"original")
            expected = {"private.py": replay._sha256(b"original")}
            with patch.object(replay, "UPSTREAM_SOURCE_SHA256", expected):
                self.assertEqual(replay._verify_sources(root), expected)
                (root / "private.py").write_bytes(b"modified")
                with self.assertRaisesRegex(replay.ReplayEvaluationError, "source mismatch"):
                    replay._verify_sources(root)
                (root / "private.py").unlink()
                with self.assertRaisesRegex(replay.ReplayEvaluationError, "missing frozen"):
                    replay._verify_sources(root)

    def test_concurrent_calls_rejected(self):
        replay._RUN_LOCK.acquire()
        try:
            with self.assertRaisesRegex(replay.ReplayEvaluationError, "concurrent"):
                replay.run_evaluation(records=(b"x",), native_payload=b"n", receptor_payload=b"r", mode="baseline")
        finally:
            replay._RUN_LOCK.release()


@unittest.skipIf(np is None or pd is None, "numpy/pandas unavailable")
class CanonicalReportTests(unittest.TestCase):
    def test_exact_float_bits_and_missing_types(self):
        self.assertNotEqual(replay._typed_scalar(0.0), replay._typed_scalar(-0.0))
        nan = struct.unpack(">d", bytes.fromhex("7ff8000000000042"))[0]
        self.assertEqual(replay._typed_scalar(nan)["binary64_be"], "7ff8000000000042")
        missing = [replay._typed_scalar(x) for x in (pd.NA, pd.NaT, None, float("nan"))]
        self.assertEqual(len({x["missing"] for x in missing}), 4)
        self.assertNotEqual(replay._typed_scalar(1.0)["type"], replay._typed_scalar(np.float64(1.0))["type"])
        self.assertEqual(replay._typed_scalar(np.int64(2**60))["decimal"], str(2**60))
        self.assertEqual(replay._typed_scalar(np.bool_(True))["value"], True)
        json.dumps(missing, allow_nan=False)
        with self.assertRaisesRegex(replay.ReplayEvaluationError, "scalar type"):
            replay._typed_scalar(object())

    def _report(self, mols):
        index = pd.MultiIndex.from_tuples([(str(mol), mol.props["_Name"]) for mol in mols], names=["file", "molecule"])
        return pd.DataFrame({"numeric": [0.0, -0.0], "nullable": [pd.NA, None], "boolean": [True, False]}, index=index)

    def test_validated_addresses_normalize_but_values_order_and_dtype_remain(self):
        mols = (_FakeMol(["protein"], [[0, 0, 0]]), _FakeMol(["protein"], [[1, 0, 0]]))
        copies = tuple(_FakeMol(mol) for mol in mols)
        pb = SimpleNamespace(_get_name=lambda mol, i: mol.props["_Name"])
        records = (b"first", b"second")
        kwargs = dict(records=records, PoseBusters=pb)
        first = replay._canonical_report(self._report(mols), predicted=mols, **kwargs)
        other = replay._canonical_report(self._report(copies), predicted=copies, **kwargs)
        self.assertEqual(first, other)
        self.assertEqual(first["columns"], ["numeric", "nullable", "boolean"])
        self.assertEqual(first["dtypes"][0]["name"], "float64")
        self.assertNotEqual(first["rows"][0]["cells"][0], first["rows"][1]["cells"][0])
        for mol in mols:
            self.assertNotIn(str(mol), json.dumps(first))
        wrong = self._report(mols).iloc[::-1]
        with self.assertRaisesRegex(replay.ReplayEvaluationError, "identity/order"):
            replay._canonical_report(wrong, predicted=mols, **kwargs)


@unittest.skipIf(np is None, "numpy unavailable")
class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.Chem, self.volume, self.calls = _fake_dependencies()
        self.receptor = _FakeMol(["protein", "waters", "hydrogens"], [[0, 0, 0], [1, 0, 0], [2, 0, 0]])
        self.measurements = replay._Measurements()
        self.context = ("case_receptor_sha", "native_sha", "config_sha", "code_sha")
        self.cache = replay._PreparedReceptorCategories(
            self.receptor, context=self.context, Chem=self.Chem, volume=self.volume, measurements=self.measurements)

    def select(self, ignore_types, **kwargs):
        return self.cache.select(self.receptor, ignore_types, context=self.context, label="volume", **kwargs)

    def test_private_copies_and_policy_specific_cache(self):
        first = self.select({"hydrogens"})
        first.coords[:] = 500
        first.props["mutation"] = "not in cache"
        second = self.select(["hydrogens"])
        self.assertNotIn("mutation", second.props)
        np.testing.assert_array_equal(second.coords, [[0, 0, 0], [1, 0, 0]])
        self.assertIsNot(first, second)
        self.assertEqual(self.calls["mask"], 1)
        self.assertEqual(self.select({"waters", "hydrogens"}).GetNumAtoms(), 1)
        self.assertEqual(self.calls["mask"], 2)
        self.cache.verify()
        self.assertEqual(self.cache.document(), dict(hits=1, misses=2, entries=2, max_entries=4))

    def test_context_or_receptor_identity_change_rejected(self):
        self.select(set())
        for receptor, context in ((_FakeMol(self.receptor), self.context), (self.receptor, ("other",))):
            with self.assertRaisesRegex(replay.ReplayEvaluationError, "context changed"):
                self.cache.select(receptor, set(), context=context, label="volume")
        # A new invocation gets independent state for the same molecule object.
        other = replay._PreparedReceptorCategories(self.receptor, context=("other",), Chem=self.Chem,
                                                   volume=self.volume, measurements=replay._Measurements())
        other.select(self.receptor, set(), context=("other",), label="volume")
        self.assertEqual(other.document()["misses"], 1)

    def test_source_and_cached_prototype_mutations_rejected(self):
        self.select(set())
        self.receptor.coords[0, 0] = 0.000000000001
        with self.assertRaisesRegex(replay.ReplayEvaluationError, "input mutated"):
            self.select(set())
        self.receptor.coords[0, 0] = 0
        prototype, _ = self.cache._entries[()]
        prototype.props["pdb_metadata"] = "changed"
        with self.assertRaisesRegex(replay.ReplayEvaluationError, "prototype mutated"):
            self.select(set())

    def test_failures_not_cached_and_cache_bounded(self):
        with self.assertRaises(ValueError):
            self.select({"unsupported"})
        self.assertEqual(self.cache.document()["entries"], 0)
        for ignored in (set(), {"hydrogens"}, {"waters"}, {"protein"}):
            self.select(ignored)
        with self.assertRaisesRegex(replay.ReplayEvaluationError, "exceeded"):
            self.select({"waters", "hydrogens"})

    def adapted(self, pred, **params):
        return replay._prepared_volume_overlap(pred, self.receptor, cache=self.cache, context=self.context,
                                              volume=self.volume, measurements=self.measurements, label="volume", **params)

    def test_empty_category_and_pose_specific_filter_are_not_reused(self):
        pred = _FakeMol(["ligand"], [[0, 0, 0]])
        empty = self.adapted(pred, ignore_types={"protein", "waters", "hydrogens"})
        self.assertTrue(np.isnan(empty["results"]["volume_overlap"]))
        self.assertIs(empty["results"]["no_volume_clash"], True)
        self.assertEqual(self.calls["shape"], [])
        self.adapted(pred, ignore_types={"hydrogens"})
        pred.coords[:] = 100
        distant = self.adapted(pred, ignore_types={"hydrogens"})
        self.assertTrue(np.isnan(distant["results"]["volume_overlap"]))
        self.assertEqual(len(self.calls["shape"]), 1)
        self.assertEqual(self.cache.document()["hits"], 1)

    def test_ignore_hydrogens_and_inclusive_thresholds_preserved(self):
        pred = _FakeMol(["ligand"], [[0, 0, 0]])
        result = self.adapted(pred, ignore_types={"hydrogens"}, clash_cutoff=0.075)
        self.assertTrue(result["results"]["no_volume_clash"])
        self.assertEqual(self.calls["shape"][-1][1], dict(alpha=1, beta=0, vdwScale=0.8, ignoreHs=True))
        result = self.adapted(pred, ignore_types=set(), clash_cutoff=np.nextafter(0.075, -np.inf))
        self.assertFalse(result["results"]["no_volume_clash"])
        self.assertIs(self.calls["shape"][-1][1]["ignoreHs"], False)
        # A receptor atom exactly at search_distance*vdw_scale must be retained.
        pred.coords[:] = (4.8, 0, 0)
        self.adapted(pred, ignore_types={"hydrogens", "waters"})
        self.assertEqual(self.calls["shape"][-1][0], 1)

    def test_injected_filter_receives_each_pose_mask(self):
        pred = _FakeMol(["ligand"], [[0, 0, 0]])
        calls = []

        def distance_filter(mol, mask):
            calls.append(mask.copy())
            return self.volume._filter_by_mask(mol, mask)

        first = self.adapted(pred, distance_filter=distance_filter)
        self.assertEqual(len(calls), 1)
        self.assertEqual(first, self.adapted(pred))
        pred.coords[:] = 100
        self.adapted(pred, distance_filter=distance_filter)
        self.assertEqual(len(calls), 2)
        self.assertFalse(np.array_equal(calls[0], calls[1]))

    def test_injected_filter_failure_is_not_hidden(self):
        pred = _FakeMol(["ligand"], [[0, 0, 0]])

        def failing_filter(mol, mask):
            raise RuntimeError("subset sentinel")

        with self.assertRaisesRegex(RuntimeError, "subset sentinel"):
            self.adapted(pred, distance_filter=failing_filter)

    def test_diagnostic_profiler_restored_on_exception(self):
        self.assertIsNone(sys.getprofile())
        with self.assertRaisesRegex(RuntimeError, "sentinel"):
            with replay._VolumeTrace(self.volume, self.measurements, "volume"):
                self.volume.get_atom_type_mask(self.receptor, set())
                raise RuntimeError("sentinel")
        self.assertIsNone(sys.getprofile())
        stages = self.measurements.volume_document()
        self.assertEqual(stages[0]["stage"], "category_mask")
        self.assertEqual(stages[0]["calls"], 1)


class FrozenRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [name for name in ("rdkit", "posebusters", "torch") if importlib.util.find_spec(name) is None]
        if missing:
            message = f"frozen runtime dependencies unavailable: {missing}"
            if os.environ.get("PB_REPLAY_REQUIRE_FROZEN_RUNTIME") == "1":
                raise AssertionError(message)
            raise unittest.SkipTest(message)
        # Any installed but changed version/source is a failure, never a skip.
        cls.runtime = replay._load_runtime()
        cls.Chem = cls.runtime.Chem

    def molecules_and_payloads(self):
        from rdkit.Chem import AllChem

        Chem = self.Chem
        native = Chem.AddHs(Chem.MolFromSmiles("CCO"))
        self.assertEqual(AllChem.EmbedMolecule(native, randomSeed=42), 0)
        AllChem.UFFOptimizeMolecule(native)
        native.SetProp("_Name", "native")
        native_payload = (Chem.MolToMolBlock(native).rstrip("\n") + "\n$$$$\n").encode("ascii")
        records = []
        for rank, delta in enumerate((0.0, 7.0), 1):
            mol = Chem.Mol(native)
            conf = mol.GetConformer()
            for index, xyz in enumerate(conf.GetPositions()):
                conf.SetAtomPosition(index, (float(xyz[0]) + delta, float(xyz[1]), float(xyz[2])))
            mol.SetProp("_Name", f"synthetic_engine_v2_rank_{rank}")
            records.append((Chem.MolToMolBlock(mol).rstrip("\n") + "\n$$$$\n").encode("ascii"))
        receptor_payload = (
            "ATOM      1  CA  ALA A   1       4.000   0.000   0.000  1.00 20.00           C  \n"
            "HETATM    2  O   HOH A   2       0.000   4.000   0.000  1.00 20.00           O  \n"
            "HETATM    3 ZN    ZN A   3       0.000   0.000   4.000  1.00 20.00          ZN  \n"
            "HETATM    4  C1  LIG A   4      -4.000   0.000   0.000  1.00 20.00           C  \n"
            "ATOM      5  H   ALA A   1       4.000   1.000   0.000  1.00 20.00           H  \n"
            "END\n"
        ).encode("ascii")
        return tuple(records), native_payload, receptor_payload

    def test_real_all_modes_match_entire_report_and_legacy_results(self):
        records, native, receptor = self.molecules_and_payloads()
        outputs = {mode: replay.run_evaluation(records=records, native_payload=native,
                                              receptor_payload=receptor, mode=mode)
                   for mode in ("baseline", "profile", "prepared_receptor")}
        baseline = outputs["baseline"]
        for mode, output in outputs.items():
            with self.subTest(mode=mode):
                self.assertEqual(output["fullReport"], baseline["fullReport"])
                self.assertEqual(output["legacy_outcomes"], baseline["legacy_outcomes"])
                self.assertEqual(output["input_immutability"]["before"], output["input_immutability"]["after"])
                self.assertTrue(output["input_immutability"]["verified"])
                self.assertEqual(self.runtime.energy.get_average_energy.cache_info().currsize, 0)
                json.dumps(output, allow_nan=False)
        self.assertEqual(baseline["timings"]["modules"], [])
        self.assertFalse(baseline["timings"]["instrumented"])
        self.assertTrue(outputs["profile"]["timings"]["profile_timing_is_diagnostic"])
        prepared = outputs["prepared_receptor"]
        self.assertFalse(prepared["timings"]["profile_timing_is_diagnostic"])
        self.assertEqual(prepared["receptor_preparation"], dict(hits=4, misses=4, entries=4, max_entries=4))
        self.assertEqual(len(prepared["timings"]["modules"]), 18)
        self.assertTrue(all(row["calls"] == 2 for row in prepared["timings"]["modules"]))

    def test_real_volume_empty_and_missing_pdb_metadata_match(self):
        records, native, receptor = self.molecules_and_payloads()
        predicted, _, condition = self.runtime.runner._posebusters_molecules(
            output_payload=b"".join(records), native_payload=native, receptor_payload=receptor,
            expected_pose_count=2)
        for cond in (condition, self.Chem.Mol(predicted[0])):
            measurements = replay._Measurements()
            context = ("one invocation",)
            cache = replay._PreparedReceptorCategories(cond, context=context, Chem=self.Chem,
                                                      volume=self.runtime.volume, measurements=measurements)
            for ignored in (set(), {"hydrogens"}, {"protein", "waters", "organic_cofactors", "inorganic_cofactors", "hydrogens"}):
                for pred in predicted:
                    params = dict(ignore_types=ignored, clash_cutoff=0.075, vdw_scale=0.5)
                    original = self.runtime.volume.check_volume_overlap(pred, cond, **params)
                    adapted = replay._prepared_volume_overlap(
                        pred, cond, cache=cache, context=context, volume=self.runtime.volume,
                        measurements=measurements, label="volume", **params)
                    self.assertEqual(
                        {key: replay._typed_scalar(value) for key, value in original["results"].items()},
                        {key: replay._typed_scalar(value) for key, value in adapted["results"].items()},
                    )
            cache.verify()


if __name__ == "__main__":
    unittest.main()
