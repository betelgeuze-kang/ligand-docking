"""Negative controls for the blocked JQ1 source-identity contrast."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "_brd4_jq1_chemical_lineage_tested", ROOT / "verify_jq1_chemical_lineage.py"
)
assert SPEC is not None and SPEC.loader is not None
lineage = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lineage
SPEC.loader.exec_module(lineage)


class JQ1ChemicalLineageTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for filename in (lineage.PROJECTION_NAME, lineage.RECEIPT_NAME):
            shutil.copyfile(ROOT / filename, self.root / filename)
        (self.root / "official_sources").mkdir()
        for relative, _, _ in lineage.SOURCES.values():
            shutil.copyfile(ROOT / relative, self.root / relative)

    def tearDown(self):
        self.temporary.cleanup()

    def test_original_sources_pass_with_blocked_eligibility(self):
        result = lineage.verify(self.root)
        self.assertEqual(result["status"], "PASS_SOURCE_CHEMICAL_LINEAGE_ONLY")
        receipt = json.loads((self.root / lineage.RECEIPT_NAME).read_text())
        self.assertFalse(receipt["eligibility"]["scientifically_validated"])
        self.assertFalse(
            receipt["interpretation_boundaries"][
                "complete_unique_ccd_to_pubchem_atom_map"
            ]
        )
        self.assertEqual(
            [
                item["element_graph_isomorphism_count"]
                for item in receipt["comparisons"]
            ],
            [12] * 4,
        )
        self.assertEqual(
            [
                item["literal_bond_order_preserving_mapping_count"]
                for item in receipt["comparisons"]
            ],
            [0] * 4,
        )

    def test_receipt_promotion_is_rejected(self):
        path = self.root / lineage.RECEIPT_NAME
        receipt = json.loads(path.read_text())
        receipt["eligibility"]["training_admitted"] = True
        path.write_bytes(lineage.json_bytes(receipt))
        with self.assertRaisesRegex(ValueError, "lineage_receipt_mismatch"):
            lineage.verify(self.root)

    def test_coordinated_projection_and_receipt_tampering_is_rejected(self):
        path = self.root / lineage.PROJECTION_NAME
        projection = json.loads(path.read_text())
        projection["records"][0]["systematic_name"] += " tampered"
        path.write_bytes(lineage.json_bytes(projection))
        (self.root / lineage.RECEIPT_NAME).write_bytes(
            lineage.json_bytes(lineage.build_observation(self.root, projection))
        )
        with self.assertRaisesRegex(ValueError, "pubchem_projection_bytes_changed"):
            lineage.verify(self.root)

    def test_wrong_proton_location_is_rejected_even_with_same_heavy_graph(self):
        projection = copy.deepcopy(lineage._checked_projection(self.root))
        neutral_s = projection["records"][0]
        # Move CBC's explicit H to NAP; all heavy-atom connectivity remains intact.
        moved = [
            bond for bond in neutral_s["bonds"] if 9 in bond[:2] and 32 in bond[:2]
        ]
        self.assertEqual(len(moved), 1)
        moved[0][0] = 7
        with self.assertRaisesRegex(ValueError, "neutral_s_proton_contrast_changed"):
            lineage.build_observation(self.root, projection)

    def test_r_descriptor_flip_is_rejected(self):
        projection = copy.deepcopy(lineage._checked_projection(self.root))
        r_record = projection["records"][1]
        r_record["systematic_name"] = r_record["systematic_name"].replace(
            "(9R)", "(9S)"
        )
        with self.assertRaisesRegex(ValueError, "pubchem_stereo_descriptor_changed"):
            lineage.build_observation(self.root, projection)

    def test_r_tetrahedral_record_flip_is_rejected(self):
        projection = copy.deepcopy(lineage._checked_projection(self.root))
        projection["records"][1]["tetrahedral"]["parity"] = 2
        with self.assertRaisesRegex(ValueError, "pubchem_tetrahedral_source_changed"):
            lineage.build_observation(self.root, projection)

    def test_ccd_source_bytes_change_is_rejected(self):
        path = self.root / lineage.SOURCES["ccd_jq1"][0]
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "cif_source_bytes_changed"):
            lineage.verify(self.root)


if __name__ == "__main__":
    unittest.main()
