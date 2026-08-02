"""Canonical preparation service (P1-1).

One entry point builds the receptor/ligand packet pair that every engine
surface consumes. Legacy and V2 must not prepare their own inputs: if they do,
a shadow comparison cannot separate an engine difference from a preparation
difference.

Preparation fails closed. A receptor whose atoms cannot be trusted, a ligand
whose flexibility cannot be perceived (for example a macrocycle), or a ligand
with no usable conformer produces a blocked packet with named blockers instead
of a partially prepared input that still looks dockable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from betelgeuze_engine.chemistry.conformer_ensemble import (
    DEFAULT_MAX_CONFORMERS,
    DEFAULT_SEED,
    generate_conformer_ensemble,
)
from betelgeuze_engine.chemistry.rotor_perception import perceive_ligand_rotors
from betelgeuze_product.preparation_packet import (
    STATUS_LIGAND_BLOCKED,
    STATUS_LIGAND_READY,
    STATUS_RECEPTOR_BLOCKED,
    STATUS_RECEPTOR_READY,
    PocketIdentity,
    PreparationPacket,
    PreparedLigandPacket,
    PreparedReceptorPacket,
)
from betelgeuze_product.structure_analysis import analyze_structure_source


def _pocket_from_payload(payload: dict[str, Any]) -> PocketIdentity:
    center = payload.get("pocket_center") or [0.0, 0.0, 0.0]
    try:
        cx, cy, cz = (float(center[0]), float(center[1]), float(center[2]))
    except (TypeError, ValueError, IndexError):
        cx, cy, cz = 0.0, 0.0, 0.0
    try:
        radius = float(payload.get("pocket_radius_a") or 0.0)
    except (TypeError, ValueError):
        radius = 0.0
    return PocketIdentity(
        status=str(payload.get("status") or "blocked_pocket_not_detected"),
        method=str(payload.get("method") or ""),
        center=(cx, cy, cz),
        radius_a=radius,
    )


def _legacy_input_blocked_row(analysis: dict[str, Any]) -> dict[str, Any]:
    """Extract the fail-closed intake reason, if intake refused the structure.

    The legacy product path needs the *reason*, not just the fact that a blocker
    exists: "coordinates were unparseable" and "structure carried no atoms" lead
    to different operator actions, and collapsing them was the original P0-3 bug.
    """

    from betelgeuze_product.legacy_input_contract import (
        LEGACY_INPUT_FAIL_CLOSED_REASON_CODES,
    )

    for blocker in analysis.get("blockers") or []:
        if not isinstance(blocker, dict):
            continue
        code = str(blocker.get("code") or "")
        if code in LEGACY_INPUT_FAIL_CLOSED_REASON_CODES:
            return {
                "legacy_input_blocked": True,
                "legacy_input_reason_code": code,
                "legacy_input_reason": str(blocker.get("reason") or ""),
            }
    return {
        "legacy_input_blocked": False,
        "legacy_input_reason_code": "",
        "legacy_input_reason": "",
    }


def prepare_receptor(
    payload: dict[str, Any],
    *,
    target_id: str = "",
    root: str | Path = ".",
    ligand_reference_coords: Any = None,
    legacy_input_compatibility_mode: bool | None = None,
) -> PreparedReceptorPacket:
    """Parse and normalize the receptor once, for all engine surfaces."""

    analysis = analyze_structure_source(
        payload,
        root=root,
        legacy_input_compatibility_mode=legacy_input_compatibility_mode,
    )
    blockers: list[str] = [
        str(blocker.get("code") or "")
        for blocker in analysis.get("blockers") or []
        if isinstance(blocker, dict) and blocker.get("code")
    ]
    legacy_contract = {
        "legacy_input_contract_version": analysis.get("legacy_input_contract_version", ""),
        "fail_closed": bool(analysis.get("fail_closed")),
        "compatibility_mode": bool(analysis.get("compatibility_mode")),
        **_legacy_input_blocked_row(analysis),
    }
    source_text_available = bool(analysis.get("source_available"))
    atoms: list[dict[str, Any]] = []
    if source_text_available and not blockers:
        atoms = _receptor_atoms(payload, root=root, legacy_input_compatibility_mode=legacy_input_compatibility_mode)
    coords: list[tuple[float, float, float]] = []
    elements: list[str] = []
    for atom in atoms:
        xyz = atom.get("xyz")
        if xyz is None:
            continue
        values = np.asarray(xyz, dtype=np.float64).reshape(-1)
        if values.size < 3:
            continue
        coords.append((float(values[0]), float(values[1]), float(values[2])))
        elements.append(str(atom.get("element") or "C"))
    if not coords:
        blockers.append("prepared_receptor_has_no_coordinates")

    pocket = _detect_pocket(coords, ligand_reference_coords)
    if not pocket.ready:
        blockers.append("prepared_receptor_pocket_not_ready")

    unique_blockers = tuple(dict.fromkeys(blocker for blocker in blockers if blocker))
    status = STATUS_RECEPTOR_BLOCKED if unique_blockers else STATUS_RECEPTOR_READY
    return PreparedReceptorPacket(
        target_id=str(target_id or payload.get("target_id") or payload.get("target_name") or ""),
        status=status,
        source_kind=str(analysis.get("source_kind") or ""),
        atom_count=len(coords),
        elements=tuple(elements),
        coordinates=tuple(coords),
        pocket=pocket,
        legacy_input_contract=legacy_contract,
        blockers=unique_blockers,
    )


def _receptor_atoms(
    payload: dict[str, Any],
    *,
    root: str | Path,
    legacy_input_compatibility_mode: bool | None,
) -> list[dict[str, Any]]:
    from betelgeuze_product.legacy_input_contract import (
        LegacyInputContractError,
        resolve_legacy_input_policy,
    )
    from core.structure_metrics import parse_pdb_atoms_with_coords

    policy = resolve_legacy_input_policy(compatibility_mode=legacy_input_compatibility_mode)
    text = str(payload.get("pdb_content") or "").strip()
    if not text:
        path_value = str(payload.get("pdb_path") or "").strip()
        if path_value:
            candidate = Path(path_value)
            if not candidate.is_absolute():
                candidate = Path(root) / candidate
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8", errors="ignore")
    if not text:
        return []
    try:
        return parse_pdb_atoms_with_coords(text, policy=policy)
    except LegacyInputContractError:
        # The structure analysis pass already reports the specific contract
        # blocker; here an unparseable receptor simply yields no atoms.
        return []


def _detect_pocket(
    coords: list[tuple[float, float, float]],
    ligand_reference_coords: Any,
) -> PocketIdentity:
    if not coords:
        return PocketIdentity(
            status="blocked_empty_protein", method="", center=(0.0, 0.0, 0.0), radius_a=0.0
        )
    from core.pocket_detection import detect_binding_pocket

    protein = np.asarray(coords, dtype=np.float64)
    ligand = (
        np.asarray(ligand_reference_coords, dtype=np.float64)
        if ligand_reference_coords is not None
        else None
    )
    return _pocket_from_payload(detect_binding_pocket(protein, ligand))


def _conformer_coordinates(
    coordinates: Any,
) -> tuple[tuple[tuple[float, float, float], ...], ...]:
    """Freeze the embedded conformer coordinates into the packet.

    The coordinates travel with the packet so no engine surface re-runs
    embedding: a re-embed would give legacy and V2 different atoms and make a
    shadow comparison meaningless.
    """

    if coordinates is None:
        return ()
    array = np.asarray(coordinates, dtype=np.float64)
    if array.ndim != 3 or array.shape[0] == 0 or array.shape[2] != 3:
        return ()
    return tuple(
        tuple((float(row[0]), float(row[1]), float(row[2])) for row in conformer)
        for conformer in array
    )


def prepare_ligand(
    smiles: str,
    *,
    ligand_id: str = "",
    max_conformers: int = DEFAULT_MAX_CONFORMERS,
    seed: int = DEFAULT_SEED,
) -> PreparedLigandPacket:
    """Perceive flexibility and build the conformer ensemble once, for all engines."""

    from betelgeuze_engine.topology import ligand_topology_from_smiles

    smi = str(smiles or "").strip()
    topology = ligand_topology_from_smiles(smi)
    validity = dict(topology.validity)
    perception = perceive_ligand_rotors(smi).to_dict()
    blockers: list[str] = [
        str(blocker) for blocker in validity.get("claim_safe_blockers") or [] if str(blocker)
    ]
    if not validity.get("valid"):
        blockers.append(str(validity.get("reason") or "invalid_ligand_topology"))

    ensemble_payload: dict[str, Any] = {}
    conformer_coordinates: tuple[tuple[tuple[float, float, float], ...], ...] = ()
    atom_elements = tuple(str(element) for element in topology.atom_elements or ())
    if perception.get("supported"):
        ensemble = generate_conformer_ensemble(
            smi, max_conformers=int(max_conformers), seed=int(seed)
        )
        ensemble_payload = ensemble.to_dict()
        if not ensemble.ready:
            blockers.extend(str(item) for item in ensemble.blockers)
        elif int(ensemble_payload.get("retained_conformer_count") or 0) <= 0:
            blockers.append("prepared_ligand_has_no_retained_conformer")
        else:
            conformer_coordinates = _conformer_coordinates(ensemble.coordinates)
            if not conformer_coordinates:
                blockers.append("prepared_ligand_has_no_conformer_coordinates")
            elif any(len(conformer) != len(atom_elements) for conformer in conformer_coordinates):
                # The packet exists so both engines dock the *same* atoms. An
                # element/coordinate length mismatch would silently re-introduce
                # per-engine preparation, so it fails closed here.
                blockers.append("prepared_ligand_atom_element_coordinate_mismatch")
    else:
        blockers.extend(str(item) for item in perception.get("blockers") or [])

    unique_blockers = tuple(dict.fromkeys(blocker for blocker in blockers if blocker))
    status = STATUS_LIGAND_BLOCKED if unique_blockers else STATUS_LIGAND_READY
    return PreparedLigandPacket(
        ligand_id=str(ligand_id or ""),
        status=status,
        smiles=smi,
        atom_count=int(validity.get("atom_count") or 0),
        flexibility_lane=str(validity.get("ligand_flexibility_lane") or "unsupported"),
        atom_elements=atom_elements,
        conformer_coordinates=conformer_coordinates,
        rotor_perception=perception,
        conformer_ensemble=ensemble_payload,
        chemistry_validity=validity,
        blockers=unique_blockers,
    )


def build_preparation_packet(
    *,
    receptor_payload: dict[str, Any],
    ligand_smiles: str,
    target_id: str = "",
    ligand_id: str = "",
    root: str | Path = ".",
    max_conformers: int = DEFAULT_MAX_CONFORMERS,
    seed: int = DEFAULT_SEED,
    ligand_reference_coords: Any = None,
    legacy_input_compatibility_mode: bool | None = None,
) -> PreparationPacket:
    """Build the single packet pair handed to every engine surface."""

    receptor = prepare_receptor(
        receptor_payload,
        target_id=target_id,
        root=root,
        ligand_reference_coords=ligand_reference_coords,
        legacy_input_compatibility_mode=legacy_input_compatibility_mode,
    )
    ligand = prepare_ligand(
        ligand_smiles,
        ligand_id=ligand_id,
        max_conformers=max_conformers,
        seed=seed,
    )
    return PreparationPacket(receptor=receptor, ligand=ligand)


__all__ = [
    "build_preparation_packet",
    "prepare_ligand",
    "prepare_receptor",
]
