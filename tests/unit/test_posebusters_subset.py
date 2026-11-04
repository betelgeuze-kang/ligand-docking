"""Guard tests and real frozen-runtime equivalence for the subset experiment.

Fake molecules test routing and ownership only. Molecular assertions require
the original RDKit/PoseBusters runtime; cloud must set
PB_REPLAY_REQUIRE_FROZEN_RUNTIME=1 or PB_INTEGRATION_REQUIRE_FROZEN_RUNTIME=1.
"""

from __future__ import annotations

from copy import deepcopy
import gc
import importlib.util
import itertools
import json
import math
import os
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import weakref

from tools import posebusters_subset as subset

try:
    import numpy as np
except ImportError:
    np = None


class _FakeAtom:
    def __init__(self, index):
        self.index = index
        self.query = False
        self.chirality = 0
        self.props = {"serial": index + 100, "_computed": index * 2}
        self.computed = {"_computed"}
        self.pdb = {"name": f"atom-{index}", "chain": "A"}

    def HasQuery(self):
        return self.query

    def GetChiralTag(self):
        return self.chirality


class _FakeConformer:
    def __init__(self, count):
        self.positions = [(0.0, 0.0, 0.0)] * count
        self.identifier = 0
        self.three_d = True
        self.props = {}

    def GetNumAtoms(self):
        return len(self.positions)

    def GetId(self):
        return self.identifier

    def SetId(self, identifier):
        self.identifier = identifier

    def Is3D(self):
        return self.three_d

    def Set3D(self, value):
        self.three_d = value

    def GetPropNames(self, **kwargs):
        return tuple(self.props)

    def GetAtomPosition(self, index):
        return self.positions[index]

    def SetAtomPosition(self, index, position):
        self.positions[index] = tuple(position)


class _FakeMol:
    def __init__(self, source=0):
        if isinstance(source, _FakeMol):
            self.__dict__.update(deepcopy(source.__dict__))
            return
        self.atoms = [_FakeAtom(index) for index in range(source)]
        self.bonds = 0
        self.stereo_groups = []
        self.substance_groups = []
        self.props = {}
        self.computed = set()
        self.conformers = []
        if source:
            conf = _FakeConformer(source)
            conf.positions = [(float(i), -0.0, float(i) + 0.25) for i in range(source)]
            self.conformers.append(conf)

    def GetNumAtoms(self):
        return len(self.atoms)

    def GetNumBonds(self):
        return self.bonds

    def GetStereoGroups(self):
        return self.stereo_groups

    def GetPropNames(self, *, includePrivate, includeComputed):
        return tuple(key for key in self.props if includeComputed or key not in self.computed)

    def GetAtoms(self):
        return tuple(self.atoms)

    def GetAtomWithIdx(self, index):
        return self.atoms[index]

    def GetConformers(self):
        return tuple(self.conformers)


class _FakeRWMol(_FakeMol):
    def AddAtom(self, atom):
        copied = deepcopy(atom)
        copied.index = len(self.atoms)
        self.atoms.append(copied)
        return copied.index

    def AddConformer(self, conformer, *, assignId):
        assert not assignId
        self.conformers.append(deepcopy(conformer))

    def ClearComputedProps(self, *, includeRings):
        assert includeRings
        for key in self.computed:
            self.props.pop(key, None)
        self.computed.clear()
        for atom in self.atoms:
            for key in atom.computed:
                atom.props.pop(key, None)
            atom.computed.clear()


def _fake_chem():
    return SimpleNamespace(
        rdBase=SimpleNamespace(rdkitVersion=subset.FROZEN_RDKIT_VERSION),
        Mol=_FakeMol, RWMol=_FakeRWMol, Conformer=_FakeConformer,
        ChiralType=SimpleNamespace(CHI_UNSPECIFIED=0),
        GetMolSubstanceGroups=lambda mol: mol.substance_groups,
    )


@unittest.skipIf(np is None, "numpy unavailable")
class SubsetGuardTests(unittest.TestCase):
    def setUp(self):
        self.Chem = _fake_chem()
        self.sentinel = object()
        self.reference = Mock(return_value=self.sentinel)
        self.filtered = subset.ExactSubsetFilter(Chem=self.Chem, reference_filter=self.reference)
        self.mol = _FakeMol(4)
        self.mask = np.array([False, True, False, True], dtype=bool)

    def test_runtime_version_and_reference_admission(self):
        self.Chem.rdBase.rdkitVersion = "2026.03.6"
        with self.assertRaisesRegex(subset.SubsetOptimizationError, "requires RDKit"):
            subset.ExactSubsetFilter(Chem=self.Chem, reference_filter=self.reference)
        with self.assertRaisesRegex(TypeError, "callable"):
            subset.ExactSubsetFilter(Chem=_fake_chem(), reference_filter=None)
        self.reference.assert_not_called()

    def test_all_keep_preserves_identity_even_for_unsupported_features(self):
        self.mol.bonds = 1
        self.mol.props["_Name"] = "named"
        self.assertIs(self.filtered(self.mol, np.ones(4, dtype=bool)), self.mol)
        empty = _FakeMol()
        self.assertIs(self.filtered(empty, np.zeros(0, dtype=bool)), empty)
        self.reference.assert_not_called()
        self.assertEqual(self.filtered.document()["identity_calls"], 2)

    def test_bondless_subset_preserves_order_metadata_and_ownership(self):
        before = deepcopy(self.mol.__dict__)
        result = self.filtered(self.mol, self.mask)
        self.assertIs(type(result), _FakeMol)
        self.assertEqual([a.props["serial"] for a in result.atoms], [101, 103])
        self.assertEqual([a.pdb["name"] for a in result.atoms], ["atom-1", "atom-3"])
        self.assertEqual(result.conformers[0].positions, [before["conformers"][0].positions[i] for i in (1, 3)])
        self.assertEqual(struct.pack(">d", result.conformers[0].positions[0][1]), struct.pack(">d", -0.0))
        self.assertNotIn("_computed", result.atoms[0].props)
        self.assertIn("_computed", self.mol.atoms[1].props)
        result.atoms[0].pdb["chain"] = "changed"
        result.conformers[0].SetAtomPosition(0, (99, 99, 99))
        self.assertEqual(self.mol.atoms[1].pdb["chain"], "A")
        self.assertEqual(self.mol.conformers[0].positions, before["conformers"][0].positions)
        self.reference.assert_not_called()
        self.assertEqual(self.filtered.document()["fast_path_calls"], 1)
        self.assertEqual(self.filtered.document()["removed_atoms_fast_path"], 2)

    def test_empty_subset_keeps_empty_conformers_and_source_unchanged(self):
        self.mol.conformers[0].identifier = 17
        self.mol.conformers[0].three_d = False
        result = self.filtered(self.mol, np.zeros(4, dtype=bool))
        self.assertEqual(result.GetNumAtoms(), 0)
        self.assertEqual(len(result.conformers), 1)
        self.assertEqual(result.conformers[0].GetId(), 17)
        self.assertFalse(result.conformers[0].Is3D())
        self.assertEqual(result.conformers[0].positions, [])
        self.assertEqual(self.mol.GetNumAtoms(), 4)

    def test_conformer_order_ids_and_flags_are_retained(self):
        other = deepcopy(self.mol.conformers[0])
        other.identifier = 79
        other.three_d = False
        other.positions = [(x + 8, y, z) for x, y, z in other.positions]
        self.mol.conformers.append(other)
        result = self.filtered(self.mol, self.mask)
        self.assertEqual([c.GetId() for c in result.conformers], [0, 79])
        self.assertEqual([c.Is3D() for c in result.conformers], [True, False])
        self.assertEqual(result.conformers[1].positions, [other.positions[i] for i in (1, 3)])

    def test_persistent_molecule_properties_and_every_unsupported_feature_fall_back(self):
        cases = (
            ("has_bonds", lambda m: setattr(m, "bonds", 1)),
            ("stereo_groups", lambda m: m.stereo_groups.append("enhanced-stereo")),
            ("substance_groups", lambda m: m.substance_groups.append("sgroup")),
            ("molecule_properties", lambda m: m.props.update({"_Name": "kept by upstream"})),
            ("query_atom", lambda m: setattr(m.atoms[0], "query", True)),
            ("atom_chirality", lambda m: setattr(m.atoms[0], "chirality", 1)),
            ("conformer_size", lambda m: m.conformers[0].positions.pop()),
            ("conformer_properties", lambda m: m.conformers[0].props.update({"x": 9})),
        )
        for reason, mutate in cases:
            with self.subTest(reason=reason):
                mol = _FakeMol(4)
                mutate(mol)
                self.assertIs(self.filtered(mol, self.mask), self.sentinel)
                self.assertIs(self.reference.call_args.args[0], mol)
                self.assertIs(self.reference.call_args.args[1], self.mask)
                self.assertEqual(self.filtered.document()["fallback_reasons"][reason], 1)
        self.assertEqual(self.filtered.document()["fast_path_calls"], 0)

    def test_computed_molecule_property_is_removed_like_reference(self):
        self.mol.props["_computed_mol"] = "discarded"
        self.mol.computed.add("_computed_mol")
        result = self.filtered(self.mol, self.mask)
        self.assertNotIn("_computed_mol", result.props)
        self.assertIn("_computed_mol", self.mol.props)
        self.reference.assert_not_called()

    def test_invalid_masks_and_mutable_molecule_type_delegate_unchanged(self):
        masks = (
            [False, True, False, True], np.ones(4, dtype=int),
            np.zeros((2, 2), dtype=bool), np.zeros(3, dtype=bool),
            np.ma.array(self.mask, mask=[False] * 4),
        )
        for mask in masks:
            with self.subTest(mask=repr(mask)):
                self.assertIs(self.filtered(self.mol, mask), self.sentinel)
                self.assertIs(self.reference.call_args.args[1], mask)
        mutable = _FakeRWMol(self.mol)
        self.assertIs(self.filtered(mutable, self.mask), self.sentinel)
        self.assertEqual(self.filtered.document()["fallback_reasons"],
                         {"molecule_type": 1, "unsupported_mask": len(masks)})

    def test_original_failure_is_not_changed(self):
        self.mol.bonds = 1
        error = RuntimeError("upstream sentinel")
        self.reference.side_effect = error
        with self.assertRaises(RuntimeError) as caught:
            self.filtered(self.mol, self.mask)
        self.assertIs(caught.exception, error)
        self.assertEqual(self.filtered.document()["fallback_errors"], 1)

    def test_unexpected_fast_path_error_is_not_hidden_by_fallback(self):
        error = RuntimeError("construction sentinel")
        with patch.object(self.filtered, "_build_bondless_subset", side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                self.filtered(self.mol, self.mask)
        self.assertIs(caught.exception, error)
        self.reference.assert_not_called()
        self.assertEqual(self.filtered.document()["fast_path_errors"], 1)
        self.assertEqual(self.filtered.document()["fast_path_calls"], 0)

    def test_no_input_molecule_is_retained_and_statistics_are_json_safe(self):
        mol = _FakeMol(4)
        observed = weakref.ref(mol)
        self.filtered(mol, self.mask)
        del mol
        gc.collect()
        self.assertIsNone(observed())
        document = self.filtered.document()
        json.dumps(document, allow_nan=False)
        document["fallback_reasons"]["not_real"] = 1
        self.assertEqual(self.filtered.document()["fallback_reasons"], {})


class FrozenSubsetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [name for name in ("numpy", "rdkit", "posebusters", "torch")
                   if importlib.util.find_spec(name) is None]
        if missing:
            message = f"frozen molecular dependencies unavailable: {missing}"
            if any(os.environ.get(key) == "1" for key in (
                "PB_REPLAY_REQUIRE_FROZEN_RUNTIME", "PB_INTEGRATION_REQUIRE_FROZEN_RUNTIME"
            )):
                raise AssertionError(message)
            raise unittest.SkipTest(message)
        from tools import posebusters_replay_evaluator as replay

        cls.replay = replay
        cls.runtime = replay._load_runtime()
        cls.Chem = cls.runtime.Chem
        cls.flags = int(cls.Chem.PropertyPickleOptions.AllProps) | int(cls.Chem.PropertyPickleOptions.CoordsAsDouble)

    @staticmethod
    def receptor_payload():
        return (
            "ATOM      1  CA  ALA A   1       4.000   0.000   0.000  0.75 20.00           C  \n"
            "HETATM    2  O   HOH A   2       0.000   4.000   0.000  1.00 21.00           O  \n"
            "HETATM    3 ZN    ZN A   3       0.000   0.000   4.000  1.00 22.00          ZN  \n"
            "HETATM    4  C1  LIG A   4      -4.000   0.000   0.000  1.00 23.00           C  \n"
            "ATOM      5  H   ALA A   1       4.000   1.000   0.000  1.00 24.00           H  \n"
            "ATOM      6  N   ALA B   9      40.000   0.000   0.000  1.00 25.00           N  \n"
            "END\n"
        ).encode("ascii")

    def bondless_receptor(self):
        mol = self.Chem.MolFromPDBBlock(self.receptor_payload().decode("ascii"),
                                       sanitize=False, removeHs=False, proximityBonding=False)
        self.assertIsNotNone(mol)
        self.assertEqual(mol.GetNumAtoms(), 6)
        self.assertEqual(mol.GetNumBonds(), 0)
        self.Chem.AssignStereochemistryFrom3D(mol)
        return mol

    def binary(self, mol):
        return bytes(mol.ToBinary(self.flags))

    def test_all_masks_match_binary_atom_metadata_and_double_coordinates(self):
        mol = self.bondless_receptor()
        atom = mol.GetAtomWithIdx(0)
        atom.SetProp("_private_string", "001")
        atom.SetIntProp("signed", -2147483647)
        atom.SetUnsignedProp("unsigned", 4294967295)
        atom.SetBoolProp("boolean", True)
        atom.SetDoubleProp("negative_zero", -0.0)
        atom.SetIsotope(13)
        atom.SetFormalCharge(-1)
        atom.SetNumExplicitHs(1)
        atom.SetNoImplicit(True)
        mol.SetProp("_disposable", "computed", computed=True)
        first = mol.GetConformer()
        first.SetId(31)
        first.SetAtomPosition(0, (-0.0, math.nextafter(1.0, 2.0), 1e-200))
        second = self.Chem.Conformer(first)
        second.SetId(7)
        second.Set3D(False)
        second.SetAtomPosition(0, (math.nextafter(-1.0, -2.0), 0.0, -1e-200))
        mol.AddConformer(second, assignId=False)
        source = self.binary(mol)
        filtered = subset.ExactSubsetFilter(Chem=self.Chem, reference_filter=self.runtime.volume._filter_by_mask)
        for bits in itertools.product((False, True), repeat=6):
            with self.subTest(mask=bits):
                mask = np.array(bits, dtype=bool)
                baseline = self.runtime.volume._filter_by_mask(mol, mask)
                observed = filtered(mol, mask)
                self.assertEqual(self.binary(observed), self.binary(baseline))
                self.assertEqual(self.binary(mol), source)
                self.assertEqual([c.GetId() for c in observed.GetConformers()], [31, 7])
                self.assertEqual([c.Is3D() for c in observed.GetConformers()], [True, False])
                if all(bits):
                    self.assertIs(observed, mol)
                else:
                    self.assertIsNot(observed, mol)
        self.assertEqual(filtered.document()["fast_path_calls"], 63)
        self.assertEqual(filtered.document()["fallback_calls"], 0)
        self.assertEqual(filtered.document()["identity_calls"], 1)

    def test_original_fallback_preserves_properties_queries_and_bond_stereo(self):
        named = self.bondless_receptor()
        named.SetUnsignedProp("typed_property", 4294967295)
        conformer_property = self.bondless_receptor()
        conformer_property.GetConformer().SetDoubleProp("typed_conformer_property", -0.0)
        chiral = self.bondless_receptor()
        chiral.GetAtomWithIdx(0).SetChiralTag(self.Chem.ChiralType.CHI_TETRAHEDRAL_CW)
        cases = (named, conformer_property, chiral,
                 self.Chem.MolFromSmarts("[#6].[#8]"),
                 self.Chem.MolFromSmiles("F/C=C/F"),
                 self.Chem.MolFromSmiles("N[C@@H](C)C(=O)O"))
        filtered = subset.ExactSubsetFilter(Chem=self.Chem, reference_filter=self.runtime.volume._filter_by_mask)
        for mol in cases:
            with self.subTest(atoms=mol.GetNumAtoms(), bonds=mol.GetNumBonds()):
                source = self.binary(mol)
                mask = np.ones(mol.GetNumAtoms(), dtype=bool)
                mask[-1] = False
                baseline = self.runtime.volume._filter_by_mask(mol, mask)
                observed = filtered(mol, mask)
                self.assertEqual(self.binary(observed), self.binary(baseline))
                self.assertEqual(self.binary(mol), source)
        self.assertEqual(filtered.document()["fast_path_calls"], 0)
        self.assertEqual(filtered.document()["fallback_calls"], len(cases))

    def test_constructed_molecule_and_pdb_metadata_do_not_alias_source(self):
        mol = self.bondless_receptor()
        before = self.binary(mol)
        filtered = subset.ExactSubsetFilter(Chem=self.Chem, reference_filter=self.runtime.volume._filter_by_mask)
        result = filtered(mol, np.array([True, False, True, False, False, True], dtype=bool))
        self.assertEqual(filtered.document()["fast_path_calls"], 1)
        result.GetAtomWithIdx(0).GetPDBResidueInfo().SetChainId("Z")
        result.GetAtomWithIdx(0).SetProp("changed", "new")
        result.GetConformer().SetAtomPosition(0, (900.0, 900.0, 900.0))
        self.assertEqual(self.binary(mol), before)

    def test_full_report_and_legacy_outcomes_match_with_distance_filter_hook(self):
        from rdkit.Chem import AllChem

        Chem, replay, runtime = self.Chem, self.replay, self.runtime
        native = Chem.AddHs(Chem.MolFromSmiles("CCO"))
        self.assertEqual(AllChem.EmbedMolecule(native, randomSeed=42), 0)
        AllChem.UFFOptimizeMolecule(native)
        native.SetProp("_Name", "native")
        native_payload = (Chem.MolToMolBlock(native).rstrip("\n") + "\n$$$$\n").encode("ascii")
        records = []
        for rank, shift in enumerate((0.0, 7.0), 1):
            mol = Chem.Mol(native)
            conf = mol.GetConformer()
            for index, xyz in enumerate(conf.GetPositions()):
                conf.SetAtomPosition(index, (float(xyz[0]) + shift, float(xyz[1]), float(xyz[2])))
            mol.SetProp("_Name", f"synthetic_subset_rank_{rank}")
            records.append((Chem.MolToMolBlock(mol).rstrip("\n") + "\n$$$$\n").encode("ascii"))
        records = tuple(records)
        reports, outcomes = {}, {}
        optimized_stats = None
        for mode in ("baseline", "prepared", "prepared_subset"):
            runtime.energy.get_average_energy.cache_clear()
            try:
                predicted, reference, receptor = runtime.runner._posebusters_molecules(
                    output_payload=b"".join(records), native_payload=native_payload,
                    receptor_payload=self.receptor_payload(), expected_pose_count=len(records))
                before = replay._input_fingerprints(predicted, reference, receptor, Chem)
                evaluator_class = runtime.PoseBusters
                cache = None
                if mode != "baseline":
                    context = ("frozen-subset-test",)
                    measurements = replay._Measurements()
                    cache = replay._PreparedReceptorCategories(receptor, context=context, Chem=Chem,
                                                               volume=runtime.volume, measurements=measurements)
                    distance_filter = (subset.ExactSubsetFilter(Chem=Chem, reference_filter=runtime.volume._filter_by_mask)
                                       if mode == "prepared_subset" else None)
                    evaluator_class = replay._instrumented_class(
                        runtime, mode="prepared_receptor", cache=cache, context=context,
                        measurements=measurements, trace_coverage={}, energy_events=[],
                        distance_filter=distance_filter)
                report = evaluator_class(config="redock", top_n=len(records)).bust(
                    mol_pred=list(predicted), mol_true=reference, mol_cond=receptor, full_report=True)
                reports[mode] = replay._canonical_report(report, predicted=predicted, records=records,
                                                        PoseBusters=runtime.PoseBusters)
                outcomes[mode] = runtime.runner._posebusters_report_outcomes(report, expected_pose_count=len(records))
                self.assertEqual(replay._input_fingerprints(predicted, reference, receptor, Chem), before)
                if cache is not None:
                    cache.verify()
                if mode == "prepared_subset":
                    optimized_stats = distance_filter.document()
            finally:
                runtime.energy.get_average_energy.cache_clear()
        self.assertEqual(reports["baseline"], reports["prepared"])
        self.assertEqual(reports["baseline"], reports["prepared_subset"])
        self.assertEqual(outcomes["baseline"], outcomes["prepared_subset"])
        self.assertEqual(len(reports["baseline"]["columns"]), 126)
        self.assertGreater(optimized_stats["fast_path_calls"], 0)
        self.assertEqual(optimized_stats["fast_path_errors"], 0)


if __name__ == "__main__":
    unittest.main()
