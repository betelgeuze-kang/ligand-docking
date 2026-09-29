"""Build a source-bound 7XTB receptor projection for the cross-only reader.

This deliberately does not make a GROMACS topology or an assay-state claim.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
import openmm
from openmm import NonbondedForce, Platform, XmlSerializer, app, unit


HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parents[1] / "evidence/human_5ht6_7xtb_receptor_extraction_v1"
sys.path.insert(0, str(EXTRACTION))
from verify_packet import verify_packet as verify_source_packet  # noqa: E402

SOURCE_SHA256 = "e81b271ee863340c0e1e65101be7695849bdd56f408c887b03b89929cc4e9cb7"
SOURCE_BYTES = 900097
DEFAULT_OUTPUT = Path("/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-7xtb-openmm-projection-20260929")
FILES = ("receptor-prepared.pdb", "receptor-A.itp", "receptor-B.itp", "atomtypes.itp",
         "defaults.itp", "openmm-system.xml", "atom-provenance.csv")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def forcefield_source_hashes() -> dict[str, str]:
    data = Path(app.__file__).parent / "data"
    root = (data / "amber14-all.xml").read_bytes()
    includes = [node.attrib["file"] for node in ET.fromstring(root).findall("Include")]
    if includes != ["amber14/protein.ff14SB.xml", "amber14/DNA.OL15.xml",
                    "amber14/RNA.OL3.xml", "amber14/lipid17.xml"]:
        raise ValueError("unexpected amber14-all.xml include inventory")
    return {name: sha((data / name).read_bytes()) for name in ["amber14-all.xml", *includes]}


def xyz(line: str) -> np.ndarray:
    return np.array([float(line[i:i + 8]) for i in (30, 38, 46)])


def unit_vector(value: np.ndarray) -> np.ndarray:
    length = float(np.linalg.norm(value))
    if length < 1e-8:
        raise ValueError("degenerate atom geometry")
    return value / length


def generated_line(parent: str, name: str, point: np.ndarray, serial: int) -> str:
    line = (parent[:6] + f"{serial:5d}" + parent[11:12] + f" {name:<3s}" + parent[16:30]
            + "".join(f"{value:8.3f}" for value in point) + parent[54:76]
            + f"{name[0]:>2s}" + parent[78:])
    if len(line) != 80:
        raise ValueError("generated PDB record is not 80 columns")
    return line


def augment_observed_pdb(raw: bytes) -> str:
    """Add only source-declared Ser26 OG and the two artificial chain-end OXT atoms."""
    lines = raw.decode("ascii").splitlines()
    residues: dict[tuple[str, int], dict[str, str]] = {}
    for line in lines:
        if line.startswith("ATOM  "):
            residues.setdefault((line[21], int(line[22:26])), {})[line[12:16].strip()] = line
    if set(residues) != ({("A", n) for n in range(26, 228)} |
                         {("B", n) for n in range(263, 339)}):
        raise ValueError("observed residue inventory changed")
    ser = residues["A", 26]
    if set(ser) != {"N", "CA", "C", "O", "CB"}:
        raise ValueError("unexpected Ser26 atom inventory")
    ca, cb, n = (xyz(ser[name]) for name in ("CA", "CB", "N"))
    # A fixed, explicitly artificial CB--OG geometry. Heavy source atoms do not move.
    og = cb + 1.41 * unit_vector(unit_vector(cb - ca) - 0.3 * unit_vector(n - ca))
    oxygen_positions = {("A", 26, "CB"): ("OG", og)}
    for chain, number in (("A", 227), ("B", 338)):
        residue = residues[chain, number]
        if "OXT" in residue or not {"CA", "C", "O"} <= set(residue):
            raise ValueError("unexpected terminal oxygen inventory")
        c, ca, o = (xyz(residue[name]) for name in ("C", "CA", "O"))
        axis = unit_vector(ca - c)
        old = o - c
        # Mirror the observed C--O vector about the CA--C axis, at ~1.25 A.
        oxt = c + (2 * np.dot(old, axis) * axis - old) * 1.03
        oxygen_positions[chain, number, "O"] = ("OXT", oxt)
    result, serial = [], 1
    for line in lines:
        if line.startswith(("ATOM  ", "TER   ")):
            result.append(line[:6] + f"{serial:5d}" + line[11:])
            serial += 1
            if line.startswith("ATOM  "):
                key = (line[21], int(line[22:26]), line[12:16].strip())
                if key in oxygen_positions:
                    name, point = oxygen_positions[key]
                    result.append(generated_line(line, name, point, serial))
                    serial += 1
        elif line == "END":
            result.append(line)
        else:
            raise ValueError("unexpected observed PDB record")
    return "\n".join(result) + "\n"


def _pdb_with_complete_bonds(modeller: app.Modeller) -> tuple[bytes, list[str]]:
    stream = io.StringIO()
    app.PDBFile.writeFile(modeller.topology, modeller.positions, stream, keepIds=True)
    # OpenMM emits only selected CONECT records. The strict cross-only reader
    # interprets *any* CONECT as a complete edge set, so replace them all.
    lines = [line for line in stream.getvalue().splitlines()
             if not line.startswith(("REMARK", "CONECT", "MASTER", "END"))]
    atoms = list(modeller.topology.atoms())
    atom_lines = [line for line in lines if line.startswith(("ATOM  ", "HETATM"))]
    if len(atom_lines) != len(atoms):
        raise ValueError("OpenMM PDB atom count changed")
    serials = [int(line[6:11]) for line in atom_lines]
    if len(set(serials)) != len(serials):
        raise ValueError("duplicate prepared PDB atom serial")
    for line, atom in zip(atom_lines, atoms):
        if (line[21], line[22:26].strip(), line[12:16].strip()) != (
                atom.residue.chain.id, atom.residue.id, atom.name):
            raise ValueError("OpenMM PDB atom ordering changed")
    bonds = {tuple(sorted((a.index, b.index))) for a, b in modeller.topology.bonds()}
    for first, second in sorted(bonds):
        lines.append(f"CONECT{serials[first]:5d}{serials[second]:5d}")
    lines.append("END")
    return ("\n".join(lines) + "\n").encode("ascii"), atom_lines


def _fmt(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("nonfinite OpenMM parameter")
    return repr(value)


def _export(modeller: app.Modeller, system: openmm.System, source_rows: list[dict[str, str]],
            actual_variants: list[str | None]) -> tuple[dict[str, bytes], dict]:
    pdb, pdb_atoms = _pdb_with_complete_bonds(modeller)
    atoms = list(modeller.topology.atoms())
    nb = [force for force in system.getForces() if isinstance(force, NonbondedForce)]
    if len(nb) != 1 or nb[0].getNumParticles() != len(atoms):
        raise ValueError("expected one complete OpenMM nonbonded force")
    nb = nb[0]
    types: dict[tuple[int, float, float, float], str] = {}
    atom_records: list[dict] = []
    by_chain = {"A": [], "B": []}
    source_by_identity = {(row["output_chain_id"], row["output_residue_number"],
                           row["output_atom_name"]): row for row in source_rows}
    if len(source_by_identity) != 2124:
        raise ValueError("duplicate observed atom identity")
    provenance_rows = []
    for atom, line in zip(atoms, pdb_atoms):
        if atom.residue.chain.id not in by_chain:
            raise ValueError("unexpected prepared chain")
        charge, sigma, epsilon = nb.getParticleParameters(atom.index)
        mass = system.getParticleMass(atom.index).value_in_unit(unit.dalton)
        charge = float(charge.value_in_unit(unit.elementary_charge))
        sigma = float(sigma.value_in_unit(unit.nanometer))
        epsilon = float(epsilon.value_in_unit(unit.kilojoule_per_mole))
        number = atom.element.atomic_number
        key = (number, mass, sigma, epsilon)
        if key not in types:
            types[key] = f"OMM{len(types) + 1:03d}"
        identity = (line[21], line[22:26].strip(), line[12:16].strip())
        source = source_by_identity.get(identity)
        if source:
            if any(line[start:start + 8].strip() != source[f"source_{axis}"]
                   for axis, start in zip("xyz", (30, 38, 46))):
                raise ValueError(f"observed source heavy coordinate changed: {identity}")
            origin = "source_observed_heavy"
        elif atom.element.symbol != "H":
            if identity not in {("A", "26", "OG"), ("A", "227", "OXT"), ("B", "338", "OXT")}:
                raise ValueError(f"unexpected generated heavy atom: {identity}")
            origin = "explicitly_modelled_heavy"
        else:
            origin = "openmm_generated_hydrogen"
        row = {"index": atom.index, "chain": atom.residue.chain.id,
               "resnum": atom.residue.id, "resname": atom.residue.name,
               "name": atom.name, "type": types[key], "charge": charge, "mass": mass,
               "serial": int(line[6:11]), "origin": origin,
               "source_atom_site_id": source["source_atom_site_id"] if source else ""}
        atom_records.append(row)
        by_chain[row["chain"]].append(row)
        provenance_rows.append(row)
    if sum(row["origin"] == "source_observed_heavy" for row in atom_records) != 2124:
        raise ValueError("observed heavy atom count changed")
    atomtype_lines = ["; OpenMM amber14-all.xml nonbonded projection; not a full GROMACS force field", "[ atomtypes ]",
                      "; name atomic_number mass charge ptype sigma_nm epsilon_kj_mol"]
    for (number, mass, sigma, epsilon), name in types.items():
        atomtype_lines.append(f"{name} {number} {_fmt(mass)} 0 A {_fmt(sigma)} {_fmt(epsilon)}")
    files = {"receptor-prepared.pdb": pdb,
             "atomtypes.itp": ("\n".join(atomtype_lines) + "\n").encode("ascii"),
             "defaults.itp": b"; Cross-only reader projection; no bonded parameter tables\n[ defaults ]\n1 2 no 1.0 1.0\n",
             "openmm-system.xml": XmlSerializer.serialize(system).encode("utf-8")}
    atom_to_local = {row["index"]: (chain, local_index)
                     for chain, rows in by_chain.items()
                     for local_index, row in enumerate(rows, 1)}
    all_bonds = sorted({tuple(sorted((a.index, b.index))) for a, b in modeller.topology.bonds()})
    for chain in ("A", "B"):
        rows = by_chain[chain]
        section = [f"; OpenMM cross-only reader projection for chain {chain}; bonded parameters omitted",
                   "[ moleculetype ]", f"RECEPTOR_{chain} 3", "", "[ atoms ]",
                   "; nr type resnr residue atom cgnr charge mass"]
        for local_index, row in enumerate(rows, 1):
            section.append(f"{local_index} {row['type']} {row['resnum']} {row['resname']} {row['name']} "
                           f"{local_index} {_fmt(row['charge'])} {_fmt(row['mass'])}")
        section += ["", "[ bonds ]", "; ai aj funct; adjacency only, no GROMACS bonded parameter source"]
        for first, second in all_bonds:
            c1, i1 = atom_to_local[first]
            c2, i2 = atom_to_local[second]
            if c1 == c2 == chain:
                section.append(f"{i1} {i2} 1")
            elif c1 != c2:
                raise ValueError("cross-chain bond or missing 227-263 break")
        files[f"receptor-{chain}.itp"] = ("\n".join(section) + "\n").encode("ascii")
    table = io.StringIO(newline="")
    writer = csv.writer(table, lineterminator="\n")
    writer.writerow(("prepared_serial", "prepared_chain", "prepared_residue_number", "prepared_residue_name",
                     "prepared_atom_name", "prepared_element", "origin", "source_atom_site_id"))
    for row, atom in zip(provenance_rows, atoms):
        writer.writerow((row["serial"], row["chain"], row["resnum"], row["resname"], row["name"],
                         atom.element.symbol, row["origin"], row["source_atom_site_id"]))
    files["atom-provenance.csv"] = table.getvalue().encode("ascii")
    variants = {(res.chain.id, res.id): variant for res, variant in
                zip(modeller.topology.residues(), actual_variants) if variant is not None}
    counts = {"atoms": len(atoms), "observed_heavy_atoms": 2124,
              "generated_heavy_atoms": 3,
              "generated_hydrogens": sum(atom.element.symbol == "H" for atom in atoms),
              "bonds": modeller.topology.getNumBonds(),
              "chain_atoms": {chain: len(rows) for chain, rows in by_chain.items()},
              "histidine_variants": {f"{chain}:{resnum}": variant for (chain, resnum), variant in variants.items()
                                     if (chain, resnum) in {("A", "167"), ("A", "171")}}}
    return files, counts


def build(source: Path, output_dir: Path) -> dict:
    if not openmm.version.version.startswith("8.4."):
        raise ValueError("this pinned projection requires OpenMM 8.4")
    raw_source = source.read_bytes()
    if len(raw_source) != SOURCE_BYTES or sha(raw_source) != SOURCE_SHA256:
        raise ValueError("pinned 7XTB CIF size or SHA-256 mismatch")
    verify_source_packet(EXTRACTION, source)
    observed = (EXTRACTION / "receptor-E-observed.pdb").read_bytes()
    with (EXTRACTION / "source-atom-map.csv").open(newline="", encoding="ascii") as stream:
        source_rows = list(csv.DictReader(stream))
    initial = app.PDBFile(io.StringIO(augment_observed_pdb(observed)))
    if initial.topology.getNumAtoms() != 2127 or initial.topology.getNumChains() != 2:
        raise ValueError("unexpected supplemented heavy topology")
    if {frozenset((a.residue.id, b.residue.id)) for a, b in initial.topology.bonds()
            if a.name == b.name == "SG"} != {frozenset(("99", "180"))}:
        raise ValueError("declared Cys99-180 disulfide not connected")
    ff = app.ForceField("amber14-all.xml")
    modeller = app.Modeller(initial.topology, initial.positions)
    # Modelled chain ends are charged standard AMBER termini. Histidines are
    # explicitly epsilon-protonated; all other variants use OpenMM pH 7 rules.
    requested_variants = ["HIE" if residue.name == "HIS" else None
                          for residue in modeller.topology.residues()]
    random.seed(7)
    actual_variants = modeller.addHydrogens(
        ff, pH=7.0, variants=requested_variants,
        platform=Platform.getPlatformByName("Reference"))
    system = ff.createSystem(modeller.topology, nonbondedMethod=app.NoCutoff,
                             constraints=None, rigidWater=False)
    files, counts = _export(modeller, system, source_rows, actual_variants)
    if set(files) != set(FILES):
        raise ValueError("projection file set incomplete")
    manifest = {
        "schema_version": "human_5ht6_7xtb_openmm_cross_projection_v1",
        "status": "RESEARCH_ONLY_CROSS_PROJECTION_NOT_QUALIFIED",
        "source": {"entry_id": "7XTB", "cif_bytes": SOURCE_BYTES, "cif_sha256": SOURCE_SHA256,
                   "observed_pdb_sha256": sha(observed),
                   "source_atom_map_sha256": sha((EXTRACTION / "source-atom-map.csv").read_bytes())},
        "method": {"openmm_version": openmm.version.version,
                   "forcefield": "amber14-all.xml", "forcefield_source_sha256": forcefield_source_hashes(),
                   "nonbonded_method": "NoCutoff", "constraints": None, "rigid_water": False,
                   "pH_for_hydrogen_rules": 7.0, "python_random_seed": 7,
                   "hydrogen_optimization_platform": "Reference",
                   "histidine_requested_variants": {"A:167": "HIE", "A:171": "HIE"},
                   "generated_heavy_geometry": "Ser26 OG: CB + 1.41 A normalized[(CB-CA)^ - 0.3 (N-CA)^]; terminal OXT: mirrored observed C-O about CA-C axis times 1.03",
                   "termini": "standard charged AMBER N/C termini at A26/A227 and B263/B338",
                   "disulfide": "Cys99-Cys180 inferred by OpenMM from source SG geometry"},
        "counts": counts,
        "files": {name: {"bytes": len(files[name]), "sha256": sha(files[name])} for name in FILES},
        "scope": {"reader": "prepared_gromacs_components_v1 receptor fields only",
                  "cross_only_nonbonded_projection": True,
                  "complete_gromacs_forcefield_or_topology": False,
                  "bonded_parameters_exported": False,
                  "solvent_or_membrane_included": False,
                  "ligand_included": False,
                  "assay_state_equivalence_verified": False,
                  "scientifically_validated": False,
                  "product_qualified": False,
                  "protected_outcomes_read": False},
    }
    files["manifest.v1.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("ascii")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        target = output_dir / name
        if target.exists():
            if target.read_bytes() != content:
                raise ValueError(f"refusing to replace different projection artifact: {target}")
        else:
            target.write_bytes(content)
    if source.read_bytes() != raw_source:
        raise ValueError("source changed during projection")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build(args.source, args.output_dir)
    print(json.dumps({"status": report["status"], "atoms": report["counts"]["atoms"],
                      "output_dir": str(args.output_dir.resolve())}, sort_keys=True))


if __name__ == "__main__":
    main()
