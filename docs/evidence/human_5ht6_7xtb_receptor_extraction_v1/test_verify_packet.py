"""Mutation checks for the pinned source-only receptor packet."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from verify_packet import HERE, MAP_NAME, PDB_NAME, PacketError, verify_packet


class PacketVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for name in (PDB_NAME, MAP_NAME, "manifest.v1.json"):
            shutil.copyfile(HERE / name, self.root / name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _reseal(self, key: str, name: str) -> None:
        manifest_path = self.root / "manifest.v1.json"
        manifest = json.loads(manifest_path.read_text())
        content = (self.root / name).read_bytes()
        manifest["output"][key]["bytes"] = len(content)
        manifest["output"][key]["sha256"] = hashlib.sha256(content).hexdigest()
        manifest_path.write_text(json.dumps(manifest, sort_keys=True))

    def test_tracked_packet_passes_without_external_source(self) -> None:
        report = verify_packet(self.root)
        self.assertEqual(report["status"], "PASS_SOURCE_ONLY_PACKET")
        self.assertFalse(report["source_rederived"])
        self.assertFalse(report["prepared"])

    def test_coordinate_edit_resealed_in_manifest_is_rejected(self) -> None:
        path = self.root / PDB_NAME
        lines = path.read_text().splitlines(keepends=True)
        lines[0] = lines[0][:30] + f"{float(lines[0][30:38]) + 1:8.3f}" + lines[0][38:]
        path.write_text("".join(lines))
        self._reseal("pdb", PDB_NAME)
        with self.assertRaises(PacketError):
            verify_packet(self.root)

    def test_gap_break_edit_resealed_in_manifest_is_rejected(self) -> None:
        path = self.root / PDB_NAME
        lines = path.read_text().splitlines(keepends=True)
        gap = next(i for i, line in enumerate(lines) if line.startswith("TER"))
        lines[gap] = lines[gap].replace("TER", "REM", 1)
        path.write_text("".join(lines))
        self._reseal("pdb", PDB_NAME)
        with self.assertRaises(PacketError):
            verify_packet(self.root)

    def test_source_atom_id_edit_resealed_in_manifest_is_rejected(self) -> None:
        path = self.root / MAP_NAME
        lines = path.read_text().splitlines(keepends=True)
        lines[1] = "99999," + lines[1].split(",", 1)[1]
        path.write_text("".join(lines))
        self._reseal("source_atom_map", MAP_NAME)
        with self.assertRaises(PacketError):
            verify_packet(self.root)

    def test_authority_promotion_is_rejected(self) -> None:
        path = self.root / "manifest.v1.json"
        manifest = json.loads(path.read_text())
        manifest["authority"]["prepared_receptor"] = True
        path.write_text(json.dumps(manifest, sort_keys=True))
        with self.assertRaises(PacketError):
            verify_packet(self.root)

    @unittest.skipUnless(os.environ.get("BETELGEUZE_7XTB_SOURCE"),
                         "optional source rederivation requires BETELGEUZE_7XTB_SOURCE")
    def test_original_source_rederives_and_changed_copy_rejects(self) -> None:
        source = Path(os.environ["BETELGEUZE_7XTB_SOURCE"])
        self.assertTrue(verify_packet(self.root, source)["source_rederived"])
        changed = self.root / "changed-source.cif"
        raw = bytearray(source.read_bytes())
        raw[0] = 65 if raw[0] != 65 else 66
        changed.write_bytes(raw)
        with self.assertRaises(PacketError):
            verify_packet(self.root, changed)


if __name__ == "__main__":
    unittest.main()
