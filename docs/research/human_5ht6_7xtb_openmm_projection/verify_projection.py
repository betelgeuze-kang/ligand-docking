"""Independent integrity and reader-projection check for the 7XTB OpenMM export.

This imports neither the projection builder nor any protected outcome source.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from openmm import NonbondedForce, XmlSerializer, app, unit


HERE = Path(__file__).resolve().parent
EXTRACTION = HERE.parents[1] / "evidence/human_5ht6_7xtb_receptor_extraction_v1"
sys.path.insert(0, str(EXTRACTION))
from verify_packet import verify_packet as verify_source_packet  # noqa: E402

SOURCE_SHA256 = "e81b271ee863340c0e1e65101be7695849bdd56f408c887b03b89929cc4e9cb7"
SOURCE_BYTES = 900097
FILES = {"receptor-prepared.pdb", "receptor-A.itp", "receptor-B.itp", "atomtypes.itp",
         "defaults.itp", "openmm-system.xml", "atom-provenance.csv"}
DEFAULT_OUTPUT = Path("/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-7xtb-openmm-projection-20260929")


class ProjectionError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProjectionError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _installed_forcefield_sources() -> dict[str, str]:
    data = Path(app.__file__).parent / "data"
    wrapper = (data / "amber14-all.xml").read_bytes()
    includes = [node.attrib["file"] for node in ET.fromstring(wrapper).findall("Include")]
    require(includes == ["amber14/protein.ff14SB.xml", "amber14/DNA.OL15.xml",
                         "amber14/RNA.OL3.xml", "amber14/lipid17.xml"],
            "installed force field include inventory changed")
    return {name: sha((data / name).read_bytes()) for name in ["amber14-all.xml", *includes]}


def _sections(raw: bytes, allowed: set[str]) -> dict[str, list[list[str]]]:
    sections: dict[str, list[list[str]]] = {}
    current = None
    for original in raw.decode("ascii").splitlines():
        line = original.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            require(line.endswith("]"), "malformed ITP section")
            current = line[1:-1].strip()
            require(current in allowed and current not in sections, "unexpected or duplicate ITP section")
            sections[current] = []
        else:
            require(current is not None and not line.startswith("#"), "ITP data outside section")
            sections[current].append(line.split())
    return sections


def _atomtypes(raw: bytes) -> dict[str, tuple[int, float, float, float]]:
    sections = _sections(raw, {"atomtypes"})
    require(set(sections) == {"atomtypes"}, "missing atomtypes")
    result = {}
    for row in sections["atomtypes"]:
        require(len(row) == 7 and row[4] == "A" and float(row[3]) == 0,
                "nonbonded atomtype row malformed")
        name, number, mass, _, _, sigma, epsilon = row
        require(name not in result, "duplicate atomtype")
        values = (int(number), float(mass), float(sigma), float(epsilon))
        require(values[0] > 0 and all(math.isfinite(x) and x >= 0 for x in values[1:]),
                "invalid atomtype values")
        result[name] = values
    require(bool(result), "empty atomtype set")
    return result


def _itp(raw: bytes, chain: str) -> tuple[list[dict], set[tuple[int, int]]]:
    sections = _sections(raw, {"moleculetype", "atoms", "bonds"})
    require(set(sections) == {"moleculetype", "atoms", "bonds"}, "ITP sections incomplete")
    require(sections["moleculetype"] == [[f"RECEPTOR_{chain}", "3"]], "moleculetype changed")
    atoms = []
    for row in sections["atoms"]:
        require(len(row) == 8 and int(row[0]) == len(atoms) + 1
                and int(row[5]) == len(atoms) + 1, "ITP atom row ordering changed")
        index, atomtype, resnum, resname, name, _, charge, mass = row
        require(math.isfinite(float(charge)) and math.isfinite(float(mass)) and float(mass) > 0,
                "ITP nonfinite or nonpositive mass/charge")
        atoms.append({"index": int(index), "type": atomtype, "resnum": int(resnum),
                      "resname": resname, "name": name,
                      "charge": float(charge), "mass": float(mass)})
    require(bool(atoms), "empty chain ITP")
    bonds = set()
    for row in sections["bonds"]:
        require(len(row) == 3 and row[2] == "1", "reader adjacency row malformed")
        first, second = int(row[0]), int(row[1])
        require(1 <= first <= len(atoms) and 1 <= second <= len(atoms) and first != second,
                "ITP bond index invalid")
        pair = tuple(sorted((first - 1, second - 1)))
        require(pair not in bonds, "duplicate ITP bond")
        bonds.add(pair)
    return atoms, bonds


def _pdb(raw: bytes) -> tuple[list[str], set[tuple[int, int]], list[str]]:
    lines = raw.decode("ascii").splitlines()
    atom_lines = [line for line in lines if line.startswith(("ATOM  ", "HETATM"))]
    require(all(len(line) == 80 and line.startswith("ATOM  ") for line in atom_lines),
            "prepared PDB ATOM record malformed")
    serials = [int(line[6:11]) for line in atom_lines]
    require(len(set(serials)) == len(serials), "PDB atom serial duplicated")
    serial_to_index = {serial: index for index, serial in enumerate(serials)}
    bonds = set()
    for line in lines:
        if not line.startswith("CONECT"):
            continue
        require(len(line) == 16, "CONECT must have one complete edge per row")
        first, second = int(line[6:11]), int(line[11:16])
        require(first in serial_to_index and second in serial_to_index,
                "CONECT references missing atom")
        pair = tuple(sorted((serial_to_index[first], serial_to_index[second])))
        require(pair[0] != pair[1] and pair not in bonds, "duplicate or self CONECT")
        bonds.add(pair)
    require(lines[-1] == "END" and len(bonds) > 4000, "PDB complete bond table absent")
    ter = [line for line in lines if line.startswith("TER   ")]
    require(len(ter) == 2 and ter[0][21] == "A" and int(ter[0][22:26]) == 227
            and ter[1][21] == "B" and int(ter[1][22:26]) == 338,
            "PDB gap/terminal break changed")
    return atom_lines, bonds, ter


def _source_map() -> list[dict[str, str]]:
    with (EXTRACTION / "source-atom-map.csv").open(newline="", encoding="ascii") as stream:
        return list(csv.DictReader(stream))


def _close(a: float, b: float, tolerance: float = 1e-10) -> bool:
    return abs(a - b) <= tolerance


def verify(output_dir: Path, source: Path) -> dict:
    source_raw = source.read_bytes()
    require(len(source_raw) == SOURCE_BYTES and sha(source_raw) == SOURCE_SHA256,
            "pinned 7XTB source mismatch")
    verify_source_packet(EXTRACTION, source)
    original_map_raw = (EXTRACTION / "source-atom-map.csv").read_bytes()
    original_pdb_raw = (EXTRACTION / "receptor-E-observed.pdb").read_bytes()
    manifest = json.loads((output_dir / "manifest.v1.json").read_text(encoding="ascii"))
    require(manifest.get("schema_version") == "human_5ht6_7xtb_openmm_cross_projection_v1"
            and manifest.get("status") == "RESEARCH_ONLY_CROSS_PROJECTION_NOT_QUALIFIED",
            "manifest schema or research status changed")
    require(manifest.get("source") == {
        "entry_id": "7XTB", "cif_bytes": SOURCE_BYTES, "cif_sha256": SOURCE_SHA256,
        "observed_pdb_sha256": sha(original_pdb_raw),
        "source_atom_map_sha256": sha(original_map_raw)}, "manifest source relationship changed")
    scope = manifest.get("scope", {})
    require(scope.get("reader") == "prepared_gromacs_components_v1 receptor fields only"
            and scope.get("cross_only_nonbonded_projection") is True
            and all(scope.get(key) is False for key in (
                "complete_gromacs_forcefield_or_topology", "bonded_parameters_exported",
                "solvent_or_membrane_included", "ligand_included", "assay_state_equivalence_verified",
                "scientifically_validated", "product_qualified", "protected_outcomes_read")),
            "projection scope or authority changed")
    method = manifest.get("method", {})
    require(method.get("openmm_version", "").startswith("8.4.")
            and method.get("forcefield") == "amber14-all.xml"
            and method.get("forcefield_source_sha256") == _installed_forcefield_sources()
            and method.get("nonbonded_method") == "NoCutoff"
            and method.get("constraints") is None
            and method.get("rigid_water") is False
            and method.get("pH_for_hydrogen_rules") == 7.0
            and method.get("histidine_requested_variants") == {"A:167": "HIE", "A:171": "HIE"},
            "OpenMM method declaration changed")
    require(set(manifest.get("files", {})) == FILES, "artifact inventory changed")
    raw = {name: (output_dir / name).read_bytes() for name in FILES}
    for name, content in raw.items():
        require(manifest["files"][name] == {"bytes": len(content), "sha256": sha(content)},
                f"artifact digest mismatch: {name}")
    pdb_atoms, pdb_bonds, _ = _pdb(raw["receptor-prepared.pdb"])
    require(len(pdb_atoms) == 4376, "prepared atom count changed")
    provenance = list(csv.DictReader(io.StringIO(raw["atom-provenance.csv"].decode("ascii"))))
    require(len(provenance) == len(pdb_atoms) and len(set(tuple(row.items()) for row in provenance)) == len(provenance),
            "atom provenance cardinality changed")
    source_rows = _source_map()
    require(len(source_rows) == 2124, "observed source map count changed")
    source_ids = {row["source_atom_site_id"]: row for row in source_rows}
    require(len(source_ids) == 2124, "observed source map duplicate ID")
    found_source, generated_heavy, hydrogens = set(), set(), 0
    chains = []
    for line, row in zip(pdb_atoms, provenance):
        identity = (line[21], line[22:26].strip(), line[17:20].strip(),
                    line[12:16].strip(), line[76:78].strip())
        require((row["prepared_serial"], row["prepared_chain"],
                 row["prepared_residue_number"], row["prepared_residue_name"],
                 row["prepared_atom_name"], row["prepared_element"]) ==
                (line[6:11].strip(), *identity), "PDB/provenance atom identity mismatch")
        if not chains or chains[-1] != line[21]:
            chains.append(line[21])
        if row["origin"] == "source_observed_heavy":
            source_id = row["source_atom_site_id"]
            require(source_id in source_ids and source_id not in found_source,
                    "source heavy atom missing or reused")
            found_source.add(source_id)
            source_row = source_ids[source_id]
            require((line[21], line[22:26].strip(), line[17:20].strip(),
                     line[12:16].strip(), line[76:78].strip()) ==
                    (source_row["output_chain_id"], source_row["source_auth_seq_id"],
                     source_row["source_label_comp_id"], source_row["source_label_atom_id"],
                     source_row["source_type_symbol"]), "source heavy atom identity changed")
            require(all(line[start:start + 8].strip() == source_row[f"source_{axis}"]
                        for axis, start in zip("xyz", (30, 38, 46))),
                    "source heavy coordinate changed")
        elif row["origin"] == "explicitly_modelled_heavy":
            require(row["source_atom_site_id"] == "" and identity[-1] != "H",
                    "modelled heavy atom falsely source-bound")
            generated_heavy.add((identity[0], identity[1], identity[3]))
        else:
            require(row["origin"] == "openmm_generated_hydrogen" and identity[-1] == "H"
                    and row["source_atom_site_id"] == "", "hydrogen provenance changed")
            hydrogens += 1
        require(all(math.isfinite(float(line[start:start + 8])) for start in (30, 38, 46)),
                "nonfinite prepared coordinate")
    require(chains == ["A", "B"], "PDB chain order or gap changed")
    require(found_source == set(source_ids) and generated_heavy == {
        ("A", "26", "OG"), ("A", "227", "OXT"), ("B", "338", "OXT")}
        and hydrogens == 2249, "observed/generated atom inventory changed")
    residue_keys = {(line[21], int(line[22:26])) for line in pdb_atoms}
    require(residue_keys == ({("A", n) for n in range(26, 228)} |
                             {("B", n) for n in range(263, 339)}), "residue gaps changed")
    names_by_residue: dict[tuple[str, int], set[str]] = {}
    for line in pdb_atoms:
        names_by_residue.setdefault((line[21], int(line[22:26])), set()).add(line[12:16].strip())
    for key in (("A", 26), ("B", 263)):
        require({"H", "H2", "H3"} <= names_by_residue[key],
                "charged N-terminal hydrogen signature changed")
    for key in (("A", 227), ("B", 338)):
        require("OXT" in names_by_residue[key], "modelled C-terminal OXT absent")
    for key in (("A", 167), ("A", 171)):
        require("HE2" in names_by_residue[key] and "HD1" not in names_by_residue[key],
                "declared HIE histidine signature changed")
    for key in (("A", 99), ("A", 180)):
        require("SG" in names_by_residue[key] and "HG" not in names_by_residue[key],
                "disulfide cysteine hydrogen signature changed")
    types = _atomtypes(raw["atomtypes.itp"])
    defaults = _sections(raw["defaults.itp"], {"defaults"})
    require(defaults == {"defaults": [["1", "2", "no", "1.0", "1.0"]]},
            "cross-only defaults changed")
    chain_atoms, chain_bonds = {}, {}
    offsets = {"A": 0, "B": 0}
    cursor = 0
    for chain in ("A", "B"):
        chain_atoms[chain], chain_bonds[chain] = _itp(raw[f"receptor-{chain}.itp"], chain)
        offsets[chain] = cursor
        cursor += len(chain_atoms[chain])
    require(cursor == len(pdb_atoms), "ITP/PDB atom count mismatch")
    itp_edges = set()
    for chain in ("A", "B"):
        offset = offsets[chain]
        for local_index, row in enumerate(chain_atoms[chain]):
            line = pdb_atoms[offset + local_index]
            require((line[21], int(line[22:26]), line[17:20].strip(), line[12:16].strip()) ==
                    (chain, row["resnum"], row["resname"], row["name"]),
                    "reader atom row/PDB order mismatch")
            require(row["type"] in types and types[row["type"]][0] ==
                    {"H": 1, "C": 6, "N": 7, "O": 8, "S": 16}[line[76:78].strip()],
                    "reader atomtype element mismatch")
            require(_close(types[row["type"]][1], row["mass"], 1e-8),
                    "reader atom mass differs from type")
        itp_edges.update((offset + i, offset + j) for i, j in chain_bonds[chain])
    require(pdb_bonds == itp_edges, "partial CONECT or ITP adjacency mismatch")
    sg = {(line[21], line[22:26].strip(), line[12:16].strip()): index
          for index, line in enumerate(pdb_atoms) if line[12:16].strip() == "SG"}
    require(tuple(sorted((sg["A", "99", "SG"], sg["A", "180", "SG"]))) in itp_edges,
            "Cys99-180 disulfide missing")
    require(all(pdb_atoms[i][21] == pdb_atoms[j][21] for i, j in itp_edges),
            "cross-gap bond present")
    system = XmlSerializer.deserialize(raw["openmm-system.xml"].decode("utf-8"))
    require(system.getNumParticles() == len(pdb_atoms), "OpenMM XML particle count mismatch")
    nbs = [force for force in system.getForces() if isinstance(force, NonbondedForce)]
    require(len(nbs) == 1 and nbs[0].getNumParticles() == len(pdb_atoms),
            "OpenMM XML nonbonded force missing")
    nb = nbs[0]
    for chain in ("A", "B"):
        for local_index, row in enumerate(chain_atoms[chain]):
            index = offsets[chain] + local_index
            charge, sigma, epsilon = nb.getParticleParameters(index)
            _, mass, sigma_itp, epsilon_itp = types[row["type"]]
            require(_close(float(charge.value_in_unit(unit.elementary_charge)), row["charge"])
                    and _close(float(sigma.value_in_unit(unit.nanometer)), sigma_itp)
                    and _close(float(epsilon.value_in_unit(unit.kilojoule_per_mole)), epsilon_itp)
                    and _close(float(system.getParticleMass(index).value_in_unit(unit.dalton)), mass, 1e-8),
                    "OpenMM XML/ITP nonbonded parameter mismatch")
    require(manifest.get("counts") == {
        "atoms": len(pdb_atoms), "bonds": len(itp_edges), "chain_atoms": {
            chain: len(chain_atoms[chain]) for chain in ("A", "B")},
        "generated_heavy_atoms": 3, "generated_hydrogens": hydrogens,
        "observed_heavy_atoms": 2124,
        "histidine_variants": {"A:167": "HIE", "A:171": "HIE"}},
        "manifest atom/bond counts changed")
    # Exercise the same bounded parser used by the product reader, separately
    # from this verifier's own PDB and ITP checks.
    from betelgeuze_engine_v2.io import parse_pdb
    from betelgeuze_engine.product import prepared_gromacs_input as reader
    parsed = parse_pdb(raw["receptor-prepared.pdb"], unit_cell_policy="ignore")
    require(parsed.atom_count == len(pdb_atoms) and len(parsed.bonds) == len(itp_edges),
            "strict reader PDB projection failed")
    for chain in ("A", "B"):
        top = reader._topology(raw[f"receptor-{chain}.itp"], f"chain_{chain}", role="molecule")
        rows, bonds = reader._molecule(top, f"chain_{chain}")
        require(len(rows) == len(chain_atoms[chain]) and bonds == chain_bonds[chain],
                "cross-only reader ITP parse mismatch")
    reader._atomtypes(reader._topology(raw["atomtypes.itp"], "atomtypes", role="atomtypes"), "atomtypes")
    reader._defaults(reader._topology(raw["defaults.itp"], "defaults", role="defaults"), "defaults")
    require(source.read_bytes() == source_raw, "source changed during verification")
    return {"status": "PASS_RESEARCH_ONLY_CROSS_PROJECTION", "atoms": len(pdb_atoms),
            "observed_heavy_atoms": len(found_source), "generated_heavy_atoms": 3,
            "hydrogens": hydrogens, "bonds": len(itp_edges),
            "full_gromacs_or_assay_equivalence": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(verify(args.output_dir, args.source), sort_keys=True))


if __name__ == "__main__":
    main()
