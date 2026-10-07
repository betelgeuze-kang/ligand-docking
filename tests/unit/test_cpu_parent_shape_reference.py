"""Synthetic contract and analytic-force checks only; no optimizer or chemistry."""
from dataclasses import FrozenInstanceError
import hashlib
import json
import math
import unittest

from betelgeuze_product.cpu_refinement_shape_v1.reference import (
    MAX_ATOMS, MIN_DISTANCE, MoleculeIdentity, ShapeContract, ShapeContractError,
    ShapeDomainError, ShapeReference, evaluate_shape,
)


SOURCE_DIGEST = hashlib.sha256(b"synthetic standalone source binding").hexdigest()
PARENT = ((0.0, 0.0, 0.0), (1.1, 0.2, 0.0), (0.0, 1.3, 0.1), (0.2, 0.1, 1.4))
TRIAL = ((0.02, -0.03, 0.01), (1.14, 0.24, -0.04),
         (-0.03, 1.25, 0.08), (0.25, 0.14, 1.36))


def identity(n=4, **overrides):
    args = dict(atom_ids=[f"source:{i}" for i in range(n)],
                elements=["C"] * (n - 1) + ["H"],
                covalent_bonds=[(i, i + 1, "single") for i in range(n - 1)],
                canonical_molecule=f"synthetic-source-canonical-molecule-{n}")
    args.update(overrides)
    return MoleculeIdentity(**args)


def reference(coords=PARENT, ident=None, **overrides):
    args = dict(identity=ident or identity(len(coords)), coordinates=coords,
                parent_provenance="synthetic original supplied parent; no molecular claims",
                source_identity="standalone-synthetic-test/1", source_digest=SOURCE_DIGEST)
    args.update(overrides)
    return ShapeReference(**args)


def reseal(document):
    body = {k: v for k, v in document.items() if k != "digest"}
    document["digest"] = hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False).encode("ascii")).hexdigest()
    return document


def scalar_energy(coords, parent, strength):
    # Independent scalar expression uses direct squares and sqrt on small data.
    terms = []
    n = len(coords)
    for i in range(n):
        for j in range(i + 1, n):
            r = math.sqrt(sum((coords[i][k] - coords[j][k]) ** 2 for k in range(3)))
            r0 = math.sqrt(sum((parent[i][k] - parent[j][k]) ** 2 for k in range(3)))
            terms.append((r - r0) ** 2)
    return strength * sum(terms) / (2 * len(terms))


class ShapeNumericsTests(unittest.TestCase):
    def setUp(self):
        self.ref = reference()
        self.ident = self.ref.identity

    def test_reference_zero_for_every_strength(self):
        for strength in (0, 100, 1000):
            with self.subTest(strength=strength):
                result = ShapeContract(self.ref, strength).evaluate(PARENT, identity=self.ident)
                self.assertEqual(result.energy, 0.0)
                self.assertEqual(result.forces, ((0.0, 0.0, 0.0),) * 4)

    def test_all_36_force_components_against_independent_finite_differences(self):
        h = 1e-6
        checked = 0
        for strength in (0, 100, 1000):
            result = ShapeContract(self.ref, strength).evaluate(TRIAL, identity=self.ident)
            self.assertAlmostEqual(result.energy, scalar_energy(TRIAL, PARENT, strength), places=12)
            for i in range(4):
                for axis in range(3):
                    plus, minus = [list(r) for r in TRIAL], [list(r) for r in TRIAL]
                    plus[i][axis] += h
                    minus[i][axis] -= h
                    numeric = -(scalar_energy(plus, PARENT, strength) -
                                scalar_energy(minus, PARENT, strength)) / (2 * h)
                    self.assertAlmostEqual(result.forces[i][axis], numeric, delta=3e-8)
                    checked += 1
        self.assertEqual(checked, 36)

    def test_mean_pair_normalization_and_decade_strength(self):
        a = ShapeContract(self.ref, 100).evaluate(TRIAL, identity=self.ident)
        b = ShapeContract(self.ref, 1000).evaluate(TRIAL, identity=self.ident)
        deviations = [math.dist(TRIAL[i], TRIAL[j]) - math.dist(PARENT[i], PARENT[j])
                      for i in range(4) for j in range(i + 1, 4)]
        rms = math.sqrt(sum(v * v for v in deviations) / 6)
        self.assertAlmostEqual(a.energy, 100 * rms * rms / 2, places=14)
        self.assertAlmostEqual(b.energy, 10 * a.energy, places=13)
        for fa, fb in zip(a.forces, b.forces):
            for ca, cb in zip(fa, fb):
                self.assertAlmostEqual(cb, 10 * ca, places=12)
        two = reference(((0, 0, 0), (1, 0, 0)))
        for strength, expected in ((0, 0), (100, 0.125), (1000, 1.25)):
            got = ShapeContract(two, strength).evaluate(((0, 0, 0), (1.05, 0, 0)), identity=two.identity)
            self.assertAlmostEqual(got.energy, expected, places=13)

    def test_rigid_invariance_and_force_covariance(self):
        def rotate(p):
            return (-p[1], p[0], p[2])
        shifted = tuple(tuple(v + t for v, t in zip(rotate(p), (3, -4, 2))) for p in TRIAL)
        contract = ShapeContract(self.ref, 1000)
        a = contract.evaluate(TRIAL, identity=self.ident)
        b = contract.evaluate(shifted, identity=self.ident)
        self.assertAlmostEqual(a.energy, b.energy, places=12)
        for actual, original in zip(b.forces, a.forces):
            for x, y in zip(actual, rotate(original)):
                self.assertAlmostEqual(x, y, places=12)

    def test_zero_net_force_and_torque(self):
        result = ShapeContract(self.ref, 1000).evaluate(TRIAL, identity=self.ident)
        for axis in range(3):
            self.assertAlmostEqual(sum(f[axis] for f in result.forces), 0.0, places=12)
        torque = [0.0] * 3
        for (x, y, z), (fx, fy, fz) in zip(TRIAL, result.forces):
            torque[0] += y * fz - z * fy
            torque[1] += z * fx - x * fz
            torque[2] += x * fy - y * fx
        for component in torque:
            self.assertAlmostEqual(component, 0.0, places=12)

    def test_reflection_blindness_is_explicit(self):
        mirrored = tuple((-x, y, z) for x, y, z in PARENT)
        result = ShapeContract(self.ref, 1000).evaluate(mirrored, identity=self.ident)
        self.assertEqual(result.energy, 0.0)
        self.assertEqual(result.forces, ((0.0, 0.0, 0.0),) * 4)

    def test_exact_zero_branch_never_inspects_trial_coordinates(self):
        class Poison:
            def __iter__(self):
                raise AssertionError("zero branch touched trial coordinates")
            def __len__(self):
                raise AssertionError("zero branch touched trial coordinates")
        contract = ShapeContract(self.ref, 0)
        for coords in (Poison(), None, [(float("nan"),) * 3], [(0, 0, 0)] * 4):
            result = evaluate_shape(contract, coords, identity=self.ident)
            self.assertEqual(result.energy.hex(), "0x0.0p+0")
            self.assertTrue(all(v.hex() == "0x0.0p+0" for f in result.forces for v in f))
        changed = identity(canonical_molecule="different source identity")
        with self.assertRaises(ShapeContractError):
            contract.evaluate(Poison(), identity=changed)

    def test_guard_boundary_in_reference_and_positive_trial(self):
        for distance, accepted in ((math.nextafter(MIN_DISTANCE, 0.0), False),
                                   (MIN_DISTANCE, True),
                                   (math.nextafter(MIN_DISTANCE, math.inf), True)):
            coords = ((0, 0, 0), (distance, 0, 0))
            with self.subTest(distance=distance):
                if accepted:
                    self.assertEqual(reference(coords).distances, (distance,))
                else:
                    with self.assertRaises(ShapeDomainError):
                        reference(coords)
                base = reference(((0, 0, 0), (1, 0, 0)))
                contract = ShapeContract(base, 100)
                if accepted:
                    self.assertTrue(math.isfinite(contract.evaluate(coords, identity=base.identity).energy))
                else:
                    with self.assertRaises(ShapeDomainError):
                        contract.evaluate(coords, identity=base.identity)
        with self.assertRaises(ShapeDomainError):
            reference(((0, 0, 0), (0, 0, 0)))

    def test_two_and_256_atoms_include_hydrogens_and_every_pair(self):
        for n in (2, MAX_ATOMS):
            with self.subTest(n=n):
                coords = tuple((float(i), 0.0, 0.0) for i in range(n))
                ref = reference(coords)
                self.assertEqual(len(ref.pairs), n * (n - 1) // 2)
                self.assertEqual(ref.pairs[0], (0, 1))
                self.assertEqual(ref.pairs[-1], (n - 2, n - 1))
                self.assertEqual(ref.identity.elements[-1], "H")
                result = ShapeContract(ref, 100).evaluate(coords, identity=ref.identity)
                self.assertEqual(result.energy, 0.0)
                changed = [list(p) for p in coords]
                changed[-1][1] += 0.2
                result = ShapeContract(ref, 100).evaluate(changed, identity=ref.identity)
                self.assertGreater(result.energy, 0)
                self.assertNotEqual(result.forces[-1], (0.0, 0.0, 0.0))

    def test_overflow_and_nonfinite_inputs_are_rejected(self):
        for coords in (((-1e308, 0, 0), (1e308, 0, 0)),
                       ((0, 0, 0), (1.5e308, 1.5e308, 1.5e308))):
            with self.subTest(coords=coords):
                with self.assertRaises(ShapeDomainError):
                    reference(coords)
                base = reference(((0, 0, 0), (1, 0, 0)))
                with self.assertRaises(ShapeDomainError):
                    ShapeContract(base, 100).evaluate(coords, identity=base.identity)
        base = reference(((0, 0, 0), (1, 0, 0)))
        for value in (float("nan"), float("inf"), -float("inf"), 1e200, -1e200, 1e154, 10 ** 400):
            with self.subTest(value=str(value)[:25]):
                with self.assertRaises(ShapeDomainError):
                    ShapeContract(base, 1000).evaluate(((0, 0, 0), (value, 0, 0)), identity=base.identity)
        # A finite large distance itself is representable; no naive squared norm.
        huge = reference(((0, 0, 0), (1e200, 0, 0)))
        self.assertEqual(ShapeContract(huge, 100).evaluate(huge.coordinates, identity=huge.identity).energy, 0)
        # Individual squares fit, their unnormalized sum does not.
        ref3 = reference(((0, 0, 0), (1, 0, 0), (2, 0, 0)))
        with self.assertRaises(ShapeDomainError):
            ShapeContract(ref3, 100).evaluate(((0, 0, 0), (1e154, 0, 0), (0, 1e154, 0)), identity=ref3.identity)

    def test_invalid_trial_coordinate_shapes_and_types(self):
        contract = ShapeContract(self.ref, 100)
        for coords in (None, "xyz", [[0, 0, 0]], [[0, 0]] * 4,
                       [[True, 0, 0]] * 4, [["1", 0, 0]] * 4, [[0, 0, 0]] * 4):
            with self.subTest(coords=coords):
                with self.assertRaises(ShapeContractError):
                    contract.evaluate(coords, identity=self.ident)


class ShapeIdentityTests(unittest.TestCase):
    def test_invalid_graphs_atom_counts_and_ids(self):
        for n in (0, 1, 257):
            with self.subTest(n=n), self.assertRaises(ShapeContractError):
                identity(n)
        invalid = [[], [(0, 1, "single")], [(0, 1, "single"), (2, 3, "single")],
                   [(0, 1, "single"), (0, 1, "double"), (1, 2, "single"), (2, 3, "single")],
                   [(1, 2, "single"), (0, 1, "single"), (2, 3, "single")],
                   [(1, 0, "single")], [(0, 4, "single")], [(False, 1, "single")],
                   [(0, 0, "single")], [(0, 1, "")], [(0, 1)]]
        for bonds in invalid:
            with self.subTest(bonds=bonds), self.assertRaises(ShapeContractError):
                identity(covalent_bonds=bonds)
        for ids in (["a"] * 4, ["a", "b", "c", ""], ["a", "b", "c", 4]):
            with self.assertRaises(ShapeContractError):
                identity(atom_ids=ids)
        for elements in (["C"] * 3, ["C", "C", "C", "hydrogen"], ["C", "C", "C", True]):
            with self.assertRaises(ShapeContractError):
                identity(elements=elements)

    def test_trial_order_element_topology_and_molecule_are_bound(self):
        ref = reference()
        cases = [identity(atom_ids=["source:1", "source:0", "source:2", "source:3"]),
                 identity(elements=["C"] * 4),
                 identity(covalent_bonds=[(0, 1, "double"), (1, 2, "single"), (2, 3, "single")]),
                 identity(covalent_bonds=[(0, 1, "single"), (0, 2, "single"), (0, 3, "single")]),
                 identity(canonical_molecule="different")]
        for strength in (0, 100):
            contract = ShapeContract(ref, strength)
            for changed in cases:
                with self.subTest(strength=strength, changed=changed), self.assertRaises(ShapeContractError):
                    contract.evaluate(PARENT, identity=changed)

    def test_all_values_are_defensively_copied(self):
        ids, elements = ["a", "b"], ["C", "H"]
        bonds, coords = [[0, 1, "single"]], [[-0.0, 0, 0], [1, 0, 0]]
        ident = MoleculeIdentity(ids, elements, bonds, "synthetic CH")
        ref = reference(coords, ident)
        contract = ShapeContract(ref, 100)
        expected = contract.to_json()
        ids.reverse()
        elements[1] = "O"
        bonds[0][2] = "double"
        coords[1][0] = 2
        self.assertEqual(expected, contract.to_json())
        object.__setattr__(ident, "atom_ids", ("changed", "b"))
        object.__setattr__(ref, "coordinates", ((0.0, 0.0, 0.0), (9.0, 0.0, 0.0)))
        self.assertEqual(expected, contract.to_json())
        output = contract.to_document()
        output["reference"]["identity"]["atom_ids"][0] = "changed"
        self.assertEqual(expected, contract.to_json())

    def test_ordinary_mutation_is_impossible_and_forced_mutation_is_detected(self):
        contract = ShapeContract(reference(), 100)
        for obj, attr, value in ((contract, "strength", 1000),
                                 (contract.reference, "coordinates", PARENT),
                                 (contract.reference.identity, "atom_ids", ("x",))):
            with self.assertRaises((FrozenInstanceError, AttributeError)):
                setattr(obj, attr, value)
        cases = [("strength", 1000.0), ("reference_digest", "0" * 64), ("digest", "0" * 64)]
        for attr, value in cases:
            bad = ShapeContract(reference(), 100)
            object.__setattr__(bad, attr, value)
            with self.assertRaises(ShapeContractError):
                bad.evaluate(TRIAL, identity=identity())
        for attr, value in (("pairs", ((0, 1),) * 6), ("distances", (1.0,) * 6),
                            ("coordinates", [list(r) for r in PARENT]),
                            ("coordinates_digest", "0" * 64), ("parent_provenance", "changed")):
            bad = ShapeContract(reference(), 100)
            object.__setattr__(bad.reference, attr, value)
            with self.subTest(attr=attr), self.assertRaises(ShapeContractError):
                bad.evaluate(TRIAL, identity=identity())
        bad = ShapeContract(reference(), 0)
        object.__setattr__(bad.reference.identity, "covalent_bonds", ((0, 1, "double"), (1, 2, "single"), (2, 3, "single")))
        with self.assertRaises(ShapeContractError):
            bad.evaluate(None, identity=identity())

    def test_uninitialized_forged_and_subclassed_objects_are_rejected(self):
        for cls in (MoleculeIdentity, ShapeReference, ShapeContract):
            fake = object.__new__(cls)
            with self.subTest(cls=cls), self.assertRaises(ShapeContractError):
                fake.validate_integrity()
        class FakeContract(ShapeContract):
            pass
        fake = FakeContract(reference(), 100)
        with self.assertRaises(ShapeContractError):
            evaluate_shape(fake, TRIAL, identity=identity())
        with self.assertRaises(ShapeContractError):
            evaluate_shape(object(), TRIAL, identity=identity())

    def test_strength_and_reference_metadata_validation(self):
        for strength in (-0.0, -1, 1, 101, 1001, float("nan"), float("inf"), True, "100"):
            with self.subTest(strength=strength), self.assertRaises(ShapeContractError):
                ShapeContract(reference(), strength)
        for kwargs in ({"parent_role": "current_restart"}, {"parent_provenance": ""},
                       {"source_identity": " padded"}, {"source_digest": "A" * 64},
                       {"source_digest": "a" * 63}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ShapeContractError):
                reference(**kwargs)


class ShapeSerializationTests(unittest.TestCase):
    def setUp(self):
        self.ref = reference()
        self.contract = ShapeContract(self.ref, 100)

    def test_reference_and_contract_exact_round_trip(self):
        for original in (self.ref, self.contract):
            with self.subTest(cls=type(original)):
                restored = type(original).from_json(original.to_json(), expected_digest=original.digest)
                self.assertEqual(original, restored)
                self.assertEqual(original.to_json(), restored.to_json())
                self.assertIsNot(original, restored)
                with self.assertRaises(ShapeContractError):
                    type(original).from_json(original.to_json(), expected_digest="0" * 64)
        self.assertEqual(self.contract.evaluate(TRIAL, identity=self.ref.identity),
                         ShapeContract.from_document(self.contract.to_document(), expected_digest=self.contract.digest)
                         .evaluate(TRIAL, identity=self.ref.identity))

    def test_signed_zero_and_exact_original_binary64_are_preserved(self):
        ref = reference(((-0.0, 0.0, 0.0), (math.nextafter(1.0, math.inf), 0.0, 0.0)))
        restored = ShapeReference.from_json(ref.to_json(), expected_digest=ref.digest)
        self.assertEqual(restored.coordinates[0][0].hex(), "-0x0.0p+0")
        self.assertEqual(restored.coordinates[1][0].hex(), math.nextafter(1.0, math.inf).hex())
        changed = reference(((0.0, 0.0, 0.0), (math.nextafter(1.0, math.inf), 0.0, 0.0)))
        self.assertNotEqual(ref.coordinates_digest, changed.coordinates_digest)
        self.assertNotEqual(ref.digest, changed.digest)

    def test_resealed_pair_forgeries_still_fail_structural_validation(self):
        mutations = [lambda d: d["pairs"].pop(),
                     lambda d: d["pairs"].reverse(),
                     lambda d: d["pairs"].__setitem__(1, d["pairs"][0]),
                     lambda d: d["pairs"].__setitem__(0, [1, 0]),
                     lambda d: d["pairs"].__setitem__(0, [False, 1]),
                     lambda d: d["reference_distances_binary64"].__setitem__(0, (4.0).hex()),
                     lambda d: d["reference_distances_binary64"].__setitem__(0, "inf"),
                     lambda d: d.__setitem__("pair_count", 5),
                     lambda d: d.__setitem__("pair_count", True)]
        for mutate in mutations:
            doc = self.ref.to_document()
            mutate(doc)
            if doc["pair_count"] is True:
                with self.assertRaises(ShapeContractError):
                    ShapeReference.from_document(doc, expected_digest=doc["digest"])
                continue
            reseal(doc)
            with self.subTest(doc=doc), self.assertRaises(ShapeContractError):
                ShapeReference.from_document(doc, expected_digest=doc["digest"])

    def test_resealed_metadata_forgery_and_noncanonical_values_fail(self):
        mutations = [("schema_id", "new"), ("pair_selection", "heavy_atoms_only"),
                     ("normalization", "1"), ("minimum_distance_binary64", (1e-9).hex()),
                     ("atom_count", 5), ("coordinates_digest", "0" * 64)]
        for key, value in mutations:
            doc = self.ref.to_document()
            doc[key] = value
            reseal(doc)
            with self.subTest(key=key), self.assertRaises(ShapeContractError):
                ShapeReference.from_document(doc, expected_digest=doc["digest"])
        for value in ("0x0p+0", "nan", "inf", "0x1p+99999"):
            doc = self.ref.to_document()
            doc["coordinates_binary64"][0][0] = value
            reseal(doc)
            with self.subTest(value=value), self.assertRaises(ShapeContractError):
                ShapeReference.from_document(doc, expected_digest=doc["digest"])
        for key in ("molecular_digest", "topology_digest"):
            doc = self.ref.to_document()
            doc["identity"][key] = "0" * 64
            reseal(doc)
            with self.assertRaises(ShapeContractError):
                ShapeReference.from_document(doc, expected_digest=doc["digest"])

    def test_unknown_missing_duplicate_and_wrongly_typed_fields_fail(self):
        for original in (self.ref, self.contract):
            cls = type(original)
            for change in (lambda d: d.__setitem__("unknown", "x"), lambda d: d.pop("schema_id")):
                doc = original.to_document()
                change(doc)
                with self.assertRaises(ShapeContractError):
                    cls.from_document(doc, expected_digest=original.digest)
            text = original.to_json()
            duplicate = text[:-1] + ',"digest":"' + original.digest + '"}'
            for payload in (duplicate, "[]", "null", "{", '{"x": NaN}', '{"x": Infinity}'):
                with self.subTest(payload=payload[:30]), self.assertRaises(ShapeContractError):
                    cls.from_json(payload, expected_digest=original.digest)
        for value in (("source:0", "source:1", "source:2", "source:3"), None, True, 1.0):
            doc = self.ref.to_document()
            doc["identity"]["atom_ids"] = value
            with self.assertRaises(ShapeContractError):
                ShapeReference.from_document(doc, expected_digest=self.ref.digest)

    def test_trusted_digest_rejects_consistent_reference_substitution(self):
        replacement = reference(tuple(tuple(2 * v for v in row) for row in PARENT))
        with self.assertRaises(ShapeContractError):
            ShapeReference.from_json(replacement.to_json(), expected_digest=self.ref.digest)
        replacement_contract = ShapeContract(replacement, 100)
        with self.assertRaises(ShapeContractError):
            ShapeContract.from_json(replacement_contract.to_json(), expected_digest=self.contract.digest)
        for strength in (0, 1000):
            replacement_contract = ShapeContract(self.ref, strength)
            with self.assertRaises(ShapeContractError):
                ShapeContract.from_json(replacement_contract.to_json(), expected_digest=self.contract.digest)

    def test_resealed_contract_with_wrong_bound_reference_or_strength_fails(self):
        for key, value in (("reference_digest", "0" * 64), ("strength_binary64", (1.0).hex()),
                           ("strength_binary64", "100.0"), ("schema_id", "other")):
            doc = self.contract.to_document()
            doc[key] = value
            reseal(doc)
            with self.subTest(key=key), self.assertRaises(ShapeContractError):
                ShapeContract.from_document(doc, expected_digest=doc["digest"])
        doc = self.contract.to_document()
        doc["strength_binary64"] = (1000.0).hex()
        with self.assertRaises(ShapeContractError):
            ShapeContract.from_document(doc, expected_digest=self.contract.digest)


if __name__ == "__main__":
    unittest.main(verbosity=2)
