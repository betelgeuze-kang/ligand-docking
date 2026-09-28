"""Negative controls for the pinned, blocked BRD4 source packet."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest


PACKET = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "brd4_source_manifest_verifier", PACKET / "verify_manifest.py"
)
assert SPEC is not None and SPEC.loader is not None
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class BRD4ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "official_sources").mkdir()
        for relative, _, _, _ in VERIFIER.SOURCE_FILES.values():
            shutil.copyfile(PACKET / relative, self.root / relative)
        self.manifest = json.loads(
            (PACKET / "source_manifest.v1.json").read_text(encoding="utf-8")
        )
        original_root = VERIFIER.ROOT
        VERIFIER.ROOT = self.root
        self.addCleanup(setattr, VERIFIER, "ROOT", original_root)

    def test_original_packet_passes(self) -> None:
        self.assertEqual(VERIFIER.validate(self.manifest), 3)

    def test_coordinated_source_and_manifest_hash_tamper_rejects(self) -> None:
        altered = copy.deepcopy(self.manifest)
        receipt = next(
            item
            for item in altered["source_file_receipts"]
            if item["source_ref"] == "pdb_3mxf"
        )
        path = self.root / receipt["relative_path"]
        raw = path.read_bytes()
        path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        receipt["sha256"] = VERIFIER.sha256(path)
        with self.assertRaisesRegex(ValueError, "invalid_source_receipt_or_url"):
            VERIFIER.validate(altered)

    def test_deleted_or_promoted_eligibility_rejects(self) -> None:
        for replacement in (
            {},
            {**self.manifest["eligibility"], "scientifically_validated": True},
        ):
            with self.subTest(replacement=replacement):
                altered = copy.deepcopy(self.manifest)
                altered["eligibility"] = replacement
                with self.assertRaisesRegex(
                    ValueError, "eligibility_must_remain_false"
                ):
                    VERIFIER.validate(altered)

    def test_extra_role_claim_rejects(self) -> None:
        altered = copy.deepcopy(self.manifest)
        altered["protection_and_roles"]["training_role"] = "fit"
        with self.assertRaisesRegex(ValueError, "roles_or_rights_overclaimed"):
            VERIFIER.validate(altered)


if __name__ == "__main__":
    unittest.main()
