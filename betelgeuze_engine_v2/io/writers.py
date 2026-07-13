"""Strict bounded writers matching the Engine v2 ingest subsets."""

from __future__ import annotations

from dataclasses import dataclass
import math

import torch

from betelgeuze_engine_v2.molecular import AllAtomSystem, require_valid_all_atom_system


class MolecularWriteError(ValueError):
    """A molecular system cannot be represented by the requested strict format."""


@dataclass(frozen=True)
class WriterReceipt:
    format: str
    atom_count: int
    bond_count: int
    model_index: int
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "format": self.format,
            "atom_count": int(self.atom_count),
            "bond_count": int(self.bond_count),
            "model_index": int(self.model_index),
            "limitations": list(self.limitations),
        }


def _model_coordinates(system: AllAtomSystem, model_index: int) -> torch.Tensor:
    require_valid_all_atom_system(system)
    index = int(model_index)
    if index < 0 or index >= system.model_count:
        raise MolecularWriteError("model_index is outside the coordinate ensemble")
    coordinates = system.coordinates[index].detach().to(dtype=torch.float64, device="cpu")
    if not bool(torch.isfinite(coordinates).all().item()):
        raise MolecularWriteError("coordinates must be finite")
    return coordinates


def _pdb_charge(value: int) -> str:
    charge = int(value)
    if charge == 0:
        return "  "
    if abs(charge) > 9:
        raise MolecularWriteError("PDB formal charge magnitude must be <= 9")
    return f"{abs(charge)}{'+' if charge > 0 else '-'}"


def _pdb_coordinate(value: float) -> str:
    number = float(value)
    if not math.isfinite(number) or number <= -1000.0 or number >= 10000.0:
        raise MolecularWriteError("coordinate is outside the PDB 8.3 field range")
    return f"{number:8.3f}"


def pdb_string(
    system: AllAtomSystem,
    *,
    model_index: int = 0,
) -> tuple[str, WriterReceipt]:
    """Serialize one model to the strict PDB subset consumed by :func:`parse_pdb`."""

    coordinates = _model_coordinates(system, model_index)
    if system.atom_count > 99_999:
        raise MolecularWriteError("PDB writer supports at most 99,999 atoms")
    if any(abs(float(bond.order) - 1.0) > 1.0e-12 or bond.aromatic for bond in system.bonds):
        raise MolecularWriteError(
            "strict PDB writer cannot preserve non-single or aromatic bond orders; use SDF or canonical JSON"
        )

    lines: list[str] = []
    if system.cell is not None:
        lengths = system.cell.orthorhombic_lengths().detach().to(dtype=torch.float64, device="cpu")
        if not bool(torch.all(torch.tensor(system.cell.periodic, dtype=torch.bool)).item()):
            raise MolecularWriteError("PDB CRYST1 output requires all three axes to be periodic")
        if bool((lengths <= 0).any().item()) or bool((lengths >= 10_000.0).any().item()):
            raise MolecularWriteError("unit-cell lengths are outside the PDB CRYST1 range")
        lines.append(
            f"CRYST1{float(lengths[0]):9.3f}{float(lengths[1]):9.3f}{float(lengths[2]):9.3f}"
            f"{90.0:7.2f}{90.0:7.2f}{90.0:7.2f} P 1           1"
        )

    serial_by_index: dict[int, int] = {}
    for atom in system.atoms:
        residue = system.residues[atom.residue_index]
        chain = system.chains[residue.chain_index]
        serial = atom.serial if atom.serial is not None else atom.index + 1
        if serial < 1 or serial > 99_999 or serial in serial_by_index.values():
            serial = atom.index + 1
        if serial > 99_999:
            raise MolecularWriteError("PDB atom serial exceeds five digits")
        serial_by_index[atom.index] = serial
        if len(atom.name) > 4 or not atom.name:
            raise MolecularWriteError("PDB atom names must contain 1-4 characters")
        if len(residue.name) > 3 or not residue.name:
            raise MolecularWriteError("PDB residue names must contain 1-3 characters")
        if len(chain.chain_id) > 1:
            raise MolecularWriteError("strict PDB writer supports one-character chain IDs")
        if len(residue.insertion_code) > 1:
            raise MolecularWriteError("PDB insertion codes must contain at most one character")
        if residue.sequence_number < -999 or residue.sequence_number > 9_999:
            raise MolecularWriteError("PDB residue sequence number is outside the four-column range")
        occupancy = 1.0 if atom.occupancy is None else float(atom.occupancy)
        b_factor = 0.0 if atom.b_factor is None else float(atom.b_factor)
        if not 0.0 <= occupancy <= 1.0:
            raise MolecularWriteError("PDB occupancy must be in [0,1]")
        if not math.isfinite(b_factor) or b_factor < 0.0 or b_factor >= 1_000.0:
            raise MolecularWriteError("PDB B-factor must be finite and in [0,1000)")
        x, y, z = (float(value) for value in coordinates[atom.index].tolist())
        record = "HETATM" if residue.hetero or residue.entity_type != "polymer" else "ATOM"
        line = (
            f"{record:<6}{serial:5d} {atom.name:<4}{'':1}{residue.name:>3} {chain.chain_id:1}"
            f"{residue.sequence_number:4d}{residue.insertion_code:1}   "
            f"{_pdb_coordinate(x)}{_pdb_coordinate(y)}{_pdb_coordinate(z)}"
            f"{occupancy:6.2f}{b_factor:6.2f}          {atom.element:>2}{_pdb_charge(atom.formal_charge)}"
        )
        lines.append(line)

    adjacency: dict[int, list[int]] = {atom.index: [] for atom in system.atoms}
    for bond in system.bonds:
        adjacency[bond.atom_i].append(bond.atom_j)
        adjacency[bond.atom_j].append(bond.atom_i)
    for atom_index in sorted(adjacency):
        targets = sorted(adjacency[atom_index])
        for offset in range(0, len(targets), 4):
            chunk = targets[offset : offset + 4]
            lines.append(
                "CONECT"
                + f"{serial_by_index[atom_index]:5d}"
                + "".join(f"{serial_by_index[target]:5d}" for target in chunk)
            )
    lines.append("END")
    text = "\n".join(lines) + "\n"
    return text, WriterReceipt(
        format="pdb_strict_v1",
        atom_count=system.atom_count,
        bond_count=len(system.bonds),
        model_index=int(model_index),
        limitations=(
            "single_coordinate_model",
            "orthorhombic_cell_only",
            "single_bond_connectivity_only",
            "no_link_or_ssbond_records",
        ),
    )


_SDF_STEREO_CODE = {"none": 0, "up": 1, "either": 4, "down": 6}


def _sdf_charge_code(formal_charge: int) -> int:
    reverse = {0: 0, 3: 1, 2: 2, 1: 3, -1: 5, -2: 6, -3: 7}
    return reverse.get(int(formal_charge), 0)


def sdf_v2000_string(
    system: AllAtomSystem,
    *,
    model_index: int = 0,
    title: str | None = None,
) -> tuple[str, WriterReceipt]:
    """Serialize one connected molecular state to strict single-record SDF V2000."""

    coordinates = _model_coordinates(system, model_index)
    if system.cell is not None:
        raise MolecularWriteError("SDF V2000 writer does not encode periodic unit cells")
    if system.atom_count > 999 or len(system.bonds) > 999:
        raise MolecularWriteError("SDF V2000 counts fields support at most 999 atoms and bonds")
    if any(len(atom.element) > 3 or not atom.element for atom in system.atoms):
        raise MolecularWriteError("SDF atoms require explicit 1-3 character elements")

    lines = [str(title or system.system_id)[:80], "EngineV2", "strict V2000 export"]
    lines.append(f"{system.atom_count:3d}{len(system.bonds):3d}  0  0  0  0            999 V2000")
    charge_overrides: list[tuple[int, int]] = []
    isotope_overrides: list[tuple[int, int]] = []
    for atom in system.atoms:
        x, y, z = (float(value) for value in coordinates[atom.index].tolist())
        if any(not math.isfinite(value) or value <= -10_000.0 or value >= 100_000.0 for value in (x, y, z)):
            raise MolecularWriteError("coordinate is outside the SDF V2000 10.4 field range")
        charge_code = _sdf_charge_code(atom.formal_charge)
        if charge_code == 0 and atom.formal_charge != 0:
            charge_overrides.append((atom.index + 1, atom.formal_charge))
        if atom.isotope_mass_number is not None:
            isotope_overrides.append((atom.index + 1, atom.isotope_mass_number))
        lines.append(
            f"{x:10.4f}{y:10.4f}{z:10.4f} {atom.element:<3}{0:2d}{charge_code:3d}"
            "  0  0  0  0  0  0  0  0  0  0  0  0"
        )
    for bond in system.bonds:
        if bond.aromatic or abs(bond.order - 1.5) <= 1.0e-12:
            bond_type = 4
        elif any(abs(bond.order - value) <= 1.0e-12 for value in (1.0, 2.0, 3.0)):
            bond_type = int(round(bond.order))
        else:
            raise MolecularWriteError("SDF V2000 supports bond orders 1, 2, 3, or aromatic 1.5")
        stereo_code = _SDF_STEREO_CODE.get(bond.stereo)
        if stereo_code is None:
            raise MolecularWriteError(f"unsupported SDF bond stereo {bond.stereo!r}")
        lines.append(
            f"{bond.atom_i + 1:3d}{bond.atom_j + 1:3d}{bond_type:3d}{stereo_code:3d}  0  0  0"
        )

    def append_pairs(label: str, pairs: list[tuple[int, int]]) -> None:
        for offset in range(0, len(pairs), 8):
            chunk = pairs[offset : offset + 8]
            lines.append(
                f"M  {label}{len(chunk):3d}"
                + "".join(f"{atom_number:4d}{value:4d}" for atom_number, value in chunk)
            )

    append_pairs("CHG", charge_overrides)
    append_pairs("ISO", isotope_overrides)
    lines.extend(["M  END", "$$$$"])
    text = "\n".join(lines) + "\n"
    return text, WriterReceipt(
        format="sdf_v2000_strict_v1",
        atom_count=system.atom_count,
        bond_count=len(system.bonds),
        model_index=int(model_index),
        limitations=(
            "single_molecule_record",
            "single_coordinate_model",
            "no_periodic_cell",
            "no_data_fields",
            "no_sanitization_or_aromaticity_perception",
        ),
    )


__all__ = [
    "MolecularWriteError",
    "WriterReceipt",
    "pdb_string",
    "sdf_v2000_string",
]
