"""Deterministic, failure-closed ligand conformer preparation."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
import hashlib
import importlib
import json
import math
import re
from types import MappingProxyType
from typing import Any

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    require_valid_all_atom_system,
)


CONFORMER_ENSEMBLE_SCHEMA_ID = (
    "betelgeuze.engine_v2_prepared_conformer_ensemble/1.0.0"
)
CONFORMER_PREPARATION_POLICY_ID = (
    "betelgeuze.engine_v2_deterministic_etkdgv3_energy_rmsd/1.0.0"
)
MAX_CONFORMER_INPUT_ATOMS = 256
MAX_CONFORMER_INPUT_BONDS = 512
MAX_CONFORMER_PREPARED_ATOMS = 512
MAX_CONFORMER_PREPARED_BONDS = 2_048
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ConformerPreparationError(ValueError):
    """Conformer preparation failed closed."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ConformerPreparationError(
            "conformer state is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    text = str(value or "").strip().lower()
    if _SHA256_RE.fullmatch(text) is None:
        raise ConformerPreparationError(f"{name} must be a lowercase SHA-256")
    return text


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ConformerPreparationError(
                "prepared-state receipt contains a nonfinite float"
            )
        return value
    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                str(key): _freeze_json(item)
                for key, item in value.items()
            }
        )
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_json(item) for item in value)
    raise ConformerPreparationError(
        "prepared-state receipt is not JSON-compatible"
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _thaw_json(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _load_rdkit():
    try:
        chemistry = importlib.import_module("rdkit.Chem")
        all_chem = importlib.import_module("rdkit.Chem.AllChem")
        rd_base = importlib.import_module("rdkit.rdBase")
    except (ImportError, OSError) as exc:
        raise ConformerPreparationError(
            "RDKit is required for deterministic ETKDG preparation"
        ) from exc
    return chemistry, all_chem, rd_base


def _coordinate_model_sha256(coordinates: torch.Tensor) -> str:
    tensor = coordinates.detach().to(
        dtype=torch.float64,
        device="cpu",
    ).contiguous()
    if tensor.ndim != 2 or tensor.shape[1] != 3:
        raise ConformerPreparationError(
            "conformer coordinates must have shape [N,3]"
        )
    if not bool(torch.isfinite(tensor).all().item()):
        raise ConformerPreparationError(
            "conformer coordinates must be finite"
        )
    return _sha256(
        {
            "shape": [int(tensor.shape[0]), 3],
            "dtype": "float64",
            "rows_binary64_hex": [
                [float(value).hex() for value in row]
                for row in tensor.tolist()
            ],
        }
    )


def _conformer_identity(
    *,
    canonical_smiles: str,
    rdkit_version: str,
    config_projection: Mapping[str, Any],
    source_conformer_index: int,
    energy_model: str,
    energy_kcal_mol: float,
    coordinates_sha256: str,
) -> str:
    return _sha256(
        {
            "policy_id": CONFORMER_PREPARATION_POLICY_ID,
            "canonical_isomeric_smiles": canonical_smiles,
            "rdkit_version": rdkit_version,
            "config": _thaw_json(config_projection),
            "source_conformer_index": source_conformer_index,
            "energy_model": energy_model,
            "energy_kcal_mol_binary64_hex": energy_kcal_mol.hex(),
            "coordinates_sha256": coordinates_sha256,
        }
    )


@dataclass(frozen=True, slots=True)
class ConformerPreparationConfig:
    candidate_count: int = 32
    selected_count: int = 8
    random_seed: int = 0x45544B44
    max_optimization_iterations: int = 500
    energy_window_kcal_mol: float = 20.0
    diversity_rmsd_angstrom: float = 0.5

    def __post_init__(self) -> None:
        for name, minimum, maximum in (
            ("candidate_count", 1, 256),
            ("selected_count", 1, 64),
            ("random_seed", 0, 0x7FFFFFFF),
            ("max_optimization_iterations", 1, 10_000),
        ):
            value = getattr(self, name)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ConformerPreparationError(
                    f"{name} must be an integer in [{minimum},{maximum}]"
                )
        if self.selected_count > self.candidate_count:
            raise ConformerPreparationError(
                "selected_count cannot exceed candidate_count"
            )
        for name, minimum, maximum in (
            ("energy_window_kcal_mol", 0.0, 1_000.0),
            ("diversity_rmsd_angstrom", 0.0, 20.0),
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ConformerPreparationError(
                    f"{name} must be finite in [{minimum},{maximum}]"
                )
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_count": self.candidate_count,
            "selected_count": self.selected_count,
            "random_seed": self.random_seed,
            "max_optimization_iterations": (
                self.max_optimization_iterations
            ),
            "energy_window_kcal_mol_binary64_hex": (
                self.energy_window_kcal_mol.hex()
            ),
            "diversity_rmsd_angstrom_binary64_hex": (
                self.diversity_rmsd_angstrom.hex()
            ),
        }


@dataclass(frozen=True, slots=True)
class PreparedConformerRecord:
    conformer_id: str
    source_conformer_index: int
    energy_kcal_mol: float
    minimum_selected_rmsd_angstrom: float | None
    coordinates_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "conformer_id",
            _digest(self.conformer_id, name="conformer_id"),
        )
        object.__setattr__(
            self,
            "coordinates_sha256",
            _digest(self.coordinates_sha256, name="coordinates_sha256"),
        )
        if (
            type(self.source_conformer_index) is not int
            or self.source_conformer_index < 0
        ):
            raise ConformerPreparationError(
                "source_conformer_index must be a nonnegative integer"
            )
        energy = float(self.energy_kcal_mol)
        if not math.isfinite(energy):
            raise ConformerPreparationError("conformer energy must be finite")
        rmsd = self.minimum_selected_rmsd_angstrom
        if rmsd is not None:
            rmsd = float(rmsd)
            if not math.isfinite(rmsd) or rmsd < 0.0:
                raise ConformerPreparationError(
                    "minimum selected RMSD must be finite and nonnegative"
                )
        object.__setattr__(self, "energy_kcal_mol", energy)
        object.__setattr__(self, "minimum_selected_rmsd_angstrom", rmsd)

    def to_dict(self) -> dict[str, object]:
        return {
            "conformer_id": self.conformer_id,
            "source_conformer_index": self.source_conformer_index,
            "energy_kcal_mol_binary64_hex": self.energy_kcal_mol.hex(),
            "minimum_selected_rmsd_angstrom_binary64_hex": (
                None
                if self.minimum_selected_rmsd_angstrom is None
                else self.minimum_selected_rmsd_angstrom.hex()
            ),
            "coordinates_sha256": self.coordinates_sha256,
        }


@dataclass(frozen=True, slots=True)
class PreparedConformerEnsemble:
    system: AllAtomSystem
    records: tuple[PreparedConformerRecord, ...]
    receipt: Mapping[str, Any]
    receipt_sha256: str

    def _verify_records(
        self,
        receipt: Mapping[str, Any],
        records: tuple[PreparedConformerRecord, ...],
    ) -> None:
        projections = [row.to_dict() for row in records]
        if receipt.get("selected_conformer_records") != projections:
            raise ConformerPreparationError(
                "prepared conformer records are cross-wired"
            )
        optimization_rows = receipt.get("optimization_rows")
        if not isinstance(optimization_rows, list):
            raise ConformerPreparationError(
                "optimization rows are missing from the receipt"
            )
        optimization_by_source = {
            int(row["source_conformer_index"]): row
            for row in optimization_rows
            if isinstance(row, dict)
        }
        heavy_indices = tuple(
            atom.index
            for atom in self.system.atoms
            if atom.atomic_number > 1
        )
        for model_index, record in enumerate(records):
            observed_coordinates_sha256 = _coordinate_model_sha256(
                self.system.coordinates[model_index]
            )
            if observed_coordinates_sha256 != record.coordinates_sha256:
                raise ConformerPreparationError(
                    "conformer record coordinates are cross-wired"
                )
            optimization = optimization_by_source.get(
                record.source_conformer_index
            )
            if (
                optimization is None
                or optimization.get("energy_kcal_mol_binary64_hex")
                != record.energy_kcal_mol.hex()
                or optimization.get("admitted_to_energy_filter") is not True
            ):
                raise ConformerPreparationError(
                    "conformer record energy is cross-wired"
                )
            expected_id = _conformer_identity(
                canonical_smiles=str(
                    receipt.get("canonical_isomeric_smiles") or ""
                ),
                rdkit_version=str(receipt.get("rdkit_version") or ""),
                config_projection=receipt.get("config", {}),
                source_conformer_index=record.source_conformer_index,
                energy_model=str(receipt.get("energy_model") or ""),
                energy_kcal_mol=record.energy_kcal_mol,
                coordinates_sha256=record.coordinates_sha256,
            )
            if record.conformer_id != expected_id:
                raise ConformerPreparationError(
                    "conformer identity is cross-wired"
                )
            rmsds = [
                _heavy_atom_rmsd(
                    self.system.coordinates[model_index],
                    self.system.coordinates[previous],
                    heavy_indices,
                )
                for previous in range(model_index)
            ]
            expected_rmsd = min(rmsds) if rmsds else None
            if expected_rmsd is None:
                if record.minimum_selected_rmsd_angstrom is not None:
                    raise ConformerPreparationError(
                        "first conformer RMSD must be absent"
                    )
            elif (
                record.minimum_selected_rmsd_angstrom is None
                or abs(
                    record.minimum_selected_rmsd_angstrom - expected_rmsd
                )
                > 1.0e-10
            ):
                raise ConformerPreparationError(
                    "conformer diversity RMSD is cross-wired"
                )

    def __post_init__(self) -> None:
        if not isinstance(self.system, AllAtomSystem):
            raise TypeError("system must be AllAtomSystem")
        require_valid_all_atom_system(self.system)
        records = tuple(self.records)
        if any(
            not isinstance(row, PreparedConformerRecord)
            for row in records
        ):
            raise TypeError(
                "records must contain PreparedConformerRecord values"
            )
        if len(records) != self.system.model_count or not records:
            raise ConformerPreparationError(
                "conformer records and coordinate models disagree"
            )
        if len({row.conformer_id for row in records}) != len(records):
            raise ConformerPreparationError("conformer IDs must be unique")
        receipt = _thaw_json(self.receipt)
        digest = _digest(self.receipt_sha256, name="receipt_sha256")
        if _sha256(receipt) != digest:
            raise ConformerPreparationError("prepared-state receipt changed")
        try:
            observed_system_sha256 = canonical_system_sha256(self.system)
        except Exception as exc:
            raise ConformerPreparationError(
                "prepared system changed after preparation"
            ) from exc
        if receipt.get("prepared_system_sha256") != observed_system_sha256:
            raise ConformerPreparationError(
                "prepared-state receipt is cross-wired"
            )
        if receipt.get("selected_conformer_ids") != [
            row.conformer_id for row in records
        ]:
            raise ConformerPreparationError(
                "prepared conformer identities are cross-wired"
            )
        self._verify_records(receipt, records)
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "receipt", _freeze_json(receipt))
        object.__setattr__(self, "receipt_sha256", digest)

    def _verified_receipt(self) -> dict[str, Any]:
        receipt = _thaw_json(self.receipt)
        if _sha256(receipt) != self.receipt_sha256:
            raise ConformerPreparationError("prepared-state receipt changed")
        try:
            observed_system_sha256 = canonical_system_sha256(self.system)
        except Exception as exc:
            raise ConformerPreparationError(
                "prepared system changed after preparation"
            ) from exc
        if receipt.get("prepared_system_sha256") != observed_system_sha256:
            raise ConformerPreparationError(
                "prepared system changed after preparation"
            )
        if receipt.get("selected_conformer_ids") != [
            row.conformer_id for row in self.records
        ]:
            raise ConformerPreparationError(
                "prepared conformer identities changed after preparation"
            )
        self._verify_records(receipt, self.records)
        return receipt

    def to_dict(self) -> dict[str, object]:
        return {
            **self._verified_receipt(),
            "receipt_sha256": self.receipt_sha256,
            "conformers": [row.to_dict() for row in self.records],
        }


def _heavy_atom_rmsd(
    first: torch.Tensor,
    second: torch.Tensor,
    heavy_atom_indices: tuple[int, ...],
) -> float:
    left = first[list(heavy_atom_indices)].to(dtype=torch.float64)
    right = second[list(heavy_atom_indices)].to(dtype=torch.float64)
    left = left - left.mean(dim=0)
    right = right - right.mean(dim=0)
    covariance = left.T @ right
    u, _, vh = torch.linalg.svd(covariance)
    correction = torch.eye(3, dtype=torch.float64)
    if float(torch.linalg.det(u @ vh).item()) < 0.0:
        correction[-1, -1] = -1.0
    rotation = u @ correction @ vh
    aligned = left @ rotation
    return float(
        torch.sqrt(torch.mean(torch.sum((aligned - right) ** 2, dim=1))).item()
    )


def _coordinates(molecule: Any, conformer_id: int) -> torch.Tensor:
    conformer = molecule.GetConformer(int(conformer_id))
    return torch.tensor(
        [
            [
                float(conformer.GetAtomPosition(index).x),
                float(conformer.GetAtomPosition(index).y),
                float(conformer.GetAtomPosition(index).z),
            ]
            for index in range(molecule.GetNumAtoms())
        ],
        dtype=torch.float64,
    )


def _system_from_rdkit(
    molecule: Any,
    *,
    canonical_smiles: str,
    coordinates: torch.Tensor,
    conformer_ids: tuple[str, ...],
    rdkit_version: str,
) -> AllAtomSystem:
    atoms = []
    for atom in molecule.GetAtoms():
        stereo = (
            str(atom.GetProp("_CIPCode"))
            if atom.HasProp("_CIPCode")
            else "unspecified"
        )
        atoms.append(
            Atom(
                index=int(atom.GetIdx()),
                name=f"{atom.GetSymbol()}{atom.GetIdx() + 1}",
                element=str(atom.GetSymbol()),
                atomic_number=int(atom.GetAtomicNum()),
                residue_index=0,
                formal_charge=int(atom.GetFormalCharge()),
                isotope_mass_number=(
                    int(atom.GetIsotope()) or None
                ),
                aromatic=bool(atom.GetIsAromatic()),
                stereo=stereo,
            )
        )
    stereo_labels = {
        "STEREONONE": "none",
        "STEREOANY": "either",
        "STEREOE": "E",
        "STEREOZ": "Z",
        "STEREOCIS": "cis",
        "STEREOTRANS": "trans",
    }
    bonds = []
    for index, bond in enumerate(molecule.GetBonds()):
        first, second = sorted(
            (int(bond.GetBeginAtomIdx()), int(bond.GetEndAtomIdx()))
        )
        bonds.append(
            Bond(
                index=index,
                atom_i=first,
                atom_j=second,
                order=float(bond.GetBondTypeAsDouble()),
                aromatic=bool(bond.GetIsAromatic()),
                stereo=stereo_labels.get(str(bond.GetStereo()), "unknown"),
                source="rdkit_etkdgv3",
            )
        )
    source_sha256 = hashlib.sha256(
        canonical_smiles.encode("utf-8")
    ).hexdigest()
    atom_indices = tuple(range(len(atoms)))
    return AllAtomSystem(
        system_id=f"prepared-ligand-{source_sha256[:16]}",
        atoms=tuple(atoms),
        bonds=tuple(bonds),
        residues=(
            Residue(
                index=0,
                name="LIG",
                chain_index=0,
                sequence_number=1,
                atom_indices=atom_indices,
                entity_type="non-polymer",
                hetero=True,
            ),
        ),
        chains=(Chain(index=0, chain_id="L", residue_indices=(0,)),),
        coordinates=coordinates.contiguous(),
        provenance=StructureProvenance(
            source_format="smiles",
            source_id=canonical_smiles,
            source_sha256=source_sha256,
            parser_name="rdkit_etkdgv3_conformer_preparation",
            parser_version=rdkit_version,
            operations=(
                "add_explicit_hydrogens",
                "deterministic_etkdgv3_embedding",
                "force_field_optimization",
                "energy_window_filter",
                "heavy_atom_rmsd_diversity_filter",
            ),
            source_digest_verified=True,
            transformation_chain_verified=True,
            chemistry_validated=False,
            metadata={
                "canonical_isomeric_smiles": canonical_smiles,
                "conformer_ids": list(conformer_ids),
            },
        ),
        metadata={
            "prepared_conformer_ids": list(conformer_ids),
            "scientifically_validated": False,
            "claim_safe": False,
        },
    )


def prepare_deterministic_conformer_ensemble(
    smiles: str,
    *,
    config: ConformerPreparationConfig | None = None,
) -> PreparedConformerEnsemble:
    """Prepare a deterministic ETKDG ensemble with exact provenance."""

    settings = config or ConformerPreparationConfig()
    if not isinstance(settings, ConformerPreparationConfig):
        raise TypeError("config must be ConformerPreparationConfig")
    raw_smiles = str(smiles or "").strip()
    if not raw_smiles or len(raw_smiles) > 16_384:
        raise ConformerPreparationError("SMILES input is empty or too large")
    chemistry, all_chem, rd_base = _load_rdkit()
    molecule = chemistry.MolFromSmiles(raw_smiles)
    if molecule is None:
        raise ConformerPreparationError("SMILES parsing failed")
    input_atom_count = int(molecule.GetNumAtoms())
    input_bond_count = int(molecule.GetNumBonds())
    if input_atom_count > MAX_CONFORMER_INPUT_ATOMS:
        raise ConformerPreparationError(
            "ligand atom count exceeds the conformer preparation bound"
        )
    if input_bond_count > MAX_CONFORMER_INPUT_BONDS:
        raise ConformerPreparationError(
            "ligand bond count exceeds the conformer preparation bound"
        )
    if len(chemistry.GetMolFrags(molecule)) != 1:
        raise ConformerPreparationError(
            "conformer preparation requires one connected ligand component"
        )
    canonical_smiles = chemistry.MolToSmiles(
        molecule,
        canonical=True,
        isomericSmiles=True,
    )
    molecule = chemistry.MolFromSmiles(canonical_smiles)
    if molecule is None:
        raise ConformerPreparationError(
            "canonical SMILES reconstruction failed"
        )
    unspecified_stereo = [
        row
        for row in chemistry.FindPotentialStereo(
            molecule,
            cleanIt=True,
            flagPossible=True,
        )
        if str(row.specified) != "Specified"
    ]
    if unspecified_stereo:
        raise ConformerPreparationError(
            "potential ligand stereochemistry must be explicitly assigned"
        )
    molecule = chemistry.AddHs(molecule)
    prepared_atom_count = int(molecule.GetNumAtoms())
    prepared_bond_count = int(molecule.GetNumBonds())
    if prepared_atom_count > MAX_CONFORMER_PREPARED_ATOMS:
        raise ConformerPreparationError(
            "hydrogen-expanded atom count exceeds the preparation bound"
        )
    if prepared_bond_count > MAX_CONFORMER_PREPARED_BONDS:
        raise ConformerPreparationError(
            "hydrogen-expanded bond count exceeds the preparation bound"
        )
    chemistry.AssignStereochemistry(
        molecule,
        cleanIt=True,
        force=True,
    )
    ring_info = molecule.GetRingInfo()
    ring_atoms: set[int] = set()
    ring_adjacency: dict[int, set[int]] = {}
    for ring in ring_info.AtomRings():
        ring_atoms.update(int(value) for value in ring)
        for offset, atom_index in enumerate(ring):
            neighbor = ring[(offset + 1) % len(ring)]
            ring_adjacency.setdefault(int(atom_index), set()).add(int(neighbor))
            ring_adjacency.setdefault(int(neighbor), set()).add(int(atom_index))
    remaining = set(ring_atoms)
    while remaining:
        root = min(remaining)
        component = {root}
        frontier = [root]
        while frontier:
            node = frontier.pop()
            for neighbor in ring_adjacency.get(node, set()):
                if neighbor not in component:
                    component.add(neighbor)
                    frontier.append(neighbor)
        if len(component) >= 12:
            raise ConformerPreparationError(
                "macrocycle and ambiguous large ring systems are unsupported"
            )
        remaining -= component

    parameters = all_chem.ETKDGv3()
    parameters.randomSeed = settings.random_seed
    parameters.numThreads = 1
    parameters.pruneRmsThresh = -1.0
    parameters.enforceChirality = True
    parameters.useRandomCoords = False
    parameters.useSmallRingTorsions = True
    parameters.useMacrocycleTorsions = False
    embedded_ids = tuple(
        int(value)
        for value in all_chem.EmbedMultipleConfs(
            molecule,
            numConfs=settings.candidate_count,
            params=parameters,
        )
    )
    if not embedded_ids:
        raise ConformerPreparationError("ETKDG produced no conformers")

    if all_chem.MMFFHasAllMoleculeParams(molecule):
        energy_model = "MMFF94"
        optimized = all_chem.MMFFOptimizeMoleculeConfs(
            molecule,
            numThreads=1,
            maxIters=settings.max_optimization_iterations,
            mmffVariant="MMFF94",
        )
    elif all_chem.UFFHasAllMoleculeParams(molecule):
        energy_model = "UFF"
        optimized = all_chem.UFFOptimizeMoleculeConfs(
            molecule,
            numThreads=1,
            maxIters=settings.max_optimization_iterations,
        )
    else:
        raise ConformerPreparationError(
            "no supported conformer energy model covers this ligand"
        )
    if len(optimized) != len(embedded_ids):
        raise ConformerPreparationError(
            "energy rows do not cover embedded conformers"
        )
    optimization_rows = []
    candidate_rows = []
    for source_id, result in zip(embedded_ids, optimized):
        status, energy = int(result[0]), float(result[1])
        optimization_rows.append((source_id, status, energy))
        if status not in {0, 1} or not math.isfinite(energy):
            continue
        candidate_rows.append(
            (source_id, status, energy, _coordinates(molecule, source_id))
        )
    if not candidate_rows:
        raise ConformerPreparationError(
            "all conformer energy evaluations failed"
        )
    candidate_rows.sort(key=lambda row: (row[2], row[0]))
    minimum_energy = candidate_rows[0][2]
    energy_filtered = [
        row
        for row in candidate_rows
        if row[2] <= minimum_energy + settings.energy_window_kcal_mol
    ]
    heavy_indices = tuple(
        int(atom.GetIdx())
        for atom in molecule.GetAtoms()
        if int(atom.GetAtomicNum()) > 1
    )
    if not heavy_indices:
        raise ConformerPreparationError("ligand has no heavy atoms")
    selected: list[tuple[int, int, float, torch.Tensor, float | None]] = []
    for source_id, status, energy, coordinates in energy_filtered:
        rmsds = [
            _heavy_atom_rmsd(coordinates, row[3], heavy_indices)
            for row in selected
        ]
        minimum_rmsd = min(rmsds) if rmsds else None
        if (
            minimum_rmsd is not None
            and minimum_rmsd + 1.0e-12
            < settings.diversity_rmsd_angstrom
        ):
            continue
        selected.append(
            (source_id, status, energy, coordinates, minimum_rmsd)
        )
        if len(selected) >= settings.selected_count:
            break
    if not selected:
        raise ConformerPreparationError(
            "energy and diversity filters removed every conformer"
        )
    config_projection = settings.to_dict()
    records = []
    conformer_ids = []
    for source_id, _, energy, coordinates, minimum_rmsd in selected:
        coordinates_sha256 = _coordinate_model_sha256(coordinates)
        conformer_id = _conformer_identity(
            canonical_smiles=canonical_smiles,
            rdkit_version=str(rd_base.rdkitVersion),
            config_projection=config_projection,
            source_conformer_index=source_id,
            energy_model=energy_model,
            energy_kcal_mol=energy,
            coordinates_sha256=coordinates_sha256,
        )
        conformer_ids.append(conformer_id)
        records.append(
            PreparedConformerRecord(
                conformer_id=conformer_id,
                source_conformer_index=source_id,
                energy_kcal_mol=energy,
                minimum_selected_rmsd_angstrom=minimum_rmsd,
                coordinates_sha256=coordinates_sha256,
            )
        )
    system = _system_from_rdkit(
        molecule,
        canonical_smiles=canonical_smiles,
        coordinates=torch.stack([row[3] for row in selected]),
        conformer_ids=tuple(conformer_ids),
        rdkit_version=str(rd_base.rdkitVersion),
    )
    require_valid_all_atom_system(system)
    receipt = {
        "schema_id": CONFORMER_ENSEMBLE_SCHEMA_ID,
        "policy_id": CONFORMER_PREPARATION_POLICY_ID,
        "canonical_isomeric_smiles": canonical_smiles,
        "input_smiles_sha256": hashlib.sha256(
            raw_smiles.encode("utf-8")
        ).hexdigest(),
        "input_atom_count": input_atom_count,
        "input_bond_count": input_bond_count,
        "prepared_atom_count": prepared_atom_count,
        "prepared_bond_count": prepared_bond_count,
        "preparation_bounds": {
            "maximum_input_atoms": MAX_CONFORMER_INPUT_ATOMS,
            "maximum_input_bonds": MAX_CONFORMER_INPUT_BONDS,
            "maximum_prepared_atoms": MAX_CONFORMER_PREPARED_ATOMS,
            "maximum_prepared_bonds": MAX_CONFORMER_PREPARED_BONDS,
        },
        "connected_component_policy": "exactly_one",
        "unspecified_potential_stereochemistry_allowed": False,
        "rdkit_version": str(rd_base.rdkitVersion),
        "etkdg_variant": "ETKDGv3",
        "energy_model": energy_model,
        "energy_optimization_status_zero_means_converged": True,
        "energy_optimization_status_one_admitted_as_iteration_limited": True,
        "diversity_metric": "heavy_atom_kabsch_rmsd",
        "diversity_symmetry_aware": False,
        "config": config_projection,
        "requested_candidate_count": settings.candidate_count,
        "embedded_candidate_count": len(embedded_ids),
        "energy_evaluated_count": len(candidate_rows),
        "energy_window_survivor_count": len(energy_filtered),
        "selected_conformer_count": len(records),
        "selected_conformer_ids": conformer_ids,
        "selected_conformer_records": [
            row.to_dict() for row in records
        ],
        "optimization_rows": [
            {
                "source_conformer_index": source_id,
                "status": status,
                "energy_kcal_mol_binary64_hex": (
                    energy.hex() if math.isfinite(energy) else None
                ),
                "admitted_to_energy_filter": (
                    status in {0, 1} and math.isfinite(energy)
                ),
            }
            for source_id, status, energy in optimization_rows
        ],
        "prepared_system_sha256": canonical_system_sha256(system),
        "prepared_coordinates_sha256": canonical_coordinates_sha256(system),
        "deterministic": True,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return PreparedConformerEnsemble(
        system=system,
        records=tuple(records),
        receipt=receipt,
        receipt_sha256=_sha256(receipt),
    )


__all__ = [
    "CONFORMER_ENSEMBLE_SCHEMA_ID",
    "CONFORMER_PREPARATION_POLICY_ID",
    "ConformerPreparationConfig",
    "ConformerPreparationError",
    "PreparedConformerEnsemble",
    "PreparedConformerRecord",
    "prepare_deterministic_conformer_ensemble",
]
