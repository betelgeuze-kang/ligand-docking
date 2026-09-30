"""External-runtime regression: both rows read, case-tampered Cl is rejected."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

# The external OpenFF environment runs this file through unittest. During
# repository pytest collection, a missing optional runtime is an explicit skip.
try:
    import openff.toolkit  # noqa: F401
    import openff.interchange  # noqa: F401
except ImportError as exc:
    raise unittest.SkipTest(f"external OpenFF runtime unavailable: {exc}") from exc

from betelgeuze_engine.product.prepared_gromacs_input import (
    PreparedGromacsInputError, load_prepared_gromacs_components)

# Both receptor and ligand research folders have a verify_projection.py. Load
# this sibling by absolute path so pytest's module cache cannot select the other.
_verify_path = Path(__file__).resolve().with_name("verify_projection.py")
_verify_spec = importlib.util.spec_from_file_location(
    "human_5ht6_pr49_pr59_openff_verify_projection", _verify_path)
assert _verify_spec is not None and _verify_spec.loader is not None
_verify_module = importlib.util.module_from_spec(_verify_spec)
_verify_spec.loader.exec_module(_verify_module)
DEFAULT_LEDGER = _verify_module.DEFAULT_LEDGER
DEFAULT_OUTPUT = _verify_module.DEFAULT_OUTPUT
DEFAULT_PDF = _verify_module.DEFAULT_PDF
verify = _verify_module.verify


BASE = Path("/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs")
RECEPTOR = BASE / "engine-v2-7xtb-openmm-projection-20260929"


def _ref(path: Path) -> dict:
    path = path.resolve(strict=True)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_id": path.name}


def reader_request(row_id: str, ligand_root: Path) -> dict:
    ligand = ligand_root / row_id
    return {
        "schema_version": "prepared_gromacs_components_v1",
        "protein_pdb": _ref(RECEPTOR / "receptor-prepared.pdb"),
        "protein_chains": [{"chain_id": chain,
                            "molecule_itp": _ref(RECEPTOR / f"receptor-{chain}.itp")}
                           for chain in ("A", "B")],
        "protein_atomtypes": _ref(RECEPTOR / "atomtypes.itp"),
        "protein_defaults": _ref(RECEPTOR / "defaults.itp"),
        "ligand_sdf": _ref(ligand / "ligand.sdf"),
        "ligand_gro": _ref(ligand / "ligand.gro"),
        "ligand_itp": _ref(ligand / "ligand.itp"),
        "ligand_atomtypes": _ref(ligand / "atomtypes.itp"),
        "ligand_defaults": _ref(ligand / "defaults.itp"),
        "ligand_atomtype_name_mapping": {},
        "ligand_residue_name_mapping": {"itp": row_id, "gro": row_id},
        "naming_convention": "exact",
        "pdb_element_policy": "reject_missing",
        "source_declarations": {
            "coordinate_frame_id": "not_shared_reader_syntax_probe",
            "prepared_state_id": f"{row_id}_neutral_and_7xtb_research_projections",
            "parameter_source_id": "separate_amber14_and_openff221",
            "charge_source_id": "separate_amber14_and_NAGL1",
        },
        "source_relationship": "independent_projections_no_bound_pose_or_registration",
    }


class ProjectionReaderTest(unittest.TestCase):
    def test_both_rows_pass_real_reader_without_pose_claim(self) -> None:
        for row_id, count in (("PR49", 39), ("PR59", 43)):
            with self.subTest(row_id=row_id):
                receptor, ligand, receptor_parameters, ligand_parameters, evidence = (
                    load_prepared_gromacs_components(reader_request(row_id, DEFAULT_OUTPUT)))
                self.assertEqual((receptor.atom_count, ligand.atom_count), (4376, count))
                self.assertEqual((len(receptor_parameters), len(ligand_parameters)), (4376, count))
                self.assertFalse(evidence["coordinate_registration_performed"])

    def test_chlorine_name_case_tamper_rejected_after_rehash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "projection"
            shutil.copytree(DEFAULT_OUTPUT, target)
            for filename in ("ligand.gro", "ligand.itp", "atom-provenance.csv"):
                path = target / "PR49" / filename
                raw = path.read_bytes()
                self.assertIn(b"Cl1", raw)
                path.write_bytes(raw.replace(b"Cl1", b"CL1"))
            manifest_path = target / "manifest.v1.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for filename in ("ligand.gro", "ligand.itp", "atom-provenance.csv"):
                raw = (target / "PR49" / filename).read_bytes()
                manifest["rows"]["PR49"]["files"][filename] = {
                    "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True,
                                                ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "READER_ATOM_NAME_ELEMENT_CASE_MISMATCH"):
                verify(target, DEFAULT_PDF, DEFAULT_LEDGER)
            with self.assertRaisesRegex(PreparedGromacsInputError,
                                        "ligand GRO name element differs from SDF"):
                load_prepared_gromacs_components(reader_request("PR49", target))


if __name__ == "__main__":
    unittest.main()
