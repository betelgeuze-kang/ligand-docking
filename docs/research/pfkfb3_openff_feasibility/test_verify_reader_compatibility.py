"""Offline mutation controls for the pinned PFKFB3 reader compatibility receipt."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().with_name("verify_reader_compatibility.py")
SPEC = importlib.util.spec_from_file_location(
    "pfkfb3_reader_compatibility_verify", SCRIPT
)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class ReaderCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = json.loads(verifier.MANIFEST.read_text())
        cls.inventory = json.loads(verifier.INVENTORY.read_text())

    def _write(self, root: Path, name: str, doc: dict) -> Path:
        path = root / name
        path.write_text(json.dumps(doc, ensure_ascii=False) + "\n")
        return path

    def _reject_manifest(self, mutate):
        with tempfile.TemporaryDirectory() as temporary:
            doc = copy.deepcopy(self.original)
            mutate(doc)
            path = self._write(Path(temporary), "reader_compatibility.json", doc)
            with self.assertRaises(ValueError):
                verifier.verify(manifest=path, inventory=verifier.INVENTORY)

    def _reject_inventory(self, mutate):
        with tempfile.TemporaryDirectory() as temporary:
            doc = copy.deepcopy(self.inventory)
            mutate(doc)
            path = self._write(Path(temporary), "openff_lfs_inventory.json", doc)
            with self.assertRaises(ValueError):
                verifier.verify(manifest=verifier.MANIFEST, inventory=path)

    def test_pinned_receipt_passes_offline(self):
        result = verifier.verify()
        self.assertEqual(result["status"], "PASS_READ_ONLY_READER_COMPATIBILITY")
        self.assertEqual(result["ligand_count"], 40)
        self.assertFalse(result["loader_reexecuted_by_offline_verifier"])
        self.assertFalse(result["scientific_comparison_eligible"])

    def test_cli_accepts_both_explicit_paths_and_rejects_mutation(self):
        command = [
            sys.executable,
            "-I",
            "-S",
            "-B",
            str(SCRIPT),
            "--manifest",
            str(verifier.MANIFEST),
            "--inventory",
            str(verifier.INVENTORY),
        ]
        passing = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(passing.returncode, 0, passing.stderr)
        self.assertIn("PASS_READ_ONLY_READER_COMPATIBILITY", passing.stdout)
        with tempfile.TemporaryDirectory() as temporary:
            doc = copy.deepcopy(self.original)
            doc["rows"][0]["ligand_atom_count"] += 1
            bad_manifest = self._write(Path(temporary), "mutated.json", doc)
            command[command.index("--manifest") + 1] = str(bad_manifest)
            failing = subprocess.run(
                command, capture_output=True, text=True, check=False
            )
            self.assertNotEqual(failing.returncode, 0)

    def test_exact_40_id_set_and_order_are_pinned(self):
        self._reject_manifest(lambda doc: doc["rows"].pop())
        self._reject_manifest(lambda doc: doc["rows"][0].update(ligand_id="lig_999"))
        self._reject_manifest(lambda doc: doc["rows"].reverse())

    def test_each_id_file_path_and_hash_are_bound_to_inventory(self):
        self._reject_manifest(
            lambda doc: doc["rows"][0]["official_files"]["sdf"].update(
                repository_path="data/2020-07-06_pfkfb3/other.sdf"
            )
        )
        self._reject_manifest(
            lambda doc: doc["rows"][0]["official_files"]["sdf"].update(sha256="0" * 64)
        )
        self._reject_manifest(
            lambda doc: doc["common_official_files"]["protein_pdb"].update(
                sha256="0" * 64
            )
        )
        self._reject_inventory(
            lambda doc: doc["files"][0].update(lfs_oid_sha256="0" * 64)
        )

    def test_reader_outcome_and_counts_cannot_be_rewritten(self):
        self._reject_manifest(lambda doc: doc["rows"][0].update(reader_status="FAIL"))
        self._reject_manifest(lambda doc: doc["rows"][0].update(ligand_atom_count=0))
        self._reject_manifest(
            lambda doc: doc["rows"][0].update(
                receptor_atom_count=doc["rows"][0]["receptor_atom_count"] + 1
            )
        )
        self._reject_manifest(
            lambda doc: doc["rows"][0].update(source_hashes_postflight_verified=False)
        )

    def test_roles_and_scientific_claims_cannot_be_promoted(self):
        self._reject_manifest(lambda doc: doc["rows"][0].update(fit_role="fit"))
        self._reject_manifest(
            lambda doc: doc["rows"][0].update(numeric_comparison_pass=True)
        )
        self._reject_manifest(
            lambda doc: doc["rows"][0].update(
                prepared_state_assay_equivalence_verified=True
            )
        )
        self._reject_manifest(
            lambda doc: doc["boundary"].update(scientific_comparison_eligible=True)
        )
        self._reject_manifest(
            lambda doc: doc["boundary"].update(training_admitted=True)
        )
        self._reject_manifest(
            lambda doc: doc["boundary"].update(
                experimental_assay_values_extracted_or_exported=True
            )
        )
        self._reject_manifest(
            lambda doc: doc["boundary"].update(scientific_comparison_eligible=0)
        )

    def test_raw_receipt_and_code_identity_are_pinned(self):
        self._reject_manifest(
            lambda doc: doc["provenance"].update(raw_temp_receipt_sha256="0" * 64)
        )
        self._reject_manifest(
            lambda doc: doc["provenance"].update(
                raw_temp_receipt_bytes=doc["provenance"]["raw_temp_receipt_bytes"] + 1
            )
        )
        self._reject_manifest(
            lambda doc: doc["provenance"].update(reader_module_sha256="0" * 64)
        )
        self._reject_manifest(
            lambda doc: doc["provenance"].update(inventory_sha256="0" * 64)
        )


if __name__ == "__main__":
    unittest.main()
