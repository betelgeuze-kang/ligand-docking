"""Completeness is derived from keys; incomplete nodes still bridge reservations."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from betelgeuze_product import public_assay_preflight as mod
from betelgeuze_product import public_assay_components as comp


def node(name, kinds=("canonical", "document"), protected=False):
    return {"schema_version": comp.SCHEMA, "node_id": name, "record_id": name,
        "keys": [[kind, hashlib.sha256((name + kind).encode()).hexdigest()] for kind in kinds],
        "policy_declarations": [{}], "protected": protected, "chemical_identity_available": True,
        "document_identity_available": True, "source": {}}


class PreflightEvidenceTests(unittest.TestCase):
    def test_absent_keys_and_scaffold_are_incomplete(self):
        for kinds in ((), ("document",), ("record", "document"), ("scaffold", "document"), ("canonical",)):
            with self.subTest(kinds=kinds):
                row = mod.preflight([], [node("a", kinds)])["results"][0]
                self.assertEqual(row["status"], "identity_incomplete")
                self.assertFalse(row["training_allowed"])

    def test_supported_key_kinds_and_false_declaration(self):
        for kind in mod.CHEMICAL_KEYS:
            with self.subTest(kind=kind):
                n = node("a", (kind, "document"))
                self.assertEqual(mod.preflight([], [n])["results"][0]["status"], "identity_clear_review_required")
                n["chemical_identity_available"] = False
                self.assertEqual(mod.preflight([], [n])["results"][0]["status"], "identity_incomplete")

    def test_empty_identity_builder_cannot_clear(self):
        n = comp.node_from_raw({"Article DOI": "10.1234/synthetic"}, {},
                              node_id="a", record_id="a", ligand_id="a")
        self.assertEqual(mod.preflight([], [n])["results"][0]["status"], "identity_incomplete")

    def test_incomplete_bridge_still_blocks(self):
        reserved = node("p", ("document",), True)
        bridge = node("a", ("document",))
        bridge["keys"] += reserved["keys"]
        last = node("b")
        last["keys"] += node("a", ("document",))["keys"]
        before = deepcopy([reserved, bridge, last])
        self.assertEqual(mod.preflight([reserved], [last])["results"][0]["status"], "identity_clear_review_required")
        self.assertTrue(all(r["status"] == "blocked_identity" for r in mod.preflight([reserved], [bridge, last])["results"]))
        self.assertEqual(before, [reserved, bridge, last])

    def test_dependency_closure_includes_actual_policy(self):
        result = mod.implementation_hashes()
        self.assertEqual(set(result), {"preflight", "components", "residual_evidence"})
        real = Path.read_bytes
        target = Path(mod.residual_evidence.__file__)
        def changed(path):
            return real(path) + (b"\n# changed policy bytes" if path == target else b"")
        with patch.object(Path, "read_bytes", changed):
            new = mod.implementation_hashes()
        self.assertNotEqual(result["residual_evidence"], new["residual_evidence"])
        self.assertEqual(result["components"], new["components"])

    def test_source_drift_does_not_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            c, n, output = root / "context.jsonl", root / "candidates.json", root / "out.json"
            c.write_text("")
            n.write_text(json.dumps([node("a")]))
            args = ["--context", str(c), "--context-sha256", hashlib.sha256(c.read_bytes()).hexdigest(),
                    "--candidates", str(n), "--candidates-sha256", hashlib.sha256(n.read_bytes()).hexdigest(),
                    "--output", str(output)]
            with patch.object(mod, "implementation_hashes", side_effect=[{"source": "before"}, {"source": "after"}]):
                with self.assertRaisesRegex(ValueError, "implementation_changed"):
                    mod.main(args)
            self.assertFalse(output.exists())

    def test_cli_result_has_complete_fingerprint_and_is_exclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            c, n, out = root / "c", root / "n", root / "out"
            c.write_text("")
            n.write_text(json.dumps([node("a")]))
            args = ["--context", str(c), "--context-sha256", hashlib.sha256(c.read_bytes()).hexdigest(),
                    "--candidates", str(n), "--candidates-sha256", hashlib.sha256(n.read_bytes()).hexdigest(),
                    "--output", str(out)]
            mod.main(args)
            result = json.loads(out.read_bytes())
            self.assertEqual(result["schema_version"], mod.SCHEMA)
            self.assertEqual(result["implementation_sha256"], mod.implementation_hashes())
            self.assertEqual(out.stat().st_mode & 0o077, 0)
            with self.assertRaises(FileExistsError):
                mod.main(args)

    def test_legacy_module_alias_still_points_to_owner(self):
        from tools.product import public_assay_preflight
        self.assertIs(public_assay_preflight, mod)


if __name__ == "__main__":
    unittest.main()
