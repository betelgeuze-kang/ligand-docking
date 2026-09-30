"""Build source-bound, research-only neutral PR49/PR59 ligand projections.

Run with the pinned external OpenFF runtime. No receptor pose is generated.
The ITP is an adjacency/nonbonded reader projection; OpenMM XML contains the
actual full intramolecular parameters.
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

from rdkit import Chem, rdBase
from rdkit.Chem import AllChem, rdMolDescriptors
from openff.toolkit import ForceField, Molecule, Topology
from openff.interchange import Interchange
from openmm import NonbondedForce, XmlSerializer, unit as omm_unit, version as omm_version
import openff.toolkit
import openff.interchange


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools/product"))
from primary_5ht6_ki_2024_source_v1 import verify_source  # noqa: E402

DEFAULT_LEDGER = REPO / "docs/evidence/human_5ht6_ki_2024_source_ledger_v1.json"
DEFAULT_PDF = Path("/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/5ht6-primary-20260929/2024.pdf")
DEFAULT_OUTPUT = Path("/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-5ht6-pr49-pr59-openff-projection-20260929")
FF_NAME = "openff-2.2.1.offxml"
FF_SHA256 = "1b24deb47970bae2d179a5b4e023d4a57c9c78614fe431f1670e3f75e0012c3a"
CHARGE_MODEL = "openff-gnn-am1bcc-1.0.0.pt"
CHARGE_MODEL_SHA256 = "7981e7f5b0b1e424c9e10a40d9e7606d96dcd3dd2b095cb4eeff6829f92238ee"
SEEDS = {"PR49": 202449, "PR59": 202459}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _installed_sources() -> tuple[Path, Path]:
    import openforcefields
    import openff.nagl_models

    ff = Path(openforcefields.__file__).parent / "offxml" / FF_NAME
    model = Path(openff.nagl_models.__file__).parent / "models/am1bcc" / CHARGE_MODEL
    if sha(ff.read_bytes()) != FF_SHA256:
        raise ValueError("OPENFF_FORCEFIELD_HASH_MISMATCH")
    if sha(model.read_bytes()) != CHARGE_MODEL_SHA256:
        raise ValueError("NAGL_CHARGE_MODEL_HASH_MISMATCH")
    if openff.toolkit.__version__ != "0.18.0" or openff.interchange.__version__ != "0.5.2":
        raise ValueError("OPENFF_RUNTIME_VERSION_MISMATCH")
    if not omm_version.version.startswith("8.6.1"):
        raise ValueError("OPENMM_RUNTIME_VERSION_MISMATCH")
    return ff, model


def _name_atoms(mol: Chem.Mol) -> list[str]:
    counts: dict[str, int] = {}
    names = []
    for atom in mol.GetAtoms():
        # The cross reader requires the exact element case, e.g. Cl1.
        symbol = atom.GetSymbol()
        counts[symbol] = counts.get(symbol, 0) + 1
        name = f"{symbol}{counts[symbol]}"
        if len(name) > 5:
            raise ValueError("GRO_ATOM_NAME_TOO_LONG")
        names.append(name)
    return names


def _prepared_mol(smiles: str, row_id: str) -> tuple[Chem.Mol, dict]:
    heavy = Chem.MolFromSmiles(smiles)
    if heavy is None or Chem.GetFormalCharge(heavy) != 0 or len(Chem.GetMolFrags(heavy)) != 1:
        raise ValueError(f"{row_id}: SOURCE_NEUTRAL_GRAPH_INVALID")
    mol = Chem.AddHs(heavy)
    params = AllChem.ETKDGv3()
    params.randomSeed = SEEDS[row_id]
    params.numThreads = 1
    params.pruneRmsThresh = -1.0
    ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=8, params=params))
    if len(ids) != 8:
        raise ValueError(f"{row_id}: ETKDG_CONFORMER_GENERATION_FAILED")
    results = AllChem.MMFFOptimizeMoleculeConfs(mol, numThreads=1, maxIters=500,
                                                mmffVariant="MMFF94s")
    good = [(energy, cid) for cid, (status, energy) in zip(ids, results) if status == 0 and math.isfinite(energy)]
    if not good:
        raise ValueError(f"{row_id}: MMFF94S_CONFORMER_OPTIMIZATION_FAILED")
    energy, chosen_id = min(good)
    chosen = Chem.Conformer(mol.GetConformer(chosen_id))
    mol.RemoveAllConformers()
    mol.AddConformer(chosen, assignId=True)
    conf = mol.GetConformer()
    # Translation supplies an explicitly ligand-relative frame. Quantization
    # makes SDF (0.0001 A) and GRO (0.00001 nm) coordinates identical.
    n_heavy = heavy.GetNumAtoms()
    center = [sum(conf.GetAtomPosition(i)[axis] for i in range(n_heavy)) / n_heavy
              for axis in range(3)]
    for i in range(mol.GetNumAtoms()):
        p = conf.GetAtomPosition(i)
        conf.SetAtomPosition(i, [round(p[axis] - center[axis], 4) for axis in range(3)])
    return mol, {"seed": SEEDS[row_id], "conformer_count": 8,
                 "selected_conformer_id": int(chosen_id), "selected_mmff94s_energy_kcal_mol": energy,
                 "optimized_conformer_count": len(good), "heavy_atom_count": n_heavy}


def _fmt(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("NONFINITE_PARAMETER")
    return repr(value)


def _render(mol: Chem.Mol, molecule: Molecule, system, row_id: str,
            smiles: str, graph: dict) -> tuple[dict[str, bytes], dict]:
    n = mol.GetNumAtoms()
    if molecule.n_atoms != n or system.getNumParticles() != n:
        raise ValueError(f"{row_id}: OPENFF_ATOM_COUNT_MISMATCH")
    rd_bonds = {tuple(sorted((b.GetBeginAtomIdx(), b.GetEndAtomIdx()))) for b in mol.GetBonds()}
    off_bonds = {tuple(sorted((b.atom1_index, b.atom2_index))) for b in molecule.bonds}
    if rd_bonds != off_bonds or any(a.GetAtomicNum() != b.atomic_number
                                    for a, b in zip(mol.GetAtoms(), molecule.atoms)):
        raise ValueError(f"{row_id}: OPENFF_ATOM_ORDER_OR_BOND_MISMATCH")
    nbs = [f for f in system.getForces() if isinstance(f, NonbondedForce)]
    if len(nbs) != 1 or nbs[0].getNumParticles() != n:
        raise ValueError(f"{row_id}: OPENMM_NONBONDED_FORCE_INCOMPLETE")
    nb = nbs[0]
    names = _name_atoms(mol)
    conf = mol.GetConformer()
    mol.SetProp("_Name", row_id)
    mol_block = Chem.MolToMolBlock(mol, forceV3000=False)
    sdf = (mol_block + "> <PAPER_ROW_ID>\n" + row_id + "\n\n"
           + "> <SOURCE_GRAPH_SMILES>\n" + smiles + "\n\n"
           + "> <COMPUTATIONAL_MICROSTATE>\nneutral_source_graph_assay_state_unverified\n\n"
           + "$$$$\n").encode("ascii")
    gro_lines = [f"{row_id} isolated ligand-relative conformer; no receptor pose", str(n)]
    itp = ["; Reader projection only. Bonded energetics and intramolecular exceptions are in openmm-system.xml.",
           "[ moleculetype ]", f"{row_id} 3", "", "[ atoms ]",
           "; nr type resnr residue atom cgnr charge_e mass_da"]
    types = ["; Atom-specific OpenFF 2.2.1 LJ projection; full force field is openmm-system.xml",
             "[ atomtypes ]", "; name atomic_number mass_da charge ptype sigma_nm epsilon_kj_mol"]
    map_rows = []
    charges = []
    parent_for_h = {}
    for bond in mol.GetBonds():
        a, b = bond.GetBeginAtom(), bond.GetEndAtom()
        if a.GetAtomicNum() == 1:
            parent_for_h[a.GetIdx()] = b.GetIdx()
        elif b.GetAtomicNum() == 1:
            parent_for_h[b.GetIdx()] = a.GetIdx()
    for index, atom in enumerate(mol.GetAtoms()):
        type_name = f"L{index + 1:03d}"
        q, sigma, epsilon = nb.getParticleParameters(index)
        charge = float(q.value_in_unit(omm_unit.elementary_charge))
        sig = float(sigma.value_in_unit(omm_unit.nanometer))
        eps = float(epsilon.value_in_unit(omm_unit.kilojoule_per_mole))
        mass = float(system.getParticleMass(index).value_in_unit(omm_unit.dalton))
        if mass <= 0 or sig < 0 or eps < 0:
            raise ValueError(f"{row_id}: INVALID_OPENFF_PARTICLE_PARAMETER")
        charges.append(charge)
        types.append(f"{type_name} {atom.GetAtomicNum()} {_fmt(mass)} 0 A {_fmt(sig)} {_fmt(eps)}")
        itp.append(f"{index + 1} {type_name} 1 {row_id} {names[index]} {index + 1} {_fmt(charge)} {_fmt(mass)}")
        p = conf.GetAtomPosition(index)
        gro_lines.append(f"{1:5d}{row_id:<5.5s}{names[index]:>5s}{index + 1:5d}"
                         + " ".join(f"{p[axis] / 10:8.5f}" for axis in range(3)))
        parent = parent_for_h.get(index)
        map_rows.append((index + 1, names[index], atom.GetSymbol(),
                         "source_neutral_graph_heavy" if index < graph["heavy_atom_count"] else "computed_implicit_hydrogen",
                         index + 1 if index < graph["heavy_atom_count"] else "",
                         parent + 1 if parent is not None else ""))
    if abs(sum(charges)) > 1e-8:
        raise ValueError(f"{row_id}: MODEL_CHARGE_SUM_NOT_NEUTRAL")
    itp += ["", "[ bonds ]", "; ai aj funct; graph adjacency only, no GROMACS bonded parameters"]
    for a, b in sorted(rd_bonds):
        itp.append(f"{a + 1} {b + 1} 1")
    gro_lines.append("   10.00000   10.00000   10.00000")
    table = io.StringIO(newline="")
    writer = csv.writer(table, lineterminator="\n")
    writer.writerow(("prepared_index", "prepared_atom_name", "element", "origin",
                     "source_graph_atom_index", "source_graph_parent_atom_index"))
    writer.writerows(map_rows)
    files = {"ligand.sdf": sdf,
             "ligand.gro": ("\n".join(gro_lines) + "\n").encode("ascii"),
             "ligand.itp": ("\n".join(itp) + "\n").encode("ascii"),
             "atomtypes.itp": ("\n".join(types) + "\n").encode("ascii"),
             "defaults.itp": b"; Cross-only reader projection; intramolecular exceptions are in XML\n[ defaults ]\n1 2 no 1.0 1.0\n",
             "openmm-system.xml": XmlSerializer.serialize(system).encode("utf-8"),
             "atom-provenance.csv": table.getvalue().encode("ascii")}
    counts = {"atoms": n, "heavy_atoms": graph["heavy_atom_count"],
              "hydrogens": n - graph["heavy_atom_count"], "bonds": len(rd_bonds),
              "openmm_constraints": system.getNumConstraints(),
              "openmm_forces": [f.__class__.__name__ for f in system.getForces()],
              "openmm_exceptions": nb.getNumExceptions(), "partial_charge_sum_e": sum(charges)}
    return files, counts


def build(pdf: Path, ledger_path: Path, output_dir: Path) -> dict:
    source_receipt = verify_source(pdf.resolve(), ledger_path.resolve())
    _installed_sources()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    rows = {row["paper_row_id"]: row for row in ledger["rows"]}
    ff = ForceField(FF_NAME)
    all_files: dict[str, bytes] = {}
    row_reports = {}
    for row_id in ("PR49", "PR59"):
        graph = rows[row_id]["proposed_neutral_graph"]
        smiles = graph["canonical_isomeric_smiles"]
        mol, geometry = _prepared_mol(smiles, row_id)
        heavy = Chem.RemoveHs(mol)
        if (rdMolDescriptors.CalcMolFormula(heavy) != graph["formula"]
                or Chem.inchi.MolToInchiKey(heavy) != graph["inchikey"]
                or graph["assayed_microstate_verified"] is not False):
            raise ValueError(f"{row_id}: SOURCE_GRAPH_IDENTITY_MISMATCH")
        off = Molecule.from_rdkit(mol, hydrogens_are_explicit=True)
        try:
            off.assign_partial_charges(partial_charge_method=CHARGE_MODEL)
        except Exception as exc:
            raise ValueError(f"{row_id}: NAGL_CHARGE_ASSIGNMENT_UNSUPPORTED: {exc}") from exc
        try:
            interchange = Interchange.from_smirnoff(ff, Topology.from_molecules([off]),
                                                     charge_from_molecules=[off])
            system = interchange.to_openmm(combine_nonbonded_forces=True)
        except Exception as exc:
            raise ValueError(f"{row_id}: OPENFF_PARAMETERIZATION_UNSUPPORTED: {exc}") from exc
        files, counts = _render(mol, off, system, row_id, smiles, geometry)
        for name, raw in files.items():
            all_files[f"{row_id}/{name}"] = raw
        row_reports[row_id] = {"source_graph": graph, "geometry": geometry, "counts": counts,
                               "files": {name: {"sha256": sha(raw), "bytes": len(raw)}
                                         for name, raw in files.items()}}
    report = {
        "schema_version": "human_5ht6_pr49_pr59_openff_ligand_projection_v1",
        "status": "RESEARCH_ONLY_PREPARED_LIGAND_NOT_QUALIFIED",
        "source": {"doi": ledger["source"]["doi"], "pdf_sha256": source_receipt["pdf_sha256"],
                   "ledger_sha256": source_receipt["ledger_sha256"],
                   "license_notice": ledger["source"]["license_notice"]},
        "method": {"computational_microstate": "source-proposed neutral graph with explicit RDKit hydrogens",
                   "assayed_microstate_verified": False, "geometry": "RDKit ETKDGv3 8 conformers; single-thread MMFF94s minimum, centered on heavy-atom centroid, quantized 0.0001 A",
                   "charge": "OpenFF NAGL predicted AM1-BCC-like model charges; not toolkit AM1-BCC",
                   "charge_model": CHARGE_MODEL, "charge_model_sha256": CHARGE_MODEL_SHA256,
                   "forcefield": FF_NAME, "forcefield_sha256": FF_SHA256,
                   "rdkit_version": rdBase.rdkitVersion, "openff_toolkit_version": openff.toolkit.__version__,
                   "openff_interchange_version": openff.interchange.__version__,
                   "openmm_version": omm_version.version,
                   "coordinate_frame": "isolated_ligand_relative_centered_no_receptor_pose"},
        "rows": row_reports,
        "scope": {"full_intramolecular_openmm_system_xml": True,
                  "gromacs_itp_bonded_parameters_exported": False,
                  "gromacs_itp_cross_reader_projection_only": True,
                  "receptor_pose_or_registration_supplied": False,
                  "assay_state_equivalence_verified": False,
                  "affinity_or_ranking_validated": False,
                  "training_admitted": False,
                  "protected_outcomes_read": False}}
    all_files["manifest.v1.json"] = (json.dumps(report, indent=2, sort_keys=True,
                                                  ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, raw in all_files.items():
        target = output_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != raw:
                raise ValueError(f"REFUSING_DIFFERENT_EXISTING_ARTIFACT: {target}")
        else:
            target.write_bytes(raw)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build(args.pdf, args.ledger, args.output_dir)
    print(json.dumps({"status": result["status"], "output_dir": str(args.output_dir.resolve()),
                      "rows": {key: value["counts"] for key, value in result["rows"].items()}},
                     sort_keys=True))


if __name__ == "__main__":
    main()
