"""Context ownership tests and mandatory frozen molecular qualification.

Fake molecules test lifetime/control flow only. FrozenRunnerContextTests tests
the real runner/PoseBusters path; PB_INTEGRATION_REQUIRE_FROZEN_RUNTIME=1 makes
missing chemistry dependencies a failure instead of an explicit local skip.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache, partial
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import posebusters_evaluator_context as contexts
from tools import posebusters_replay_evaluator as replay
from tools.redocking_development_p1 import DevelopmentObservation

try:
    import numpy as np
except ImportError:
    np = None


class _Mol:
    def __init__(self, atoms_or_mol, positions=None):
        if isinstance(atoms_or_mol, _Mol):
            self.atoms = atoms_or_mol.atoms[:]
            self.positions = atoms_or_mol.positions.copy()
            self.props = deepcopy(atoms_or_mol.props)
        else:
            self.atoms = list(atoms_or_mol)
            self.positions = np.array(positions, dtype=float).reshape((-1, 3))
            self.props = {"_Name": "fixture"}

    def ToBinary(self, flags):
        return json.dumps([self.atoms, self.positions.tolist(), self.props], sort_keys=True).encode()

    def GetNumAtoms(self):
        return len(self.atoms)

    def GetConformer(self):
        return self

    def GetPositions(self):
        return self.positions.copy()


def _fake_runtime():
    calls = {"mask": 0, "filter": 0, "original": 0}

    def mask(mol, ignored):
        calls["mask"] += 1
        return [kind not in ignored for kind in mol.atoms]

    def select(mol, keep):
        calls["filter"] += 1
        if keep.sum() == len(keep):
            return mol
        other = _Mol([a for a, k in zip(mol.atoms, keep) if k], mol.positions[keep])
        other.props = deepcopy(mol.props)
        return other

    def original(mol_pred, mol_cond, *, ignore_types):
        calls["original"] += 1
        select(mol_cond, np.array(mask(mol_cond, ignore_types)))
        return {"results": {"volume_overlap": 0.075, "no_volume_clash": False}}

    @lru_cache(maxsize=128)
    def energy(reference):
        return 1.0

    volume = SimpleNamespace(
        Mol=_Mol, np=np, get_atom_type_mask=mask, _filter_by_mask=select,
        check_volume_overlap=original,
        _pairwise_distance=lambda x, y: np.linalg.norm(x[:, None, :] - y[None, :, :], axis=-1),
        ShapeTverskyIndex=lambda *args, **kwargs: 0.075,
    )
    Chem = SimpleNamespace(
        Mol=_Mol,
        PropertyPickleOptions=SimpleNamespace(AllProps=65535, CoordsAsDouble=65536),
    )

    class PoseBusters:
        def __init__(self, *, config, top_n):
            assert config == "redock"
            self.top_n = top_n
            self.config = {"modules": [{"parameters": {"ignore_types": {"hydrogens"}}}]}
            self._initialize_modules()

        def _initialize_modules(self):
            self.module_name = ["Volume overlap with protein"]
            self.fname = ["volume_overlap"]
            self.module_func = [partial(original, ignore_types={"hydrogens"})]

        def bust(self, predicted, native, receptor, *, full_report):
            assert full_report and len(predicted) == self.top_n
            rows = []
            for pred in predicted:
                energy("reference")
                rows.append(self.module_func[0](mol_pred=pred, mol_cond=receptor))
            return rows

    return SimpleNamespace(
        Chem=Chem, volume=volume, PoseBusters=PoseBusters,
        energy=SimpleNamespace(get_average_energy=energy),
        source_hashes={"fixture.py": "c" * 64}, versions={"fixture": "1"},
    ), calls


class ContextContractTests(unittest.TestCase):
    def make_context(self, **kwargs):
        with patch.object(contexts, "_pipeline_identity", return_value="a" * 64):
            return contexts.PoseBustersEvaluatorContext("fixture", **kwargs)

    def test_options_rejected_before_runtime_or_identity_loading(self):
        for kwargs in ({"mode": "unknown"}, {"mode": []},
                       {"collect_metrics": 1}, {"report_observer": 5}):
            with self.subTest(kwargs=kwargs), patch.object(contexts, "_pipeline_identity") as identity:
                with self.assertRaises(contexts.PoseBustersContextError):
                    contexts.PoseBustersEvaluatorContext("fixture", **kwargs)
                identity.assert_not_called()
        with patch.object(contexts, "_pipeline_identity") as identity:
            with self.assertRaises(contexts.PoseBustersContextError):
                contexts.PoseBustersEvaluatorContext("../other")
            identity.assert_not_called()

    def test_inputs_are_exactly_bound_for_context_lifetime(self):
        context = self.make_context()
        context.assert_inputs(native_payload=b"n", receptor_payload=b"r")
        context.assert_inputs(native_payload=b"n", receptor_payload=b"r")
        with self.assertRaisesRegex(contexts.PoseBustersContextError, "another input"):
            context.assert_inputs(native_payload=b"n", receptor_payload=b"r2")
        with self.assertRaisesRegex(contexts.PoseBustersContextError, "has failed"):
            context.assert_inputs(native_payload=b"n", receptor_payload=b"r")
        self.assertFalse(context.summary()["healthy"])
        context.close()

    def test_observation_identity_cannot_cross_evaluation_strategies(self):
        context = self.make_context()
        observation = DevelopmentObservation(
            "fixture", event_sink=lambda event: None, evaluator_identity=context.evaluator_identity
        )
        context.assert_observation(observation)
        other = DevelopmentObservation("fixture", event_sink=lambda event: None,
                                       evaluator_identity="b" * 64)
        with self.assertRaisesRegex(contexts.PoseBustersContextError, "identity does not match"):
            context.assert_observation(other)

    def test_case_and_closed_contexts_reject_reuse(self):
        context = self.make_context()
        with self.assertRaisesRegex(contexts.PoseBustersContextError, "another case"):
            context.assert_case("other")
        context = self.make_context()
        context.close()
        context.close()
        with self.assertRaisesRegex(contexts.PoseBustersContextError, "closed"):
            context.assert_case("fixture")
        self.assertTrue(context.summary()["closed"])

    def test_source_closure_includes_chosen_strategy(self):
        shared = contexts.strategy_source_paths("reference")
        self.assertEqual(shared, contexts.strategy_source_paths("prepared_receptor"))
        self.assertIn("tools/posebusters_evaluator_context.py", shared)
        self.assertIn("tools/posebusters_replay_evaluator.py", shared)
        self.assertEqual(contexts.strategy_source_paths("prepared_subset"),
                         shared + ("tools/posebusters_subset.py",))


@unittest.skipIf(np is None, "numpy unavailable for structural fake-runtime tests")
class ContextLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.runtime, self.calls = _fake_runtime()
        self.predicted = (_Mol(["ligand"], [[0, 0, 0]]), _Mol(["ligand"], [[0.1, 0, 0]]))
        self.native = _Mol(self.predicted[0])
        self.receptor = _Mol(["protein", "hydrogens"], [[1, 0, 0], [2, 0, 0]])
        self.records = (b"first\n$$$$\n", b"second\n$$$$\n")
        self.addCleanup(patch.stopall)
        patch.object(replay, "_load_runtime", return_value=self.runtime).start()
        patch.object(contexts, "_pipeline_identity", return_value="a" * 64).start()

    def make_context(self, mode="prepared_receptor", **kwargs):
        return contexts.PoseBustersEvaluatorContext("fixture", mode=mode, **kwargs)

    def bust(self, context, receptor=None):
        return context.bust(
            self.predicted, self.native, self.receptor if receptor is None else receptor,
            records=self.records, native_payload=b"native", receptor_payload=b"receptor",
            expected_pose_count=2, PoseBusters=self.runtime.PoseBusters,
        )

    def test_energy_lru_survives_context_creation_evaluation_and_close(self):
        with self.make_context("reference") as reference:
            original = self.bust(reference)
        first = self.runtime.energy.get_average_energy.cache_info()
        self.assertEqual((first.hits, first.misses, first.currsize), (1, 1, 1))
        with self.make_context() as prepared:
            self.assertEqual(self.bust(prepared), original)
        after = self.runtime.energy.get_average_energy.cache_info()
        self.assertEqual((after.hits, after.misses, after.currsize), (3, 1, 1))
        self.assertEqual(prepared.summary()["energy_cache"]["hits_added"], 2)
        self.assertEqual(prepared.summary()["energy_cache"]["misses_added"], 0)
        self.assertFalse(prepared.summary()["energy_cache"]["cleared_by_context"])

    def test_category_prototypes_reuse_fresh_equal_receptor_objects(self):
        context = self.make_context()
        first = self.bust(context)
        other = _Mol(self.receptor)
        self.assertIsNot(other, self.receptor)
        second = self.bust(context, receptor=other)
        self.assertEqual(first, second)
        self.assertIs(context._cache._receptor, other)
        self.assertEqual(context.summary()["receptor_preparation"],
                         {"hits": 3, "misses": 1, "entries": 1, "max_entries": 4})
        self.assertEqual(self.calls["mask"], 1)
        self.assertEqual(self.calls["original"], 0)
        self.assertEqual(self.calls["filter"], 5)
        self.runtime.PoseBusters(config="redock", top_n=2).bust(
            self.predicted, self.native, self.receptor, full_report=True
        )
        self.assertEqual(self.calls["original"], 2)

    def test_changed_decoded_receptor_and_prototype_are_rejected(self):
        context = self.make_context()
        self.bust(context)
        changed = _Mol(self.receptor)
        changed.positions[0, 0] += 1e-12
        with self.assertRaisesRegex(contexts.PoseBustersContextError, "different molecule"):
            self.bust(context, receptor=changed)
        self.assertFalse(context.summary()["healthy"])
        context = self.make_context()
        self.bust(context)
        prototype, _ = next(iter(context._cache._entries.values()))
        prototype.props["corruption"] = "detected"
        with self.assertRaisesRegex(replay.ReplayEvaluationError, "prototype mutated"):
            self.bust(context)
        self.assertFalse(context.summary()["healthy"])

    def test_full_report_serialization_is_opt_in_and_callback_is_detached(self):
        context = self.make_context()
        report = self.bust(context)
        outcomes = ((0.0, 1.0), (True, True), (True, True), ((), ()))
        with patch.object(replay, "_canonical_report") as canonical:
            context.observe_report(report, predicted=self.predicted, records=self.records, outcomes=outcomes)
            canonical.assert_not_called()
        captured = []

        def observe(document):
            captured.append(document)
            document["fullReport"][0]["results"]["volume_overlap"] = 1000

        context = self.make_context(report_observer=observe)
        report = self.bust(context)
        with patch.object(replay, "_canonical_report", side_effect=lambda value, **kwargs: deepcopy(value)):
            context.observe_report(report, predicted=self.predicted, records=self.records, outcomes=outcomes)
        self.assertEqual(report[0]["results"]["volume_overlap"], 0.075)
        self.assertEqual(captured[0]["record_count"], 2)
        self.assertTrue(captured[0]["input_immutability"]["verified"])
        self.assertEqual(captured[0]["input_immutability"]["before"],
                         captured[0]["input_immutability"]["after"])
        self.assertEqual(captured[0]["input_ids"]["record_sha256s"],
                         [hashlib.sha256(record).hexdigest() for record in self.records])
        self.assertEqual(context.summary()["full_reports_observed"], 1)

    def test_close_releases_corrupted_cache_and_latches_failure(self):
        context = self.make_context()
        self.bust(context)
        prototype, _ = next(iter(context._cache._entries.values()))
        prototype.props["corruption"] = "detected at close"
        before = self.runtime.energy.get_average_energy.cache_info()
        with self.assertRaisesRegex(replay.ReplayEvaluationError, "prototype mutated"):
            context.close()
        self.assertTrue(context.summary()["closed"])
        self.assertFalse(context.summary()["healthy"])
        self.assertIsNone(context._cache)
        self.assertEqual(self.runtime.energy.get_average_energy.cache_info(), before)

    def test_observer_exception_latches_and_metrics_are_optional(self):
        def broken(document):
            raise OSError("report sink failed")

        context = self.make_context(report_observer=broken, collect_metrics=True)
        report = self.bust(context)
        with patch.object(replay, "_canonical_report", return_value={}):
            with self.assertRaisesRegex(OSError, "report sink failed"):
                context.observe_report(report, predicted=self.predicted, records=self.records,
                                       outcomes=((0.0, 1.0), (True, True), (True, True), ((), ())))
        self.assertFalse(context.summary()["healthy"])
        self.assertTrue(context.summary()["timings"]["volume_substages"])
        context.close()
        self.assertTrue(context.summary()["closed"])
        ordinary = self.make_context()
        self.bust(ordinary)
        self.assertEqual(ordinary.summary()["timings"]["volume_substages"], [])

    def test_concurrent_use_and_denominator_mismatch_fail_before_evaluation(self):
        context = self.make_context()
        context._lock.acquire()
        try:
            with self.assertRaisesRegex(contexts.PoseBustersContextError, "concurrent"):
                self.bust(context)
        finally:
            context._lock.release()
        self.assertEqual(context.summary()["bust_calls"], 0)
        context = self.make_context()
        with self.assertRaisesRegex(contexts.PoseBustersContextError, "denominator"):
            context.bust(self.predicted, self.native, self.receptor,
                         records=self.records, native_payload=b"n", receptor_payload=b"r",
                         expected_pose_count=1, PoseBusters=self.runtime.PoseBusters)
        self.assertEqual(context.summary()["bust_calls"], 0)


class FrozenRunnerContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [name for name in ("rdkit", "posebusters", "torch")
                   if importlib.util.find_spec(name) is None]
        if missing:
            message = f"frozen molecular runtime unavailable: {missing}"
            if os.environ.get("PB_INTEGRATION_REQUIRE_FROZEN_RUNTIME") == "1":
                raise AssertionError(message)
            raise unittest.SkipTest(message)
        cls.runtime = replay._load_runtime()
        cls.Chem = cls.runtime.Chem
        cls.runner = cls.runtime.runner

    def fixture(self):
        from rdkit.Chem import AllChem

        Chem = self.Chem
        native = Chem.AddHs(Chem.MolFromSmiles("CCO"))
        self.assertEqual(AllChem.EmbedMolecule(native, randomSeed=42), 0)
        AllChem.UFFOptimizeMolecule(native)
        native.SetProp("_Name", "native")
        native_payload = (Chem.MolToMolBlock(native).rstrip("\n") + "\n$$$$\n").encode("ascii")
        records = []
        for rank in range(1, 7):
            mol = Chem.Mol(native)
            conf = mol.GetConformer()
            for index, xyz in enumerate(conf.GetPositions()):
                conf.SetAtomPosition(index, (float(xyz[0]) + rank / 100, float(xyz[1]), float(xyz[2])))
            mol.SetProp("_Name", f"fixture_engine_v2_rank_{rank}")
            records.append((Chem.MolToMolBlock(mol).rstrip("\n") + "\n$$$$\n").encode("ascii"))
        receptor_payload = (
            "ATOM      1  CA  ALA A   1       4.000   0.000   0.000  1.00 20.00           C  \n"
            "HETATM    2  O   HOH A   2       0.000   4.000   0.000  1.00 20.00           O  \n"
            "HETATM    3 ZN    ZN A   3       0.000   0.000   4.000  1.00 20.00          ZN  \n"
            "HETATM    4  C1  LIG A   4      -4.000   0.000   0.000  1.00 20.00           C  \n"
            "ATOM      5  H   ALA A   1       4.000   1.000   0.000  1.00 20.00           H  \n"
            "END\n"
        ).encode("ascii")
        return tuple(records), dict(native_payload=native_payload, receptor_payload=receptor_payload)

    def test_actual_runner_all_strategies_match_and_preserve_top5_reuse(self):
        records, inputs = self.fixture()
        self.runtime.energy.get_average_energy.cache_clear()  # test setup only
        expected_report = expected_outcomes = None
        identities = set()
        for mode in ("reference", "prepared_receptor", "prepared_subset"):
            captured = []
            with contexts.PoseBustersEvaluatorContext(
                "fixture", mode=mode, report_observer=captured.append
            ) as context:
                identities.add(context.evaluator_identity)
                observer = DevelopmentObservation(
                    "fixture", event_sink=lambda event: None,
                    evaluator_identity=context.evaluator_identity,
                )
                candidates = self.runner._posebusters_outcomes(
                    b"".join(records), expected_pose_count=6,
                    development_observation=observer, evaluation_context=context, **inputs
                )
                top5 = self.runner._posebusters_outcomes(
                    b"".join(records[:5]), development_observation=observer,
                    evaluation_context=context, **inputs
                )
                self.assertEqual(top5, tuple(column[:5] for column in candidates))
                self.assertEqual(observer.summary()["evaluation_cache"],
                                 {"evaluation_calls": 1, "reused_records": 5, "cached_records": 6})
                self.assertEqual(context.summary()["bust_calls"], 1)
                self.assertEqual(context.summary()["record_evaluations"], 6)
                self.assertEqual(len(captured), 1)
                if expected_report is None:
                    expected_report, expected_outcomes = captured[0]["fullReport"], candidates
                self.assertEqual(captured[0]["fullReport"], expected_report)
                self.assertEqual(candidates, expected_outcomes)
                if mode != "reference":
                    self.assertEqual(context.summary()["receptor_preparation"],
                                     {"misses": 4, "hits": 20, "entries": 4, "max_entries": 4})
                json.dumps(context.summary(), allow_nan=False)
            self.assertEqual(self.runtime.energy.get_average_energy.cache_info().currsize, 1)
            self.assertFalse(context.summary()["energy_cache"]["cleared_by_context"])
        self.assertEqual(len(identities), 3)
        default = self.runner._posebusters_outcomes(b"".join(records[:5]), **inputs)
        self.assertEqual(default, tuple(column[:5] for column in expected_outcomes))
        cache = self.runtime.energy.get_average_energy.cache_info()
        self.assertEqual((cache.misses, cache.hits), (1, 22))

    def test_actual_prepared_rebind_preserves_reference_clone_policy(self):
        records, inputs = self.fixture()
        captured = []
        with contexts.PoseBustersEvaluatorContext(
            "fixture", mode="prepared_receptor", report_observer=captured.append
        ) as context:
            observer = DevelopmentObservation(
                "fixture", event_sink=lambda event: None,
                evaluator_identity=context.evaluator_identity, reuse_evaluations=False,
            )
            first = self.runner._posebusters_outcomes(
                b"".join(records), expected_pose_count=6,
                development_observation=observer, evaluation_context=context, **inputs
            )
            original_receptor = context._cache._receptor
            second = self.runner._posebusters_outcomes(
                b"".join(records), expected_pose_count=6,
                development_observation=observer, evaluation_context=context, **inputs
            )
            self.assertEqual(first, second)
            self.assertIsNot(original_receptor, context._cache._receptor)
            self.assertEqual(captured[0]["fullReport"], captured[1]["fullReport"])
            self.assertEqual(observer.summary()["prepared_inputs"], {"cache_hits": 1, "cache_misses": 1})
            self.assertEqual(context.summary()["receptor_preparation"],
                             {"misses": 4, "hits": 44, "entries": 4, "max_entries": 4})

    def test_strategy_identity_binds_source_and_does_not_change_default_hash_shape(self):
        runner = self.runner
        with TemporaryDirectory() as temp:
            root = Path(temp)
            sources = (
                "betelgeuze_engine_v2/benchmark/public_redocking_benchmark.py",
                "tools/run_engine_v2_public_redocking_300.py", "tools/redocking_development_p1.py",
                *contexts.strategy_source_paths("prepared_subset"),
            )
            for name in sources:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(name)
            with patch.object(runner, "__file__", str(root / "tools/run_engine_v2_public_redocking_300.py")), \
                    patch.object(runner, "_evaluator_distribution_payload_sha256s", return_value={"fixture": "a" * 64}):
                def identity(mode=None):
                    return runner._evaluation_pipeline_sha256(root, evaluator_versions={"fixture": "1"}, evaluator_mode=mode)

                original = {mode: identity(mode) for mode in (None, "reference", "prepared_receptor", "prepared_subset")}
                self.assertEqual(len(set(original.values())), 4)
                (root / "tools/posebusters_subset.py").write_text("changed subset")
                self.assertNotEqual(identity("prepared_subset"), original["prepared_subset"])
                for mode in (None, "reference", "prepared_receptor"):
                    self.assertEqual(identity(mode), original[mode])
                (root / "tools/posebusters_evaluator_context.py").unlink()
                self.assertEqual(identity(), original[None])
                with self.assertRaises(OSError):
                    identity("reference")

    def test_context_cannot_reuse_another_case_or_frozen_profile(self):
        context = contexts.PoseBustersEvaluatorContext("fixture", mode="reference")
        with self.assertRaisesRegex(contexts.PoseBustersContextError, "another case"):
            self.runner._engine_v2_result("other", {}, input_sha256s={}, output=Path("unused"), seed=1,
                                          evaluation_context=context)
        context = contexts.PoseBustersEvaluatorContext("fixture", mode="reference")
        with self.assertRaisesRegex(self.runner.PublicRedockingRunnerError, "frozen execution profile"):
            self.runner._engine_v2_result("fixture", {}, input_sha256s={}, output=Path("unused"), seed=1,
                                          execution_profile_sha256="a" * 64, evaluation_context=context)
        with self.assertRaisesRegex(self.runner.PublicRedockingRunnerError, "unchanged V7"):
            self.runner._engine_v2_pose_coordinates("fixture", {}, seed=1,
                                                   development_v8_clearance_variant=True,
                                                   evaluation_context=context)


if __name__ == "__main__":
    unittest.main()
