"""Negative controls for source-only BRD4/JQ1 atom and geometry lineage."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


PACKET = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "_brd4_source_geometry_verifier", PACKET / "verify_source_geometry.py"
)
assert SPEC is not None and SPEC.loader is not None
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

    def test_source_lineage_preserves_unprepared_chemical_state_and_environment(self):
        ligand = self.observation["jq1_source_and_ccd_lineage"]
        self.assertEqual(ligand["observed_heavy_atom_count"], 31)
        self.assertEqual(len(ligand["ccd_missing_hydrogen_names"]), 26)
        self.assertTrue(
            ligand["ccd_heavy_atom_names_elements_and_model_coordinates_match"]
        )
        self.assertEqual(ligand["ccd_stereocenters"], {"CBC": "S"})
        self.assertEqual(ligand["ccd_nonzero_atom_charges"], {"NBD": "1"})
        self.assertEqual(ligand["coordinate_atom_site_unknown_formal_charge_count"], 31)
        self.assertEqual(len(ligand["ccd_heavy_bond_distances"]), 34)
        self.assertFalse(ligand["assay_microstate_equivalence_inferred"])
        self.assertFalse(ligand["r_enantiomer_bound_pose_observed"])
        protein = self.observation["protein_source_scope"]
        self.assertEqual(protein["source_residues_42_43"][1]["mon_id"], "MET")
        self.assertEqual(protein["source_core_residues_44_168_count"], 125)
        self.assertEqual(len(protein["protein_altloc_rows"]), 30)
        environment = self.observation["jq1_source_environment"]
        self.assertEqual(
            {
                name: len(ids)
                for name, ids in environment["nonpoly_component_atom_site_ids"].items()
            },
            {"DMS": 4, "EDO": 12, "HOH": 208, "IOD": 1, "JQ1": 31},
        )
        self.assertEqual(environment["water_oxygens_within_radius"], 15)
        self.assertEqual(
            environment["nearest_iodide_pair"]["distance_angstrom"], "26.835179261559"
        )
        self.assertFalse(
            environment["ion_solvent_water_retain_or_exclude_decision_made"]
        )
        self.assertTrue(
            all(
                value is False or type(value) is int and value == 0
                for value in self.observation["eligibility"].values()
            )
        )

    def test_receipt_recomputes_without_site_packages(self):
        self.assertEqual(
            (PACKET / MODULE.RECEIPT_NAME).read_bytes(),
            MODULE.json_bytes(self.observation),
        )
        self.assertEqual(MODULE.verify()["status"], "PASS_SOURCE_GEOMETRY_ONLY")
        self.assertNotIn("betelgeuze_engine_v2", sys.modules)

    def test_selection_distance_and_prepared_claim_tamper_reject(self):
        changes = [
            (("jq1_source_and_ccd_lineage", "selection", "label_asym_id"), "C"),
            (("jq1_source_and_ccd_lineage", "ccd_stereocenters", "CBC"), "R"),
            (
                ("jq1_source_environment", "nearest_iodide_pair", "distance_angstrom"),
                "2.0",
            ),
            (("eligibility", "receptor_prepared"), True),
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

    def test_same_size_source_byte_tamper_rejects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.copy_packet(root)
            for key, old, new in (
                ("coordinates", b"29.899", b"29.898"),
                ("ccd_jq1", b"JQ1 CBC", b"JQ1 CBE"),
            ):
                with self.subTest(source=key):
                    path = root / MODULE.SOURCES[key][0]
                    original = path.read_bytes()
                    altered = original.replace(old, new, 1)
                    self.assertNotEqual(original, altered)
                    self.assertEqual(len(original), len(altered))
                    path.write_bytes(altered)
                    with self.assertRaisesRegex(ValueError, "archive_bytes_changed"):
                        MODULE.build_observation(root)
                    path.write_bytes(original)

    def test_duplicate_json_key_and_false_numeric_alias_reject(self):
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
