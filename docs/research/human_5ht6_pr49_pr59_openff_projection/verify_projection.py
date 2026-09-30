"""Independently verify the source, graph, geometry and OpenFF projection.

This reads the written artifacts and reruns charge and force-field assignment;
it does not call build_projection or infer a receptor pose.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys

from rdkit import Chem
from rdkit.Chem import rdMolDescriptors
from openff.toolkit import ForceField, Molecule, Topology
from openff.interchange import Interchange
from openmm import (HarmonicAngleForce, HarmonicBondForce, NonbondedForce,
                    PeriodicTorsionForce, XmlSerializer, unit)


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools/product"))
from primary_5ht6_ki_2024_source_v1 import verify_source  # noqa: E402

DEFAULT_PDF = Path("/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/5ht6-primary-20260929/2024.pdf")
DEFAULT_LEDGER = REPO / "docs/evidence/human_5ht6_ki_2024_source_ledger_v1.json"
DEFAULT_OUTPUT = Path("/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-5ht6-pr49-pr59-openff-projection-20260929")
EXPECTED_SCHEMA = "human_5ht6_pr49_pr59_openff_ligand_projection_v1"
EXPECTED_FF_SHA = "1b24deb47970bae2d179a5b4e023d4a57c9c78614fe431f1670e3f75e0012c3a"
EXPECTED_MODEL_SHA = "7981e7f5b0b1e424c9e10a40d9e7606d96dcd3dd2b095cb4eeff6829f92238ee"
FILES = {"ligand.sdf", "ligand.gro", "ligand.itp", "atomtypes.itp", "defaults.itp",
         "openmm-system.xml", "atom-provenance.csv"}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sections(raw: bytes, allowed: set[str]) -> dict[str, list[list[str]]]:
    sections: dict[str, list[list[str]]] = {}
    active = None
    for line in raw.decode("ascii").splitlines():
        line = line.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            active = line.strip("[ ]")
            require(active in allowed and active not in sections, "ITP_SECTION_INVALID_OR_DUPLICATE")
            sections[active] = []
        else:
            require(active is not None, "ITP_DATA_OUTSIDE_SECTION")
            sections[active].append(line.split())
    return sections


def _gro(raw: bytes, n: int, row_id: str) -> tuple[list[str], list[tuple[float, float, float]]]:
    lines = raw.decode("ascii").splitlines()
    require(len(lines) == n + 3 and int(lines[1]) == n, "GRO_COUNT_MISMATCH")
    require([float(x) for x in lines[-1].split()] == [10.0] * 3, "GRO_BOX_MISMATCH")
    names, coords = [], []
    for index, line in enumerate(lines[2:-1], 1):
        require(int(line[:5]) == 1 and line[5:10].strip() == row_id
                and int(line[15:20]) == index, "GRO_ATOM_IDENTITY_MISMATCH")
        names.append(line[10:15].strip())
        values = tuple(float(x) * 10.0 for x in line[20:].split())
        require(len(values) == 3 and all(math.isfinite(x) for x in values), "GRO_COORDINATE_INVALID")
        coords.append(values)
    return names, coords


def _verify_one(directory: Path, row_id: str, source_row: dict, report: dict,
                ff: ForceField) -> dict:
    declared = report["files"]
    require(set(declared) == FILES, f"{row_id}: ARTIFACT_FILE_SET_MISMATCH")
    raw = {}
    for filename in sorted(FILES):
        path = directory / filename
        require(path.is_file() and not path.is_symlink(), f"{row_id}: MISSING_OR_LINKED_ARTIFACT: {filename}")
        data = path.read_bytes()
        require(len(data) == declared[filename]["bytes"] and sha(data) == declared[filename]["sha256"],
                f"{row_id}: ARTIFACT_HASH_MISMATCH: {filename}")
        raw[filename] = data
    graph = source_row["proposed_neutral_graph"]
    require(report["source_graph"] == graph and graph["assayed_microstate_verified"] is False,
            f"{row_id}: SOURCE_GRAPH_DECLARATION_MISMATCH")
    molecules = list(Chem.ForwardSDMolSupplier(io.BytesIO(raw["ligand.sdf"]),
                                               removeHs=False, sanitize=True))
    require(len(molecules) == 1 and molecules[0] is not None, f"{row_id}: SDF_MOLECULE_INVALID")
    mol = molecules[0]
    n = mol.GetNumAtoms()
    heavy = Chem.RemoveHs(mol)
    source_heavy = Chem.MolFromSmiles(graph["canonical_isomeric_smiles"])
    require(source_heavy is not None and n == report["counts"]["atoms"],
            f"{row_id}: SOURCE_OR_PREPARED_ATOM_COUNT_MISMATCH")
    require(heavy.GetNumAtoms() == source_heavy.GetNumAtoms()
            and rdMolDescriptors.CalcMolFormula(heavy) == graph["formula"]
            and Chem.inchi.MolToInchiKey(heavy) == graph["inchikey"]
            and Chem.GetFormalCharge(mol) == 0,
            f"{row_id}: SDF_SOURCE_GRAPH_MISMATCH")
    require(mol.GetProp("PAPER_ROW_ID") == row_id
            and mol.GetProp("SOURCE_GRAPH_SMILES") == graph["canonical_isomeric_smiles"]
            and mol.GetProp("COMPUTATIONAL_MICROSTATE") == "neutral_source_graph_assay_state_unverified",
            f"{row_id}: SDF_SOURCE_METADATA_MISMATCH")
    for i, atom in enumerate(source_heavy.GetAtoms()):
        require(mol.GetAtomWithIdx(i).GetAtomicNum() == atom.GetAtomicNum(),
                f"{row_id}: SOURCE_ATOM_ORDER_MISMATCH")
    source_bonds = {tuple(sorted((b.GetBeginAtomIdx(), b.GetEndAtomIdx())))
                    for b in source_heavy.GetBonds()}
    prepared_heavy_bonds = {tuple(sorted((b.GetBeginAtomIdx(), b.GetEndAtomIdx())))
                            for b in mol.GetBonds()
                            if b.GetBeginAtomIdx() < heavy.GetNumAtoms() and b.GetEndAtomIdx() < heavy.GetNumAtoms()}
    require(source_bonds == prepared_heavy_bonds, f"{row_id}: SOURCE_BOND_ORDER_MISMATCH")
    for pair in source_bonds:
        a, b = pair
        require(mol.GetBondBetweenAtoms(a, b).GetBondType() == source_heavy.GetBondBetweenAtoms(a, b).GetBondType(),
                f"{row_id}: SOURCE_BOND_TYPE_MISMATCH")
    sdf_xyz = [tuple(mol.GetConformer().GetAtomPosition(i)[axis] for axis in range(3))
               for i in range(n)]
    names, gro_xyz = _gro(raw["ligand.gro"], n, row_id)
    require(max(abs(a - b) for p, q in zip(sdf_xyz, gro_xyz) for a, b in zip(p, q)) < 0.00011,
            f"{row_id}: SDF_GRO_COORDINATE_MISMATCH")
    bond_pairs = {tuple(sorted((b.GetBeginAtomIdx(), b.GetEndAtomIdx()))) for b in mol.GetBonds()}
    for a, b in bond_pairs:
        distance = math.dist(sdf_xyz[a], sdf_xyz[b])
        hydrogen = 1 in (mol.GetAtomWithIdx(a).GetAtomicNum(), mol.GetAtomWithIdx(b).GetAtomicNum())
        require((0.70 <= distance <= 1.30) if hydrogen else (1.0 <= distance <= 2.1),
                f"{row_id}: BONDED_GEOMETRY_OUT_OF_RANGE: {a + 1}-{b + 1}")
    for a in range(heavy.GetNumAtoms()):
        for b in range(a + 1, heavy.GetNumAtoms()):
            if (a, b) not in bond_pairs:
                require(math.dist(sdf_xyz[a], sdf_xyz[b]) > 1.5,
                        f"{row_id}: NONBONDED_HEAVY_CLASH: {a + 1}-{b + 1}")
    atom_map = list(csv.DictReader(raw["atom-provenance.csv"].decode("ascii").splitlines()))
    require(len(atom_map) == n and len(set(names)) == n, f"{row_id}: ATOM_MAP_COUNT_OR_NAME_MISMATCH")
    for index, item in enumerate(atom_map):
        atom = mol.GetAtomWithIdx(index)
        require(int(item["prepared_index"]) == index + 1 and item["prepared_atom_name"] == names[index]
                and item["element"] == atom.GetSymbol(), f"{row_id}: ATOM_MAP_ORDER_MISMATCH")
        require(re.fullmatch(re.escape(atom.GetSymbol()) + r"[0-9]+", names[index]) is not None,
                f"{row_id}: READER_ATOM_NAME_ELEMENT_CASE_MISMATCH")
        if index < heavy.GetNumAtoms():
            require(item["origin"] == "source_neutral_graph_heavy"
                    and item["source_graph_atom_index"] == str(index + 1)
                    and item["source_graph_parent_atom_index"] == "",
                    f"{row_id}: HEAVY_SOURCE_MAP_MISMATCH")
        else:
            parent = item["source_graph_parent_atom_index"]
            require(item["origin"] == "computed_implicit_hydrogen"
                    and item["source_graph_atom_index"] == "" and parent.isdigit()
                    and 1 <= int(parent) <= heavy.GetNumAtoms()
                    and atom.GetAtomicNum() == 1 and atom.GetDegree() == 1
                    and atom.GetNeighbors()[0].GetIdx() == int(parent) - 1,
                    f"{row_id}: GENERATED_HYDROGEN_MAP_MISMATCH")
    tops = _sections(raw["ligand.itp"], {"moleculetype", "atoms", "bonds"})
    types = _sections(raw["atomtypes.itp"], {"atomtypes"})
    defaults = _sections(raw["defaults.itp"], {"defaults"})
    require(tops.get("moleculetype") == [[row_id, "3"]]
            and set(tops) == {"moleculetype", "atoms", "bonds"}
            and set(types) == {"atomtypes"} and set(defaults) == {"defaults"}
            and defaults["defaults"] == [["1", "2", "no", "1.0", "1.0"]],
            f"{row_id}: ITP_HEADER_OR_DEFAULTS_MISMATCH")
    require(len(tops["atoms"]) == len(types["atomtypes"]) == n,
            f"{row_id}: ITP_PARTICLE_COUNT_MISMATCH")
    itp_bonds = {tuple(sorted((int(a) - 1, int(b) - 1))) for a, b, funct in tops["bonds"] if funct == "1"}
    require(itp_bonds == bond_pairs and len(tops["bonds"]) == len(bond_pairs),
            f"{row_id}: ITP_BOND_ADJACENCY_MISMATCH")
    xml = raw["openmm-system.xml"].decode("utf-8")
    system = XmlSerializer.deserialize(xml)
    require(system.getNumParticles() == n, f"{row_id}: OPENMM_PARTICLE_COUNT_MISMATCH")
    force_classes = [force.__class__.__name__ for force in system.getForces()]
    require(force_classes == report["counts"]["openmm_forces"]
            and sum(isinstance(f, NonbondedForce) for f in system.getForces()) == 1
            and any(isinstance(f, HarmonicBondForce) for f in system.getForces())
            and any(isinstance(f, HarmonicAngleForce) for f in system.getForces())
            and any(isinstance(f, PeriodicTorsionForce) for f in system.getForces()),
            f"{row_id}: OPENMM_FORCE_INVENTORY_INCOMPLETE")
    nb = next(f for f in system.getForces() if isinstance(f, NonbondedForce))
    require(nb.getNumParticles() == n and nb.getNumExceptions() == report["counts"]["openmm_exceptions"],
            f"{row_id}: OPENMM_NONBONDED_INCOMPLETE")
    constrained_pairs = set()
    for i in range(system.getNumConstraints()):
        a, b, distance = system.getConstraintParameters(i)
        constrained_pairs.add(tuple(sorted((a, b))))
        require(distance.value_in_unit(unit.nanometer) > 0, f"{row_id}: BAD_CONSTRAINT_DISTANCE")
    bonded_forces = [f for f in system.getForces() if isinstance(f, HarmonicBondForce)]
    force_pairs = set()
    for force in bonded_forces:
        for i in range(force.getNumBonds()):
            a, b, length, k = force.getBondParameters(i)
            force_pairs.add(tuple(sorted((a, b))))
            require(length.value_in_unit(unit.nanometer) > 0 and
                    k.value_in_unit(unit.kilojoule_per_mole / unit.nanometer**2) > 0,
                    f"{row_id}: BAD_BONDED_PARAMETER")
    require(constrained_pairs.isdisjoint(force_pairs) and constrained_pairs | force_pairs == bond_pairs
            and system.getNumConstraints() == report["counts"]["openmm_constraints"],
            f"{row_id}: OPENMM_BONDED_COVERAGE_MISMATCH")
    charge_sum = 0.0
    for index, (itp_atom, atype) in enumerate(zip(tops["atoms"], types["atomtypes"])):
        require(len(itp_atom) == 8 and len(atype) == 7, f"{row_id}: ITP_PARAMETER_ROW_WIDTH")
        serial, type_name, resnum, resname, name, cgnr, q_text, mass_text = itp_atom
        t_name, atomic_number, type_mass, type_charge, ptype, sigma_text, epsilon_text = atype
        require(serial == cgnr == str(index + 1) and resnum == "1" and resname == row_id
                and name == names[index] and type_name == t_name == f"L{index + 1:03d}"
                and int(atomic_number) == mol.GetAtomWithIdx(index).GetAtomicNum()
                and type_charge == "0" and ptype == "A", f"{row_id}: ITP_ATOM_MAP_MISMATCH")
        q, sigma, epsilon = nb.getParticleParameters(index)
        charge = q.value_in_unit(unit.elementary_charge)
        require(math.isclose(float(q_text), charge, rel_tol=0, abs_tol=1e-12)
                and math.isclose(float(mass_text), system.getParticleMass(index).value_in_unit(unit.dalton), rel_tol=0, abs_tol=1e-12)
                and math.isclose(float(type_mass), float(mass_text), rel_tol=0, abs_tol=1e-12)
                and math.isclose(float(sigma_text), sigma.value_in_unit(unit.nanometer), rel_tol=0, abs_tol=1e-12)
                and math.isclose(float(epsilon_text), epsilon.value_in_unit(unit.kilojoule_per_mole), rel_tol=0, abs_tol=1e-12),
                f"{row_id}: ITP_OPENMM_PARAMETER_MISMATCH")
        charge_sum += charge
    require(abs(charge_sum) < 1e-8 and abs(charge_sum - report["counts"]["partial_charge_sum_e"]) < 1e-12,
            f"{row_id}: PARTIAL_CHARGE_SUM_MISMATCH")
    # This recomputation is separate from the builder and verifies the complete
    # XML parameter assignment, including angles, torsions and exceptions.
    off = Molecule.from_rdkit(mol, hydrogens_are_explicit=True)
    off.assign_partial_charges(partial_charge_method="openff-gnn-am1bcc-1.0.0.pt")
    regenerated = Interchange.from_smirnoff(ff, Topology.from_molecules([off]),
                                             charge_from_molecules=[off]).to_openmm(
                                                 combine_nonbonded_forces=True)
    require(XmlSerializer.serialize(regenerated) == xml,
            f"{row_id}: OPENFF_FULL_PARAMETER_RECOMPUTATION_MISMATCH")
    return {"atoms": n, "heavy_atoms": heavy.GetNumAtoms(), "bonds": len(bond_pairs),
            "constraints": len(constrained_pairs), "charge_sum_e": charge_sum,
            "full_openmm_parameters_recomputed": True,
            "min_nonbonded_heavy_distance_angstrom": min(math.dist(sdf_xyz[a], sdf_xyz[b])
                for a in range(heavy.GetNumAtoms()) for b in range(a + 1, heavy.GetNumAtoms())
                if (a, b) not in bond_pairs)}


def verify(directory: Path, pdf: Path, ledger_path: Path) -> dict:
    receipt = verify_source(pdf.resolve(), ledger_path.resolve())
    manifest = json.loads((directory / "manifest.v1.json").read_text(encoding="utf-8"))
    require(manifest["schema_version"] == EXPECTED_SCHEMA
            and manifest["status"] == "RESEARCH_ONLY_PREPARED_LIGAND_NOT_QUALIFIED"
            and manifest["source"]["pdf_sha256"] == receipt["pdf_sha256"]
            and manifest["source"]["ledger_sha256"] == receipt["ledger_sha256"]
            and manifest["method"]["assayed_microstate_verified"] is False
            and manifest["method"]["forcefield"] == "openff-2.2.1.offxml"
            and manifest["method"]["forcefield_sha256"] == EXPECTED_FF_SHA
            and manifest["method"]["charge_model"] == "openff-gnn-am1bcc-1.0.0.pt"
            and manifest["method"]["charge_model_sha256"] == EXPECTED_MODEL_SHA
            and manifest["scope"]["receptor_pose_or_registration_supplied"] is False
            and manifest["scope"]["training_admitted"] is False,
            "MANIFEST_SOURCE_METHOD_OR_AUTHORITY_MISMATCH")
    import openforcefields
    import openff.nagl_models
    ff_path = Path(openforcefields.__file__).parent / "offxml/openff-2.2.1.offxml"
    model_path = Path(openff.nagl_models.__file__).parent / "models/am1bcc/openff-gnn-am1bcc-1.0.0.pt"
    require(sha(ff_path.read_bytes()) == EXPECTED_FF_SHA and sha(model_path.read_bytes()) == EXPECTED_MODEL_SHA,
            "INSTALLED_PARAMETER_SOURCE_HASH_MISMATCH")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    rows = {row["paper_row_id"]: row for row in ledger["rows"]}
    require(set(manifest["rows"]) == {"PR49", "PR59"}, "MANIFEST_ROW_SET_MISMATCH")
    ff = ForceField("openff-2.2.1.offxml")
    results = {row_id: _verify_one(directory / row_id, row_id, rows[row_id],
                                   manifest["rows"][row_id], ff)
               for row_id in ("PR49", "PR59")}
    return {"status": "PASS_RESEARCH_ONLY_LIGAND_PROJECTION", "source_pdf_sha256": receipt["pdf_sha256"],
            "rows": results, "receptor_pose_or_affinity_validated": False,
            "training_admitted": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args()
    print(json.dumps(verify(args.output_dir, args.pdf, args.ledger), sort_keys=True,
                     allow_nan=False))


if __name__ == "__main__":
    main()
