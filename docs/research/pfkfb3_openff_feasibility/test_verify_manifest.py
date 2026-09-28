"""Mutation controls for the metadata-only PFKFB3 receipt."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().with_name("verify_manifest.py")
SPEC = importlib.util.spec_from_file_location("pfkfb3_feasibility_verify", SCRIPT)
verify_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_module)


class FeasibilityReceiptTests(unittest.TestCase):
    def _write(self, root: Path, value: dict) -> Path:
        path = root / "feasibility.json"
        path.write_text(json.dumps(value, ensure_ascii=False) + "\n")
        return path

    def _reject(self, mutate):
        with tempfile.TemporaryDirectory() as temp:
            value = copy.deepcopy(verify_module.expected_manifest())
            mutate(value)
            with self.assertRaises(ValueError):
                verify_module.verify(self._write(Path(temp), value))

    def test_original_packet_passes_without_archive(self):
        result = verify_module.verify()
        self.assertEqual(result["status"], "PASS_STATIC_FEASIBILITY_BLOCKED")
        self.assertEqual(result["candidate_count"], 40)
        self.assertEqual(result["eligible_source_state_join_count"], 0)
        self.assertFalse(result["external_archive_or_source_bytes_checked"])

    def test_candidate_denominator_or_identity_cannot_change(self):
        self._reject(lambda doc: doc["candidates"].pop())
        self._reject(lambda doc: doc["candidates"][0].update(ligand_id="lig_999"))

    def test_archived_hash_cannot_be_resealed_inside_json(self):
        self._reject(
            lambda doc: doc["archived_lig_38_prepared_input_refs"][0].update(
                sha256="0" * 64
            )
        )
        self._reject(lambda doc: doc["source"].update(archive_sha256="0" * 64))

    def test_roles_and_eligibility_stay_blocked(self):
        self._reject(lambda doc: doc["candidates"][0].update(fit_role="fit"))
        self._reject(
            lambda doc: doc["candidates"][13].update(eligible_source_state_join=True)
        )
        self._reject(
            lambda doc: doc["eligibility"].update(eligible_source_state_join_count=1)
        )

    def test_missing_numeric_report_cannot_be_invented(self):
        self._reject(
            lambda doc: doc["candidates"][0].update(
                historical_pfk40_numeric_report_ref={"sha256": "0" * 64}
            )
        )
        self._reject(
            lambda doc: doc["historical_pfk40_numeric_reports"].update(
                individual_report_refs_in_checkout=40
            )
        )

    def test_old_context_cannot_be_promoted_or_assay_join_asserted(self):
        self._reject(
            lambda doc: doc["archived_context_observation"].update(
                archived_context_is_current_frozen_context=True
            )
        )
        self._reject(
            lambda doc: doc["assay_boundary"].update(
                same_assay_active_inactive_pair_proven=True
            )
        )
        self._reject(
            lambda doc: doc["eligibility"].update(
                current_protected_context_clearance_verified=True
            )
        )

    def test_integer_boolean_substitution_and_extra_field_rejected(self):
        self._reject(lambda doc: doc["eligibility"].update(training_admitted=0))
        self._reject(lambda doc: doc.update(experimental_value=123))

    def test_duplicate_key_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "duplicate.json"
            path.write_text('{"schema_version":"x","schema_version":"y"}')
            with self.assertRaisesRegex(ValueError, "duplicate_json_key"):
                verify_module.verify(path)
            link = root / "link.json"
            link.symlink_to(verify_module.MANIFEST)
            with self.assertRaises(OSError):
                verify_module.verify(link)


if __name__ == "__main__":
    unittest.main()
