"""Synthetic contract tests; no package initialization or scientific dependencies."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/analyze_residue_contacts.py"
FIXTURE = ROOT / "tests/fixtures/residue_contacts/synthetic.json"
SPEC = importlib.util.spec_from_file_location("offline_residue_contacts", TOOL)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def source():
    return json.loads(FIXTURE.read_text())


def analyze(data, **kwargs):
    return m.analyze_contacts(json.dumps(data).encode(), **kwargs)


def pose(output, pid):
    return next(p for p in output["poses"] if p["pose_id"] == pid)


class ContactsTests(unittest.TestCase):
    def test_hand_calculated_and_direction(self):
        out = analyze(source())
        initial = pose(out, "initial")
        final = pose(out, "final")
        self.assertEqual([r["distance"] for r in initial["nearest_by_residue"]], [2, 8])
        self.assertEqual([r["bin_index"] for r in initial["nearest_by_residue"]], [0, 2])
        self.assertEqual(final["contact_residue_ids"], ["B:7:A"])
        pair = out["comparisons"][0]
        self.assertEqual(pair["gained_residue_ids"], ["B:7:A"])
        self.assertEqual(pair["lost_residue_ids"], ["A:7"])
        self.assertEqual(pair["jaccard"], 0)
        self.assertEqual(pair["jaccard_distance"], 1)
        self.assertIsNone(out["comparisons"][1]["jaccard"])
        self.assertFalse(any(out["claims"].values()))
        self.assertEqual(out["contact_set_diversity"]["supplied_pose_count"], 3)
        self.assertEqual(out["contact_set_diversity"]["unavailable_pose_count"], 1)

    def test_boundaries_and_all_atoms(self):
        for distance, expected_bin in [(0, 0), (2, 0), (2.0001, 1), (4, 1), (8, 2), (8.0001, 3)]:
            with self.subTest(distance=distance):
                data = source()
                data["poses"][0]["atoms"][0]["xyz"] = [distance, 0, 0]
                row = pose(analyze(data), "initial")["nearest_by_residue"][0]
                self.assertEqual(row["bin_index"], expected_bin)
                self.assertEqual(row["contact"], distance <= 4)
                self.assertEqual(row["ligand_atom_id"], "l1")  # Explicit H included.

    def test_rigid_transform(self):
        data = source()
        before = analyze(data)
        for container in [data["receptor"], *data["poses"]]:
            for atom in container.get("atoms") or []:
                x, y, z = atom["xyz"]
                atom["xyz"] = [100 - y, x - 31, z + 7]
        after = analyze(data)
        self.assertEqual(before["poses"], after["poses"])
        self.assertEqual(before["comparisons"], after["comparisons"])

    def test_permutation_tie_and_identity(self):
        data = source()
        data["receptor"]["atoms"].append({"atom_id": "r0", "residue_id": "A:7", "element": "C", "xyz": [4, 0, 0]})
        data["poses"][0]["atoms"].append({"atom_id": "l0", "element": "C", "xyz": [2, 0, 0]})
        before = analyze(data)
        row = pose(before, "initial")["nearest_by_residue"][0]
        self.assertEqual((row["receptor_atom_id"], row["ligand_atom_id"]), ("r0", "l0"))
        for container in [data["receptor"], *data["poses"]]:
            if container.get("atoms"):
                container["atoms"].reverse()
        data["receptor"]["residues"].reverse()
        data["poses"].reverse()
        data["comparisons"].reverse()
        after = analyze(data)
        before.pop("input_sha256")
        after.pop("input_sha256")
        self.assertEqual(before, after)
        self.assertEqual(len(after["residues"]), 2)

    def test_missing_null_empty_and_contact_free(self):
        data = source()
        del data["poses"][0]["atoms"]
        out = analyze(data)
        self.assertEqual(pose(out, "initial")["geometry_state"], "missing")
        self.assertIsNone(pose(out, "initial")["contact_count"])
        self.assertEqual(pose(out, "unavailable")["geometry_state"], "null")
        data["poses"][0]["atoms"] = []
        empty = pose(analyze(data), "initial")
        self.assertIsNone(empty["contact_count"])
        self.assertIsNone(empty["nearest_by_residue"][0]["contact"])
        self.assertIsNone(empty["nearest_by_residue"][0]["distance"])
        data["poses"][0]["atoms"] = [{"atom_id": "far", "element": "C", "xyz": [100, 0, 0]}]
        far = pose(analyze(data), "initial")
        self.assertEqual(far["geometry_state"], "observed")
        self.assertEqual(far["contact_count"], 0)
        self.assertEqual(far["nearest_by_residue"][0]["distance"], 100)
        data["receptor"]["atoms"] = None
        self.assertIsNone(pose(analyze(data), "initial")["contact_count"])
        del data["receptor"]["atoms"]
        self.assertEqual(analyze(data)["receptor_geometry_state"], "missing")
        data["receptor"]["atoms"] = []
        self.assertIsNone(pose(analyze(data), "initial")["contact_count"])

    def test_overlapping_and_empty_sets(self):
        data = source()
        data["settings"]["cutoff"] = 6
        partial = analyze(data)["comparisons"][0]
        self.assertEqual(partial["jaccard"], 0.5)
        self.assertEqual(partial["shared_residue_ids"], ["A:7"])
        data["settings"]["cutoff"] = 8
        out = analyze(data)
        self.assertEqual(out["comparisons"][0]["jaccard"], 1)
        self.assertEqual(out["comparisons"][0]["gained_residue_ids"], [])
        data["poses"][0]["atoms"][0]["xyz"] = [100, 0, 0]
        data["poses"][1]["atoms"][0]["xyz"] = [100, 0, 0]
        pair = analyze(data)["comparisons"][0]
        self.assertIsNone(pair["jaccard"])
        self.assertIsNone(pair["jaccard_distance"])
        self.assertEqual(pair["reason"], "empty_contact_union")
        self.assertEqual(pair["lost_residue_ids"], [])
        data["poses"][0]["atoms"] = None
        pair = analyze(data)["comparisons"][0]
        self.assertIsNone(pair["lost_residue_ids"])
        self.assertEqual(pair["reason"], "unavailable_geometry")

    def test_empty_and_partial_geometry_never_proves_absence(self):
        for target in ("ligand", "receptor", "residue"):
            with self.subTest(target=target):
                data = source()
                if target == "ligand":
                    data["poses"][0]["atoms"] = []
                elif target == "receptor":
                    data["receptor"]["atoms"] = []
                else:
                    data["receptor"]["atoms"].pop()
                output = analyze(data)
                initial = pose(output, "initial")
                self.assertIsNone(initial["contact_count"])
                self.assertIsNone(initial["contact_residue_ids"])
                self.assertEqual(initial["fingerprint_state"], "unavailable")
                self.assertIsNone(output["comparisons"][0]["lost_residue_ids"])
                self.assertIsNone(output["comparisons"][0]["jaccard"])
                if target == "residue":
                    self.assertEqual(initial["nearest_by_residue"][0]["distance"], 2)
                    self.assertTrue(initial["nearest_by_residue"][0]["contact"])
                    self.assertIsNone(initial["nearest_by_residue"][1]["contact"])

    def test_invalid_json(self):
        for raw in (b'{"a":1,"a":2}', b'NaN', b'Infinity', b'{}x', b'\xff', b'[' * 2000, b'1e100000'):
            with self.subTest(raw=raw[:30]), self.assertRaises(m.ContactInputError):
                m.analyze_contacts(raw)

    def test_malformed_schema(self):
        mutations = [
            lambda d: d.update(extra=True),
            lambda d: d.update(units="nm"),
            lambda d: d.update(schema_version=True),
            lambda d: d["poses"][0].update(coordinate_frame="other"),
            lambda d: d["poses"][0]["atoms"][0].update(xyz=[True, 0, 0]),
            lambda d: d["poses"][0]["atoms"][0].update(xyz=[float("nan"), 0, 0]),
            lambda d: d["poses"][0]["atoms"][0].update(xyz=[1e151, 0, 0]),
            lambda d: d["poses"][0]["atoms"][0].update(xyz=[0, 0]),
            lambda d: d["poses"][0]["atoms"].append(copy.deepcopy(d["poses"][0]["atoms"][0])),
            lambda d: d["receptor"]["residues"].append(copy.deepcopy(d["receptor"]["residues"][0])),
            lambda d: d["poses"].append(copy.deepcopy(d["poses"][0])),
            lambda d: d["receptor"]["atoms"][0].update(residue_id="absent"),
            lambda d: d["comparisons"][0].update(final_pose_id="absent"),
            lambda d: d["comparisons"].append(copy.deepcopy(d["comparisons"][0])),
            lambda d: d["settings"].update(bin_edges=[4, 2]),
            lambda d: d["settings"].update(bin_edges=[]),
            lambda d: d["settings"].update(bin_edges=[2, 2]),
            lambda d: d["settings"].update(bin_edges=[True]),
            lambda d: d["settings"].update(cutoff=-1),
            lambda d: d["settings"].update(cutoff=True),
            lambda d: d["poses"][0].update(pose_id="\x1bsecret"),
        ]
        for index, change in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(m.ContactInputError):
                data = source()
                change(data)
                analyze(data)

    def test_budgets_preflight_no_distance_work(self):
        raw = FIXTURE.read_bytes()
        output = m.analyze_contacts(raw)
        ops = output["preflight"]["distance_ops"]
        rows = output["preflight"]["output_row_upper_bound"]
        self.assertEqual(ops, 4)
        m.analyze_contacts(raw, limits={"distance_ops": ops, "output_rows": rows, "input_bytes": len(raw)})
        for limits in ({"distance_ops": ops - 1}, {"output_rows": rows - 1}, {"input_bytes": len(raw) - 1},
                       {"comparison_pairs": 1}, {"residues": 1}, {"receptor_atoms": 1}, {"poses": 2}, {"ligand_atoms": 1}):
            with self.subTest(limits=limits), patch.object(m.math, "dist", side_effect=AssertionError("must preflight")):
                with self.assertRaises(m.ContactInputError):
                    m.analyze_contacts(raw, limits=limits)
        with self.assertRaisesRegex(m.ContactInputError, "output_byte_budget"):
            m.analyze_contacts(raw, limits={"output_bytes": 1})
        for limits in ({"poses": True}, {"poses": -1}, {"unknown": 1}, {"poses": 1001}):
            with self.assertRaises(m.ContactInputError):
                m.analyze_contacts(raw, limits=limits)

    def test_input_binding_defaults_and_no_mutation(self):
        data = source()
        snapshot = copy.deepcopy(data)
        raw = json.dumps(data).encode()
        out = m.analyze_contacts(raw)
        self.assertEqual(data, snapshot)
        self.assertEqual(out["input_sha256"], hashlib.sha256(raw).hexdigest())
        del data["settings"]
        self.assertEqual(analyze(data)["settings"]["cutoff"], 8)
        data["poses"] = []
        data["comparisons"] = []
        self.assertIsNone(analyze(data)["contact_set_diversity"]["distinct_available_contact_sets"])

    def test_cli_isolated_no_native_imports(self):
        for fmt in ("json", "text"):
            proc = subprocess.run([sys.executable, "-I", "-S", str(TOOL), str(FIXTURE), "--format", fmt], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("geometric" if fmt == "text" else "residue_contacts_output.v1", proc.stdout.lower())
        code = "import runpy,sys; runpy.run_path(sys.argv[1],run_name='test_module'); assert not any(n.startswith(('betelgeuze','numpy','torch','rdkit')) for n in sys.modules)"
        proc = subprocess.run([sys.executable, "-I", "-S", "-c", code, str(TOOL)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc = subprocess.run([sys.executable, str(TOOL), "/nonexistent/private-secret"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertNotIn("private-secret", proc.stderr)


if __name__ == "__main__":
    unittest.main()
