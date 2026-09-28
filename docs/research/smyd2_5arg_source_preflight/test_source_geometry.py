"""Standard-library regression controls for the pinned source-only receipt."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


PACKET = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "_smyd2_source_geometry_verifier", PACKET / "verify_source_geometry.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SourceGeometryReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.observation = MODULE.build_observation()

    def copy_packet(self, root):
        (root / "official_sources").mkdir()
        for relative, _, _ in MODULE.SOURCES.values():
            shutil.copyfile(PACKET / relative, root / relative)
        (root / MODULE.RECEIPT_NAME).write_bytes(MODULE.json_bytes(self.observation))

    def test_pinned_source_preserves_absence_and_competing_annotations(self):
        h41 = self.observation["h41_completeness"]
        self.assertEqual(h41["observed_heavy_atom_count"], 35)
        self.assertEqual(h41["observed_hydrogen_atom_count"], 0)
        self.assertEqual(h41["missing_heavy_atom_names"], [])
        self.assertEqual(len(h41["missing_hydrogen_atom_names"]), 20)
        self.assertEqual(h41["source_atom_site_unknown_formal_charge_count"], 35)
        context = self.observation["disulfide_annotation_and_nearby_zinc"]
        self.assertEqual(
            context["source_struct_conn_annotation"]["values"]["conn_type_id"], "disulf"
        )
        self.assertEqual(
            context["source_annotated_partner_distance"]["distance_angstrom"],
            "2.333410379680",
        )
        self.assertEqual(
            [pair["distance_angstrom"] for pair in context["zinc_to_sulfur_distances"]],
            [
                "2.270418023184",
                "2.413958367495",
                "2.358644737980",
                "2.269158875002",
            ],
        )
        self.assertFalse(context["annotation_adjudicated"])
        self.assertFalse(context["coordination_or_covalence_inferred"])
        environment = self.observation["h41_environment"]
        self.assertEqual(environment["protein_altloc_rows_retained"], 88)
        self.assertEqual(environment["water_oxygens_within_radius"], 13)
        self.assertEqual(
            environment["all_nonpoly_component_atom_site_counts"],
            {"GOL": 6, "H41": 35, "HOH": 137, "SAM": 27, "ZN": 3},
        )
        self.assertTrue(
            all(
                value is False or type(value) is int and value == 0
                for value in self.observation["eligibility"].values()
            )
        )

    def test_canonical_receipt_is_reproduced_without_site_packages(self):
        self.assertEqual(
            (PACKET / MODULE.RECEIPT_NAME).read_bytes(),
            MODULE.json_bytes(self.observation),
        )
        self.assertEqual(MODULE.verify()["status"], "PASS_SOURCE_GEOMETRY_ONLY")
        self.assertNotIn("torch", sys.modules)
        self.assertNotIn("betelgeuze_engine_v2", sys.modules)

    def test_distance_selection_annotation_and_claim_tampering_reject(self):
        changes = [
            (("h41_completeness", "selection", "auth_seq_id"), "1433"),
            (
                (
                    "disulfide_annotation_and_nearby_zinc",
                    "source_annotated_partner_distance",
                    "distance_angstrom",
                ),
                "2.0",
            ),
            (
                (
                    "disulfide_annotation_and_nearby_zinc",
                    "source_struct_conn_annotation",
                    "values",
                    "conn_type_id",
                ),
                "metalc",
            ),
            (("eligibility", "scientifically_validated"), True),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.copy_packet(root)
            for keys, value in changes:
                with self.subTest(keys=keys):
                    altered = deepcopy(self.observation)
                    target = altered
                    for key in keys[:-1]:
                        target = target[key]
                    target[keys[-1]] = value
                    (root / MODULE.RECEIPT_NAME).write_bytes(MODULE.json_bytes(altered))
                    with self.assertRaisesRegex(
                        ValueError, "source_geometry_receipt_mismatch"
                    ):
                        MODULE.verify(root)

    def test_same_size_source_coordinate_tamper_rejects_before_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.copy_packet(root)
            path = root / MODULE.SOURCES["coordinates"][0]
            raw = path.read_bytes()
            altered = raw.replace(b"-20.370", b"-20.371", 1)
            self.assertNotEqual(raw, altered)
            self.assertEqual(len(raw), len(altered))
            path.write_bytes(altered)
            with self.assertRaisesRegex(ValueError, "archive_bytes_changed"):
                MODULE.build_observation(root)

    def test_duplicate_json_keys_extra_fields_and_false_numeric_alias_reject(self):
        raw = MODULE.json_bytes(self.observation)
        altered_documents = [
            raw.replace(
                b'"scientifically_validated": false',
                b'"scientifically_validated": false, "scientifically_validated": false',
                1,
            ),
            raw.replace(
                b'"scientifically_validated": false',
                b'"scientifically_validated": 0',
                1,
            ),
            raw[:-2] + b', "extra": null\n}\n',
        ]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.copy_packet(root)
            for altered in altered_documents:
                with self.subTest(document=altered[-80:]):
                    (root / MODULE.RECEIPT_NAME).write_bytes(altered)
                    with self.assertRaisesRegex(
                        ValueError, "source_geometry_receipt_mismatch"
                    ):
                        MODULE.verify(root)


if __name__ == "__main__":
    unittest.main()
