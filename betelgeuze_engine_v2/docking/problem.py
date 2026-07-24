"""Authenticated generic docking-problem and search-space derivation contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem,
    canonical_system_sha256,
    canonical_topology_sha256,
    require_valid_all_atom_system,
)

from .identity import DockingProblemIdentity, PocketDefinition
from .identity import coordinate_fingerprint
from .molecular_torsion import MolecularTorsionSearchReceipt
from .proposals import TorsionSearchSpace


SEARCH_SPACE_DERIVATION_RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_search_space_derivation_receipt/1.0.0"
)
DOCKING_PROBLEM_INPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_authenticated_docking_problem_input/1.0.0"
)
RIGID_SEARCH_SPACE_DERIVATION_POLICY_ID = (
    "canonical_ligand_coordinates_as_independent_rigid_roots/1.0.0"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class DockingProblemInputError(ValueError):
    """A docking problem is not authenticated to its concrete molecular state."""


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
        raise DockingProblemInputError(
            "docking problem input is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(
    value: object,
    *,
    name: str,
    allow_empty: bool = False,
) -> str:
    if allow_empty and value == "":
        return ""
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise DockingProblemInputError(f"{name} must be a lowercase SHA-256")
    return value


@dataclass(frozen=True, slots=True)
class SearchSpaceDerivationReceipt:
    """Receipt binding one immutable search space to one ligand state."""

    ligand_system_sha256: str
    ligand_topology_sha256: str
    ligand_coordinate_fingerprint_sha256: str
    search_space_sha256: str
    derivation_policy_id: str
    derivation_config_sha256: str
    parent_derivation_receipt_sha256: str
    atom_count: int
    coordinate_dtype: str
    schema_id: str = SEARCH_SPACE_DERIVATION_RECEIPT_SCHEMA_ID

    def __post_init__(self) -> None:
        if self.schema_id != SEARCH_SPACE_DERIVATION_RECEIPT_SCHEMA_ID:
            raise DockingProblemInputError(
                "unsupported search-space derivation receipt schema"
            )
        for name in (
            "ligand_system_sha256",
            "ligand_topology_sha256",
            "ligand_coordinate_fingerprint_sha256",
            "search_space_sha256",
            "derivation_config_sha256",
        ):
            object.__setattr__(
                self,
                name,
                _digest(getattr(self, name), name=name),
            )
        object.__setattr__(
            self,
            "parent_derivation_receipt_sha256",
            _digest(
                self.parent_derivation_receipt_sha256,
                name="parent_derivation_receipt_sha256",
                allow_empty=True,
            ),
        )
        policy = str(self.derivation_policy_id or "").strip()
        if not policy:
            raise DockingProblemInputError(
                "derivation_policy_id must be non-empty"
            )
        atom_count = int(self.atom_count)
        if atom_count < 1:
            raise DockingProblemInputError("atom_count must be positive")
        dtype = str(self.coordinate_dtype or "").strip()
        if dtype not in {"float32", "float64"}:
            raise DockingProblemInputError(
                "coordinate_dtype must be float32 or float64"
            )
        object.__setattr__(self, "derivation_policy_id", policy)
        object.__setattr__(self, "atom_count", atom_count)
        object.__setattr__(self, "coordinate_dtype", dtype)

    def _payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "ligand_system_sha256": self.ligand_system_sha256,
            "ligand_topology_sha256": self.ligand_topology_sha256,
            "ligand_coordinate_fingerprint_sha256": (
                self.ligand_coordinate_fingerprint_sha256
            ),
            "search_space_sha256": self.search_space_sha256,
            "derivation_policy_id": self.derivation_policy_id,
            "derivation_config_sha256": self.derivation_config_sha256,
            "parent_derivation_receipt_sha256": (
                self.parent_derivation_receipt_sha256
            ),
            "atom_count": self.atom_count,
            "coordinate_dtype": self.coordinate_dtype,
            "device": "cpu",
            "authenticated_to_concrete_ligand_state": True,
        }

    @property
    def fingerprint_sha256(self) -> str:
        return _sha256(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {
            **self._payload(),
            "receipt_sha256": self.fingerprint_sha256,
        }


def bind_molecular_torsion_search_space(
    ligand: AllAtomSystem,
    search_space: TorsionSearchSpace,
    receipt: MolecularTorsionSearchReceipt,
) -> SearchSpaceDerivationReceipt:
    """Authenticate an existing molecular-torsion receipt to concrete objects."""

    if not isinstance(ligand, AllAtomSystem):
        raise TypeError("ligand must be AllAtomSystem")
    if not isinstance(search_space, TorsionSearchSpace):
        raise TypeError("search_space must be TorsionSearchSpace")
    if not isinstance(receipt, MolecularTorsionSearchReceipt):
        raise TypeError("receipt must be MolecularTorsionSearchReceipt")
    search_space.assert_integrity()
    ligand_system_sha256 = canonical_system_sha256(ligand)
    ligand_topology_sha256 = canonical_topology_sha256(ligand)
    ligand_coordinate_sha256 = coordinate_fingerprint(ligand.coordinates[0])
    if (
        receipt.system_sha256 != ligand_system_sha256
        or receipt.topology_sha256 != ligand_topology_sha256
        or receipt.input_coordinate_sha256 != ligand_coordinate_sha256
        or receipt.search_space_sha256 != search_space.fingerprint_sha256
        or receipt.atom_count != ligand.atom_count
    ):
        raise DockingProblemInputError(
            "molecular torsion receipt is cross-wired to another ligand or space"
        )
    return SearchSpaceDerivationReceipt(
        ligand_system_sha256=ligand_system_sha256,
        ligand_topology_sha256=ligand_topology_sha256,
        ligand_coordinate_fingerprint_sha256=ligand_coordinate_sha256,
        search_space_sha256=search_space.fingerprint_sha256,
        derivation_policy_id=(
            "bounded_molecular_graph_torsion_tree/"
            f"{receipt.schema_id.rsplit('/', 1)[-1]}"
        ),
        derivation_config_sha256=receipt.config_sha256,
        parent_derivation_receipt_sha256=receipt.fingerprint_sha256,
        atom_count=ligand.atom_count,
        coordinate_dtype=str(ligand.coordinates.dtype).removeprefix("torch."),
    )


def build_authenticated_rigid_search_space(
    ligand: AllAtomSystem,
    *,
    source_receipt_sha256: str = "",
) -> tuple[TorsionSearchSpace, SearchSpaceDerivationReceipt]:
    """Build a zero-torsion search space directly from canonical ligand bytes."""

    if not isinstance(ligand, AllAtomSystem):
        raise TypeError("ligand must be AllAtomSystem")
    require_valid_all_atom_system(ligand)
    if ligand.model_count != 1:
        raise DockingProblemInputError(
            "rigid search-space derivation requires one ligand model"
        )
    coordinates = ligand.coordinates[0]
    if coordinates.device.type != "cpu" or coordinates.dtype not in {
        torch.float32,
        torch.float64,
    }:
        raise DockingProblemInputError(
            "rigid search-space derivation requires CPU float32 or float64"
        )
    atom_count = ligand.atom_count
    search_space = TorsionSearchSpace(
        local_offsets=torch.zeros_like(coordinates),
        parent=torch.full((atom_count,), -1, dtype=torch.long),
        local_axes=torch.tensor(
            [[0.0, 0.0, 1.0]] * atom_count,
            dtype=coordinates.dtype,
        ),
        rotatable_mask=torch.zeros(atom_count, dtype=torch.bool),
        root_positions=coordinates,
    )
    source_digest = _digest(
        source_receipt_sha256,
        name="source_receipt_sha256",
        allow_empty=True,
    )
    config_sha256 = _sha256(
        {
            "policy_id": RIGID_SEARCH_SPACE_DERIVATION_POLICY_ID,
            "source_receipt_sha256": source_digest,
        }
    )
    receipt = SearchSpaceDerivationReceipt(
        ligand_system_sha256=canonical_system_sha256(ligand),
        ligand_topology_sha256=canonical_topology_sha256(ligand),
        ligand_coordinate_fingerprint_sha256=coordinate_fingerprint(
            coordinates
        ),
        search_space_sha256=search_space.fingerprint_sha256,
        derivation_policy_id=RIGID_SEARCH_SPACE_DERIVATION_POLICY_ID,
        derivation_config_sha256=config_sha256,
        parent_derivation_receipt_sha256=source_digest,
        atom_count=atom_count,
        coordinate_dtype=str(coordinates.dtype).removeprefix("torch."),
    )
    return search_space, receipt


@dataclass(frozen=True, slots=True)
class DockingProblemInput:
    """Concrete receptor, ligand, pocket, and search space authenticated together."""

    receptor: AllAtomSystem
    ligand: AllAtomSystem
    pocket: PocketDefinition
    search_space: TorsionSearchSpace
    search_space_derivation: SearchSpaceDerivationReceipt
    source_artifact_sha256_by_role: Mapping[str, str] = field(
        default_factory=dict
    )
    schema_id: str = DOCKING_PROBLEM_INPUT_SCHEMA_ID
    _input_fingerprint_sha256: str = field(init=False, repr=False)
    _identity: DockingProblemIdentity = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != DOCKING_PROBLEM_INPUT_SCHEMA_ID:
            raise DockingProblemInputError(
                "unsupported authenticated docking problem input schema"
            )
        if not isinstance(self.receptor, AllAtomSystem) or not isinstance(
            self.ligand, AllAtomSystem
        ):
            raise TypeError("receptor and ligand must be AllAtomSystem")
        if not isinstance(self.pocket, PocketDefinition):
            raise TypeError("pocket must be PocketDefinition")
        if not isinstance(self.search_space, TorsionSearchSpace):
            raise TypeError("search_space must be TorsionSearchSpace")
        if not isinstance(
            self.search_space_derivation,
            SearchSpaceDerivationReceipt,
        ):
            raise TypeError(
                "search_space_derivation must be SearchSpaceDerivationReceipt"
            )
        require_valid_all_atom_system(self.receptor)
        require_valid_all_atom_system(self.ligand)
        self.search_space.assert_integrity()

        artifact_bindings: dict[str, str] = {}
        for role, digest in self.source_artifact_sha256_by_role.items():
            normalized_role = str(role or "").strip()
            if not normalized_role or normalized_role in artifact_bindings:
                raise DockingProblemInputError(
                    "source artifact roles must be unique and non-empty"
                )
            artifact_bindings[normalized_role] = _digest(
                digest,
                name=f"source_artifact_sha256_by_role[{normalized_role!r}]",
            )
        object.__setattr__(
            self,
            "source_artifact_sha256_by_role",
            MappingProxyType(dict(sorted(artifact_bindings.items()))),
        )
        self._verify_bindings()
        input_fingerprint = _sha256(self._input_payload())
        identity = DockingProblemIdentity(
            receptor_system_sha256=canonical_system_sha256(self.receptor),
            ligand_system_sha256=canonical_system_sha256(self.ligand),
            pocket_definition_sha256=self.pocket.fingerprint_sha256,
            coordinate_frame_id=self.pocket.coordinate_frame_id,
            metadata={
                "authenticated_problem_input": True,
                "problem_input_schema_id": self.schema_id,
                "problem_input_fingerprint_sha256": input_fingerprint,
                "search_space_derivation_receipt_sha256": (
                    self.search_space_derivation.fingerprint_sha256
                ),
            },
        )
        object.__setattr__(
            self,
            "_input_fingerprint_sha256",
            input_fingerprint,
        )
        object.__setattr__(self, "_identity", identity)

    def _verify_bindings(self) -> None:
        receptor_sha256 = canonical_system_sha256(self.receptor)
        ligand_sha256 = canonical_system_sha256(self.ligand)
        derivation = self.search_space_derivation
        ligand_coordinates = self.ligand.coordinates
        if self.receptor.model_count != 1 or self.ligand.model_count != 1:
            raise DockingProblemInputError(
                "authenticated docking requires one receptor and ligand model"
            )
        if self.pocket.receptor_system_sha256 != receptor_sha256:
            raise DockingProblemInputError(
                "pocket definition is cross-wired to another receptor"
            )
        if (
            derivation.ligand_system_sha256 != ligand_sha256
            or derivation.ligand_topology_sha256
            != canonical_topology_sha256(self.ligand)
            or derivation.ligand_coordinate_fingerprint_sha256
            != coordinate_fingerprint(ligand_coordinates[0])
            or derivation.search_space_sha256
            != self.search_space.fingerprint_sha256
            or derivation.atom_count != self.ligand.atom_count
            or derivation.coordinate_dtype
            != str(ligand_coordinates.dtype).removeprefix("torch.")
            or self.search_space.atom_count != self.ligand.atom_count
        ):
            raise DockingProblemInputError(
                "search-space derivation is cross-wired to another ligand or space"
            )

    def _input_payload(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "receptor_system_sha256": canonical_system_sha256(self.receptor),
            "ligand_system_sha256": canonical_system_sha256(self.ligand),
            "pocket_definition_sha256": self.pocket.fingerprint_sha256,
            "search_space_sha256": self.search_space.fingerprint_sha256,
            "search_space_derivation_receipt_sha256": (
                self.search_space_derivation.fingerprint_sha256
            ),
            "coordinate_frame_id": self.pocket.coordinate_frame_id,
            "source_artifact_sha256_by_role": dict(
                self.source_artifact_sha256_by_role
            ),
            "authenticated_to_concrete_molecular_state": True,
        }

    @property
    def input_fingerprint_sha256(self) -> str:
        self.assert_integrity()
        return self._input_fingerprint_sha256

    @property
    def identity(self) -> DockingProblemIdentity:
        self.assert_integrity()
        return self._identity

    def assert_integrity(self) -> None:
        self.search_space.assert_integrity()
        self._verify_bindings()
        if _sha256(self._input_payload()) != self._input_fingerprint_sha256:
            raise DockingProblemInputError(
                "authenticated docking problem input changed after construction"
            )

    def to_dict(self) -> dict[str, object]:
        self.assert_integrity()
        return {
            **self._input_payload(),
            "input_fingerprint_sha256": self._input_fingerprint_sha256,
            "docking_problem_fingerprint_sha256": (
                self._identity.fingerprint_sha256
            ),
            "search_space_derivation": self.search_space_derivation.to_dict(),
            "pocket": self.pocket.to_dict(),
        }


__all__ = [
    "DOCKING_PROBLEM_INPUT_SCHEMA_ID",
    "RIGID_SEARCH_SPACE_DERIVATION_POLICY_ID",
    "SEARCH_SPACE_DERIVATION_RECEIPT_SCHEMA_ID",
    "DockingProblemInput",
    "DockingProblemInputError",
    "SearchSpaceDerivationReceipt",
    "bind_molecular_torsion_search_space",
    "build_authenticated_rigid_search_space",
]
