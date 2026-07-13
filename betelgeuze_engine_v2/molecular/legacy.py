"""Explicit compatibility boundary between canonical v2 and legacy EngineState.

The legacy state contains coordinates and integer type arrays but no complete
topology.  The forward adapter embeds a versioned topology payload in metadata;
the reverse adapter rejects states without that payload unless the caller opts
into visibly lossy inference.
"""

from __future__ import annotations

from dataclasses import fields, replace
import hashlib
from typing import Any, Callable, Mapping

import torch

from betelgeuze_engine.contracts.state import EngineState
from .models import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    StructureProvenance,
    UnitCell,
    element_for_atomic_number,
)
from .validation import require_valid_all_atom_system


LEGACY_METADATA_KEY = "betelgeuze_engine_v2_contract"
LEGACY_ADAPTER_VERSION = "1.2.0"

_STANDARD_RESIDUE_CODES = {
    "ALA": 1,
    "ARG": 2,
    "ASN": 3,
    "ASP": 4,
    "CYS": 5,
    "GLN": 6,
    "GLU": 7,
    "GLY": 8,
    "HIS": 9,
    "ILE": 10,
    "LEU": 11,
    "LYS": 12,
    "MET": 13,
    "PHE": 14,
    "PRO": 15,
    "SER": 16,
    "THR": 17,
    "TRP": 18,
    "TYR": 19,
    "VAL": 20,
    "SEC": 21,
    "PYL": 22,
}


class LegacyAdapterError(ValueError):
    """Raised when a lossless legacy conversion cannot be guaranteed."""


def _mutable_metadata_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _mutable_metadata_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_mutable_metadata_value(item) for item in value]
    return value


def _record_dict(record: object) -> dict[str, Any]:
    payload = {item.name: getattr(record, item.name) for item in fields(record)}
    if "metadata" in payload:
        payload["metadata"] = _mutable_metadata_value(payload["metadata"])
    return payload


def _tensor_fingerprint(tensor: torch.Tensor) -> str:
    value = tensor.detach().to(device="cpu").contiguous()
    digest = hashlib.sha256()
    digest.update(str(tuple(value.shape)).encode("ascii"))
    digest.update(str(value.dtype).encode("ascii"))
    digest.update(value.numpy().tobytes(order="C"))
    return digest.hexdigest()


def _topology_payload(
    system: AllAtomSystem,
    *,
    encoding: Mapping[str, str],
    coordinates: torch.Tensor,
    atom_types: torch.Tensor,
    residue_types: torch.Tensor,
    legacy_box: torch.Tensor | None,
) -> dict[str, Any]:
    cell_payload = None
    if system.cell is not None:
        cell_payload = {
            "vectors": system.cell.vectors.detach().cpu().tolist(),
            "periodic": list(system.cell.periodic),
        }
    return {
        "adapter_version": LEGACY_ADAPTER_VERSION,
        "schema_id": system.schema_id,
        "system_id": system.system_id,
        "coordinate_unit": system.coordinate_unit,
        "atoms": [_record_dict(record) for record in system.atoms],
        "bonds": [_record_dict(record) for record in system.bonds],
        "residues": [_record_dict(record) for record in system.residues],
        "chains": [_record_dict(record) for record in system.chains],
        "cell": cell_payload,
        "provenance": _record_dict(system.provenance),
        "system_metadata": _mutable_metadata_value(system.metadata),
        "legacy_encoding": dict(encoding),
        "legacy_state_contract": {
            "atom_types": atom_types.detach().cpu().tolist(),
            "residue_types": residue_types.detach().cpu().tolist(),
            "atom_types_sha256": _tensor_fingerprint(atom_types),
            "residue_types_sha256": _tensor_fingerprint(residue_types),
            "coordinates_sha256": _tensor_fingerprint(coordinates),
            "box_sha256": None if legacy_box is None else _tensor_fingerprint(legacy_box),
            "coordinate_order_policy": "atom_order_is_immutable",
        },
    }


def _legacy_box(cell: UnitCell | None, *, coords: torch.Tensor) -> torch.Tensor | None:
    if cell is None:
        return None
    if not all(cell.periodic):
        raise LegacyAdapterError("legacy EngineState cannot preserve partially periodic unit cells")
    try:
        lengths = cell.orthorhombic_lengths()
    except ValueError as exc:
        raise LegacyAdapterError("legacy EngineState cannot preserve triclinic unit cells") from exc
    if not bool((lengths > 0.0).all().detach().cpu().item()):
        raise LegacyAdapterError("unit-cell lengths must be positive")
    return lengths.to(device=coords.device, dtype=coords.dtype)


def to_legacy_engine_state(
    system: AllAtomSystem,
    *,
    atom_type_encoder: Callable[[Atom], int] | None = None,
    residue_type_encoder: Callable[[Residue], int] | None = None,
    dtype: torch.dtype | None = None,
    device: torch.device | str | None = None,
) -> EngineState:
    """Create a legacy state while embedding enough topology for round-trip.

    Default atom types are atomic numbers.  Default residue types are standard
    amino-acid codes per atom, with zero reserved for non-standard residues.
    Custom encoders affect only the legacy arrays; the canonical topology is
    always retained in the namespaced metadata payload.
    """

    require_valid_all_atom_system(system)
    if LEGACY_METADATA_KEY in system.metadata:
        raise LegacyAdapterError(f"system metadata uses reserved key {LEGACY_METADATA_KEY!r}")

    target_device = device if device is not None else system.coordinates.device
    target_dtype = dtype if dtype is not None else system.coordinates.dtype
    if target_dtype not in (torch.float32, torch.float64):
        raise LegacyAdapterError(
            "legacy round-trip supports only torch.float32 or torch.float64 coordinates"
        )
    coords = system.coordinates.to(device=target_device, dtype=target_dtype)

    atom_encoder = atom_type_encoder or (lambda atom: int(atom.atomic_number))
    residue_encoder = residue_type_encoder or (
        lambda residue: int(_STANDARD_RESIDUE_CODES.get(residue.name.upper(), 0))
    )
    atom_types = torch.tensor(
        [int(atom_encoder(atom)) for atom in system.atoms],
        dtype=torch.long,
        device=target_device,
    )
    residue_codes = [int(residue_encoder(residue)) for residue in system.residues]
    residue_types = torch.tensor(
        [residue_codes[atom.residue_index] for atom in system.atoms],
        dtype=torch.long,
        device=target_device,
    )
    encoding = {
        "atom_types": "custom" if atom_type_encoder is not None else "atomic_number",
        "residue_types": "custom" if residue_type_encoder is not None else "standard_residue_code_per_atom",
    }
    legacy_box = _legacy_box(system.cell, coords=coords)
    metadata = _mutable_metadata_value(system.metadata)
    metadata[LEGACY_METADATA_KEY] = _topology_payload(
        system,
        encoding=encoding,
        coordinates=coords,
        atom_types=atom_types,
        residue_types=residue_types,
        legacy_box=legacy_box,
    )
    return EngineState(
        coords=coords,
        atom_types=atom_types,
        residue_types=residue_types,
        box=legacy_box,
        metadata=metadata,
    )


def _mapping_list(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(record, Mapping) for record in value):
        raise LegacyAdapterError(f"embedded topology field {key!r} must be a list of mappings")
    return list(value)


def _from_embedded_payload(
    state: EngineState,
    payload: Mapping[str, Any],
    *,
    allow_coordinate_updates: bool,
) -> AllAtomSystem:
    if payload.get("adapter_version") != LEGACY_ADAPTER_VERSION:
        raise LegacyAdapterError(
            f"unsupported legacy adapter version {payload.get('adapter_version')!r}; "
            f"expected {LEGACY_ADAPTER_VERSION!r}"
        )
    try:
        atoms = tuple(Atom(**dict(record)) for record in _mapping_list(payload, "atoms"))
        bonds = tuple(Bond(**dict(record)) for record in _mapping_list(payload, "bonds"))
        residues = tuple(Residue(**dict(record)) for record in _mapping_list(payload, "residues"))
        chains = tuple(Chain(**dict(record)) for record in _mapping_list(payload, "chains"))
        provenance_raw = payload.get("provenance")
        if not isinstance(provenance_raw, Mapping):
            raise LegacyAdapterError("embedded provenance must be a mapping")
        provenance = StructureProvenance(**dict(provenance_raw))
        state_contract = payload.get("legacy_state_contract")
        if not isinstance(state_contract, Mapping):
            raise LegacyAdapterError("embedded legacy_state_contract must be a mapping")
        expected_atom_types = state_contract.get("atom_types")
        expected_residue_types = state_contract.get("residue_types")
        if state.atom_types.detach().cpu().tolist() != expected_atom_types:
            raise LegacyAdapterError("legacy atom_types changed or atom order cannot be verified")
        if state.residue_types is None or state.residue_types.detach().cpu().tolist() != expected_residue_types:
            raise LegacyAdapterError("legacy residue_types changed or atom order cannot be verified")
        if _tensor_fingerprint(state.atom_types) != state_contract.get("atom_types_sha256"):
            raise LegacyAdapterError("legacy atom_types fingerprint mismatch")
        if _tensor_fingerprint(state.residue_types) != state_contract.get("residue_types_sha256"):
            raise LegacyAdapterError("legacy residue_types fingerprint mismatch")

        coordinates_changed = _tensor_fingerprint(state.coords) != state_contract.get("coordinates_sha256")
        cell_raw = payload.get("cell")
        cell = None
        box_changed = False
        if cell_raw is not None:
            if not isinstance(cell_raw, Mapping):
                raise LegacyAdapterError("embedded cell must be a mapping")
            if state.box is None:
                raise LegacyAdapterError("legacy periodic topology requires a current box")
            box = torch.as_tensor(state.box, dtype=state.coords.dtype, device=state.coords.device)
            if box.ndim == 0:
                box = box.repeat(3)
            if box.shape != (3,) or not bool(torch.isfinite(box).all().item()) or bool((box <= 0.0).any().item()):
                raise LegacyAdapterError("legacy box must be a finite positive scalar or length-three tensor")
            cell = UnitCell.orthorhombic(box, dtype=state.coords.dtype, device=state.coords.device)
            expected_box_fingerprint = state_contract.get("box_sha256")
            box_changed = _tensor_fingerprint(box) != expected_box_fingerprint
        elif state.box is not None:
            raise LegacyAdapterError("legacy state introduced a box absent from canonical topology")
        if (coordinates_changed or box_changed) and not allow_coordinate_updates:
            raise LegacyAdapterError(
                "legacy coordinates or box changed; set allow_coordinate_updates=True only when "
                "the operation preserves canonical atom order"
            )
        if coordinates_changed or box_changed:
            operations = provenance.operations + ("legacy_state_coordinates_or_box_updated",)
            provenance = replace(provenance, operations=operations, claim_safe=False)
        system_metadata = payload.get("system_metadata", {})
        if not isinstance(system_metadata, Mapping):
            raise LegacyAdapterError("embedded system_metadata must be a mapping")
        system = AllAtomSystem(
            system_id=str(payload.get("system_id", "")),
            atoms=atoms,
            bonds=bonds,
            residues=residues,
            chains=chains,
            coordinates=state.coords,
            provenance=provenance,
            cell=cell,
            coordinate_unit=str(payload.get("coordinate_unit", "angstrom")),
            metadata=dict(system_metadata),
            schema_id=str(payload.get("schema_id", "")),
        )
    except LegacyAdapterError:
        raise
    except (TypeError, ValueError, KeyError) as exc:
        raise LegacyAdapterError(f"invalid embedded canonical topology: {exc}") from exc
    require_valid_all_atom_system(system)
    return system


def _infer_lossy_topology(state: EngineState) -> AllAtomSystem:
    atomic_numbers = [int(value) for value in state.atom_types.detach().cpu().tolist()]
    try:
        elements = [element_for_atomic_number(value) for value in atomic_numbers]
    except ValueError as exc:
        raise LegacyAdapterError(
            "lossy legacy inference requires atom_types to contain atomic numbers in [1, 118]"
        ) from exc
    atoms = tuple(
        Atom(
            index=index,
            name=f"{element}{index + 1}",
            element=element,
            atomic_number=atomic_number,
            residue_index=0,
            formal_charge_known=False,
        )
        for index, (element, atomic_number) in enumerate(zip(elements, atomic_numbers))
    )
    residue = Residue(
        index=0,
        name="LEG",
        chain_index=0,
        sequence_number=1,
        atom_indices=tuple(range(len(atoms))),
        entity_type="unknown",
        hetero=True,
    )
    chain = Chain(index=0, chain_id="A", residue_indices=(0,))
    cell = None
    if state.box is not None:
        box = torch.as_tensor(state.box, dtype=state.coords.dtype, device=state.coords.device)
        if box.ndim == 0:
            box = box.repeat(3)
        if box.numel() != 3:
            raise LegacyAdapterError("legacy box must be scalar or length three")
        cell = UnitCell.orthorhombic(box.reshape(3), dtype=state.coords.dtype, device=state.coords.device)
    system = AllAtomSystem(
        system_id=str(state.metadata.get("system_id", "legacy-inferred")),
        atoms=atoms,
        bonds=(),
        residues=(residue,),
        chains=(chain,),
        coordinates=state.coords,
        provenance=StructureProvenance(
            source_format="legacy_engine_state",
            parser_name="betelgeuze_engine_v2.lossy_legacy_adapter",
            parser_version=LEGACY_ADAPTER_VERSION,
            operations=("lossy_topology_inference",),
            preparation_ready=False,
            claim_safe=False,
        ),
        cell=cell,
        metadata={"legacy_inference": "atom_types_interpreted_as_atomic_numbers"},
    )
    require_valid_all_atom_system(system)
    return system


def from_legacy_engine_state(
    state: EngineState,
    *,
    allow_lossy_inference: bool = False,
    allow_coordinate_updates: bool = False,
) -> AllAtomSystem:
    """Restore a canonical system from legacy state metadata.

    ``allow_lossy_inference`` is false by default because a bare EngineState has
    no bonds, residue boundaries, atom names, stereochemistry, or provenance.
    """

    payload = state.metadata.get(LEGACY_METADATA_KEY)
    if payload is None:
        if not allow_lossy_inference:
            raise LegacyAdapterError(
                "legacy EngineState lacks embedded canonical topology; "
                "set allow_lossy_inference=True only for non-claimable compatibility work"
            )
        return _infer_lossy_topology(state)
    if not isinstance(payload, Mapping):
        raise LegacyAdapterError(f"legacy metadata field {LEGACY_METADATA_KEY!r} must be a mapping")
    return _from_embedded_payload(
        state,
        payload,
        allow_coordinate_updates=bool(allow_coordinate_updates),
    )


# Descriptive aliases for callers migrating from earlier naming conventions.
all_atom_to_legacy_state = to_legacy_engine_state
legacy_state_to_all_atom = from_legacy_engine_state
