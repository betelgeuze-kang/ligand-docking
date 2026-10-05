"""Archive projection must preserve all declared rows without assay labels."""
from __future__ import annotations

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from betelgeuze_product import public_assay_components as components
from betelgeuze_product import public_assay_preflight
from tools.product import build_public_source_identity_nodes as builder


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture(root: Path, second: bytes = b"name,smiles,pIC50\nB,N,9999_secret\n"):
    members = {
        "SI/first.csv": b"name,smiles,pIC50\nA,C,9999_secret\n",
        "SI/second.csv": second,
    }
    archive = root / "source.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        for name, data in members.items():
            stream.writestr(name, data)
    manifest = {
        "schema_version": builder.SCHEMA,
        "archive": {"path": str(archive), "sha256": sha(archive.read_bytes())},
        "document": {"doi": "10.1234/synthetic", "pmid": ""},
        "members": [
            {"name": name, "sha256": sha(data), "id_column": "name",
             "smiles_column": "smiles"}
            for name, data in members.items()
        ],
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    out = root / "nodes.json"
    args = ["--manifest", str(path), "--manifest-sha256", sha(path.read_bytes()),
            "--output", str(out)]
    return manifest, args, out


class PublicSourceIdentityNodesTests(unittest.TestCase):
    def test_joint_projection_has_no_assay_values_and_preflight_bridges(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest, args, out = fixture(Path(temp))
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(builder.main(args), 0)
            nodes = json.loads(out.read_text())
            self.assertEqual(len(nodes), 2)
            self.assertNotIn("9999_secret", out.read_text())
            self.assertNotIn("SI/first.csv:A", out.read_text())
            self.assertEqual({node["source"]["source_line"] for node in nodes}, {2})
            self.assertEqual({node["source"]["source_member"] for node in nodes},
                             {member["name"] for member in manifest["members"]})
            summary = json.loads(output.getvalue())
            self.assertEqual(summary["output_sha256"], sha(out.read_bytes()))
            self.assertEqual(
                {row["status"] for row in public_assay_preflight.preflight([], nodes)["results"]},
                {"identity_incomplete"})
            reserved = components.node_from_raw(
                {"Article DOI": "10.1234/synthetic"}, None,
                node_id="reserved", record_id="reserved", ligand_id="", protected=True)
            result = public_assay_preflight.preflight([reserved], nodes)
            self.assertEqual({row["status"] for row in result["results"]}, {"blocked_identity"})
            self.assertFalse(any(row["training_allowed"] for row in result["results"]))

    def test_bad_second_member_aborts_without_partial_output(self):
        with tempfile.TemporaryDirectory() as temp:
            _, args, out = fixture(Path(temp), b"name,smiles,pIC50\nB,not-a-smiles,9999_secret\n")
            with self.assertRaisesRegex(ValueError, "invalid_source_smiles"):
                builder.main(args)
            self.assertFalse(out.exists())

    def test_duplicate_identity_or_source_drift_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, args, out = fixture(root, b"name,smiles,pIC50\nB,N,1\nB,O,2\n")
            with self.assertRaisesRegex(ValueError, "duplicate_source_identity"):
                builder.main(args)
            self.assertFalse(out.exists())
            manifest = json.loads((root / "manifest.json").read_text())
            manifest["members"][1]["sha256"] = "0" * 64
            (root / "manifest.json").write_text(json.dumps(manifest))
            args[3] = sha((root / "manifest.json").read_bytes())
            with self.assertRaisesRegex(ValueError, "source_member_sha256_mismatch"):
                builder.main(args)
            self.assertFalse(out.exists())

    def test_assay_as_id_and_role_column_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, args, out = fixture(root)
            manifest["members"][0]["id_column"] = "pIC50"
            (root / "manifest.json").write_text(json.dumps(manifest))
            args[3] = sha((root / "manifest.json").read_bytes())
            with self.assertRaisesRegex(ValueError, "invalid_or_duplicate_source_member"):
                builder.main(args)
            self.assertFalse(out.exists())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, args, out = fixture(root, b"name,smiles,role\nB,N,development_test\n")
            with self.assertRaisesRegex(ValueError, "policy_bearing_source_csv"):
                builder.main(args)
            self.assertFalse(out.exists())

    def test_source_id_is_never_emitted_even_when_header_is_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, args, out = fixture(root, b"name,smiles,pIC50\n7.25,N,9999_secret\n")
            with redirect_stdout(io.StringIO()):
                builder.main(args)
            self.assertNotIn("7.25", out.read_text())


if __name__ == "__main__":
    unittest.main()
