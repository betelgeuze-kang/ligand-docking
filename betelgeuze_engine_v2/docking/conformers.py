"""Deterministic, failure-closed ligand conformer preparation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from collections.abc import Mapping
import hashlib
import importlib
import json
import math
import re
from types import MappingProxyType
from typing import Any

import torch

from betelgeuze_engine_v2.io import (
    SDF_PARSER_NAME,
    SDF_PARSER_VERSION,
    parse_sdf_v2000,
)
from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    canonical_coordinates_sha256,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
)


CONFORMER_ENSEMBLE_SCHEMA_ID = "betelgeuze.engine_v2_prepared_conformer_ensemble/1.0.0"
CONFORMER_PREPARATION_POLICY_ID = (
    "betelgeuze.engine_v2_deterministic_etkdgv3_energy_rmsd/1.0.0"
)
SOURCE_BOUND_CONFORMER_ENSEMBLE_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_bound_prepared_conformer_ensemble/1.2.0"
)
SOURCE_BOUND_CONFORMER_DERIVATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_bound_conformer_derivation/1.2.0"
)
SOURCE_BOUND_CONFORMER_PREPARATION_POLICY_ID = (
    "betelgeuze.engine_v2_source_bound_deterministic_etkdgv3_energy_rmsd/1.2.0"
)
SOURCE_BOUND_CONFORMER_SOURCE_INDEX_MAPPING_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_bound_rdkit_source_index_mapping/1.0.0"
)
MAX_CONFORMER_INPUT_ATOMS = 256
MAX_CONFORMER_INPUT_BONDS = 512
MAX_CONFORMER_PREPARED_ATOMS = 512
MAX_CONFORMER_PREPARED_BONDS = 2_048
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_ATOM_INDEX_PROPERTY = "_BetelgeuzeSourceAtomIndex"


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
            {str(key): _freeze_json(item) for key, item in value.items()}
        )
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_json(item) for item in value)
    raise ConformerPreparationError("prepared-state receipt is not JSON-compatible")


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
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
    tensor = (
        coordinates.detach()
        .to(
            dtype=torch.float64,
            device="cpu",
        )
        .contiguous()
    )
    if tensor.ndim != 2 or tensor.shape[1] != 3:
        raise ConformerPreparationError("conformer coordinates must have shape [N,3]")
    if not bool(torch.isfinite(tensor).all().item()):
        raise ConformerPreparationError("conformer coordinates must be finite")
    return _sha256(
        {
            "shape": [int(tensor.shape[0]), 3],
            "dtype": "float64",
            "rows_binary64_hex": [
                [float(value).hex() for value in row] for row in tensor.tolist()
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


def _source_bound_conformer_identity(
    *,
    source_system_sha256: str,
    source_artifact_sha256: str,
    canonical_smiles: str,
    rdkit_version: str,
    config_projection: Mapping[str, Any],
    source_conformer_index: int,
    energy_model: str,
    energy_kcal_mol: float,
    raw_coordinates_sha256: str,
    coordinates_sha256: str,
) -> str:
    return _sha256(
        {
            "policy_id": SOURCE_BOUND_CONFORMER_PREPARATION_POLICY_ID,
            "source_system_sha256": source_system_sha256,
            "source_artifact_sha256": source_artifact_sha256,
            "canonical_isomeric_smiles": canonical_smiles,
            "rdkit_version": rdkit_version,
            "config": _thaw_json(config_projection),
            "source_conformer_index": source_conformer_index,
            "energy_model": energy_model,
            "energy_kcal_mol_binary64_hex": energy_kcal_mol.hex(),
            "raw_coordinates_sha256": raw_coordinates_sha256,
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
            "max_optimization_iterations": (self.max_optimization_iterations),
            "energy_window_kcal_mol_binary64_hex": (self.energy_window_kcal_mol.hex()),
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
            atom.index for atom in self.system.atoms if atom.atomic_number > 1
        )
        for model_index, record in enumerate(records):
            observed_coordinates_sha256 = _coordinate_model_sha256(
                self.system.coordinates[model_index]
            )
            if observed_coordinates_sha256 != record.coordinates_sha256:
                raise ConformerPreparationError(
                    "conformer record coordinates are cross-wired"
                )
            optimization = optimization_by_source.get(record.source_conformer_index)
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
                canonical_smiles=str(receipt.get("canonical_isomeric_smiles") or ""),
                rdkit_version=str(receipt.get("rdkit_version") or ""),
                config_projection=receipt.get("config", {}),
                source_conformer_index=record.source_conformer_index,
                energy_model=str(receipt.get("energy_model") or ""),
                energy_kcal_mol=record.energy_kcal_mol,
                coordinates_sha256=record.coordinates_sha256,
            )
            if record.conformer_id != expected_id:
                raise ConformerPreparationError("conformer identity is cross-wired")
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
                or abs(record.minimum_selected_rmsd_angstrom - expected_rmsd) > 1.0e-10
            ):
                raise ConformerPreparationError(
                    "conformer diversity RMSD is cross-wired"
                )

    def __post_init__(self) -> None:
        if not isinstance(self.system, AllAtomSystem):
            raise TypeError("system must be AllAtomSystem")
        require_valid_all_atom_system(self.system)
        records = tuple(self.records)
        if any(not isinstance(row, PreparedConformerRecord) for row in records):
            raise TypeError("records must contain PreparedConformerRecord values")
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
            raise ConformerPreparationError("prepared-state receipt is cross-wired")
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
            raise ConformerPreparationError("prepared system changed after preparation")
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


@dataclass(frozen=True, slots=True)
class SourceBoundPreparedConformerRecord:
    conformer_id: str
    source_conformer_index: int
    energy_kcal_mol: float
    minimum_selected_rmsd_angstrom: float | None
    source_pose_rmsd_angstrom: float
    raw_coordinates_sha256: str
    coordinates_sha256: str
    alignment_rotation: tuple[tuple[float, float, float], ...]
    alignment_translation: tuple[float, float, float]

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
        object.__setattr__(
            self,
            "raw_coordinates_sha256",
            _digest(
                self.raw_coordinates_sha256,
                name="raw_coordinates_sha256",
            ),
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
        selected_rmsd = self.minimum_selected_rmsd_angstrom
        if selected_rmsd is not None:
            selected_rmsd = float(selected_rmsd)
            if not math.isfinite(selected_rmsd) or selected_rmsd < 0.0:
                raise ConformerPreparationError(
                    "minimum selected RMSD must be finite and nonnegative"
                )
        source_rmsd = float(self.source_pose_rmsd_angstrom)
        if not math.isfinite(source_rmsd) or source_rmsd < 0.0:
            raise ConformerPreparationError(
                "source-pose RMSD must be finite and nonnegative"
            )
        object.__setattr__(self, "energy_kcal_mol", energy)
        object.__setattr__(
            self,
            "minimum_selected_rmsd_angstrom",
            selected_rmsd,
        )
        object.__setattr__(
            self,
            "source_pose_rmsd_angstrom",
            source_rmsd,
        )
        try:
            rotation = tuple(
                tuple(float(value) for value in row) for row in self.alignment_rotation
            )
            translation = tuple(float(value) for value in self.alignment_translation)
        except (TypeError, ValueError) as exc:
            raise ConformerPreparationError(
                "source-bound alignment transform is invalid"
            ) from exc
        if (
            len(rotation) != 3
            or any(len(row) != 3 for row in rotation)
            or len(translation) != 3
            or any(not math.isfinite(value) for row in rotation for value in row)
            or any(not math.isfinite(value) for value in translation)
        ):
            raise ConformerPreparationError(
                "source-bound alignment transform must be finite 3D data"
            )
        rotation_tensor = torch.tensor(rotation, dtype=torch.float64)
        determinant = float(torch.linalg.det(rotation_tensor).item())
        if abs(determinant - 1.0) > 1.0e-10 or not bool(
            torch.allclose(
                rotation_tensor.T @ rotation_tensor,
                torch.eye(3, dtype=torch.float64),
                atol=1.0e-10,
                rtol=0.0,
            )
        ):
            raise ConformerPreparationError(
                "source-bound alignment must use a proper rotation"
            )
        object.__setattr__(self, "alignment_rotation", rotation)
        object.__setattr__(self, "alignment_translation", translation)

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
            "source_pose_rmsd_angstrom_binary64_hex": (
                self.source_pose_rmsd_angstrom.hex()
            ),
            "raw_coordinates_sha256": self.raw_coordinates_sha256,
            "coordinates_sha256": self.coordinates_sha256,
            "alignment_rotation_rows_binary64_hex": [
                [value.hex() for value in row] for row in self.alignment_rotation
            ],
            "alignment_translation_binary64_hex": [
                value.hex() for value in self.alignment_translation
            ],
        }


@dataclass(frozen=True, slots=True)
class SourceBoundPreparedConformerEnsemble:
    source_system: AllAtomSystem
    source_sdf: bytes = field(repr=False)
    system: AllAtomSystem
    raw_coordinates: torch.Tensor
    records: tuple[SourceBoundPreparedConformerRecord, ...]
    receipt: Mapping[str, Any]
    receipt_sha256: str

    def _verify_records(
        self,
        receipt: Mapping[str, Any],
        records: tuple[SourceBoundPreparedConformerRecord, ...],
    ) -> None:
        derivation = receipt.get("derivation_evidence")
        if not isinstance(derivation, dict):
            raise ConformerPreparationError(
                "source-bound derivation evidence is missing"
            )
        if derivation.get("selected_conformer_records") != [
            row.to_dict() for row in records
        ]:
            raise ConformerPreparationError(
                "source-bound conformer records are cross-wired"
            )
        optimization_rows = derivation.get("optimization_rows")
        if not isinstance(optimization_rows, list):
            raise ConformerPreparationError(
                "optimization rows are missing from the source-bound receipt"
            )
        try:
            optimization_by_source = {
                int(row["source_conformer_index"]): row
                for row in optimization_rows
                if isinstance(row, dict)
            }
            config_projection = derivation["config"]
            diversity_threshold = float.fromhex(
                str(config_projection["diversity_rmsd_angstrom_binary64_hex"])
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ConformerPreparationError(
                "source-bound conformer receipt is incomplete"
            ) from exc
        heavy_indices = tuple(
            atom.index for atom in self.source_system.atoms if atom.atomic_number > 1
        )
        if not heavy_indices:
            raise ConformerPreparationError("source ligand has no heavy atoms")
        source_coordinates = self.source_system.coordinates[0]
        for model_index, record in enumerate(records):
            coordinates = self.system.coordinates[model_index]
            raw_coordinates = self.raw_coordinates[model_index]
            if (
                _coordinate_model_sha256(coordinates) != record.coordinates_sha256
                or _coordinate_model_sha256(raw_coordinates)
                != record.raw_coordinates_sha256
            ):
                raise ConformerPreparationError(
                    "source-bound conformer coordinates are cross-wired"
                )
            rotation = torch.tensor(
                record.alignment_rotation,
                dtype=torch.float64,
            )
            translation = torch.tensor(
                record.alignment_translation,
                dtype=torch.float64,
            )
            reconstructed = raw_coordinates @ rotation + translation
            if not bool(
                torch.allclose(
                    reconstructed,
                    coordinates,
                    atol=1.0e-12,
                    rtol=0.0,
                )
            ):
                raise ConformerPreparationError(
                    "source-bound alignment transform is cross-wired"
                )
            optimization = optimization_by_source.get(record.source_conformer_index)
            if (
                optimization is None
                or optimization.get("energy_kcal_mol_binary64_hex")
                != record.energy_kcal_mol.hex()
                or optimization.get("admitted_to_energy_filter") is not True
            ):
                raise ConformerPreparationError(
                    "source-bound conformer energy is cross-wired"
                )
            expected_id = _source_bound_conformer_identity(
                source_system_sha256=str(derivation.get("source_system_sha256") or ""),
                source_artifact_sha256=str(
                    derivation.get("source_artifact_sha256") or ""
                ),
                canonical_smiles=str(derivation.get("canonical_isomeric_smiles") or ""),
                rdkit_version=str(derivation.get("rdkit_version") or ""),
                config_projection=config_projection,
                source_conformer_index=record.source_conformer_index,
                energy_model=str(derivation.get("energy_model") or ""),
                energy_kcal_mol=record.energy_kcal_mol,
                raw_coordinates_sha256=record.raw_coordinates_sha256,
                coordinates_sha256=record.coordinates_sha256,
            )
            if record.conformer_id != expected_id:
                raise ConformerPreparationError(
                    "source-bound conformer identity is cross-wired"
                )
            source_rmsd = _heavy_atom_rmsd(
                coordinates,
                source_coordinates,
                heavy_indices,
            )
            if abs(record.source_pose_rmsd_angstrom - source_rmsd) > 1.0e-10:
                raise ConformerPreparationError(
                    "source-pose diversity RMSD is cross-wired"
                )
            if source_rmsd + 1.0e-12 < diversity_threshold:
                raise ConformerPreparationError(
                    "source-bound conformer is not distinct from the source pose"
                )
            selected_rmsds = [
                _heavy_atom_rmsd(
                    coordinates,
                    self.system.coordinates[previous],
                    heavy_indices,
                )
                for previous in range(model_index)
            ]
            expected_selected_rmsd = min(selected_rmsds) if selected_rmsds else None
            if expected_selected_rmsd is None:
                if record.minimum_selected_rmsd_angstrom is not None:
                    raise ConformerPreparationError(
                        "first source-bound conformer RMSD must be absent"
                    )
            elif (
                record.minimum_selected_rmsd_angstrom is None
                or abs(record.minimum_selected_rmsd_angstrom - expected_selected_rmsd)
                > 1.0e-10
            ):
                raise ConformerPreparationError(
                    "source-bound conformer diversity RMSD is cross-wired"
                )
            if (
                expected_selected_rmsd is not None
                and expected_selected_rmsd + 1.0e-12 < diversity_threshold
            ):
                raise ConformerPreparationError(
                    "source-bound conformer diversity policy was bypassed"
                )

    def _verify_state(
        self,
        receipt: Mapping[str, Any],
        records: tuple[SourceBoundPreparedConformerRecord, ...],
        digest: str,
    ) -> None:
        if _sha256(receipt) != digest:
            raise ConformerPreparationError(
                "source-bound prepared-state receipt changed"
            )
        if (
            receipt.get("schema_id") != SOURCE_BOUND_CONFORMER_ENSEMBLE_SCHEMA_ID
            or receipt.get("policy_id") != SOURCE_BOUND_CONFORMER_PREPARATION_POLICY_ID
        ):
            raise ConformerPreparationError(
                "source-bound prepared-state policy is invalid"
            )
        derivation = receipt.get("derivation_evidence")
        if not isinstance(derivation, dict):
            raise ConformerPreparationError(
                "source-bound derivation evidence is missing"
            )
        derivation_sha256 = _digest(
            receipt.get("derivation_evidence_sha256"),
            name="derivation_evidence_sha256",
        )
        if _sha256(derivation) != derivation_sha256:
            raise ConformerPreparationError("source-bound derivation evidence changed")
        if derivation_sha256 == digest:
            raise ConformerPreparationError(
                "derivation evidence and final receipt must use separate hashes"
            )
        if (
            derivation.get("schema_id") != SOURCE_BOUND_CONFORMER_DERIVATION_SCHEMA_ID
            or derivation.get("policy_id")
            != SOURCE_BOUND_CONFORMER_PREPARATION_POLICY_ID
        ):
            raise ConformerPreparationError("source-bound derivation policy is invalid")
        for projection_name in (
            "source_raw_rdkit_projection",
            "source_text_projection",
            "source_stereo_projection",
        ):
            projection = derivation.get(projection_name)
            if not isinstance(projection, dict) or derivation.get(
                f"{projection_name}_sha256"
            ) != _sha256(projection):
                raise ConformerPreparationError(
                    "source-bound RDKit projection is cross-wired"
                )
        if not isinstance(self.source_sdf, bytes):
            raise ConformerPreparationError(
                "source-bound source SDF authority must be exact bytes"
            )
        source_artifact_sha256 = hashlib.sha256(self.source_sdf).hexdigest()
        if (
            not self.source_system.provenance.source_digest_verified
            or self.source_system.provenance.source_sha256
            != source_artifact_sha256
        ):
            raise ConformerPreparationError(
                "source-bound source SDF authority digest is cross-wired"
            )
        try:
            source_text_authority = self.source_sdf.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ConformerPreparationError(
                "source-bound source SDF authority must be UTF-8"
            ) from exc
        source_text_authority_projection = (
            _require_supported_source_molfile_fields(source_text_authority)
        )
        observed_source_text_projection = derivation["source_text_projection"]
        observed_source_text_authority = dict(observed_source_text_projection)
        observed_source_text_authority.pop(
            "rdkit_declared_valence_checks",
            None,
        )
        if observed_source_text_authority != source_text_authority_projection:
            raise ConformerPreparationError(
                "source-bound source SDF atom fields changed from the exact bytes"
            )
        _require_source_text_projection_contract(
            observed_source_text_projection,
            self.source_system,
        )
        source_index_mapping = derivation.get("source_index_mapping")
        source_index_mapping_sha256 = derivation.get(
            "source_index_mapping_sha256"
        )
        identity = list(range(self.source_system.atom_count))
        if (
            not isinstance(source_index_mapping, dict)
            or source_index_mapping_sha256 != _sha256(source_index_mapping)
            or source_index_mapping.get("schema_id")
            != SOURCE_BOUND_CONFORMER_SOURCE_INDEX_MAPPING_SCHEMA_ID
            or source_index_mapping.get("source_index_property")
            != _SOURCE_ATOM_INDEX_PROPERTY
            or source_index_mapping.get("source_atom_count")
            != self.source_system.atom_count
            or source_index_mapping.get(
                "pre_sanitize_source_index_by_rdkit_index"
            )
            != identity
            or source_index_mapping.get(
                "normalized_source_index_by_rdkit_index"
            )
            != identity
            or source_index_mapping.get(
                "raw_source_projection_exact_before_sanitization"
            )
            is not True
            or source_index_mapping.get("post_sanitize_atom_identity_fields")
            != ["atomic_number", "formal_charge", "isotope_mass_number"]
            or source_index_mapping.get("post_sanitize_bond_identity")
            != "exact_source_endpoint_connectivity"
            or source_index_mapping.get(
                "post_sanitize_bond_order_aromaticity_policy"
            )
            != "exact_or_kekule_ring_to_rdkit_aromatic"
            or source_index_mapping.get(
                "source_coordinates_preserved_after_normalization"
            )
            is not True
        ):
            raise ConformerPreparationError(
                "source-bound RDKit source-index mapping is cross-wired"
            )
        post_sanitize_indices = source_index_mapping.get(
            "post_sanitize_source_index_by_rdkit_index"
        )
        if (
            not isinstance(post_sanitize_indices, list)
            or any(type(value) is not int for value in post_sanitize_indices)
            or sorted(post_sanitize_indices) != identity
            or source_index_mapping.get("renumbered_to_source_order")
            is not (post_sanitize_indices != identity)
        ):
            raise ConformerPreparationError(
                "source-bound RDKit source-index mapping is not bijective"
            )
        post_sanitize_bonds = source_index_mapping.get(
            "post_sanitize_bond_projection"
        )
        if (
            not isinstance(post_sanitize_bonds, list)
            or source_index_mapping.get(
                "post_sanitize_bond_projection_sha256"
            )
            != _sha256(post_sanitize_bonds)
            or len(post_sanitize_bonds) != len(self.source_system.bonds)
        ):
            raise ConformerPreparationError(
                "source-bound post-sanitize bond projection is cross-wired"
            )
        source_bonds = {
            (bond.atom_i, bond.atom_j): bond for bond in self.source_system.bonds
        }
        observed_bonds: list[tuple[int, int]] = []
        for row in post_sanitize_bonds:
            if not isinstance(row, dict):
                raise ConformerPreparationError(
                    "source-bound post-sanitize bond projection is invalid"
                )
            source_atom_i = row.get("source_atom_i")
            source_atom_j = row.get("source_atom_j")
            if (
                type(source_atom_i) is not int
                or type(source_atom_j) is not int
                or source_atom_i >= source_atom_j
            ):
                raise ConformerPreparationError(
                    "source-bound post-sanitize bond endpoints are invalid"
                )
            endpoints = (source_atom_i, source_atom_j)
            source_bond = source_bonds.get(endpoints)
            if source_bond is None:
                raise ConformerPreparationError(
                    "source-bound post-sanitize bond connectivity is cross-wired"
                )
            try:
                rdkit_order = float.fromhex(
                    str(row.get("rdkit_order_binary64_hex") or "")
                )
            except (OverflowError, ValueError) as exc:
                raise ConformerPreparationError(
                    "source-bound post-sanitize bond order is invalid"
                ) from exc
            rdkit_aromatic = row.get("rdkit_aromatic")
            rdkit_conjugated = row.get("rdkit_conjugated")
            rdkit_in_ring = row.get("rdkit_in_ring")
            endpoint_atoms_aromatic = row.get(
                "rdkit_endpoint_atoms_aromatic"
            )
            equivalence = row.get("equivalence")
            if (
                row.get("source_order_binary64_hex") != source_bond.order.hex()
                or row.get("source_aromatic") is not source_bond.aromatic
                or not math.isfinite(rdkit_order)
                or type(rdkit_aromatic) is not bool
                or type(rdkit_conjugated) is not bool
                or type(rdkit_in_ring) is not bool
                or not isinstance(endpoint_atoms_aromatic, list)
                or len(endpoint_atoms_aromatic) != 2
                or any(type(value) is not bool for value in endpoint_atoms_aromatic)
            ):
                raise ConformerPreparationError(
                    "source-bound post-sanitize bond projection is cross-wired"
                )
            exact = (
                equivalence == "exact"
                and rdkit_order == source_bond.order
                and rdkit_aromatic is source_bond.aromatic
            )
            kekule_aromatic = (
                equivalence == "kekule_ring_to_rdkit_aromatic"
                and not source_bond.aromatic
                and source_bond.order in {1.0, 2.0}
                and rdkit_order == 1.5
                and rdkit_aromatic
                and rdkit_conjugated
                and rdkit_in_ring
                and endpoint_atoms_aromatic == [True, True]
            )
            if not exact and not kekule_aromatic:
                raise ConformerPreparationError(
                    "source-bound post-sanitize bond equivalence is invalid"
                )
            observed_bonds.append(endpoints)
        if tuple(observed_bonds) != tuple(sorted(source_bonds)):
            raise ConformerPreparationError(
                "source-bound post-sanitize bond projection is not complete"
            )
        try:
            source_system_sha256 = canonical_system_sha256(self.source_system)
            source_topology_sha256 = canonical_topology_sha256(self.source_system)
            source_coordinates_sha256 = canonical_coordinates_sha256(self.source_system)
            prepared_system_sha256 = canonical_system_sha256(self.system)
            prepared_topology_sha256 = canonical_topology_sha256(self.system)
            prepared_coordinates_sha256 = canonical_coordinates_sha256(self.system)
        except Exception as exc:
            raise ConformerPreparationError(
                "source-bound molecular state changed after preparation"
            ) from exc
        expected_fields = {
            "source_system_sha256": source_system_sha256,
            "source_topology_sha256": source_topology_sha256,
            "source_coordinates_sha256": source_coordinates_sha256,
            "source_artifact_sha256": (self.source_system.provenance.source_sha256),
        }
        if any(derivation.get(key) != value for key, value in expected_fields.items()):
            raise ConformerPreparationError(
                "source-bound prepared-state receipt is cross-wired"
            )
        if (
            derivation.get("source_atom_count") != self.source_system.atom_count
            or derivation.get("source_bond_count") != len(self.source_system.bonds)
            or derivation.get("selected_conformer_count") != len(records)
            or derivation.get("generated_conformer_stereo_verified_count")
            != derivation.get("embedded_candidate_count")
        ):
            raise ConformerPreparationError(
                "source-bound derivation denominators are cross-wired"
            )
        stereo_rows = derivation.get("generated_conformer_stereo_verifications")
        expected_stereo_digest = derivation.get("source_stereo_projection_sha256")
        if (
            not isinstance(stereo_rows, list)
            or len(stereo_rows) != derivation.get("embedded_candidate_count")
            or [
                row.get("source_conformer_index")
                for row in stereo_rows
                if isinstance(row, dict)
            ]
            != list(range(len(stereo_rows)))
            or any(
                not isinstance(row, dict)
                or row.get("stereo_projection_sha256") != expected_stereo_digest
                for row in stereo_rows
            )
        ):
            raise ConformerPreparationError(
                "generated conformer stereo evidence is cross-wired"
            )
        prepared_fields = {
            "prepared_system_sha256": prepared_system_sha256,
            "prepared_topology_sha256": prepared_topology_sha256,
            "prepared_coordinates_sha256": prepared_coordinates_sha256,
        }
        if any(receipt.get(key) != value for key, value in prepared_fields.items()):
            raise ConformerPreparationError(
                "source-bound prepared system is cross-wired"
            )
        source_order_projection_sha256 = _sha256(
            {
                "atoms": _source_atom_projection(self.source_system),
                "bonds": _source_bond_projection(self.source_system),
            }
        )
        if (
            derivation.get("source_order_projection_sha256")
            != source_order_projection_sha256
        ):
            raise ConformerPreparationError(
                "source-bound atom-order projection is cross-wired"
            )
        if source_topology_sha256 != prepared_topology_sha256:
            raise ConformerPreparationError(
                "source-bound conformer preparation changed source topology"
            )
        if (
            not self.system.provenance.parent_sha256
            or self.system.provenance.parent_sha256[-1] != source_system_sha256
            or not self.system.provenance.operations
            or self.system.provenance.operations[-1]
            != "source_bound_deterministic_etkdgv3_conformer_preparation"
            or self.system.provenance.metadata.get("last_operation_evidence_sha256")
            != derivation_sha256
            or self.system.provenance.metadata.get(
                "source_bound_conformer_development_only"
            )
            is not True
            or self.system.provenance.metadata.get(
                "source_bound_conformer_stage0_eligible"
            )
            is not False
            or self.system.provenance.metadata.get(
                "source_bound_conformer_fresh_execution_authorized"
            )
            is not False
            or self.system.provenance.metadata.get(
                "source_bound_conformer_derivation_evidence_sha256"
            )
            != derivation_sha256
        ):
            raise ConformerPreparationError(
                "source-bound derivation evidence is not embedded in provenance"
            )
        if derivation.get("selected_conformer_ids") != [
            row.conformer_id for row in records
        ]:
            raise ConformerPreparationError(
                "source-bound conformer identities are cross-wired"
            )
        if any(
            receipt.get(key) is not expected
            for key, expected in (
                ("development_only", True),
                ("stage0_eligible", False),
                ("fresh_execution_authorized", False),
                ("scientifically_validated", False),
                ("claim_safe", False),
            )
        ):
            raise ConformerPreparationError("source-bound claim boundary is invalid")
        self._verify_records(receipt, records)

    def __post_init__(self) -> None:
        if not isinstance(self.source_system, AllAtomSystem):
            raise TypeError("source_system must be AllAtomSystem")
        if not isinstance(self.system, AllAtomSystem):
            raise TypeError("system must be AllAtomSystem")
        require_valid_all_atom_system(self.source_system)
        require_valid_all_atom_system(self.system)
        if self.source_system.model_count != 1:
            raise ConformerPreparationError(
                "source-bound preparation requires exactly one source model"
            )
        if (
            self.source_system.coordinates.device.type != "cpu"
            or self.source_system.coordinates.dtype != torch.float64
            or self.source_system.provenance.source_format != "sdf_v2000"
            or self.source_system.provenance.parser_name != SDF_PARSER_NAME
            or self.source_system.provenance.parser_version != SDF_PARSER_VERSION
        ):
            raise ConformerPreparationError(
                "source-bound source system contract is invalid"
            )
        if (
            not isinstance(self.raw_coordinates, torch.Tensor)
            or self.raw_coordinates.device.type != "cpu"
            or self.raw_coordinates.dtype != torch.float64
            or self.raw_coordinates.shape != self.system.coordinates.shape
            or not bool(torch.isfinite(self.raw_coordinates).all().item())
        ):
            raise ConformerPreparationError(
                "raw source-bound coordinates must be finite CPU float64 data matching the ensemble"
            )
        records = tuple(self.records)
        if any(
            not isinstance(row, SourceBoundPreparedConformerRecord) for row in records
        ):
            raise TypeError(
                "records must contain SourceBoundPreparedConformerRecord values"
            )
        if len(records) != self.system.model_count or not records:
            raise ConformerPreparationError(
                "source-bound records and coordinate models disagree"
            )
        if len({row.conformer_id for row in records}) != len(records):
            raise ConformerPreparationError("source-bound conformer IDs must be unique")
        receipt = _thaw_json(self.receipt)
        digest = _digest(self.receipt_sha256, name="receipt_sha256")
        self._verify_state(receipt, records, digest)
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "receipt", _freeze_json(receipt))
        object.__setattr__(self, "receipt_sha256", digest)

    def _verified_receipt(self) -> dict[str, Any]:
        receipt = _thaw_json(self.receipt)
        self._verify_state(receipt, self.records, self.receipt_sha256)
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


def _validated_alignment_frame(
    coordinates: torch.Tensor,
    heavy_atom_indices: tuple[int, ...],
    *,
    name: str,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if not isinstance(coordinates, torch.Tensor):
        raise ConformerPreparationError(f"{name} coordinates must be a tensor")
    tensor = coordinates.detach().to(dtype=torch.float64, device="cpu")
    if (
        tensor.ndim != 2
        or tensor.shape[1] != 3
        or len(heavy_atom_indices) < 3
        or min(heavy_atom_indices, default=-1) < 0
        or max(heavy_atom_indices, default=-1) >= tensor.shape[0]
        or not bool(torch.isfinite(tensor).all().item())
    ):
        raise ConformerPreparationError(f"{name} alignment coordinates are invalid")
    selected = tensor[list(heavy_atom_indices)]
    center = selected.mean(dim=0)
    centered = selected - center
    try:
        singular_values = torch.linalg.svdvals(centered)
    except RuntimeError as exc:
        raise ConformerPreparationError(
            f"{name} alignment geometry decomposition failed"
        ) from exc
    if singular_values.numel() < 2 or float(singular_values[1].item()) <= 1.0e-8:
        raise ConformerPreparationError(
            f"{name} alignment requires non-collinear heavy atoms"
        )
    return tensor, center, centered


def _aligned_to_reference(
    coordinates: torch.Tensor,
    reference: torch.Tensor,
    heavy_atom_indices: tuple[int, ...],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    moving, moving_center, centered_moving = _validated_alignment_frame(
        coordinates,
        heavy_atom_indices,
        name="moving",
    )
    target, target_center, centered_target = _validated_alignment_frame(
        reference,
        heavy_atom_indices,
        name="reference",
    )
    covariance = centered_moving.T @ centered_target
    try:
        u, _, vh = torch.linalg.svd(covariance)
    except RuntimeError as exc:
        raise ConformerPreparationError(
            "alignment rotation decomposition failed"
        ) from exc
    correction = torch.eye(3, dtype=torch.float64)
    if float(torch.linalg.det(u @ vh).item()) < 0.0:
        correction[-1, -1] = -1.0
    rotation = u @ correction @ vh
    translation = target_center - moving_center @ rotation
    aligned = (moving @ rotation + translation).contiguous()
    return aligned, rotation.contiguous(), translation.contiguous()


def _source_atom_projection(system: AllAtomSystem) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            atom.index,
            atom.atomic_number,
            atom.formal_charge,
            atom.isotope_mass_number,
            atom.aromatic,
        )
        for atom in system.atoms
    )


def _source_bond_projection(system: AllAtomSystem) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            bond.index,
            bond.atom_i,
            bond.atom_j,
            bond.order,
            bond.aromatic,
            bond.stereo,
        )
        for bond in system.bonds
    )


def _rdkit_bond_projection(molecule: Any) -> tuple[tuple[object, ...], ...]:
    rows = []
    for bond in molecule.GetBonds():
        atom_i, atom_j = sorted(
            (int(bond.GetBeginAtomIdx()), int(bond.GetEndAtomIdx()))
        )
        rows.append(
            (
                atom_i,
                atom_j,
                float(bond.GetBondTypeAsDouble()),
                bool(bond.GetIsAromatic()),
            )
        )
    return tuple(sorted(rows))


def _bind_rdkit_source_atom_indices(
    molecule: Any,
    *,
    source_atom_count: int,
) -> None:
    if int(molecule.GetNumAtoms()) != source_atom_count:
        raise ConformerPreparationError(
            "RDKit source atom count does not match the strict SDF parser"
        )
    for atom in molecule.GetAtoms():
        atom.SetIntProp(_SOURCE_ATOM_INDEX_PROPERTY, int(atom.GetIdx()))


def _require_rdkit_source_identity(
    molecule: Any,
    source_system: AllAtomSystem,
) -> tuple[tuple[int, ...], list[dict[str, object]]]:
    atom_count = source_system.atom_count
    if int(molecule.GetNumAtoms()) != atom_count:
        raise ConformerPreparationError(
            "RDKit sanitization changed the source atom count"
        )
    try:
        source_indices = tuple(
            int(atom.GetIntProp(_SOURCE_ATOM_INDEX_PROPERTY))
            for atom in molecule.GetAtoms()
            if atom.HasProp(_SOURCE_ATOM_INDEX_PROPERTY)
        )
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        raise ConformerPreparationError(
            "RDKit sanitization invalidated the source atom-index mapping"
        ) from exc
    identity = tuple(range(atom_count))
    if len(source_indices) != atom_count or tuple(sorted(source_indices)) != identity:
        raise ConformerPreparationError(
            "RDKit sanitization invalidated the source atom-index mapping"
        )
    source_atoms = {
        atom.index: (
            atom.atomic_number,
            atom.formal_charge,
            atom.isotope_mass_number,
        )
        for atom in source_system.atoms
    }
    observed_atoms = {
        source_index: (
            int(atom.GetAtomicNum()),
            int(atom.GetFormalCharge()),
            int(atom.GetIsotope()) or None,
        )
        for atom, source_index in zip(molecule.GetAtoms(), source_indices)
    }
    if observed_atoms != source_atoms:
        raise ConformerPreparationError(
            "RDKit sanitization changed the source atom identity"
        )
    source_bonds = {
        (bond.atom_i, bond.atom_j): bond for bond in source_system.bonds
    }
    observed_connectivity: list[tuple[int, int]] = []
    post_sanitize_bonds: list[dict[str, object]] = []
    for bond in molecule.GetBonds():
        endpoints = tuple(
            sorted(
                (
                    source_indices[int(bond.GetBeginAtomIdx())],
                    source_indices[int(bond.GetEndAtomIdx())],
                )
            )
        )
        observed_connectivity.append(endpoints)
        source_bond = source_bonds.get(endpoints)
        if source_bond is None:
            raise ConformerPreparationError(
                "RDKit sanitization changed the source bond connectivity"
            )
        rdkit_order = float(bond.GetBondTypeAsDouble())
        rdkit_aromatic = bool(bond.GetIsAromatic())
        if (
            rdkit_order == source_bond.order
            and rdkit_aromatic is source_bond.aromatic
        ):
            equivalence = "exact"
        elif (
            not source_bond.aromatic
            and source_bond.order in {1.0, 2.0}
            and rdkit_order == 1.5
            and rdkit_aromatic
            and bool(bond.IsInRing())
            and bool(bond.GetBeginAtom().GetIsAromatic())
            and bool(bond.GetEndAtom().GetIsAromatic())
        ):
            equivalence = "kekule_ring_to_rdkit_aromatic"
        else:
            raise ConformerPreparationError(
                "RDKit sanitization changed the source bond order outside the "
                "allowed aromatic equivalence"
            )
        post_sanitize_bonds.append(
            {
                "source_atom_i": endpoints[0],
                "source_atom_j": endpoints[1],
                "source_order_binary64_hex": source_bond.order.hex(),
                "source_aromatic": source_bond.aromatic,
                "rdkit_order_binary64_hex": rdkit_order.hex(),
                "rdkit_aromatic": rdkit_aromatic,
                "rdkit_conjugated": bool(bond.GetIsConjugated()),
                "rdkit_in_ring": bool(bond.IsInRing()),
                "rdkit_endpoint_atoms_aromatic": [
                    bool(bond.GetBeginAtom().GetIsAromatic()),
                    bool(bond.GetEndAtom().GetIsAromatic()),
                ],
                "equivalence": equivalence,
            }
        )
    source_connectivity = tuple(sorted(source_bonds))
    if tuple(sorted(observed_connectivity)) != source_connectivity:
        raise ConformerPreparationError(
            "RDKit sanitization changed the source bond connectivity"
        )
    post_sanitize_bonds.sort(
        key=lambda row: (int(row["source_atom_i"]), int(row["source_atom_j"]))
    )
    return source_indices, post_sanitize_bonds


def _normalize_rdkit_source_atom_order(
    molecule: Any,
    source_system: AllAtomSystem,
    *,
    chemistry: Any,
) -> tuple[Any, dict[str, object]]:
    identity = tuple(range(source_system.atom_count))
    source_indices, _ = _require_rdkit_source_identity(molecule, source_system)
    renumbered = source_indices != identity
    if renumbered:
        source_to_current = [0] * source_system.atom_count
        for current_index, source_index in enumerate(source_indices):
            source_to_current[source_index] = current_index
        molecule = chemistry.RenumberAtoms(molecule, source_to_current)
    normalized_indices, post_sanitize_bonds = _require_rdkit_source_identity(
        molecule,
        source_system,
    )
    if normalized_indices != identity:
        raise ConformerPreparationError(
            "RDKit source atom-index mapping was not normalized to source order"
        )
    if int(molecule.GetNumConformers()) != 1 or not torch.equal(
        _coordinates(molecule, 0),
        source_system.coordinates[0],
    ):
        raise ConformerPreparationError(
            "RDKit source atom-index mapping did not preserve source coordinates"
        )
    projection: dict[str, object] = {
        "schema_id": SOURCE_BOUND_CONFORMER_SOURCE_INDEX_MAPPING_SCHEMA_ID,
        "source_index_property": _SOURCE_ATOM_INDEX_PROPERTY,
        "source_atom_count": source_system.atom_count,
        "pre_sanitize_source_index_by_rdkit_index": list(identity),
        "post_sanitize_source_index_by_rdkit_index": list(source_indices),
        "normalized_source_index_by_rdkit_index": list(normalized_indices),
        "renumbered_to_source_order": renumbered,
        "raw_source_projection_exact_before_sanitization": True,
        "post_sanitize_atom_identity_fields": [
            "atomic_number",
            "formal_charge",
            "isotope_mass_number",
        ],
        "post_sanitize_bond_identity": "exact_source_endpoint_connectivity",
        "post_sanitize_bond_order_aromaticity_policy": (
            "exact_or_kekule_ring_to_rdkit_aromatic"
        ),
        "post_sanitize_bond_projection": post_sanitize_bonds,
        "post_sanitize_bond_projection_sha256": _sha256(post_sanitize_bonds),
        "source_coordinates_preserved_after_normalization": True,
    }
    return molecule, projection


def _rdkit_raw_source_projection(molecule: Any) -> dict[str, object]:
    return {
        "atoms": [
            {
                "index": int(atom.GetIdx()),
                "atomic_number": int(atom.GetAtomicNum()),
                "formal_charge": int(atom.GetFormalCharge()),
                "isotope_mass_number": int(atom.GetIsotope()) or None,
            }
            for atom in molecule.GetAtoms()
        ],
        "bonds": [
            {
                "index": int(bond.GetIdx()),
                "begin_atom_index": int(bond.GetBeginAtomIdx()),
                "end_atom_index": int(bond.GetEndAtomIdx()),
                "order_binary64_hex": float(bond.GetBondTypeAsDouble()).hex(),
                "aromatic": bool(bond.GetIsAromatic()),
                "bond_direction": str(bond.GetBondDir()),
                "molfile_stereo_code": (
                    int(bond.GetIntProp("_MolFileBondStereo"))
                    if bond.HasProp("_MolFileBondStereo")
                    else 0
                ),
                "stereo": str(bond.GetStereo()),
                "stereo_atom_indices": [int(value) for value in bond.GetStereoAtoms()],
            }
            for bond in molecule.GetBonds()
        ],
    }


def _rdkit_stereo_projection(molecule: Any) -> dict[str, object]:
    return {
        "atoms": [
            {
                "index": int(atom.GetIdx()),
                "chiral_tag": str(atom.GetChiralTag()),
                "cip_code": str(atom.GetProp("_CIPCode")),
            }
            for atom in molecule.GetAtoms()
            if atom.HasProp("_CIPCode")
        ],
        "bonds": [
            {
                "index": int(bond.GetIdx()),
                "begin_atom_index": int(bond.GetBeginAtomIdx()),
                "end_atom_index": int(bond.GetEndAtomIdx()),
                "bond_direction": str(bond.GetBondDir()),
                "molfile_stereo_code": (
                    int(bond.GetIntProp("_MolFileBondStereo"))
                    if bond.HasProp("_MolFileBondStereo")
                    else 0
                ),
                "stereo": str(bond.GetStereo()),
                "stereo_atom_indices": [int(value) for value in bond.GetStereoAtoms()],
            }
            for bond in molecule.GetBonds()
            if (
                str(bond.GetStereo()) != "STEREONONE"
                or str(bond.GetBondDir()) != "NONE"
                or (
                    bond.HasProp("_MolFileBondStereo")
                    and int(bond.GetIntProp("_MolFileBondStereo")) != 0
                )
            )
        ],
    }


def _require_supported_source_molfile_fields(
    source_text: str,
) -> dict[str, object]:
    lines = source_text.splitlines()
    if len(lines) < 4:
        raise ConformerPreparationError("source SDF V2000 record is incomplete")
    counts = lines[3].ljust(39)
    try:
        atom_count = int(counts[0:3])
        bond_count = int(counts[3:6])
    except ValueError as exc:
        raise ConformerPreparationError("source SDF V2000 counts are invalid") from exc
    if len(lines) < 4 + atom_count + bond_count:
        raise ConformerPreparationError("source SDF V2000 record is truncated")
    unsupported_atom_slices = (
        (42, 45),
        (45, 48),
        (51, 54),
        (54, 57),
        (57, 60),
        (60, 63),
        (63, 66),
        (66, 69),
    )
    atom_projection = []
    for offset in range(atom_count):
        line = lines[4 + offset].ljust(69)
        try:
            parity_code = int(line[39:42].strip() or "0")
            declared_valence_code = int(line[48:51].strip() or "0")
        except ValueError as exc:
            raise ConformerPreparationError(
                "source SDF uses an invalid atom field"
            ) from exc
        if parity_code not in {0, 1, 2, 3}:
            raise ConformerPreparationError(
                "source SDF uses an unsupported atom parity code"
            )
        if declared_valence_code == 0:
            declared_valence = None
        elif 1 <= declared_valence_code <= 14:
            declared_valence = declared_valence_code
        else:
            raise ConformerPreparationError(
                "source SDF uses an unsupported declared atom valence"
            )
        for start, end in unsupported_atom_slices:
            field = line[start:end].strip()
            if field and field != "0":
                raise ConformerPreparationError(
                    "source SDF uses unsupported non-default atom fields"
                )
        atom_projection.append(
            {
                "index": offset,
                "molfile_atom_parity_code": parity_code,
                "declared_valence": declared_valence,
            }
        )
    supported_bond_stereo_codes = {0, 1, 4, 6}
    bond_projection = []
    raw_bond_order_sums = [0.0] * atom_count
    for offset in range(bond_count):
        line = lines[4 + atom_count + offset]
        padded = line.ljust(12)
        try:
            begin_atom_index = int(padded[0:3]) - 1
            end_atom_index = int(padded[3:6]) - 1
            bond_type = int(padded[6:9])
            stereo_code = int(padded[9:12])
        except ValueError as exc:
            raise ConformerPreparationError(
                "source SDF uses an invalid bond record"
            ) from exc
        if (
            begin_atom_index < 0
            or end_atom_index < 0
            or begin_atom_index >= atom_count
            or end_atom_index >= atom_count
            or begin_atom_index == end_atom_index
            or bond_type not in {1, 2, 3, 4}
            or stereo_code not in supported_bond_stereo_codes
        ):
            raise ConformerPreparationError(
                "source SDF uses an unsupported bond record"
            )
        for field in line[12:].split():
            if field != "0":
                raise ConformerPreparationError(
                    "source SDF uses unsupported non-default bond fields"
                )
        order = 1.5 if bond_type == 4 else float(bond_type)
        raw_bond_order_sums[begin_atom_index] += order
        raw_bond_order_sums[end_atom_index] += order
        bond_projection.append(
            {
                "index": offset,
                "begin_atom_index": begin_atom_index,
                "end_atom_index": end_atom_index,
                "order_binary64_hex": order.hex(),
                "aromatic": bond_type == 4,
                "molfile_stereo_code": stereo_code,
            }
        )
    for row, raw_bond_order_sum in zip(atom_projection, raw_bond_order_sums):
        row["raw_bond_order_sum_binary64_hex"] = raw_bond_order_sum.hex()
        declared_valence = row["declared_valence"]
        if (
            declared_valence is not None
            and raw_bond_order_sum != float(declared_valence)
        ):
            raise ConformerPreparationError(
                "source SDF declared atom valence does not match the raw bond order sum"
            )
    return {
        "atom_parity_policy": (
            "raw_code_bound_perceived_stereo_verified_separately"
        ),
        "declared_valence_policy": (
            "nonzero_1_to_14_must_equal_raw_bond_order_sum"
        ),
        "atoms": atom_projection,
        "bonds": bond_projection,
    }


def _require_rdkit_declared_valence(
    molecule: Any,
    source_text_projection: Mapping[str, Any],
) -> list[dict[str, object]]:
    atom_rows = source_text_projection.get("atoms")
    if not isinstance(atom_rows, list):
        raise ConformerPreparationError(
            "source SDF atom-field projection is missing"
        )
    checks: list[dict[str, object]] = []
    for row in atom_rows:
        if not isinstance(row, dict) or type(row.get("index")) is not int:
            raise ConformerPreparationError(
                "source SDF atom-field projection is invalid"
            )
        declared_valence = row.get("declared_valence")
        if declared_valence is None:
            continue
        atom_index = row["index"]
        try:
            atom = molecule.GetAtomWithIdx(atom_index)
            explicit_valence = int(atom.GetExplicitValence())
            total_valence = int(atom.GetTotalValence())
            implicit_hydrogen_count = int(atom.GetNumImplicitHs())
            no_implicit = bool(atom.GetNoImplicit())
        except (IndexError, RuntimeError, ValueError) as exc:
            raise ConformerPreparationError(
                "RDKit could not verify the source declared atom valence"
            ) from exc
        if (
            explicit_valence != declared_valence
            or total_valence != declared_valence
            or implicit_hydrogen_count != 0
            or not no_implicit
        ):
            raise ConformerPreparationError(
                "RDKit declared atom valence does not match the source topology"
            )
        checks.append(
            {
                "atom_index": atom_index,
                "declared_valence": declared_valence,
                "rdkit_explicit_valence": explicit_valence,
                "rdkit_total_valence": total_valence,
                "rdkit_implicit_hydrogen_count": implicit_hydrogen_count,
                "rdkit_no_implicit": no_implicit,
            }
        )
    return checks


def _require_source_text_projection_contract(
    projection: Mapping[str, Any],
    source_system: AllAtomSystem,
) -> None:
    if (
        set(projection)
        != {
            "atom_parity_policy",
            "declared_valence_policy",
            "atoms",
            "bonds",
            "rdkit_declared_valence_checks",
        }
        or projection.get("atom_parity_policy")
        != "raw_code_bound_perceived_stereo_verified_separately"
        or projection.get("declared_valence_policy")
        != "nonzero_1_to_14_must_equal_raw_bond_order_sum"
    ):
        raise ConformerPreparationError(
            "source SDF atom-field policy is invalid"
        )
    stereo_codes = {"none": 0, "up": 1, "either": 4, "down": 6}
    bond_rows = projection.get("bonds")
    if not isinstance(bond_rows, list) or len(bond_rows) != len(
        source_system.bonds
    ):
        raise ConformerPreparationError(
            "source SDF bond projection is incomplete"
        )
    raw_bond_order_sums = [0.0] * source_system.atom_count
    for bond, row in zip(source_system.bonds, bond_rows):
        stereo_code = stereo_codes.get(bond.stereo)
        begin_atom_index = (
            row.get("begin_atom_index") if isinstance(row, dict) else None
        )
        end_atom_index = (
            row.get("end_atom_index") if isinstance(row, dict) else None
        )
        if (
            stereo_code is None
            or not isinstance(row, dict)
            or set(row)
            != {
                "index",
                "begin_atom_index",
                "end_atom_index",
                "order_binary64_hex",
                "aromatic",
                "molfile_stereo_code",
            }
            or row.get("index") != bond.index
            or type(begin_atom_index) is not int
            or type(end_atom_index) is not int
            or tuple(sorted((begin_atom_index, end_atom_index)))
            != (bond.atom_i, bond.atom_j)
            or row.get("order_binary64_hex") != bond.order.hex()
            or row.get("aromatic") is not bond.aromatic
            or row.get("molfile_stereo_code") != stereo_code
        ):
            raise ConformerPreparationError(
                "source SDF bond projection is cross-wired"
            )
        raw_bond_order_sums[bond.atom_i] += bond.order
        raw_bond_order_sums[bond.atom_j] += bond.order
    atom_rows = projection.get("atoms")
    if not isinstance(atom_rows, list) or len(atom_rows) != source_system.atom_count:
        raise ConformerPreparationError(
            "source SDF atom-field projection is incomplete"
        )
    expected_checks = []
    for atom_index, (row, raw_bond_order_sum) in enumerate(
        zip(atom_rows, raw_bond_order_sums)
    ):
        if not isinstance(row, dict):
            raise ConformerPreparationError(
                "source SDF atom-field projection is invalid"
            )
        parity_code = row.get("molfile_atom_parity_code")
        declared_valence = row.get("declared_valence")
        if (
            set(row)
            != {
                "index",
                "molfile_atom_parity_code",
                "declared_valence",
                "raw_bond_order_sum_binary64_hex",
            }
            or row.get("index") != atom_index
            or type(parity_code) is not int
            or parity_code not in {0, 1, 2, 3}
            or (
                declared_valence is not None
                and (
                    type(declared_valence) is not int
                    or not 1 <= declared_valence <= 14
                    or raw_bond_order_sum != float(declared_valence)
                )
            )
            or row.get("raw_bond_order_sum_binary64_hex")
            != raw_bond_order_sum.hex()
        ):
            raise ConformerPreparationError(
                "source SDF atom-field projection is cross-wired"
            )
        if declared_valence is not None:
            expected_checks.append(
                {
                    "atom_index": atom_index,
                    "declared_valence": declared_valence,
                    "rdkit_explicit_valence": declared_valence,
                    "rdkit_total_valence": declared_valence,
                    "rdkit_implicit_hydrogen_count": 0,
                    "rdkit_no_implicit": True,
                }
            )
    if projection.get("rdkit_declared_valence_checks") != expected_checks:
        raise ConformerPreparationError(
            "source SDF RDKit declared-valence checks are cross-wired"
        )


def _verify_generated_conformer_stereo(
    molecule: Any,
    *,
    conformer_id: int,
    expected_projection: Mapping[str, Any],
    chemistry: Any,
) -> str:
    candidate = chemistry.Mol(molecule)
    try:
        chemistry.AssignAtomChiralTagsFromStructure(
            candidate,
            confId=int(conformer_id),
            replaceExistingTags=True,
        )
        chemistry.AssignStereochemistryFrom3D(
            candidate,
            confId=int(conformer_id),
            replaceExistingTags=True,
        )
        chemistry.AssignStereochemistry(
            candidate,
            cleanIt=True,
            force=True,
        )
    except (RuntimeError, ValueError) as exc:
        raise ConformerPreparationError(
            "generated conformer stereochemistry assignment failed"
        ) from exc
    unspecified = [
        row
        for row in chemistry.FindPotentialStereo(
            candidate,
            cleanIt=True,
            flagPossible=True,
        )
        if str(row.specified) != "Specified"
    ]
    observed_projection = _rdkit_stereo_projection(candidate)
    if unspecified or observed_projection != dict(expected_projection):
        raise ConformerPreparationError(
            "generated conformer changed source stereochemistry"
        )
    return _sha256(observed_projection)


def _require_supported_ring_system(molecule: Any) -> None:
    ring_atoms: set[int] = set()
    ring_adjacency: dict[int, set[int]] = {}
    for ring in molecule.GetRingInfo().AtomRings():
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


def _source_bound_rdkit_molecule(
    source_system: AllAtomSystem,
    source_sdf: bytes,
    *,
    chemistry: Any,
) -> tuple[
    Any,
    str,
    str,
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    if not isinstance(source_system, AllAtomSystem):
        raise TypeError("source_system must be AllAtomSystem")
    require_valid_all_atom_system(source_system)
    if source_system.model_count != 1:
        raise ConformerPreparationError(
            "source-bound preparation requires exactly one source model"
        )
    if source_system.coordinate_unit != "angstrom":
        raise ConformerPreparationError(
            "source-bound preparation requires Angstrom coordinates"
        )
    if (
        source_system.coordinates.device.type != "cpu"
        or source_system.coordinates.dtype != torch.float64
    ):
        raise ConformerPreparationError(
            "source-bound preparation requires CPU float64 coordinates"
        )
    if source_system.atom_count > MAX_CONFORMER_INPUT_ATOMS:
        raise ConformerPreparationError(
            "ligand atom count exceeds the conformer preparation bound"
        )
    if len(source_system.bonds) > MAX_CONFORMER_INPUT_BONDS:
        raise ConformerPreparationError(
            "ligand bond count exceeds the conformer preparation bound"
        )
    if not isinstance(source_sdf, bytes):
        raise TypeError("source_sdf must be exact source bytes")
    raw = source_sdf
    artifact_sha256 = hashlib.sha256(raw).hexdigest()
    if (
        not source_system.provenance.source_digest_verified
        or source_system.provenance.source_sha256 != artifact_sha256
    ):
        raise ConformerPreparationError(
            "source SDF digest does not match the source system provenance"
        )
    if (
        source_system.provenance.source_format != "sdf_v2000"
        or source_system.provenance.parser_name != SDF_PARSER_NAME
        or source_system.provenance.parser_version != SDF_PARSER_VERSION
    ):
        raise ConformerPreparationError(
            "source system is not bound to the strict SDF V2000 parser"
        )
    try:
        parsed_source = parse_sdf_v2000(
            raw,
            source_id=source_system.provenance.source_id,
            dtype=torch.float64,
            device="cpu",
        )
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ConformerPreparationError("source SDF strict parsing failed") from exc
    if (
        _source_atom_projection(parsed_source) != _source_atom_projection(source_system)
        or _source_bond_projection(parsed_source)
        != _source_bond_projection(source_system)
        or not torch.equal(
            parsed_source.coordinates,
            source_system.coordinates,
        )
    ):
        raise ConformerPreparationError(
            "source system atom order, bond table, or coordinates do not match the source SDF"
        )
    try:
        source_text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConformerPreparationError("source SDF must be UTF-8 text") from exc
    source_text_projection = _require_supported_source_molfile_fields(source_text)
    mol_block = source_text.split("$$$$", 1)[0]
    if not mol_block.endswith(("\n", "\r")):
        mol_block += "\n"
    molecule = chemistry.MolFromMolBlock(
        mol_block,
        sanitize=False,
        removeHs=False,
        strictParsing=True,
    )
    if molecule is None:
        raise ConformerPreparationError("RDKit source SDF parsing failed")
    raw_rdkit_projection = _rdkit_raw_source_projection(molecule)
    raw_text_bond_projection = [
        {
            key: row[key]
            for key in (
                "index",
                "begin_atom_index",
                "end_atom_index",
                "order_binary64_hex",
                "aromatic",
                "molfile_stereo_code",
            )
        }
        for row in raw_rdkit_projection["bonds"]
    ]
    if raw_text_bond_projection != source_text_projection["bonds"]:
        raise ConformerPreparationError(
            "RDKit molfile bond projection does not match the source SDF"
        )
    rdkit_atoms = tuple(
        (
            int(atom.GetIdx()),
            int(atom.GetAtomicNum()),
            int(atom.GetFormalCharge()),
            int(atom.GetIsotope()) or None,
        )
        for atom in molecule.GetAtoms()
    )
    source_atoms = tuple(
        (
            atom.index,
            atom.atomic_number,
            atom.formal_charge,
            atom.isotope_mass_number,
        )
        for atom in parsed_source.atoms
    )
    source_bonds = tuple(
        sorted(
            (
                bond.atom_i,
                bond.atom_j,
                bond.order,
                bond.aromatic,
            )
            for bond in parsed_source.bonds
        )
    )
    if rdkit_atoms != source_atoms or _rdkit_bond_projection(molecule) != source_bonds:
        raise ConformerPreparationError(
            "RDKit source atom order or bond topology does not match the strict SDF parser"
        )
    _bind_rdkit_source_atom_indices(
        molecule,
        source_atom_count=source_system.atom_count,
    )
    try:
        chemistry.SanitizeMol(molecule)
    except (RuntimeError, ValueError) as exc:
        raise ConformerPreparationError(
            "source SDF chemistry sanitization failed"
        ) from exc
    molecule, source_index_mapping = _normalize_rdkit_source_atom_order(
        molecule,
        source_system,
        chemistry=chemistry,
    )
    source_text_projection["rdkit_declared_valence_checks"] = (
        _require_rdkit_declared_valence(
            molecule,
            source_text_projection,
        )
    )
    try:
        chemistry.AssignAtomChiralTagsFromStructure(
            molecule,
            confId=0,
            replaceExistingTags=False,
        )
        chemistry.AssignStereochemistryFrom3D(
            molecule,
            confId=0,
            replaceExistingTags=False,
        )
        chemistry.AssignStereochemistry(
            molecule,
            cleanIt=True,
            force=True,
        )
    except (RuntimeError, ValueError) as exc:
        raise ConformerPreparationError(
            "source SDF stereochemistry assignment failed"
        ) from exc
    if len(chemistry.GetMolFrags(molecule)) != 1:
        raise ConformerPreparationError(
            "conformer preparation requires one connected ligand component"
        )
    if any(
        atom.GetAtomicNum() != 1
        and (int(atom.GetNumImplicitHs()) != 0 or int(atom.GetNumExplicitHs()) != 0)
        for atom in molecule.GetAtoms()
    ):
        raise ConformerPreparationError(
            "source-bound conformer preparation requires explicit hydrogens"
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
    stereo_projection = _rdkit_stereo_projection(molecule)
    _require_supported_ring_system(molecule)
    canonical_smiles = chemistry.MolToSmiles(
        molecule,
        canonical=True,
        isomericSmiles=True,
    )
    molecule.RemoveAllConformers()
    return (
        molecule,
        canonical_smiles,
        artifact_sha256,
        raw_rdkit_projection,
        source_text_projection,
        stereo_projection,
        source_index_mapping,
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
            str(atom.GetProp("_CIPCode")) if atom.HasProp("_CIPCode") else "unspecified"
        )
        atoms.append(
            Atom(
                index=int(atom.GetIdx()),
                name=f"{atom.GetSymbol()}{atom.GetIdx() + 1}",
                element=str(atom.GetSymbol()),
                atomic_number=int(atom.GetAtomicNum()),
                residue_index=0,
                formal_charge=int(atom.GetFormalCharge()),
                isotope_mass_number=(int(atom.GetIsotope()) or None),
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
        first, second = sorted((int(bond.GetBeginAtomIdx()), int(bond.GetEndAtomIdx())))
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
    source_sha256 = hashlib.sha256(canonical_smiles.encode("utf-8")).hexdigest()
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
        raise ConformerPreparationError("canonical SMILES reconstruction failed")
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
        raise ConformerPreparationError("energy rows do not cover embedded conformers")
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
        raise ConformerPreparationError("all conformer energy evaluations failed")
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
            _heavy_atom_rmsd(coordinates, row[3], heavy_indices) for row in selected
        ]
        minimum_rmsd = min(rmsds) if rmsds else None
        if (
            minimum_rmsd is not None
            and minimum_rmsd + 1.0e-12 < settings.diversity_rmsd_angstrom
        ):
            continue
        selected.append((source_id, status, energy, coordinates, minimum_rmsd))
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
        "input_smiles_sha256": hashlib.sha256(raw_smiles.encode("utf-8")).hexdigest(),
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
        "selected_conformer_records": [row.to_dict() for row in records],
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


def prepare_source_bound_conformer_ensemble(
    source_system: AllAtomSystem,
    source_sdf: bytes,
    *,
    config: ConformerPreparationConfig | None = None,
) -> SourceBoundPreparedConformerEnsemble:
    """Prepare deterministic conformers in exact source-SDF atom order.

    This development-only adapter keeps the strict source topology and any
    source-bound partial charges unchanged. Generated coordinates are aligned
    to the source pose and admitted only when they satisfy the configured
    source-pose and pairwise heavy-atom RMSD thresholds.
    """

    settings = config or ConformerPreparationConfig()
    if not isinstance(settings, ConformerPreparationConfig):
        raise TypeError("config must be ConformerPreparationConfig")
    chemistry, all_chem, rd_base = _load_rdkit()
    (
        molecule,
        canonical_smiles,
        source_artifact_sha256,
        raw_rdkit_projection,
        source_text_projection,
        stereo_projection,
        source_index_mapping,
    ) = _source_bound_rdkit_molecule(
        source_system,
        source_sdf,
        chemistry=chemistry,
    )
    heavy_indices = tuple(
        atom.index for atom in source_system.atoms if atom.atomic_number > 1
    )
    source_coordinates = source_system.coordinates[0]
    _validated_alignment_frame(
        source_coordinates,
        heavy_indices,
        name="source",
    )
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
        raise ConformerPreparationError("energy rows do not cover embedded conformers")
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
        raise ConformerPreparationError("all conformer energy evaluations failed")
    candidate_rows.sort(key=lambda row: (row[2], row[0]))
    minimum_energy = candidate_rows[0][2]
    energy_limit = minimum_energy + settings.energy_window_kcal_mol
    energy_filtered = [row for row in candidate_rows if row[2] <= energy_limit]
    post_embedding_indices, _ = _require_rdkit_source_identity(
        molecule,
        source_system,
    )
    if post_embedding_indices != tuple(range(source_system.atom_count)):
        raise ConformerPreparationError(
            "conformer preparation changed the normalized source atom order"
        )
    generated_conformer_stereo_verifications = [
        {
            "source_conformer_index": embedded_id,
            "stereo_projection_sha256": (
                _verify_generated_conformer_stereo(
                    molecule,
                    conformer_id=embedded_id,
                    expected_projection=stereo_projection,
                    chemistry=chemistry,
                )
            ),
        }
        for embedded_id in embedded_ids
    ]
    selected: list[
        tuple[
            int,
            int,
            float,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            float | None,
            float,
        ]
    ] = []
    source_pose_diversity_survivor_count = 0
    for source_id, status, energy, raw_coordinates in energy_filtered:
        aligned, rotation, translation = _aligned_to_reference(
            raw_coordinates,
            source_coordinates,
            heavy_indices,
        )
        source_pose_rmsd = _heavy_atom_rmsd(
            aligned,
            source_coordinates,
            heavy_indices,
        )
        if source_pose_rmsd + 1.0e-12 < settings.diversity_rmsd_angstrom:
            continue
        source_pose_diversity_survivor_count += 1
        selected_rmsds = [
            _heavy_atom_rmsd(aligned, row[4], heavy_indices) for row in selected
        ]
        minimum_selected_rmsd = min(selected_rmsds) if selected_rmsds else None
        if (
            minimum_selected_rmsd is not None
            and minimum_selected_rmsd + 1.0e-12 < settings.diversity_rmsd_angstrom
        ):
            continue
        selected.append(
            (
                source_id,
                status,
                energy,
                raw_coordinates,
                aligned,
                rotation,
                translation,
                minimum_selected_rmsd,
                source_pose_rmsd,
            )
        )
        if len(selected) >= settings.selected_count:
            break
    if not selected:
        raise ConformerPreparationError(
            "source-pose and pairwise diversity filters removed every conformer"
        )
    config_projection = settings.to_dict()
    source_system_sha256 = canonical_system_sha256(source_system)
    records = []
    conformer_ids = []
    for (
        source_id,
        _,
        energy,
        raw_coordinates,
        coordinates,
        rotation,
        translation,
        minimum_selected_rmsd,
        source_pose_rmsd,
    ) in selected:
        raw_coordinates_sha256 = _coordinate_model_sha256(raw_coordinates)
        coordinates_sha256 = _coordinate_model_sha256(coordinates)
        conformer_id = _source_bound_conformer_identity(
            source_system_sha256=source_system_sha256,
            source_artifact_sha256=source_artifact_sha256,
            canonical_smiles=canonical_smiles,
            rdkit_version=str(rd_base.rdkitVersion),
            config_projection=config_projection,
            source_conformer_index=source_id,
            energy_model=energy_model,
            energy_kcal_mol=energy,
            raw_coordinates_sha256=raw_coordinates_sha256,
            coordinates_sha256=coordinates_sha256,
        )
        conformer_ids.append(conformer_id)
        records.append(
            SourceBoundPreparedConformerRecord(
                conformer_id=conformer_id,
                source_conformer_index=source_id,
                energy_kcal_mol=energy,
                minimum_selected_rmsd_angstrom=(minimum_selected_rmsd),
                source_pose_rmsd_angstrom=source_pose_rmsd,
                raw_coordinates_sha256=raw_coordinates_sha256,
                coordinates_sha256=coordinates_sha256,
                alignment_rotation=tuple(
                    tuple(float(value) for value in row) for row in rotation.tolist()
                ),
                alignment_translation=tuple(
                    float(value) for value in translation.tolist()
                ),
            )
        )
    source_topology_sha256 = canonical_topology_sha256(source_system)
    source_order_projection_sha256 = _sha256(
        {
            "atoms": _source_atom_projection(source_system),
            "bonds": _source_bond_projection(source_system),
        }
    )
    raw_coordinate_tensor = torch.stack([row[3] for row in selected])
    aligned_coordinate_tensor = torch.stack([row[4] for row in selected])
    derivation_evidence = {
        "schema_id": SOURCE_BOUND_CONFORMER_DERIVATION_SCHEMA_ID,
        "policy_id": SOURCE_BOUND_CONFORMER_PREPARATION_POLICY_ID,
        "canonical_isomeric_smiles": canonical_smiles,
        "source_artifact_sha256": source_artifact_sha256,
        "source_system_sha256": source_system_sha256,
        "source_topology_sha256": source_topology_sha256,
        "source_coordinates_sha256": canonical_coordinates_sha256(source_system),
        "source_order_projection_sha256": (source_order_projection_sha256),
        "source_raw_rdkit_projection": raw_rdkit_projection,
        "source_raw_rdkit_projection_sha256": _sha256(raw_rdkit_projection),
        "source_text_projection": source_text_projection,
        "source_text_projection_sha256": _sha256(source_text_projection),
        "source_index_mapping": source_index_mapping,
        "source_index_mapping_sha256": _sha256(source_index_mapping),
        "source_stereo_projection": stereo_projection,
        "source_stereo_projection_sha256": _sha256(stereo_projection),
        "source_stereo_binding_policy": {
            "raw_v2000_bond_stereo": "exact_molfile_stereo_code",
            "perceived_stereo": "exact_source_and_generated_cip_ez_bond_dir",
            "three_dimensional_bond_dir_text_equivalence_required": False,
        },
        "source_atom_count": source_system.atom_count,
        "source_bond_count": len(source_system.bonds),
        "preparation_bounds": {
            "maximum_input_atoms": MAX_CONFORMER_INPUT_ATOMS,
            "maximum_input_bonds": MAX_CONFORMER_INPUT_BONDS,
            "maximum_prepared_atoms": MAX_CONFORMER_PREPARED_ATOMS,
            "maximum_prepared_bonds": MAX_CONFORMER_PREPARED_BONDS,
        },
        "connected_component_policy": "exactly_one",
        "explicit_hydrogen_policy": "no_implicit_hydrogens",
        "unspecified_potential_stereochemistry_allowed": False,
        "source_sdf_rdkit_atom_order_verified": True,
        "coordinate_projection": "exact_source_sdf_atom_index_identity",
        "coordinate_frame": "heavy_atom_kabsch_aligned_to_source_pose",
        "source_pose_retained_separately": True,
        "rdkit_version": str(rd_base.rdkitVersion),
        "etkdg_variant": "ETKDGv3",
        "energy_model": energy_model,
        "energy_optimization_status_zero_means_converged": True,
        "energy_optimization_status_one_admitted_as_iteration_limited": True,
        "diversity_metric": "heavy_atom_kabsch_rmsd",
        "source_pose_diversity_metric": "heavy_atom_kabsch_rmsd",
        "diversity_symmetry_aware": False,
        "config": config_projection,
        "requested_candidate_count": settings.candidate_count,
        "embedded_candidate_count": len(embedded_ids),
        "generated_conformer_stereo_verified_count": len(embedded_ids),
        "generated_conformer_stereo_verifications": (
            generated_conformer_stereo_verifications
        ),
        "energy_evaluated_count": len(candidate_rows),
        "energy_window_survivor_count": len(energy_filtered),
        "source_pose_diversity_survivor_count": (source_pose_diversity_survivor_count),
        "selected_conformer_count": len(records),
        "selected_conformer_ids": conformer_ids,
        "selected_conformer_records": [row.to_dict() for row in records],
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
                "admitted_to_energy_window": (
                    status in {0, 1}
                    and math.isfinite(energy)
                    and energy <= energy_limit
                ),
            }
            for source_id, status, energy in optimization_rows
        ],
        "deterministic": True,
    }
    derivation_evidence_sha256 = _sha256(derivation_evidence)
    system = source_system.with_coordinates(
        aligned_coordinate_tensor,
        operation=("source_bound_deterministic_etkdgv3_conformer_preparation"),
        operation_evidence_sha256=derivation_evidence_sha256,
    )
    system = replace(
        system,
        provenance=replace(
            system.provenance,
            metadata={
                **dict(system.provenance.metadata),
                "source_bound_conformer_development_only": True,
                "source_bound_conformer_stage0_eligible": False,
                "source_bound_conformer_fresh_execution_authorized": False,
                "source_bound_conformer_derivation_evidence_sha256": (
                    derivation_evidence_sha256
                ),
            },
        ),
    )
    require_valid_all_atom_system(system)
    receipt = {
        "schema_id": SOURCE_BOUND_CONFORMER_ENSEMBLE_SCHEMA_ID,
        "policy_id": SOURCE_BOUND_CONFORMER_PREPARATION_POLICY_ID,
        "derivation_evidence": derivation_evidence,
        "derivation_evidence_sha256": derivation_evidence_sha256,
        "prepared_system_sha256": canonical_system_sha256(system),
        "prepared_topology_sha256": canonical_topology_sha256(system),
        "prepared_coordinates_sha256": canonical_coordinates_sha256(system),
        "deterministic": True,
        "development_only": True,
        "stage0_eligible": False,
        "fresh_execution_authorized": False,
        "scientifically_validated": False,
        "claim_safe": False,
    }
    return SourceBoundPreparedConformerEnsemble(
        source_system=source_system,
        source_sdf=source_sdf,
        system=system,
        raw_coordinates=raw_coordinate_tensor,
        records=tuple(records),
        receipt=receipt,
        receipt_sha256=_sha256(receipt),
    )


__all__ = [
    "CONFORMER_ENSEMBLE_SCHEMA_ID",
    "CONFORMER_PREPARATION_POLICY_ID",
    "SOURCE_BOUND_CONFORMER_DERIVATION_SCHEMA_ID",
    "SOURCE_BOUND_CONFORMER_ENSEMBLE_SCHEMA_ID",
    "SOURCE_BOUND_CONFORMER_PREPARATION_POLICY_ID",
    "SOURCE_BOUND_CONFORMER_SOURCE_INDEX_MAPPING_SCHEMA_ID",
    "ConformerPreparationConfig",
    "ConformerPreparationError",
    "PreparedConformerEnsemble",
    "PreparedConformerRecord",
    "SourceBoundPreparedConformerEnsemble",
    "SourceBoundPreparedConformerRecord",
    "prepare_deterministic_conformer_ensemble",
    "prepare_source_bound_conformer_ensemble",
]
