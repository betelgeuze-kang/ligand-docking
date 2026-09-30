"""Mutation controls for the pinned OpenFF LFS source inventory."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().with_name("verify_openff_lfs_inventory.py")
SPEC = importlib.util.spec_from_file_location("pfkfb3_lfs_inventory_verifier", SCRIPT)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original, _ = verifier._load(verifier.INVENTORY)

    def _write(self, root: Path, doc: dict) -> Path:
        path = root / "inventory.json"
        path.write_text(json.dumps(doc, ensure_ascii=False) + "\n")
        return path

    def _reject(self, mutate):
        with tempfile.TemporaryDirectory() as temporary:
            doc = copy.deepcopy(self.original)
            mutate(doc)
            with self.assertRaises(ValueError):
                verifier.verify(self._write(Path(temporary), doc))

    def test_pinned_inventory_passes_offline(self):
        receipt = verifier.verify()
        self.assertEqual(receipt["status"], "PASS_STATIC_SOURCE_INVENTORY_ROLE_BLOCKED")
        self.assertEqual(receipt["ligand_count"], 40)
        self.assertEqual(receipt["core_ligand_file_count"], 160)
        self.assertEqual(receipt["support_file_count"], 42)
        self.assertFalse(receipt["official_source_rechecked_now"])
        self.assertFalse(receipt["protected_evaluation_outcomes_read"])

    def test_missing_or_reordered_file_rejected(self):
        self._reject(lambda doc: doc["files"].pop())
        self._reject(lambda doc: doc["files"].reverse())
        self._reject(lambda doc: doc["support_files"].pop())

    def test_wrong_ligand_identity_or_path_rejected(self):
        self._reject(lambda doc: doc["files"][0].update(ligand_id="lig_999"))
        self._reject(lambda doc: doc["files"][0].update(path="../other.sdf"))
        self._reject(lambda doc: doc["support_files"][-1].update(kind="ligand_itp"))

    def test_hash_size_and_pointer_tampering_rejected(self):
        self._reject(lambda doc: doc["files"][0].update(lfs_oid_sha256="0" * 64))
        self._reject(lambda doc: doc["files"][0].update(git_pointer_blob_sha1="0" * 40))
        self._reject(lambda doc: doc["files"][0].update(observed_download_size_bytes=1))
        self._reject(lambda doc: doc["support_files"][0].update(lfs_size_bytes=1))

    def test_resealed_json_still_rejected_by_pinned_rows(self):
        def alter(doc):
            row = doc["files"][0]
            row["lfs_oid_sha256"] = "0" * 64
            row["observed_download_sha256"] = row["lfs_oid_sha256"]
            row["git_pointer_blob_sha1"] = verifier._git_blob_sha1(
                verifier._pointer(row["lfs_oid_sha256"], row["lfs_size_bytes"])
            )
            manifest = (
                "\n".join(
                    f"{r['path']} {r['lfs_oid_sha256']} {r['lfs_size_bytes']}"
                    for r in doc["files"]
                )
                + "\n"
            )
            doc["audit"]["core_ligand_path_oid_size_manifest_sha256"] = (
                verifier.hashlib.sha256(manifest.encode()).hexdigest()
            )

        self._reject(alter)

    def test_source_and_admission_boundary_rejected(self):
        self._reject(lambda doc: doc["source"].update(commit="0" * 40))
        self._reject(lambda doc: doc["source"].update(ligands_tree_sha1="0" * 40))
        self._reject(
            lambda doc: doc["audit"].update(scientific_comparison_eligible=True)
        )
        self._reject(lambda doc: doc["audit"].update(training_admitted=True))
        self._reject(
            lambda doc: doc["audit"].update(protected_evaluation_outcomes_read=0)
        )

    def test_duplicate_keys_or_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"schema_version":"x","schema_version":"y"}')
            with self.assertRaisesRegex(ValueError, "duplicate_json_key"):
                verifier.verify(duplicate)
            link = root / "link.json"
            link.symlink_to(verifier.INVENTORY)
            with self.assertRaises(OSError):
                verifier.verify(link)


if __name__ == "__main__":
    unittest.main()
