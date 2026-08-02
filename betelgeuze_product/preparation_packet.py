"""Canonical preparation packets shared by the legacy and V2 docking surfaces (P1-1).

Legacy and V2 previously each did their own receptor/ligand preparation. That
makes a legacy-vs-V2 comparison meaningless: a score difference could come from
the engine or from the fact that the two engines were handed different atoms,
a different pocket, or a different protonation state.

This module defines the one packet pair both surfaces must consume:

- ``PreparedReceptorPacket``: parsed atoms, elements, pocket identity, hashes.
- ``PreparedLigandPacket``: chemistry state, rotor perception, conformer
  ensemble identity, hashes.

Both carry an ``input_hash`` so a ``DockingResult`` can prove which prepared
input produced it, and both fail closed: preparation that cannot be trusted is
reported as blocked rather than silently degraded. The packets deliberately hold
no engine-specific fields, so neither adapter can smuggle preparation
differences into a comparison.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Sequence

PREPARATION_PACKET_SCHEMA_VERSION = "canonical_preparation_packet_v1"

#: Engine surfaces that may consume a packet. Kept here so the comparison
#: contract and the packet contract cannot drift apart.
ENGINE_SURFACE_LEGACY_PRODUCT = "legacy_product"
ENGINE_SURFACE_ENGINE_V2 = "engine_v2"
ENGINE_SURFACE_EXTERNAL_ORACLE = "external_oracle"

ENGINE_SURFACES = (
    ENGINE_SURFACE_LEGACY_PRODUCT,
    ENGINE_SURFACE_ENGINE_V2,
    ENGINE_SURFACE_EXTERNAL_ORACLE,
)

STATUS_RECEPTOR_READY = "prepared_receptor_ready"
STATUS_RECEPTOR_BLOCKED = "blocked_prepared_receptor"
STATUS_LIGAND_READY = "prepared_ligand_ready"
STATUS_LIGAND_BLOCKED = "blocked_prepared_ligand"

CLAIM_BOUNDARY = (
    "Canonical preparation packet only; it normalizes receptor atoms, pocket identity, ligand chemistry, "
    "rotor perception, and conformer ensemble identity so legacy and V2 adapters consume identical inputs. "
    "It does not dock, score, rank, or open an accuracy claim."
)


def _canonical_hash(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rounded_coords(coords: Sequence[Sequence[float]] | Any) -> list[list[float]]:
    rows: list[list[float]] = []
    for row in coords or []:
        rows.append([round(float(value), 4) for value in row])
    return rows


def _rounded_conformers(
    conformers: Sequence[Sequence[Sequence[float]]] | Any,
) -> list[list[list[float]]]:
    return [_rounded_coords(conformer) for conformer in conformers or []]


@dataclass(frozen=True)
class PocketIdentity:
    """The pocket both engines must dock into."""

    status: str
    method: str
    center: tuple[float, float, float]
    radius_a: float

    @property
    def ready(self) -> bool:
        return self.status == "pocket_ready" and self.radius_a > 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "method": self.method,
            "center": [round(float(value), 4) for value in self.center],
            "radius_a": round(float(self.radius_a), 4),
            "ready": self.ready,
        }

    @property
    def pocket_hash(self) -> str:
        return _canonical_hash(self.as_dict())


@dataclass(frozen=True)
class PreparedReceptorPacket:
    """Receptor side of the canonical packet."""

    target_id: str
    status: str
    source_kind: str
    atom_count: int
    elements: tuple[str, ...]
    coordinates: tuple[tuple[float, float, float], ...]
    pocket: PocketIdentity
    legacy_input_contract: dict[str, Any] = field(default_factory=dict)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ready(self) -> bool:
        return self.status == STATUS_RECEPTOR_READY

    @property
    def input_hash(self) -> str:
        return _canonical_hash(
            {
                "schema_version": PREPARATION_PACKET_SCHEMA_VERSION,
                "target_id": self.target_id,
                "source_kind": self.source_kind,
                "elements": list(self.elements),
                "coordinates": _rounded_coords(self.coordinates),
                "pocket": self.pocket.as_dict(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PREPARATION_PACKET_SCHEMA_VERSION,
            "packet_kind": "prepared_receptor",
            "target_id": self.target_id,
            "status": self.status,
            "ready": self.ready,
            "source_kind": self.source_kind,
            "atom_count": int(self.atom_count),
            "element_count": len(set(self.elements)),
            "pocket": self.pocket.as_dict(),
            "pocket_hash": self.pocket.pocket_hash,
            "input_hash": self.input_hash,
            "legacy_input_contract": dict(self.legacy_input_contract),
            "blockers": list(self.blockers),
            "claim_boundary": CLAIM_BOUNDARY,
        }


@dataclass(frozen=True)
class PreparedLigandPacket:
    """Ligand side of the canonical packet."""

    ligand_id: str
    status: str
    smiles: str
    atom_count: int
    flexibility_lane: str
    atom_elements: tuple[str, ...] = field(default_factory=tuple)
    conformer_coordinates: tuple[tuple[tuple[float, float, float], ...], ...] = field(
        default_factory=tuple
    )
    rotor_perception: dict[str, Any] = field(default_factory=dict)
    conformer_ensemble: dict[str, Any] = field(default_factory=dict)
    chemistry_validity: dict[str, Any] = field(default_factory=dict)
    blockers: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ready(self) -> bool:
        return self.status == STATUS_LIGAND_READY

    @property
    def conformer_ids(self) -> tuple[str, ...]:
        ids = self.conformer_ensemble.get("conformer_ids")
        return tuple(str(value) for value in ids or ())

    @property
    def input_hash(self) -> str:
        return _canonical_hash(
            {
                "schema_version": PREPARATION_PACKET_SCHEMA_VERSION,
                "ligand_id": self.ligand_id,
                "smiles": self.smiles,
                "flexibility_lane": self.flexibility_lane,
                "conformer_ids": list(self.conformer_ids),
                "atom_elements": list(self.atom_elements),
                "conformer_coordinates": _rounded_conformers(self.conformer_coordinates),
                "rotor_signature": [
                    [rotor.get("rotor_class"), rotor.get("begin_atom_idx"), rotor.get("end_atom_idx")]
                    for rotor in self.rotor_perception.get("rotors") or []
                ],
                "ensemble_parameter_digest": (
                    self.conformer_ensemble.get("provenance", {}) or {}
                ).get("parameter_digest", ""),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PREPARATION_PACKET_SCHEMA_VERSION,
            "packet_kind": "prepared_ligand",
            "ligand_id": self.ligand_id,
            "status": self.status,
            "ready": self.ready,
            "smiles": self.smiles,
            "atom_count": int(self.atom_count),
            "flexibility_lane": self.flexibility_lane,
            "atom_elements": list(self.atom_elements),
            "conformer_coordinate_count": len(self.conformer_coordinates),
            "conformer_coordinates_present": bool(self.conformer_coordinates),
            "rotor_count": int(self.rotor_perception.get("rotor_count") or 0),
            "restrained_rotor_count": int(self.rotor_perception.get("restrained_rotor_count") or 0),
            "rigid_component_count": int(self.rotor_perception.get("rigid_component_count") or 0),
            "macrocycle_present": bool(self.rotor_perception.get("macrocycle_present")),
            "retained_conformer_count": int(
                self.conformer_ensemble.get("retained_conformer_count") or 0
            ),
            "conformer_ids": list(self.conformer_ids),
            "input_hash": self.input_hash,
            "rotor_perception": dict(self.rotor_perception),
            "conformer_ensemble": dict(self.conformer_ensemble),
            "chemistry_validity": dict(self.chemistry_validity),
            "blockers": list(self.blockers),
            "claim_boundary": CLAIM_BOUNDARY,
        }


@dataclass(frozen=True)
class PreparationPacket:
    """The receptor+ligand pair handed to every engine surface."""

    receptor: PreparedReceptorPacket
    ligand: PreparedLigandPacket

    @property
    def ready(self) -> bool:
        return self.receptor.ready and self.ligand.ready

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(self.receptor.blockers) + tuple(self.ligand.blockers)

    @property
    def prepared_input_hash(self) -> str:
        """Joint hash proving both engines saw the same prepared input."""

        return _canonical_hash(
            {
                "receptor_input_hash": self.receptor.input_hash,
                "ligand_input_hash": self.ligand.input_hash,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PREPARATION_PACKET_SCHEMA_VERSION,
            "status": "preparation_packet_ready" if self.ready else "blocked_preparation_packet",
            "ready": self.ready,
            "prepared_input_hash": self.prepared_input_hash,
            "receptor": self.receptor.to_dict(),
            "ligand": self.ligand.to_dict(),
            "blockers": list(self.blockers),
            "supported_engine_surfaces": list(ENGINE_SURFACES),
            "claim_boundary": CLAIM_BOUNDARY,
        }

    def adapter_input(self, engine_surface: str) -> dict[str, Any]:
        """Return the identical input view handed to one engine surface.

        The view is engine-independent by construction: only the surface label
        changes, so a legacy-vs-V2 delta cannot be explained by preparation.
        """

        surface = str(engine_surface)
        if surface not in ENGINE_SURFACES:
            raise ValueError(f"unsupported_engine_surface:{surface or '<empty>'}")
        return {
            "engine_surface": surface,
            "prepared_input_hash": self.prepared_input_hash,
            "receptor_input_hash": self.receptor.input_hash,
            "ligand_input_hash": self.ligand.input_hash,
            "pocket": self.receptor.pocket.as_dict(),
            "receptor_elements": list(self.receptor.elements),
            "receptor_coordinates": _rounded_coords(self.receptor.coordinates),
            "ligand_smiles": self.ligand.smiles,
            "ligand_flexibility_lane": self.ligand.flexibility_lane,
            "ligand_conformer_ids": list(self.ligand.conformer_ids),
            "ligand_atom_elements": list(self.ligand.atom_elements),
            "ligand_conformer_coordinates": _rounded_conformers(
                self.ligand.conformer_coordinates
            ),
            "ready": self.ready,
            "blockers": list(self.blockers),
        }


__all__ = [
    "CLAIM_BOUNDARY",
    "ENGINE_SURFACES",
    "ENGINE_SURFACE_ENGINE_V2",
    "ENGINE_SURFACE_EXTERNAL_ORACLE",
    "ENGINE_SURFACE_LEGACY_PRODUCT",
    "PREPARATION_PACKET_SCHEMA_VERSION",
    "PocketIdentity",
    "PreparationPacket",
    "PreparedLigandPacket",
    "PreparedReceptorPacket",
    "STATUS_LIGAND_BLOCKED",
    "STATUS_LIGAND_READY",
    "STATUS_RECEPTOR_BLOCKED",
    "STATUS_RECEPTOR_READY",
]
