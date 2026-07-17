"""Bounded reference-canonical selection for one reviewed tautomer pair.

Only the exact neutral, acyclic C2H4O graphs recorded for PubChem CID 177
(acetaldehyde) and CID 11199 (vinyl alcohol) are recognized.  Either graph is
projected to a canonical acetaldehyde topology.  For vinyl alcohol, the only
atom transfer permitted is the generated hydroxyl hydrogen; source-observed
hydrogen is never moved.  The transferred hydrogen receives the same fixed
parent-offset coordinate used by the bounded preparation scaffold.

This is a reviewed identity-selection contract, not evidence of tautomer
population, equilibrium, thermodynamic preference, pH dependence, geometry,
energy, parameterability, scientific validity, or product readiness.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import tempfile
from typing import Any, Mapping

import torch

from .mmcif_nonpoly_all_atom_systems import (
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION,
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID,
    MmcifNonpolyAllAtomSystemInstanceReport,
    parse_mmcif_nonpoly_all_atom_systems,
)
from .mmcif_nonpoly_hydrogen_coordinates import (
    MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM,
    MMCIF_HYDROGEN_COORDINATE_OFFSET_DIRECTIONS,
)
from .models import AllAtomSystem, Atom, Bond
from .serialization import (
    all_atom_system_from_canonical_json,
    canonical_coordinates_sha256,
    canonical_system_json_bytes,
    canonical_system_sha256,
    canonical_topology_sha256,
)
from .validation import require_valid_all_atom_system


MMCIF_NONPOLY_TAUTOMER_SELECTION_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_tautomer_selection_projection/1.0.0"
)
MMCIF_NONPOLY_TAUTOMER_SELECTION_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_tautomer_selection_source_binding/1.0.0"
)
MMCIF_NONPOLY_TAUTOMER_SELECTION_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_tautomer_selection_document/1.0.0"
)
MMCIF_NONPOLY_TAUTOMER_SELECTION_PROFILE_ID = (
    "bounded_pubchem_cid_177_11199_reference_canonical_tautomer_selection/1.0.0"
)
MMCIF_NONPOLY_TAUTOMER_SELECTION_ENGINE_VERSION = "1.0.0"

MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID = "pubchem:cid:177"
MMCIF_NONPOLY_TAUTOMER_SELECTION_ALTERNATE_COMPOUND_ID = "pubchem:cid:11199"
MMCIF_NONPOLY_TAUTOMER_SELECTION_ACETALDEHYDE_RECORD_SHA256 = (
    "65d6c251528195fe45a34ad3a6ca2d3df84d5d849ee2e79a75b0f60cfbf7de44"
)
MMCIF_NONPOLY_TAUTOMER_SELECTION_VINYL_ALCOHOL_RECORD_SHA256 = (
    "f3a820615762730371b34021ada9c68284104d23be8bbaee069374dd30fe4e76"
)

_SELECTED_STATUS = "reference_canonical_tautomer_selected"
_SELECTED_STATE = "acetaldehyde"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyTautomerSelectionError(ValueError):
    """Stable fail-closed error without source coordinates or identity echo."""

    def __init__(self, code: str, detail: str):
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f"mmcif_nonpoly_tautomer_selection:{self.code}: {self.detail}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _bits(value: float) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise MmcifNonpolyTautomerSelectionError(
            "nonfinite_coordinate", "selected coordinates must be finite binary64"
        )
    return struct.pack(">d", number).hex()


def _require_digest(value: object, *, label: str, allow_empty: bool = False) -> str:
    digest = str(value or "")
    if allow_empty and not digest:
        return ""
    if _SHA256_RE.fullmatch(digest) is None:
        raise MmcifNonpolyTautomerSelectionError(
            f"invalid_{label}", f"{label} must be a lowercase SHA-256 digest"
        )
    return digest


def _claim_policy() -> dict[str, bool]:
    return {
        "source_all_atom_system_bound": True,
        "reviewed_tautomer_pair_identity_bound": True,
        "reference_match_is_exact_graph_contract": True,
        "reference_canonical_state_selected": True,
        "generated_hydrogen_only_transfer_enforced": True,
        "source_observed_hydrogen_move_forbidden": True,
        "canonical_all_atom_system_created": True,
        "canonical_json_round_trip_verified": True,
        "failure_complete_decision_report": True,
        "source_structure_identity_authenticated": False,
        "general_tautomer_enumeration_supported": False,
        "tautomer_population_predicted": False,
        "tautomer_equilibrium_inferred": False,
        "thermodynamic_preference_inferred": False,
        "ph_dependency_interpreted": False,
        "source_observed_hydrogen_moved": False,
        "partial_charge_assigned": False,
        "parameter_assignment_implemented": False,
        "atom_masses_assigned": False,
        "parameterable": False,
        "coordinate_geometry_validated": False,
        "chemistry_validated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _structure_record(
    *,
    cid: int,
    connectivity_smiles: str,
    inchi_key: str,
    title: str,
    expected_sha256: str,
) -> dict[str, Any]:
    fields = {
        "cid": cid,
        "connectivity_smiles": connectivity_smiles,
        "inchi_key": inchi_key,
        "molecular_formula": "C2H4O",
        "title": title,
    }
    if _sha256(fields) != expected_sha256:
        raise MmcifNonpolyTautomerSelectionError(
            "reference_structure_identity_drift",
            "reviewed PubChem structure identity fields changed",
        )
    return {
        "compound_id": f"pubchem:cid:{cid}",
        "structure_identity": fields,
        "structure_record_fields_sha256": expected_sha256,
    }


def reviewed_mmcif_nonpoly_tautomer_selection_reference() -> dict[str, Any]:
    """Return the reviewed identity-only pair and conservative use boundary."""

    return {
        "reference_schema_id": (
            "betelgeuze.engine_v2_tautomer_selection_reference/1.0.0"
        ),
        "reference_compound_id": (
            MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID
        ),
        "alternate_compound_id": (
            MMCIF_NONPOLY_TAUTOMER_SELECTION_ALTERNATE_COMPOUND_ID
        ),
        "reference_canonical_state": _SELECTED_STATE,
        "selection_policy": "reviewed_reference_canonical_identity",
        "structures": [
            _structure_record(
                cid=177,
                connectivity_smiles="CC=O",
                inchi_key="IKHGUXGNUITLKF-UHFFFAOYSA-N",
                title="Acetaldehyde",
                expected_sha256=(
                    MMCIF_NONPOLY_TAUTOMER_SELECTION_ACETALDEHYDE_RECORD_SHA256
                ),
            ),
            _structure_record(
                cid=11199,
                connectivity_smiles="C=CO",
                inchi_key="IMROMDMJAWUWLK-UHFFFAOYSA-N",
                title="Vinyl alcohol",
                expected_sha256=(
                    MMCIF_NONPOLY_TAUTOMER_SELECTION_VINYL_ALCOHOL_RECORD_SHA256
                ),
            ),
        ],
        "structure_source": {
            "provider": "PubChem",
            "service": "PUG REST",
            "request_urls": [
                (
                    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/177/"
                    "property/Title,MolecularFormula,ConnectivitySMILES,InChIKey/JSON"
                ),
                (
                    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/11199/"
                    "property/Title,MolecularFormula,ConnectivitySMILES,InChIKey/JSON"
                ),
            ],
            "retrieved_date": "2026-07-17",
            "response_fields_bundled": False,
            "manually_projected_factual_identity_only": True,
        },
        "licensing_boundary": {
            "policy_url": "https://pubchem.ncbi.nlm.nih.gov/docs/downloads",
            "policy_identity": "pubchem_source_specific_license_review_required",
            "raw_pubchem_record_bundled": False,
            "contributor_text_bundled": False,
            "pubchem_coordinates_used": False,
            "factual_identifiers_and_graph_only": True,
            "commercial_redistribution_approved": False,
            "source_specific_restrictions_review_required": True,
        },
        "review": {
            "reviewer_role": "engine_v2_contract_reviewer",
            "reviewed_date": "2026-07-17",
            "status": "reviewed_identity_and_reference_canonical_policy",
            "thermodynamic_review": False,
            "scientific_validation": False,
            "legal_determination": False,
        },
    }


def mmcif_nonpoly_tautomer_selection_reference_sha256() -> str:
    return _sha256(reviewed_mmcif_nonpoly_tautomer_selection_reference())


@dataclass(frozen=True, slots=True)
class _TautomerRoles:
    source_state: str
    matched_compound_id: str
    terminal_carbon_index: int
    central_carbon_index: int
    oxygen_index: int
    terminal_hydrogen_indices: tuple[int, ...]
    central_hydrogen_index: int
    oxygen_hydrogen_index: int | None
    transferred_hydrogen_identity_sha256: str
    graph_signature_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyTautomerSelectionReport:
    instance_identity_sha256: str
    component_id: str
    matched_source_state: str
    matched_compound_id: str
    reference_compound_id: str
    selected_state: str
    decision_status: str
    parent_system_sha256: str
    terminal_carbon_parent_index: int
    central_carbon_parent_index: int
    oxygen_parent_index: int
    transferred_hydrogen_parent_index: int
    transferred_hydrogen_identity_sha256: str
    graph_signature_sha256: str
    system: AllAtomSystem
    canonical_round_trip_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyTautomerSelectionReport("
            f"matched_source_state={self.matched_source_state!r}, "
            f"selected_state={self.selected_state!r})"
        )

    @property
    def system_sha256(self) -> str:
        return canonical_system_sha256(self.system)

    @property
    def topology_sha256(self) -> str:
        return canonical_topology_sha256(self.system)

    @property
    def coordinates_sha256(self) -> str:
        return canonical_coordinates_sha256(self.system)

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_identity_sha256": self.instance_identity_sha256,
            "component_id": self.component_id,
            "matched_source_state": self.matched_source_state,
            "matched_compound_id": self.matched_compound_id,
            "reference_compound_id": self.reference_compound_id,
            "selected_state": self.selected_state,
            "decision_status": self.decision_status,
            "decision_blockers": [],
            "state_selected": True,
            "parent_system_sha256": self.parent_system_sha256,
            "terminal_carbon_parent_index": self.terminal_carbon_parent_index,
            "central_carbon_parent_index": self.central_carbon_parent_index,
            "oxygen_parent_index": self.oxygen_parent_index,
            "transferred_hydrogen_parent_index": (
                self.transferred_hydrogen_parent_index
            ),
            "transferred_hydrogen_identity_sha256": (
                self.transferred_hydrogen_identity_sha256
            ),
            "transferred_generated_hydrogen_count": (
                1 if self.matched_source_state == "vinyl_alcohol" else 0
            ),
            "source_observed_hydrogen_move_count": 0,
            "graph_signature_sha256": self.graph_signature_sha256,
            "atom_count": self.system.atom_count,
            "bond_count": len(self.system.bonds),
            "system_sha256": self.system_sha256,
            "topology_sha256": self.topology_sha256,
            "coordinates_sha256": self.coordinates_sha256,
            "canonical_round_trip_verified": True,
            "canonical_round_trip_sha256": self.canonical_round_trip_sha256,
            "canonical_system_document": json.loads(
                canonical_system_json_bytes(self.system).decode("ascii")
            ),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyTautomerSelectionSnapshot:
    source_sha256: str
    parent_all_atom_system_snapshot_sha256: str
    reference_snapshot_sha256: str
    report: MmcifNonpolyTautomerSelectionReport

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyTautomerSelectionSnapshot("
            f"matched_source_state={self.report.matched_source_state!r})"
        )

    @property
    def selection_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_tautomer_selection_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_tautomer_selection_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_DOCUMENT_SCHEMA_ID,
                "selection_projection_sha256": self.selection_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_PROFILE_ID,
            "engine_version": MMCIF_NONPOLY_TAUTOMER_SELECTION_ENGINE_VERSION,
            "source_sha256": self.source_sha256,
            "parent_all_atom_system_snapshot_sha256": (
                self.parent_all_atom_system_snapshot_sha256
            ),
            "reference_snapshot_sha256": self.reference_snapshot_sha256,
            "decision_status": self.report.decision_status,
            "matched_source_state": self.report.matched_source_state,
            "selected_state": self.report.selected_state,
            "state_selected": True,
            "selection_projection_sha256": self.selection_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def _target_materialized_report(
    reports: tuple[MmcifNonpolyAllAtomSystemInstanceReport, ...],
    instance_identity_sha256: str,
) -> MmcifNonpolyAllAtomSystemInstanceReport:
    matches = tuple(
        row
        for row in reports
        if row.instance_identity_sha256 == instance_identity_sha256
    )
    if len(matches) != 1:
        raise MmcifNonpolyTautomerSelectionError(
            "target_instance_not_found",
            "target instance must identify exactly one bounded nonpoly system",
        )
    report = matches[0]
    if report.system is None:
        raise MmcifNonpolyTautomerSelectionError(
            "target_system_unavailable",
            "target instance must have a canonical all-atom materialization",
        )
    return report


def _adjacency(system: AllAtomSystem) -> dict[int, list[tuple[int, Bond]]]:
    rows: dict[int, list[tuple[int, Bond]]] = {atom.index: [] for atom in system.atoms}
    for bond in system.bonds:
        rows[bond.atom_i].append((bond.atom_j, bond))
        rows[bond.atom_j].append((bond.atom_i, bond))
    return rows


def _recognize_exact_pair(system: AllAtomSystem) -> _TautomerRoles:
    counts = {
        element: sum(atom.element == element for atom in system.atoms)
        for element in ("C", "H", "O")
    }
    if (
        system.model_count != 1
        or len(system.residues) != 1
        or len(system.chains) != 1
        or system.atom_count != 7
        or len(system.bonds) != 6
        or counts != {"C": 2, "H": 4, "O": 1}
        or any(atom.element not in {"C", "H", "O"} for atom in system.atoms)
        or any(atom.formal_charge != 0 or atom.aromatic for atom in system.atoms)
        or any(bond.aromatic or bond.order not in {1.0, 2.0} for bond in system.bonds)
    ):
        raise MmcifNonpolyTautomerSelectionError(
            "reference_structure_mismatch",
            "target graph is outside the exact neutral C2H4O tautomer-pair profile",
        )
    adjacency = _adjacency(system)
    oxygens = [atom.index for atom in system.atoms if atom.element == "O"]
    carbons = [atom.index for atom in system.atoms if atom.element == "C"]
    oxygen = oxygens[0]
    oxygen_heavy = [
        (neighbor, bond)
        for neighbor, bond in adjacency[oxygen]
        if system.atoms[neighbor].element != "H"
    ]
    if len(oxygen_heavy) != 1 or system.atoms[oxygen_heavy[0][0]].element != "C":
        raise MmcifNonpolyTautomerSelectionError(
            "reference_structure_mismatch", "oxygen must bind exactly one carbon"
        )
    central = oxygen_heavy[0][0]
    terminal = next((value for value in carbons if value != central), -1)
    cc_bonds = [bond for neighbor, bond in adjacency[central] if neighbor == terminal]
    if terminal < 0 or len(cc_bonds) != 1:
        raise MmcifNonpolyTautomerSelectionError(
            "reference_structure_mismatch", "the two carbons must be directly bonded"
        )
    co_order = oxygen_heavy[0][1].order
    cc_order = cc_bonds[0].order
    hydrogens_by_parent: dict[int, tuple[int, ...]] = {}
    for parent in (terminal, central, oxygen):
        hydrogens_by_parent[parent] = tuple(
            sorted(
                neighbor
                for neighbor, bond in adjacency[parent]
                if system.atoms[neighbor].element == "H" and bond.order == 1.0
            )
        )
    if any(
        len(adjacency[atom.index]) != 1 for atom in system.atoms if atom.element == "H"
    ):
        raise MmcifNonpolyTautomerSelectionError(
            "reference_structure_mismatch", "every hydrogen must have one parent"
        )
    source_state: str
    matched_compound_id: str
    oxygen_hydrogen: int | None
    if (
        cc_order == 1.0
        and co_order == 2.0
        and tuple(map(len, hydrogens_by_parent.values())) == (3, 1, 0)
    ):
        source_state = "acetaldehyde"
        matched_compound_id = MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID
        oxygen_hydrogen = None
    elif (
        cc_order == 2.0
        and co_order == 1.0
        and tuple(map(len, hydrogens_by_parent.values())) == (2, 1, 1)
    ):
        source_state = "vinyl_alcohol"
        matched_compound_id = MMCIF_NONPOLY_TAUTOMER_SELECTION_ALTERNATE_COMPOUND_ID
        oxygen_hydrogen = hydrogens_by_parent[oxygen][0]
        moved = system.atoms[oxygen_hydrogen]
        if (
            moved.metadata.get("origin") != "added_hydrogen"
            or moved.metadata.get("parent_atom_index") != oxygen
        ):
            raise MmcifNonpolyTautomerSelectionError(
                "source_observed_hydrogen_move_forbidden",
                "bounded tautomer selection may move only a generated hydroxyl hydrogen",
            )
    else:
        raise MmcifNonpolyTautomerSelectionError(
            "reference_structure_mismatch",
            "target graph does not match acetaldehyde or vinyl-alcohol connectivity",
        )
    transferred_identity = ""
    if oxygen_hydrogen is not None:
        transferred_identity = _require_digest(
            system.atoms[oxygen_hydrogen].metadata.get(
                "prepared_atom_identity_sha256", ""
            ),
            label="transferred_hydrogen_identity_sha256",
        )
    graph_signature = _sha256(
        {
            "parent_system_sha256": canonical_system_sha256(system),
            "source_state": source_state,
            "terminal_carbon_parent_index": terminal,
            "central_carbon_parent_index": central,
            "oxygen_parent_index": oxygen,
            "terminal_hydrogen_parent_indices": list(hydrogens_by_parent[terminal]),
            "central_hydrogen_parent_index": hydrogens_by_parent[central][0],
            "oxygen_hydrogen_parent_index": (
                -1 if oxygen_hydrogen is None else oxygen_hydrogen
            ),
        }
    )
    return _TautomerRoles(
        source_state=source_state,
        matched_compound_id=matched_compound_id,
        terminal_carbon_index=terminal,
        central_carbon_index=central,
        oxygen_index=oxygen,
        terminal_hydrogen_indices=hydrogens_by_parent[terminal],
        central_hydrogen_index=hydrogens_by_parent[central][0],
        oxygen_hydrogen_index=oxygen_hydrogen,
        transferred_hydrogen_identity_sha256=transferred_identity,
        graph_signature_sha256=graph_signature,
    )


def _coordinate_identity_payload(
    atom: Atom,
    *,
    new_index: int,
    output_parent_index: int | None,
    coordinate: tuple[float, float, float],
) -> dict[str, Any]:
    origin = str(atom.metadata.get("origin", ""))
    generation_method = str(atom.metadata.get("coordinate_generation_method", ""))
    source_identity = str(
        atom.metadata.get("source_coordinate_value_identity_sha256", "")
    )
    return {
        "atom_index": new_index,
        "atom_identity_sha256": str(
            atom.metadata.get("prepared_atom_identity_sha256", "")
        ),
        "origin": origin,
        "element": atom.element,
        "parent_atom_index": output_parent_index,
        "generation_method": generation_method,
        "source_coordinate_value_identity_sha256": source_identity,
        "coordinate_angstrom": list(coordinate),
        "coordinate_binary64_bits_hex": [_bits(value) for value in coordinate],
    }


def _atom_selection_identity_payload(
    *,
    parent_atom_index: int,
    parent_prepared_atom_identity_sha256: str,
    new_atom_index: int,
    output_parent_index: int | None,
    role: str,
    moved_generated_hydrogen: bool,
    source_state: str,
) -> dict[str, Any]:
    return {
        "parent_atom_index": parent_atom_index,
        "parent_prepared_atom_identity_sha256": (parent_prepared_atom_identity_sha256),
        "new_atom_index": new_atom_index,
        "output_parent_index": output_parent_index,
        "role": role,
        "moved_generated_hydrogen": moved_generated_hydrogen,
        "source_state": source_state,
        "selected_state": _SELECTED_STATE,
    }


def _bond_selection_identity_payload(
    *,
    parent_bond_index: int,
    parent_prepared_bond_identity_sha256: str,
    new_bond_index: int,
    atom_i: int,
    atom_j: int,
    parent_order: float,
    output_order: float,
    role: str,
    moved_generated_hydrogen_bond: bool,
    source_state: str,
) -> dict[str, Any]:
    return {
        "parent_bond_index": parent_bond_index,
        "parent_prepared_bond_identity_sha256": (parent_prepared_bond_identity_sha256),
        "new_bond_index": new_bond_index,
        "atom_i": atom_i,
        "atom_j": atom_j,
        "parent_order": parent_order,
        "output_order": output_order,
        "role": role,
        "moved_generated_hydrogen_bond": moved_generated_hydrogen_bond,
        "source_state": source_state,
        "selected_state": _SELECTED_STATE,
    }


def _parent_bond(system: AllAtomSystem, atom_i: int, atom_j: int) -> Bond:
    endpoints = {atom_i, atom_j}
    matches = [bond for bond in system.bonds if {bond.atom_i, bond.atom_j} == endpoints]
    if len(matches) != 1:
        raise MmcifNonpolyTautomerSelectionError(
            "reference_structure_mismatch", "expected parent bond is not unique"
        )
    return matches[0]


def _selected_system(parent: AllAtomSystem, roles: _TautomerRoles) -> AllAtomSystem:
    moved_parent = roles.oxygen_hydrogen_index
    terminal_h = list(roles.terminal_hydrogen_indices)
    atom_order = [
        roles.terminal_carbon_index,
        roles.central_carbon_index,
        roles.oxygen_index,
        *terminal_h,
    ]
    if moved_parent is not None:
        atom_order.append(moved_parent)
    atom_order.append(roles.central_hydrogen_index)
    if len(atom_order) != 7 or len(set(atom_order)) != 7:
        raise MmcifNonpolyTautomerSelectionError(
            "canonical_role_mapping_failed",
            "canonical role mapping must cover seven atoms",
        )
    reindex = {
        parent_index: new_index for new_index, parent_index in enumerate(atom_order)
    }
    role_names = (
        "terminal_carbon",
        "carbonyl_carbon",
        "carbonyl_oxygen",
        "terminal_hydrogen_1",
        "terminal_hydrogen_2",
        "terminal_hydrogen_3",
        "carbonyl_hydrogen",
    )
    coordinate_rows: list[torch.Tensor] = []
    for new_index, parent_index in enumerate(atom_order):
        if parent_index == moved_parent:
            direction = MMCIF_HYDROGEN_COORDINATE_OFFSET_DIRECTIONS[2]
            offset = (
                torch.tensor(
                    direction,
                    dtype=parent.coordinates.dtype,
                    device=parent.coordinates.device,
                )
                * MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM
            )
            row = parent.coordinates[:, roles.terminal_carbon_index, :] + offset
        else:
            row = parent.coordinates[:, parent_index, :]
        coordinate_rows.append(row.clone())
    coordinates = torch.stack(coordinate_rows, dim=1)
    atoms: list[Atom] = []
    for new_index, (parent_index, role) in enumerate(
        zip(atom_order, role_names, strict=True)
    ):
        atom = parent.atoms[parent_index]
        moved = parent_index == moved_parent
        output_parent: int | None = None
        if atom.metadata.get("origin") == "added_hydrogen":
            if moved:
                output_parent = 0
            else:
                old_parent = atom.metadata.get("parent_atom_index")
                if not isinstance(old_parent, int) or old_parent not in reindex:
                    raise MmcifNonpolyTautomerSelectionError(
                        "generated_hydrogen_parent_invalid",
                        "generated hydrogen parent must be in the canonical role mapping",
                    )
                output_parent = reindex[old_parent]
        coordinate = tuple(float(value) for value in coordinates[0, new_index].tolist())
        metadata = dict(atom.metadata)
        coordinate_payload = _coordinate_identity_payload(
            atom,
            new_index=new_index,
            output_parent_index=output_parent,
            coordinate=coordinate,
        )
        metadata.update(
            {
                "parent_atom_index": output_parent,
                "coordinate_binary64_bits_hex": coordinate_payload[
                    "coordinate_binary64_bits_hex"
                ],
                "coordinate_identity_sha256": _sha256(coordinate_payload),
                "tautomer_selection_parent_atom_index": parent_index,
                "tautomer_selection_parent_prepared_atom_identity_sha256": (
                    str(metadata.get("prepared_atom_identity_sha256", ""))
                ),
                "tautomer_selection_role": role,
                "tautomer_selection_moved_generated_hydrogen": moved,
                "tautomer_selection_source_state": roles.source_state,
                "tautomer_selection_selected_state": _SELECTED_STATE,
                "tautomer_selection_profile_id": (
                    MMCIF_NONPOLY_TAUTOMER_SELECTION_PROFILE_ID
                ),
            }
        )
        identity_payload = _atom_selection_identity_payload(
            parent_atom_index=parent_index,
            parent_prepared_atom_identity_sha256=str(
                metadata.get("prepared_atom_identity_sha256", "")
            ),
            new_atom_index=new_index,
            output_parent_index=output_parent,
            role=role,
            moved_generated_hydrogen=moved,
            source_state=roles.source_state,
        )
        metadata["tautomer_selection_atom_identity_sha256"] = _sha256(identity_payload)
        atoms.append(
            replace(
                atom,
                index=new_index,
                name="HADD_1_3" if moved else atom.name,
                metadata=metadata,
            )
        )

    moved_old_parent = roles.oxygen_index if moved_parent is not None else -1
    bond_specs: list[tuple[int, int, float, str, int, int, bool]] = [
        (
            0,
            1,
            1.0,
            "terminal_carbon_carbonyl_carbon",
            roles.terminal_carbon_index,
            roles.central_carbon_index,
            False,
        ),
        (
            1,
            2,
            2.0,
            "carbonyl_carbon_oxygen",
            roles.central_carbon_index,
            roles.oxygen_index,
            False,
        ),
    ]
    for ordinal, parent_h in enumerate(atom_order[3:6], start=1):
        is_moved = parent_h == moved_parent
        bond_specs.append(
            (
                0,
                ordinal + 2,
                1.0,
                f"terminal_carbon_hydrogen_{ordinal}",
                moved_old_parent if is_moved else roles.terminal_carbon_index,
                parent_h,
                is_moved,
            )
        )
    bond_specs.append(
        (
            1,
            6,
            1.0,
            "carbonyl_carbon_hydrogen",
            roles.central_carbon_index,
            roles.central_hydrogen_index,
            False,
        )
    )
    bonds: list[Bond] = []
    for new_index, (
        atom_i,
        atom_j,
        output_order,
        role,
        parent_i,
        parent_j,
        moved_bond,
    ) in enumerate(bond_specs):
        parent_bond = _parent_bond(parent, parent_i, parent_j)
        metadata = dict(parent_bond.metadata)
        metadata.update(
            {
                "tautomer_selection_parent_bond_index": parent_bond.index,
                "tautomer_selection_parent_prepared_bond_identity_sha256": str(
                    metadata.get("prepared_bond_identity_sha256", "")
                ),
                "tautomer_selection_role": role,
                "tautomer_selection_bond_order_changed": (
                    parent_bond.order != output_order
                ),
                "tautomer_selection_moved_generated_hydrogen_bond": moved_bond,
                "tautomer_selection_source_state": roles.source_state,
                "tautomer_selection_selected_state": _SELECTED_STATE,
            }
        )
        identity_payload = _bond_selection_identity_payload(
            parent_bond_index=parent_bond.index,
            parent_prepared_bond_identity_sha256=str(
                metadata.get("prepared_bond_identity_sha256", "")
            ),
            new_bond_index=new_index,
            atom_i=atom_i,
            atom_j=atom_j,
            parent_order=parent_bond.order,
            output_order=output_order,
            role=role,
            moved_generated_hydrogen_bond=moved_bond,
            source_state=roles.source_state,
        )
        metadata["tautomer_selection_bond_identity_sha256"] = _sha256(identity_payload)
        bonds.append(
            replace(
                parent_bond,
                index=new_index,
                atom_i=atom_i,
                atom_j=atom_j,
                order=output_order,
                source=(
                    "bounded_tautomer_selection"
                    if parent_bond.order != output_order or moved_bond
                    else parent_bond.source
                ),
                metadata=metadata,
            )
        )

    parent_sha256 = canonical_system_sha256(parent)
    reference_sha256 = mmcif_nonpoly_tautomer_selection_reference_sha256()
    operation_metadata = {
        "tautomer_selection_profile_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_PROFILE_ID,
        "tautomer_selection_engine_version": (
            MMCIF_NONPOLY_TAUTOMER_SELECTION_ENGINE_VERSION
        ),
        "tautomer_selection_reference_compound_id": (
            MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID
        ),
        "tautomer_selection_matched_compound_id": roles.matched_compound_id,
        "tautomer_selection_reference_snapshot_sha256": reference_sha256,
        "tautomer_selection_parent_system_sha256": parent_sha256,
        "tautomer_selection_graph_signature_sha256": (roles.graph_signature_sha256),
        "tautomer_selection_source_state": roles.source_state,
        "tautomer_selection_selected_state": _SELECTED_STATE,
        "tautomer_selection_policy": "reviewed_reference_canonical_identity",
        "tautomer_selection_interpreted": True,
        "transferred_generated_hydrogen_count": (1 if moved_parent is not None else 0),
        "transferred_generated_hydrogen_identity_sha256": (
            roles.transferred_hydrogen_identity_sha256
        ),
        "source_observed_hydrogen_moved": False,
        "source_structure_identity_authenticated": False,
        "tautomer_population_predicted": False,
        "tautomer_equilibrium_inferred": False,
        "thermodynamic_preference_inferred": False,
        "ph_dependency_interpreted": False,
        "coordinate_geometry_validated": False,
        "parameterable": False,
        "claim_safe": False,
    }
    provenance_metadata = dict(parent.provenance.metadata)
    provenance_metadata.update(operation_metadata)
    provenance = replace(
        parent.provenance,
        parser_name="bounded_mmcif_nonpoly_tautomer_selection",
        parser_version=MMCIF_NONPOLY_TAUTOMER_SELECTION_ENGINE_VERSION,
        operations=(
            *parent.provenance.operations,
            "bounded_pubchem_cid_177_11199_reference_canonical_tautomer_selection",
        ),
        parent_sha256=(*parent.provenance.parent_sha256, parent_sha256),
        source_digest_verified=False,
        transformation_chain_verified=False,
        chemistry_validated=False,
        scientifically_validated=False,
        product_qualified=False,
        metadata=provenance_metadata,
    )
    state_token = hashlib.sha256(
        _canonical_bytes(
            {
                "parent_system_sha256": parent_sha256,
                "source_state": roles.source_state,
                "selected_state": _SELECTED_STATE,
                "reference_snapshot_sha256": reference_sha256,
            }
        )
    ).hexdigest()[:16]
    residues = tuple(
        replace(
            residue,
            atom_indices=tuple(range(7)),
            metadata={
                **dict(residue.metadata),
                "tautomer_selection_source_state": roles.source_state,
                "tautomer_selection_selected_state": _SELECTED_STATE,
            },
        )
        for residue in parent.residues
    )
    system = replace(
        parent,
        system_id=f"{parent.system_id}-tautomer-{state_token}",
        atoms=tuple(atoms),
        bonds=tuple(bonds),
        residues=residues,
        coordinates=coordinates,
        provenance=provenance,
        metadata={**dict(parent.metadata), **operation_metadata},
    )
    validation = require_valid_all_atom_system(system)
    if validation.claim_stage.name.lower() != "contract_valid" or validation.claim_safe:
        raise MmcifNonpolyTautomerSelectionError(
            "unexpected_claim_promotion",
            "tautomer-selected systems must remain contract-valid and claim-blocked",
        )
    encoded = canonical_system_json_bytes(system)
    decoded = all_atom_system_from_canonical_json(encoded.decode("ascii"))
    if (
        canonical_system_json_bytes(decoded) != encoded
        or canonical_system_sha256(decoded) != canonical_system_sha256(system)
        or canonical_topology_sha256(decoded) != canonical_topology_sha256(system)
        or canonical_coordinates_sha256(decoded) != canonical_coordinates_sha256(system)
    ):
        raise MmcifNonpolyTautomerSelectionError(
            "canonical_round_trip_mismatch",
            "tautomer-selected canonical system did not round-trip exactly",
        )
    return system


def apply_mmcif_nonpoly_tautomer_selection(
    text: str,
    *,
    instance_identity_sha256: str,
    reference_compound_id: str = (
        MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID
    ),
) -> MmcifNonpolyTautomerSelectionSnapshot:
    """Select the reviewed reference-canonical state for the exact pair."""

    if type(text) is not str:
        raise TypeError("mmCIF tautomer-selection input must be a string")
    instance_digest = _require_digest(
        instance_identity_sha256, label="instance_identity_sha256"
    )
    if str(reference_compound_id) != (
        MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID
    ):
        raise MmcifNonpolyTautomerSelectionError(
            "unsupported_reference_compound",
            "bounded tautomer selection accepts only reviewed PubChem CID 177",
        )
    materialization = parse_mmcif_nonpoly_all_atom_systems(text)
    parent_report = _target_materialized_report(
        materialization.instance_reports, instance_digest
    )
    parent = parent_report.system
    assert parent is not None
    roles = _recognize_exact_pair(parent)
    system = _selected_system(parent, roles)
    report = MmcifNonpolyTautomerSelectionReport(
        instance_identity_sha256=instance_digest,
        component_id=parent_report.component_id,
        matched_source_state=roles.source_state,
        matched_compound_id=roles.matched_compound_id,
        reference_compound_id=(MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID),
        selected_state=_SELECTED_STATE,
        decision_status=_SELECTED_STATUS,
        parent_system_sha256=canonical_system_sha256(parent),
        terminal_carbon_parent_index=roles.terminal_carbon_index,
        central_carbon_parent_index=roles.central_carbon_index,
        oxygen_parent_index=roles.oxygen_index,
        transferred_hydrogen_parent_index=(
            -1 if roles.oxygen_hydrogen_index is None else roles.oxygen_hydrogen_index
        ),
        transferred_hydrogen_identity_sha256=(
            roles.transferred_hydrogen_identity_sha256
        ),
        graph_signature_sha256=roles.graph_signature_sha256,
        system=system,
        canonical_round_trip_sha256=hashlib.sha256(
            canonical_system_json_bytes(system)
        ).hexdigest(),
    )
    return MmcifNonpolyTautomerSelectionSnapshot(
        source_sha256=materialization.source_sha256,
        parent_all_atom_system_snapshot_sha256=materialization.snapshot_sha256,
        reference_snapshot_sha256=(mmcif_nonpoly_tautomer_selection_reference_sha256()),
        report=report,
    )


def mmcif_nonpoly_tautomer_selection_projection(
    snapshot: MmcifNonpolyTautomerSelectionSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_PROFILE_ID,
        "engine_version": MMCIF_NONPOLY_TAUTOMER_SELECTION_ENGINE_VERSION,
        "parent_all_atom_system_snapshot_sha256": (
            snapshot.parent_all_atom_system_snapshot_sha256
        ),
        "report": snapshot.report.to_dict(),
        **_claim_policy(),
    }


def mmcif_nonpoly_tautomer_selection_source_binding(
    snapshot: MmcifNonpolyTautomerSelectionSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "parent_all_atom_system_snapshot_sha256": (
            snapshot.parent_all_atom_system_snapshot_sha256
        ),
        "parent_all_atom_system_profile_id": MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID,
        "parent_all_atom_system_materializer_version": (
            MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION
        ),
        "reference_snapshot_sha256": snapshot.reference_snapshot_sha256,
        "reference": reviewed_mmcif_nonpoly_tautomer_selection_reference(),
        "selection_policy": "reviewed_reference_canonical_identity",
        "supported_source_states": ["acetaldehyde", "vinyl_alcohol"],
        "selected_state": _SELECTED_STATE,
        "source_observed_hydrogen_policy": "never_move",
        "generated_hydrogen_policy": "move_exact_generated_hydroxyl_h_only",
        "transferred_hydrogen_coordinate_policy": (
            "terminal_carbon_fixed_parent_offset_direction_3"
        ),
        "thermodynamic_interpretation": "not_performed",
        "population_interpretation": "not_performed",
        "ph_interpretation": "not_performed",
    }


def mmcif_nonpoly_tautomer_selection_document(
    snapshot: MmcifNonpolyTautomerSelectionSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_tautomer_selection_projection(snapshot)
    binding = mmcif_nonpoly_tautomer_selection_source_binding(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_PROFILE_ID,
        "engine_version": MMCIF_NONPOLY_TAUTOMER_SELECTION_ENGINE_VERSION,
        "selection_projection": projection,
        "source_binding": binding,
        "selection_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def _require_selected_topology(system: AllAtomSystem) -> None:
    if (
        [atom.element for atom in system.atoms] != ["C", "C", "O", "H", "H", "H", "H"]
        or any(atom.formal_charge != 0 or atom.aromatic for atom in system.atoms)
        or [(bond.index, bond.atom_i, bond.atom_j, bond.order) for bond in system.bonds]
        != [
            (0, 0, 1, 1.0),
            (1, 1, 2, 2.0),
            (2, 0, 3, 1.0),
            (3, 0, 4, 1.0),
            (4, 0, 5, 1.0),
            (5, 1, 6, 1.0),
        ]
    ):
        raise ValueError("tautomer-selected canonical topology mismatch")


def _require_selected_atom_metadata(
    system: AllAtomSystem, *, source_state: str
) -> None:
    expected_roles = (
        "terminal_carbon",
        "carbonyl_carbon",
        "carbonyl_oxygen",
        "terminal_hydrogen_1",
        "terminal_hydrogen_2",
        "terminal_hydrogen_3",
        "carbonyl_hydrogen",
    )
    moved_count = 0
    parent_indices: set[int] = set()
    for atom, role in zip(system.atoms, expected_roles, strict=True):
        metadata = atom.metadata
        parent_index = metadata.get("tautomer_selection_parent_atom_index")
        parent_prepared = str(
            metadata.get("tautomer_selection_parent_prepared_atom_identity_sha256", "")
        )
        output_parent = metadata.get("parent_atom_index")
        moved = metadata.get("tautomer_selection_moved_generated_hydrogen")
        if (
            not isinstance(parent_index, int)
            or parent_index not in range(7)
            or parent_index in parent_indices
            or _SHA256_RE.fullmatch(parent_prepared) is None
            or parent_prepared != metadata.get("prepared_atom_identity_sha256")
            or metadata.get("tautomer_selection_role") != role
            or type(moved) is not bool
            or metadata.get("tautomer_selection_source_state") != source_state
            or metadata.get("tautomer_selection_selected_state") != _SELECTED_STATE
            or metadata.get("tautomer_selection_profile_id")
            != MMCIF_NONPOLY_TAUTOMER_SELECTION_PROFILE_ID
        ):
            raise ValueError("tautomer-selected atom lineage mismatch")
        parent_indices.add(parent_index)
        expected_identity = _sha256(
            _atom_selection_identity_payload(
                parent_atom_index=parent_index,
                parent_prepared_atom_identity_sha256=parent_prepared,
                new_atom_index=atom.index,
                output_parent_index=output_parent,
                role=role,
                moved_generated_hydrogen=moved,
                source_state=source_state,
            )
        )
        coordinate = tuple(
            float(value) for value in system.coordinates[0, atom.index].tolist()
        )
        expected_coordinate = _coordinate_identity_payload(
            atom,
            new_index=atom.index,
            output_parent_index=output_parent,
            coordinate=coordinate,
        )
        if (
            metadata.get("tautomer_selection_atom_identity_sha256") != expected_identity
            or metadata.get("coordinate_binary64_bits_hex")
            != expected_coordinate["coordinate_binary64_bits_hex"]
            or metadata.get("coordinate_identity_sha256")
            != _sha256(expected_coordinate)
        ):
            raise ValueError("tautomer-selected atom identity mismatch")
        if moved:
            moved_count += 1
            if (
                source_state != "vinyl_alcohol"
                or atom.index != 5
                or atom.element != "H"
                or atom.name != "HADD_1_3"
                or metadata.get("origin") != "added_hydrogen"
                or output_parent != 0
            ):
                raise ValueError("transferred tautomer hydrogen lineage mismatch")
    if moved_count != (1 if source_state == "vinyl_alcohol" else 0):
        raise ValueError("transferred tautomer hydrogen count mismatch")
    if source_state == "vinyl_alcohol":
        direction = MMCIF_HYDROGEN_COORDINATE_OFFSET_DIRECTIONS[2]
        expected = [
            float(system.coordinates[0, 0, axis])
            + direction[axis] * MMCIF_HYDROGEN_COORDINATE_BOND_LENGTH_ANGSTROM
            for axis in range(3)
        ]
        if system.coordinates[0, 5].tolist() != expected:
            raise ValueError("transferred tautomer hydrogen coordinate mismatch")


def _require_selected_bond_metadata(
    system: AllAtomSystem, *, source_state: str
) -> None:
    expected_roles = (
        "terminal_carbon_carbonyl_carbon",
        "carbonyl_carbon_oxygen",
        "terminal_carbon_hydrogen_1",
        "terminal_carbon_hydrogen_2",
        "terminal_carbon_hydrogen_3",
        "carbonyl_carbon_hydrogen",
    )
    for bond, role in zip(system.bonds, expected_roles, strict=True):
        metadata = bond.metadata
        parent_index = metadata.get("tautomer_selection_parent_bond_index")
        parent_prepared = str(
            metadata.get("tautomer_selection_parent_prepared_bond_identity_sha256", "")
        )
        parent_order = (
            2.0
            if source_state == "vinyl_alcohol" and bond.index == 0
            else 1.0
            if source_state == "vinyl_alcohol" and bond.index == 1
            else bond.order
        )
        moved = metadata.get("tautomer_selection_moved_generated_hydrogen_bond")
        expected_moved = source_state == "vinyl_alcohol" and bond.index == 4
        if (
            not isinstance(parent_index, int)
            or parent_index not in range(6)
            or _SHA256_RE.fullmatch(parent_prepared) is None
            or parent_prepared != metadata.get("prepared_bond_identity_sha256")
            or metadata.get("tautomer_selection_role") != role
            or moved is not expected_moved
            or metadata.get("tautomer_selection_bond_order_changed")
            is not (parent_order != bond.order)
            or metadata.get("tautomer_selection_source_state") != source_state
            or metadata.get("tautomer_selection_selected_state") != _SELECTED_STATE
        ):
            raise ValueError("tautomer-selected bond lineage mismatch")
        expected = _sha256(
            _bond_selection_identity_payload(
                parent_bond_index=parent_index,
                parent_prepared_bond_identity_sha256=parent_prepared,
                new_bond_index=bond.index,
                atom_i=bond.atom_i,
                atom_j=bond.atom_j,
                parent_order=parent_order,
                output_order=bond.order,
                role=role,
                moved_generated_hydrogen_bond=expected_moved,
                source_state=source_state,
            )
        )
        if metadata.get("tautomer_selection_bond_identity_sha256") != expected:
            raise ValueError("tautomer-selected bond identity mismatch")


def require_mmcif_nonpoly_tautomer_selection_document(
    payload: object,
) -> Mapping[str, object]:
    """Verify envelope, reference binding, lineage, topology, and claims."""

    if not isinstance(payload, Mapping):
        raise ValueError("tautomer selection document must be a mapping")
    document = dict(payload)
    projection = document.get("selection_projection")
    binding = document.get("source_binding")
    if (
        document.get("schema_id") != MMCIF_NONPOLY_TAUTOMER_SELECTION_DOCUMENT_SCHEMA_ID
        or document.get("profile_id") != MMCIF_NONPOLY_TAUTOMER_SELECTION_PROFILE_ID
        or document.get("engine_version")
        != MMCIF_NONPOLY_TAUTOMER_SELECTION_ENGINE_VERSION
        or not isinstance(projection, Mapping)
        or not isinstance(binding, Mapping)
    ):
        raise ValueError("tautomer selection document envelope mismatch")
    projection_dict = dict(projection)
    binding_dict = dict(binding)
    projection_sha = _sha256(projection_dict)
    binding_sha = _sha256(binding_dict)
    if (
        document.get("selection_projection_sha256") != projection_sha
        or document.get("source_binding_sha256") != binding_sha
        or projection_dict.get("schema_id")
        != MMCIF_NONPOLY_TAUTOMER_SELECTION_PROJECTION_SCHEMA_ID
        or binding_dict.get("schema_id")
        != MMCIF_NONPOLY_TAUTOMER_SELECTION_SOURCE_BINDING_SCHEMA_ID
        or binding_dict.get("reference")
        != reviewed_mmcif_nonpoly_tautomer_selection_reference()
        or binding_dict.get("reference_snapshot_sha256")
        != mmcif_nonpoly_tautomer_selection_reference_sha256()
    ):
        raise ValueError("tautomer selection section digest or reference mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_TAUTOMER_SELECTION_DOCUMENT_SCHEMA_ID,
            "selection_projection_sha256": projection_sha,
            "source_binding_sha256": binding_sha,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("tautomer selection snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if (
            document.get(key) is not expected
            or projection_dict.get(key) is not expected
        ):
            raise ValueError("tautomer selection claim boundary mismatch")
    report_value = projection_dict.get("report")
    if not isinstance(report_value, Mapping):
        raise ValueError("tautomer selection report missing")
    report = dict(report_value)
    source_state = report.get("matched_source_state")
    expected_compound = {
        "acetaldehyde": MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID,
        "vinyl_alcohol": MMCIF_NONPOLY_TAUTOMER_SELECTION_ALTERNATE_COMPOUND_ID,
    }.get(str(source_state))
    for key in (
        "instance_identity_sha256",
        "parent_system_sha256",
        "graph_signature_sha256",
        "system_sha256",
        "topology_sha256",
        "coordinates_sha256",
        "canonical_round_trip_sha256",
    ):
        if _SHA256_RE.fullmatch(str(report.get(key, ""))) is None:
            raise ValueError("tautomer selection report digest invalid")
    transfer_count = 1 if source_state == "vinyl_alcohol" else 0
    transferred_identity = str(report.get("transferred_hydrogen_identity_sha256", ""))
    if (
        expected_compound is None
        or report.get("matched_compound_id") != expected_compound
        or report.get("reference_compound_id")
        != MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID
        or report.get("selected_state") != _SELECTED_STATE
        or report.get("decision_status") != _SELECTED_STATUS
        or report.get("decision_blockers") != []
        or report.get("state_selected") is not True
        or report.get("canonical_round_trip_verified") is not True
        or report.get("atom_count") != 7
        or report.get("bond_count") != 6
        or report.get("transferred_generated_hydrogen_count") != transfer_count
        or report.get("source_observed_hydrogen_move_count") != 0
        or (transfer_count == 1 and _SHA256_RE.fullmatch(transferred_identity) is None)
        or (transfer_count == 0 and transferred_identity != "")
        or (
            transfer_count == 0
            and report.get("transferred_hydrogen_parent_index") != -1
        )
        or (
            transfer_count == 1
            and (
                not isinstance(report.get("transferred_hydrogen_parent_index"), int)
                or report.get("transferred_hydrogen_parent_index") not in range(7)
            )
        )
    ):
        raise ValueError("tautomer selection decision identity mismatch")
    system_document = report.get("canonical_system_document")
    if not isinstance(system_document, Mapping):
        raise ValueError("tautomer-selected canonical system missing")
    encoded = json.dumps(
        dict(system_document),
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    system = all_atom_system_from_canonical_json(encoded)
    canonical_bytes = canonical_system_json_bytes(system)
    validation = require_valid_all_atom_system(system)
    if (
        canonical_bytes.decode("ascii") != encoded
        or report.get("system_sha256") != canonical_system_sha256(system)
        or report.get("topology_sha256") != canonical_topology_sha256(system)
        or report.get("coordinates_sha256") != canonical_coordinates_sha256(system)
        or report.get("canonical_round_trip_sha256")
        != hashlib.sha256(canonical_bytes).hexdigest()
        or system.metadata.get("tautomer_selection_source_state") != source_state
        or system.metadata.get("tautomer_selection_selected_state") != _SELECTED_STATE
        or system.metadata.get("tautomer_selection_matched_compound_id")
        != expected_compound
        or system.metadata.get("tautomer_selection_parent_system_sha256")
        != report.get("parent_system_sha256")
        or system.metadata.get("tautomer_selection_graph_signature_sha256")
        != report.get("graph_signature_sha256")
        or system.metadata.get("tautomer_selection_reference_snapshot_sha256")
        != document.get("reference_snapshot_sha256")
        or system.metadata.get("transferred_generated_hydrogen_count") != transfer_count
        or system.metadata.get("transferred_generated_hydrogen_identity_sha256")
        != transferred_identity
        or (
            transfer_count == 1
            and system.atoms[5].metadata.get("tautomer_selection_parent_atom_index")
            != report.get("transferred_hydrogen_parent_index")
        )
        or system.metadata.get("source_observed_hydrogen_moved") is not False
        or system.metadata.get("source_structure_identity_authenticated") is not False
        or system.metadata.get("tautomer_population_predicted") is not False
        or system.metadata.get("tautomer_equilibrium_inferred") is not False
        or system.metadata.get("thermodynamic_preference_inferred") is not False
        or system.metadata.get("ph_dependency_interpreted") is not False
        or system.metadata.get("parameterable") is not False
        or system.metadata.get("claim_safe") is not False
        or system.provenance.source_sha256 != document.get("source_sha256")
        or system.provenance.parser_name != "bounded_mmcif_nonpoly_tautomer_selection"
        or system.provenance.parser_version
        != MMCIF_NONPOLY_TAUTOMER_SELECTION_ENGINE_VERSION
        or not system.provenance.operations
        or system.provenance.operations[-1]
        != "bounded_pubchem_cid_177_11199_reference_canonical_tautomer_selection"
        or not system.provenance.parent_sha256
        or system.provenance.parent_sha256[-1] != report.get("parent_system_sha256")
        or validation.claim_stage.name.lower() != "contract_valid"
        or validation.claim_safe
        or system.provenance.chemistry_validated
        or system.provenance.scientifically_validated
        or system.provenance.product_qualified
        or any(atom.partial_charge_e is not None for atom in system.atoms)
        or any(atom.mass_da is not None for atom in system.atoms)
    ):
        raise ValueError("tautomer-selected system identity mismatch")
    _require_selected_topology(system)
    _require_selected_atom_metadata(system, source_state=str(source_state))
    _require_selected_bond_metadata(system, source_state=str(source_state))
    if (
        document.get("decision_status") != report.get("decision_status")
        or document.get("matched_source_state") != source_state
        or document.get("selected_state") != _SELECTED_STATE
        or document.get("state_selected") is not True
        or document.get("source_sha256") != binding_dict.get("source_sha256")
        or document.get("reference_snapshot_sha256")
        != binding_dict.get("reference_snapshot_sha256")
        or document.get("parent_all_atom_system_snapshot_sha256")
        != binding_dict.get("parent_all_atom_system_snapshot_sha256")
        or projection_dict.get("parent_all_atom_system_snapshot_sha256")
        != binding_dict.get("parent_all_atom_system_snapshot_sha256")
        or binding_dict.get("parent_all_atom_system_profile_id")
        != MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID
        or binding_dict.get("parent_all_atom_system_materializer_version")
        != MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION
        or binding_dict.get("selection_policy")
        != "reviewed_reference_canonical_identity"
        or binding_dict.get("supported_source_states")
        != ["acetaldehyde", "vinyl_alcohol"]
        or binding_dict.get("selected_state") != _SELECTED_STATE
        or binding_dict.get("source_observed_hydrogen_policy") != "never_move"
        or binding_dict.get("generated_hydrogen_policy")
        != "move_exact_generated_hydroxyl_h_only"
        or binding_dict.get("thermodynamic_interpretation") != "not_performed"
        or binding_dict.get("population_interpretation") != "not_performed"
        or binding_dict.get("ph_interpretation") != "not_performed"
    ):
        raise ValueError("tautomer selection document crosswire")
    return payload


def mmcif_nonpoly_tautomer_selection_json_bytes(
    snapshot: MmcifNonpolyTautomerSelectionSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_tautomer_selection_document(snapshot))


def write_mmcif_nonpoly_tautomer_selection_json(
    path: str | Path,
    snapshot: MmcifNonpolyTautomerSelectionSnapshot,
) -> Path:
    """Atomically write the canonical private selection receipt."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_tautomer_selection_json_bytes(snapshot) + b"\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        descriptor = -1
        os.replace(temporary_path, destination)
        os.chmod(destination, 0o600)
    except BaseException:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        temporary_path.unlink(missing_ok=True)
        raise
    return destination


__all__ = [
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_ALTERNATE_COMPOUND_ID",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_ENGINE_VERSION",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_PROFILE_ID",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_REFERENCE_COMPOUND_ID",
    "MMCIF_NONPOLY_TAUTOMER_SELECTION_SOURCE_BINDING_SCHEMA_ID",
    "MmcifNonpolyTautomerSelectionError",
    "MmcifNonpolyTautomerSelectionReport",
    "MmcifNonpolyTautomerSelectionSnapshot",
    "apply_mmcif_nonpoly_tautomer_selection",
    "mmcif_nonpoly_tautomer_selection_document",
    "mmcif_nonpoly_tautomer_selection_json_bytes",
    "mmcif_nonpoly_tautomer_selection_projection",
    "mmcif_nonpoly_tautomer_selection_reference_sha256",
    "mmcif_nonpoly_tautomer_selection_source_binding",
    "require_mmcif_nonpoly_tautomer_selection_document",
    "reviewed_mmcif_nonpoly_tautomer_selection_reference",
    "write_mmcif_nonpoly_tautomer_selection_json",
]
