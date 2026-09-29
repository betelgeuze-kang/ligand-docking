"""Adversarial checks for the source-bound receptor cross projection."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from verify_projection import DEFAULT_OUTPUT, FILES, ProjectionError, verify


DATA_VOLUME = Path("/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs")
SOURCE = Path(os.environ.get(
    "BETELGEUZE_7XTB_SOURCE",
    str(DATA_VOLUME / "engine-v2-7xtb-source-observation-20260929T031420Z/7XTB.cif")))
OUTPUT = Path(os.environ.get("BETELGEUZE_7XTB_PROJECTION", str(DEFAULT_OUTPUT)))


def _ref(path: Path, source_id: str) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_id": source_id}


def _reader_request(root: Path, scratch: Path) -> dict:
    """Use an invented three-atom ligand solely to exercise the complete reader."""
    sdf = ("synthetic reader ligand\nsynthetic\n\n  3  2  0  0  0  0            999 V2000\n"
           "    2.0000    1.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
           "    3.0000    1.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0\n"
           "    3.0000    2.0000    0.0000 H   0  0  0  0  0  0  0  0  0  0  0  0\n"
           "  1  2  1  0  0  0\n  2  3  1  0  0  0\nM  END\n")
    gro = "synthetic\n3\n"
    for index, (name, point) in enumerate(zip(("C0", "C1", "H2"),
                                               ((.2, .1, 0.), (.3, .1, 0.), (.3, .2, 0.))), 1):
        gro += (f"{1:5d}{'LIG':<5s}{name:>5s}{index:5d}"
                + " ".join(f"{value:.8f}" for value in point) + "\n")
    gro += "1.0 1.0 1.0\n"
    synthetic = {
        "ligand.sdf": sdf,
        "ligand.gro": gro,
        "ligand.itp": ("[ moleculetype ]\nLIG 3\n[ atoms ]\n"
                       "1 LC 1 LIG C0 1 0.0 12.011\n"
                       "2 LC 1 LIG C1 2 0.0 12.011\n"
                       "3 LH 1 LIG H2 3 0.0 1.008\n"
                       "[ bonds ]\n1 2 1\n2 3 1\n"),
        "ligand-types.itp": ("[ atomtypes ]\nLC 6 12.011 0 A 0.34 0.42\n"
                             "LH 1 1.008 0 A 0.0 0.0\n"),
        "ligand-defaults.itp": "[ defaults ]\n1 2 no 1 1\n",
    }
    for name, content in synthetic.items():
        (scratch / name).write_text(content, encoding="ascii")
    return {
        "schema_version": "prepared_gromacs_components_v1",
        "protein_pdb": _ref(root / "receptor-prepared.pdb", "7xtb-openmm-projection"),
        "protein_chains": [{"chain_id": chain,
                            "molecule_itp": _ref(root / f"receptor-{chain}.itp", f"7xtb-chain-{chain}")}
                           for chain in ("A", "B")],
        "protein_atomtypes": _ref(root / "atomtypes.itp", "7xtb-openmm-atomtypes"),
        "protein_defaults": _ref(root / "defaults.itp", "7xtb-cross-defaults"),
        "ligand_sdf": _ref(scratch / "ligand.sdf", "invented-reader-test-ligand"),
        "ligand_gro": _ref(scratch / "ligand.gro", "invented-reader-test-ligand"),
        "ligand_itp": _ref(scratch / "ligand.itp", "invented-reader-test-ligand"),
        "ligand_atomtypes": _ref(scratch / "ligand-types.itp", "invented-reader-test-ligand"),
        "ligand_defaults": _ref(scratch / "ligand-defaults.itp", "invented-reader-test-ligand"),
        "ligand_atomtype_name_mapping": {},
        "ligand_residue_name_mapping": {"gro": "LIG", "itp": "LIG"},
        "naming_convention": "exact", "pdb_element_policy": "reject_missing",
        "source_declarations": {key: "synthetic-reader-fixture-only" for key in (
            "coordinate_frame_id", "prepared_state_id", "parameter_source_id", "charge_source_id")},
        "source_relationship": "Synthetic ligand is unrelated to the 7XTB receptor; reader syntax test only.",
    }


class ProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not SOURCE.is_file() or not (OUTPUT / "manifest.v1.json").is_file():
            raise unittest.SkipTest("external pinned CIF and built projection required")

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(dir=DATA_VOLUME)
        self.scratch = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _mutated_packet(self, name: str) -> tuple[Path, Path]:
        root = self.scratch / "packet"
        root.mkdir()
        for item in FILES:
            destination = root / item
            if item == name:
                shutil.copyfile(OUTPUT / item, destination)
            else:
                destination.symlink_to(OUTPUT / item)
        shutil.copyfile(OUTPUT / "manifest.v1.json", root / "manifest.v1.json")
        return root, root / name

    @staticmethod
    def _reseal(root: Path, name: str) -> None:
        path = root / "manifest.v1.json"
        manifest = json.loads(path.read_text(encoding="ascii"))
        raw = (root / name).read_bytes()
        manifest["files"][name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        path.write_text(json.dumps(manifest, sort_keys=True), encoding="ascii")

    def test_source_bound_projection_and_full_reader_with_synthetic_ligand(self) -> None:
        from betelgeuze_engine.product.prepared_gromacs_input import load_prepared_gromacs_components

        result = verify(OUTPUT, SOURCE)
        self.assertEqual(result["status"], "PASS_RESEARCH_ONLY_CROSS_PROJECTION")
        receptor, ligand, receptor_parameters, _, evidence = load_prepared_gromacs_components(
            _reader_request(OUTPUT, self.scratch))
        self.assertEqual(receptor.atom_count, 4376)
        self.assertEqual(ligand.atom_count, 3)
        self.assertEqual(len(receptor_parameters), 4376)
        self.assertTrue(evidence["source_hashes_postflight_verified"])
        self.assertFalse(evidence["claim_policy"]["scientifically_validated"])

    def test_changed_cif_fails_before_projection_is_accepted(self) -> None:
        changed = self.scratch / "changed-7xtb.cif"
        raw = bytearray(SOURCE.read_bytes())
        raw[0] = 65 if raw[0] != 65 else 66
        changed.write_bytes(raw)
        with self.assertRaisesRegex(ProjectionError, "pinned 7XTB source mismatch"):
            verify(OUTPUT, changed)

    def test_resealed_observed_coordinate_change_fails(self) -> None:
        root, path = self._mutated_packet("receptor-prepared.pdb")
        lines = path.read_text(encoding="ascii").splitlines(keepends=True)
        index = next(i for i, line in enumerate(lines) if line.startswith("ATOM  ") and line[76:78].strip() != "H")
        line = lines[index]
        lines[index] = line[:30] + f"{float(line[30:38]) + 0.001:8.3f}" + line[38:]
        path.write_text("".join(lines), encoding="ascii")
        self._reseal(root, path.name)
        with self.assertRaisesRegex(ProjectionError, "source heavy coordinate changed"):
            verify(root, SOURCE)

    def test_resealed_partial_conect_fails_independent_and_product_reader(self) -> None:
        from betelgeuze_engine.product.prepared_gromacs_input import (
            PreparedGromacsInputError, load_prepared_gromacs_components)

        root, path = self._mutated_packet("receptor-prepared.pdb")
        lines = path.read_text(encoding="ascii").splitlines(keepends=True)
        index = next(i for i, line in enumerate(lines) if line.startswith("CONECT"))
        del lines[index]
        path.write_text("".join(lines), encoding="ascii")
        self._reseal(root, path.name)
        with self.assertRaisesRegex(ProjectionError, "partial CONECT"):
            verify(root, SOURCE)
        with self.assertRaisesRegex(PreparedGromacsInputError, "PDB explicit bond adjacency"):
            load_prepared_gromacs_components(_reader_request(root, self.scratch))

    def test_resealed_disulfide_bond_removal_fails(self) -> None:
        root, path = self._mutated_packet("receptor-A.itp")
        lines = path.read_text(encoding="ascii").splitlines(keepends=True)
        atoms = [line.split() for line in lines if len(line.split()) == 8 and line.split()[0].isdigit()]
        indices = [int(row[0]) for row in atoms if row[4] == "SG" and row[2] in {"99", "180"}]
        self.assertEqual(len(indices), 2)
        edge = {str(index) for index in indices}
        index = next(i for i, line in enumerate(lines) if len(line.split()) == 3
                     and set(line.split()[:2]) == edge and line.split()[2] == "1")
        del lines[index]
        path.write_text("".join(lines), encoding="ascii")
        self._reseal(root, path.name)
        with self.assertRaisesRegex(ProjectionError, "partial CONECT"):
            verify(root, SOURCE)

    def test_authority_promotion_fails(self) -> None:
        root, _ = self._mutated_packet("receptor-A.itp")
        manifest_path = root / "manifest.v1.json"
        manifest = json.loads(manifest_path.read_text(encoding="ascii"))
        manifest["scope"]["assay_state_equivalence_verified"] = True
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="ascii")
        with self.assertRaisesRegex(ProjectionError, "scope or authority"):
            verify(root, SOURCE)


if __name__ == "__main__":
    unittest.main()
