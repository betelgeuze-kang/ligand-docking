"""Negative controls for the source-only PFKFB3 structure-crosswalk receipt."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().with_name("verify_primary_structure_crosswalk.py")
SPEC = importlib.util.spec_from_file_location("pfkfb3_primary_structure_verify", SCRIPT)
verify_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_module)


class PrimaryStructureCrosswalkTests(unittest.TestCase):
    def _write(self, directory: Path, value: dict) -> Path:
        path = directory / "receipt.json"
        path.write_text(json.dumps(value, ensure_ascii=False) + "\n")
        return path

    def _reject(self, mutate) -> None:
        with tempfile.TemporaryDirectory() as temp:
            value = copy.deepcopy(verify_module.expected_receipt())
            mutate(value)
            with self.assertRaisesRegex(ValueError, "receipt_mismatch"):
                verify_module.verify(self._write(Path(temp), value))

    def test_pinned_receipt_passes_as_partial_and_blocked(self):
        result = verify_module.verify()
        self.assertEqual(
            result["status"], "PASS_STATIC_PRIMARY_STRUCTURE_CROSSWALK_PARTIAL_BLOCKED"
        )
        self.assertEqual(result["candidate_count"], 40)
        self.assertEqual(result["direct_primary_anchor_count"], 4)
        self.assertEqual(result["primary_text_motif_match_count"], 14)
        self.assertEqual(result["unverified_count"], 22)
        self.assertFalse(result["external_sources_rechecked_by_static_verifier"])
        self.assertFalse(result["paper_or_sdf_rechecked_by_static_verifier"])

    def test_grade_or_denominator_cannot_be_promoted(self):
        self._reject(
            lambda doc: doc["records"][0].update(evidence_grade="direct_primary_anchor")
        )
        self._reject(
            lambda doc: doc["records"][3].update(
                evidence_grade="primary_text_motif_match"
            )
        )
        self._reject(lambda doc: doc["counts"].update(unverified_count=0))
        self._reject(lambda doc: doc["records"].pop())

    def test_source_hash_and_structure_cannot_be_resealed(self):
        self._reject(
            lambda doc: doc["records"][0]["official_sdf"].update(sha256="0" * 64)
        )
        self._reject(lambda doc: doc["records"][0]["official_sdf"].update(bytes=0))
        self._reject(
            lambda doc: doc["records"][0].update(
                observed_sdf_structure="different motif"
            )
        )
        self._reject(lambda doc: doc["sources"].update(openff_commit="0" * 40))

    def test_primary_location_and_limit_cannot_be_invented(self):
        self._reject(
            lambda doc: doc["records"][0]["primary_evidence"].update(manuscript_page=9)
        )
        self._reject(
            lambda doc: doc["records"][0]["primary_evidence"].update(
                sentence_locator="new claim"
            )
        )
        self._reject(
            lambda doc: doc["records"][3].update(primary_evidence={"unverified": False})
        )
        self._reject(
            lambda doc: doc["records"][0].update(interpretation_limit="fully verified")
        )

    def test_experimental_field_and_scope_promotion_are_rejected(self):
        self._reject(
            lambda doc: doc["records"][0].update(
                measurement={"unexpected": "synthetic"}
            )
        )
        self._reject(
            lambda doc: doc["boundary"].update(all_40_primary_structures_verified=True)
        )
        self._reject(lambda doc: doc["boundary"].update(comparison_eligible=True))
        self._reject(
            lambda doc: doc["boundary"].update(
                paper_or_sdf_rechecked_by_static_verifier=True
            )
        )
        self._reject(lambda doc: doc["boundary"].update(experimental_values_recorded=0))

    def test_pinned_inventory_cannot_be_changed_with_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            inventory = Path(temp) / "inventory.json"
            raw = verify_module.INVENTORY.read_bytes()
            changed = raw.replace(
                verify_module.COMMIT.encode(),
                b"0" + verify_module.COMMIT[1:].encode(),
                1,
            )
            self.assertNotEqual(changed, raw)
            inventory.write_bytes(changed)
            with self.assertRaisesRegex(ValueError, "pinned_inventory_bytes_changed"):
                verify_module.verify(inventory_path=inventory)

    def test_duplicate_json_key_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"schema_version":"x","schema_version":"y"}')
            with self.assertRaisesRegex(ValueError, "duplicate_json_key"):
                verify_module.verify(duplicate)
            link = root / "link.json"
            link.symlink_to(verify_module.MANIFEST)
            with self.assertRaises(OSError):
                verify_module.verify(link)


if __name__ == "__main__":
    unittest.main()
