"""Synthetic metadata only: no experimental labels or protected outcomes."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from betelgeuze_product import public_assay_preflight as mod


def node(name, keys, protected=False, declarations=None):
    return {"schema_version": "public_assay_identity_context_v1", "node_id": name,
            "record_id": name, "keys": [["document", hashlib.sha256(k.encode()).hexdigest()] for k in keys] + [["canonical", hashlib.sha256(("chemical:" + name).encode()).hexdigest()]],
            "policy_declarations": declarations if declarations is not None else [{}],
            "protected": protected, "chemical_identity_available": True,
            "document_identity_available": True, "source": {}}


class PreflightTests(unittest.TestCase):
    def test_candidate_bridge_and_order(self):
        p=node("p", ["reserved"], True); a=node("a", ["reserved", "family"]); b=node("b", ["family"])
        self.assertEqual(mod.preflight([p], [b])["results"][0]["status"], "identity_clear_review_required")
        joint=mod.preflight([p], [a,b])["results"]
        self.assertTrue(all(x["status"]=="blocked_identity" for x in joint))
        self.assertEqual(joint[0]["component_id"], mod.preflight([p], [b,a])["results"][0]["component_id"])

    def test_policy_only_and_unknown(self):
        for value in (True, "ambiguous"):
            with self.subTest(value=value):
                p=node("p", ["x"], declarations=[{"evaluation_only": value}])
                self.assertEqual(mod.preflight([p], [node("a", ["x"])])["results"][0]["status"], "blocked_identity")

    def test_clear_never_admits(self):
        out=mod.preflight([], [node("a", ["a"])])["results"][0]
        for key in ("training_allowed", "calibration_allowed", "independent_evaluation_allowed", "prepared"):
            self.assertIs(out[key], False)

    def test_incomplete(self):
        a=node("a", ["a"]);a["chemical_identity_available"]=False
        self.assertEqual(mod.preflight([], [a])["results"][0]["status"], "identity_incomplete")

    def test_duplicate_across_inputs(self):
        a=node("a", ["a"])
        with self.assertRaises(ValueError):mod.preflight([a], [a])

    def test_endpoint_field_rejected(self):
        a=node("a", ["a"]);a["endpoint_value"]=1
        with self.assertRaises(ValueError):mod.preflight([], [a])

    def test_empty_candidates(self):
        with self.assertRaises(ValueError):mod.preflight([], [])

    def test_cli_hashes_gzip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);context=root/"context.gz";candidates=root/"candidates.json";output=root/"out.json"
            context.write_bytes(gzip.compress((json.dumps(node("p", ["x"], True))+"\n").encode()))
            candidates.write_text(json.dumps([node("a", ["x"])]))
            sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            args=["--context",str(context),"--context-sha256",sha(context),"--candidates",str(candidates),"--candidates-sha256",sha(candidates),"--output",str(output)]
            bad=args.copy();bad[3]="0"*64
            with self.assertRaises(ValueError):mod.main(bad)
            self.assertFalse(output.exists())
            bad=args.copy();bad[7]="0"*64
            with self.assertRaises(ValueError):mod.main(bad)
            self.assertFalse(output.exists())
            self.assertEqual(mod.main(args),0)
            before=output.read_bytes()
            self.assertEqual(json.loads(before)["results"][0]["status"],"blocked_identity")
            with self.assertRaises(FileExistsError):mod.main(args)
            self.assertEqual(before,output.read_bytes())

    def test_strict_json(self):
        with self.assertRaises(ValueError):mod.components.loads('{"a":1,"a":2}')
        with self.assertRaises(ValueError):mod.components.loads('{"a":NaN}')

if __name__ == "__main__":unittest.main()
