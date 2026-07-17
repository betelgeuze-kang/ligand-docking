"""Bounded pH-dependent protonation for one reviewed real-world graph.

This capability starts from the canonical neutral C/O/H ``AllAtomSystem``
materializer and recognizes only the exact, non-aromatic acetic-acid graph
recorded for PubChem CID 176.  It evaluates the monoprotic-acid
Henderson--Hasselbalch population at a caller-supplied pH and emits a canonical
system only when either the protonated or deprotonated state has at least 90%
population.  Ambiguous populations abstain instead of silently choosing a
microstate.

The deprotonated carrier removes only a generated hydroxyl hydrogen, assigns a
localized ``-1`` formal charge to the source singly bonded oxygen, and records
that resonance equivalence and tautomer selection were not interpreted.  The
result is a contract-valid identity artifact with an exact canonical JSON
round trip.  It is not a general acid/base predictor, a validated pKa model, a
scientifically validated protonation method, or a parameterable system.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

import torch

from .mmcif_nonpoly_all_atom_systems import (
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION,
    MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID,
    MmcifNonpolyAllAtomSystemInstanceReport,
    parse_mmcif_nonpoly_all_atom_systems,
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


MMCIF_NONPOLY_PH_PROTONATION_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_ph_protonation_projection/1.0.0"
)
MMCIF_NONPOLY_PH_PROTONATION_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_ph_protonation_source_binding/1.0.0"
)
MMCIF_NONPOLY_PH_PROTONATION_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_ph_protonation_document/1.0.0"
)
MMCIF_NONPOLY_PH_PROTONATION_PROFILE_ID = (
    "bounded_pubchem_cid_176_acetic_acid_ph_protonation/1.0.0"
)
MMCIF_NONPOLY_PH_PROTONATION_ENGINE_VERSION = "1.0.0"

MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID = "pubchem:cid:176"
MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_PKA = 4.76
MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION = 0.90
MMCIF_NONPOLY_PH_PROTONATION_MIN_PH = 0.0
MMCIF_NONPOLY_PH_PROTONATION_MAX_PH = 14.0
MMCIF_NONPOLY_PH_PROTONATION_STRUCTURE_RECORD_SHA256 = (
    "6f1ade06eec5019ec6f2e24dee973e74bba42e039e20c3892a18e2668a1c6628"
)

_SELECTED_STATUS = "dominant_protonation_state_selected"
_ABSTAINED_STATUS = "abstained_population_not_dominant"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyPhProtonationError(ValueError):
    """Stable fail-closed error without source coordinates or identity tokens."""

    def __init__(self, code: str, detail: str):
        self.code = str(code)
        self.detail = str(detail)
        super().__init__(f"mmcif_nonpoly_ph_protonation:{self.code}: {self.detail}")


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


def _float_hex(value: float) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise MmcifNonpolyPhProtonationError(
            "nonfinite_numeric_value", "pH contract values must be finite binary64"
        )
    return number.hex()


def _claim_policy() -> dict[str, bool]:
    return {
        "source_all_atom_system_bound": True,
        "reviewed_reference_compound_identity_bound": True,
        "reference_match_is_exact_graph_contract": True,
        "reviewed_pka_provenance_bound": True,
        "target_ph_binary64_bound": True,
        "henderson_hasselbalch_population_evaluated": True,
        "dominant_population_threshold_enforced": True,
        "ambiguous_population_abstention_enforced": True,
        "generated_hydrogen_only_removal_enforced": True,
        "selected_state_canonical_all_atom_system_created": True,
        "selected_state_canonical_json_round_trip_verified": True,
        "failure_complete_decision_report": True,
        "general_acid_base_chemistry_supported": False,
        "multi_site_protonation_supported": False,
        "polyprotic_protonation_supported": False,
        "proton_coupling_supported": False,
        "tautomer_selection_interpreted": False,
        "resonance_equivalence_interpreted": False,
        "source_observed_hydrogen_removed": False,
        "source_structure_identity_authenticated": False,
        "pka_predicted": False,
        "pka_calibrated": False,
        "partial_charge_assigned": False,
        "parameter_assignment_implemented": False,
        "atom_masses_assigned": False,
        "parameterable": False,
        "chemistry_validated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def reviewed_mmcif_nonpoly_ph_protonation_reference() -> dict[str, Any]:
    """Return the reviewed identity, pKa, and licensing boundary for CID 176."""

    structure_identity = {
        "cid": 176,
        "connectivity_smiles": "CC(=O)O",
        "inchi_key": "QTBSBXVTEAMEQO-UHFFFAOYSA-N",
        "molecular_formula": "C2H4O2",
        "title": "Acetic Acid",
    }
    if (
        _sha256(structure_identity)
        != MMCIF_NONPOLY_PH_PROTONATION_STRUCTURE_RECORD_SHA256
    ):
        raise MmcifNonpolyPhProtonationError(
            "reference_structure_identity_drift",
            "reviewed PubChem structure identity fields changed",
        )
    return {
        "reference_schema_id": ("betelgeuze.engine_v2_ph_protonation_reference/1.0.0"),
        "reference_compound_id": (MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID),
        "structure_identity": structure_identity,
        "structure_record_fields_sha256": (
            MMCIF_NONPOLY_PH_PROTONATION_STRUCTURE_RECORD_SHA256
        ),
        "structure_source": {
            "provider": "PubChem",
            "service": "PUG REST",
            "request_url": (
                "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
                "acetic%20acid/property/Title,MolecularFormula,"
                "ConnectivitySMILES,InChIKey/JSON"
            ),
            "retrieved_date": "2026-07-17",
            "response_fields_bundled": False,
            "manually_projected_factual_identity_only": True,
        },
        "pka_reference": {
            "value": MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_PKA,
            "value_binary64_hex": _float_hex(
                MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_PKA
            ),
            "source_label": "PubChem HSDB-sourced dissociation constant",
            "source_url": (
                "https://pubchem.ncbi.nlm.nih.gov/compound/176"
                "#section=Dissociation-Constants"
            ),
            "reviewed_date": "2026-07-17",
            "use_scope": "bounded_contract_state_selection_only",
        },
        "licensing_boundary": {
            "policy_url": "https://pubchem.ncbi.nlm.nih.gov/docs/downloads",
            "policy_identity": "pubchem_source_specific_license_review_required",
            "raw_pubchem_record_bundled": False,
            "contributor_text_bundled": False,
            "factual_identifiers_and_graph_only": True,
            "commercial_redistribution_approved": False,
            "source_specific_restrictions_review_required": True,
        },
        "review": {
            "reviewer_role": "engine_v2_contract_reviewer",
            "reviewed_date": "2026-07-17",
            "status": "reviewed_identity_pka_and_license_boundary",
            "scientific_validation": False,
            "legal_determination": False,
        },
    }


def mmcif_nonpoly_ph_protonation_reference_sha256() -> str:
    return _sha256(reviewed_mmcif_nonpoly_ph_protonation_reference())


@dataclass(frozen=True, slots=True)
class _AceticAcidSite:
    acid_carbon_index: int
    acidic_oxygen_index: int
    carbonyl_oxygen_index: int
    acidic_hydrogen_index: int
    acidic_hydrogen_identity_sha256: str
    site_signature_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyPhProtonationReport:
    instance_identity_sha256: str
    component_id: str
    reference_compound_id: str
    target_ph: float
    intrinsic_pka: float
    protonated_fraction: float
    deprotonated_fraction: float
    decision_status: str
    selected_state: str
    decision_blockers: tuple[str, ...]
    parent_system_sha256: str
    acid_carbon_parent_index: int
    acidic_oxygen_parent_index: int
    carbonyl_oxygen_parent_index: int
    acidic_hydrogen_parent_index: int
    acidic_hydrogen_identity_sha256: str
    site_signature_sha256: str
    system: AllAtomSystem | None
    canonical_round_trip_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyPhProtonationReport("
            f"decision_status={self.decision_status!r}, "
            f"selected_state={self.selected_state!r})"
        )

    @property
    def state_selected(self) -> bool:
        return self.system is not None

    @property
    def system_sha256(self) -> str:
        return "" if self.system is None else canonical_system_sha256(self.system)

    @property
    def topology_sha256(self) -> str:
        return "" if self.system is None else canonical_topology_sha256(self.system)

    @property
    def coordinates_sha256(self) -> str:
        return "" if self.system is None else canonical_coordinates_sha256(self.system)

    def to_dict(self) -> dict[str, Any]:
        system = self.system
        return {
            "instance_identity_sha256": self.instance_identity_sha256,
            "component_id": self.component_id,
            "reference_compound_id": self.reference_compound_id,
            "target_ph": self.target_ph,
            "target_ph_binary64_hex": _float_hex(self.target_ph),
            "intrinsic_pka": self.intrinsic_pka,
            "intrinsic_pka_binary64_hex": _float_hex(self.intrinsic_pka),
            "minimum_dominant_fraction": (
                MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION
            ),
            "minimum_dominant_fraction_binary64_hex": _float_hex(
                MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION
            ),
            "protonated_fraction": self.protonated_fraction,
            "protonated_fraction_binary64_hex": _float_hex(self.protonated_fraction),
            "deprotonated_fraction": self.deprotonated_fraction,
            "deprotonated_fraction_binary64_hex": _float_hex(
                self.deprotonated_fraction
            ),
            "decision_status": self.decision_status,
            "selected_state": self.selected_state,
            "decision_blockers": list(self.decision_blockers),
            "state_selected": self.state_selected,
            "parent_system_sha256": self.parent_system_sha256,
            "acid_carbon_parent_index": self.acid_carbon_parent_index,
            "acidic_oxygen_parent_index": self.acidic_oxygen_parent_index,
            "carbonyl_oxygen_parent_index": self.carbonyl_oxygen_parent_index,
            "acidic_hydrogen_parent_index": self.acidic_hydrogen_parent_index,
            "acidic_hydrogen_identity_sha256": (self.acidic_hydrogen_identity_sha256),
            "site_signature_sha256": self.site_signature_sha256,
            "removed_generated_hydrogen_count": (
                1 if self.selected_state == "deprotonated" else 0
            ),
            "formal_charge_delta": (-1 if self.selected_state == "deprotonated" else 0),
            "atom_count": 0 if system is None else system.atom_count,
            "bond_count": 0 if system is None else len(system.bonds),
            "system_sha256": self.system_sha256,
            "topology_sha256": self.topology_sha256,
            "coordinates_sha256": self.coordinates_sha256,
            "canonical_round_trip_verified": system is not None,
            "canonical_round_trip_sha256": self.canonical_round_trip_sha256,
            "canonical_system_document": (
                None
                if system is None
                else json.loads(canonical_system_json_bytes(system).decode("ascii"))
            ),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyPhProtonationSnapshot:
    source_sha256: str
    parent_all_atom_system_snapshot_sha256: str
    reference_snapshot_sha256: str
    report: MmcifNonpolyPhProtonationReport

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyPhProtonationSnapshot("
            f"decision_status={self.report.decision_status!r})"
        )

    @property
    def protonation_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_ph_protonation_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_ph_protonation_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_PH_PROTONATION_DOCUMENT_SCHEMA_ID,
                "protonation_projection_sha256": (self.protonation_projection_sha256),
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_NONPOLY_PH_PROTONATION_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_PH_PROTONATION_PROFILE_ID,
            "engine_version": MMCIF_NONPOLY_PH_PROTONATION_ENGINE_VERSION,
            "source_sha256": self.source_sha256,
            "parent_all_atom_system_snapshot_sha256": (
                self.parent_all_atom_system_snapshot_sha256
            ),
            "reference_snapshot_sha256": self.reference_snapshot_sha256,
            "decision_status": self.report.decision_status,
            "selected_state": self.report.selected_state,
            "state_selected": self.report.state_selected,
            "protonation_projection_sha256": self.protonation_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def _require_target_ph(value: object) -> float:
    if isinstance(value, bool):
        raise MmcifNonpolyPhProtonationError(
            "invalid_target_ph", "target pH must be a finite numeric value"
        )
    try:
        target = float(value)
    except (TypeError, ValueError) as exc:
        raise MmcifNonpolyPhProtonationError(
            "invalid_target_ph", "target pH must be a finite numeric value"
        ) from exc
    if not math.isfinite(target):
        raise MmcifNonpolyPhProtonationError(
            "nonfinite_target_ph", "target pH must be finite"
        )
    if (
        not MMCIF_NONPOLY_PH_PROTONATION_MIN_PH
        <= target
        <= MMCIF_NONPOLY_PH_PROTONATION_MAX_PH
    ):
        raise MmcifNonpolyPhProtonationError(
            "target_ph_out_of_bounds",
            "target pH is outside the bounded [0, 14] profile",
        )
    return target


def _require_digest(value: object, *, label: str) -> str:
    digest = str(value or "")
    if _SHA256_RE.fullmatch(digest) is None:
        raise MmcifNonpolyPhProtonationError(
            f"invalid_{label}", f"{label} must be a lowercase SHA-256 digest"
        )
    return digest


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
        raise MmcifNonpolyPhProtonationError(
            "target_instance_not_found",
            "target instance must identify exactly one bounded nonpoly system",
        )
    report = matches[0]
    if report.system is None:
        raise MmcifNonpolyPhProtonationError(
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


def _recognize_exact_acetic_acid(system: AllAtomSystem) -> _AceticAcidSite:
    if system.model_count != 1 or len(system.residues) != 1 or len(system.chains) != 1:
        raise MmcifNonpolyPhProtonationError(
            "reference_structure_mismatch",
            "CID 176 profile requires one model, residue, and chain",
        )
    counts = {
        element: sum(atom.element == element for atom in system.atoms)
        for element in ("C", "H", "O")
    }
    if (
        system.atom_count != 8
        or len(system.bonds) != 7
        or counts != {"C": 2, "H": 4, "O": 2}
        or any(atom.element not in {"C", "H", "O"} for atom in system.atoms)
        or any(atom.formal_charge != 0 for atom in system.atoms)
        or any(atom.aromatic for atom in system.atoms)
        or any(bond.aromatic for bond in system.bonds)
    ):
        raise MmcifNonpolyPhProtonationError(
            "reference_structure_mismatch",
            "target graph does not match the exact neutral CID 176 profile",
        )
    adjacency = _adjacency(system)
    candidates: list[_AceticAcidSite] = []
    for carbon in (atom for atom in system.atoms if atom.element == "C"):
        heavy_neighbors = [
            (neighbor, bond)
            for neighbor, bond in adjacency[carbon.index]
            if system.atoms[neighbor].element != "H"
        ]
        carbon_neighbors = [
            (neighbor, bond)
            for neighbor, bond in heavy_neighbors
            if system.atoms[neighbor].element == "C" and bond.order == 1.0
        ]
        double_oxygens = [
            (neighbor, bond)
            for neighbor, bond in heavy_neighbors
            if system.atoms[neighbor].element == "O" and bond.order == 2.0
        ]
        single_oxygens = [
            (neighbor, bond)
            for neighbor, bond in heavy_neighbors
            if system.atoms[neighbor].element == "O" and bond.order == 1.0
        ]
        if not (
            len(heavy_neighbors) == 3
            and len(carbon_neighbors) == 1
            and len(double_oxygens) == 1
            and len(single_oxygens) == 1
        ):
            continue
        methyl_index = carbon_neighbors[0][0]
        methyl_hydrogens = [
            neighbor
            for neighbor, _ in adjacency[methyl_index]
            if system.atoms[neighbor].element == "H"
        ]
        acidic_oxygen = single_oxygens[0][0]
        acidic_hydrogens = [
            neighbor
            for neighbor, bond in adjacency[acidic_oxygen]
            if system.atoms[neighbor].element == "H" and bond.order == 1.0
        ]
        if len(methyl_hydrogens) != 3 or len(acidic_hydrogens) != 1:
            continue
        acidic_hydrogen = system.atoms[acidic_hydrogens[0]]
        if (
            acidic_hydrogen.metadata.get("origin") != "added_hydrogen"
            or acidic_hydrogen.metadata.get("parent_atom_index") != acidic_oxygen
        ):
            raise MmcifNonpolyPhProtonationError(
                "source_observed_acidic_hydrogen_not_removable",
                "bounded deprotonation may remove only a generated hydroxyl hydrogen",
            )
        identity = str(
            acidic_hydrogen.metadata.get("prepared_atom_identity_sha256", "")
        )
        _require_digest(identity, label="acidic_hydrogen_identity_sha256")
        signature = {
            "acid_carbon_parent_index": carbon.index,
            "acidic_oxygen_parent_index": acidic_oxygen,
            "carbonyl_oxygen_parent_index": double_oxygens[0][0],
            "acidic_hydrogen_parent_index": acidic_hydrogen.index,
            "acidic_hydrogen_identity_sha256": identity,
            "parent_system_sha256": canonical_system_sha256(system),
        }
        candidates.append(
            _AceticAcidSite(
                acid_carbon_index=carbon.index,
                acidic_oxygen_index=acidic_oxygen,
                carbonyl_oxygen_index=double_oxygens[0][0],
                acidic_hydrogen_index=acidic_hydrogen.index,
                acidic_hydrogen_identity_sha256=identity,
                site_signature_sha256=_sha256(signature),
            )
        )
    if len(candidates) != 1:
        raise MmcifNonpolyPhProtonationError(
            "reference_structure_mismatch",
            "target graph must contain exactly one reviewed acetic-acid site",
        )
    return candidates[0]


def _population(target_ph: float) -> tuple[float, float]:
    ratio = 10.0 ** (target_ph - MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_PKA)
    protonated = 1.0 / (1.0 + ratio)
    deprotonated = ratio / (1.0 + ratio)
    if not (
        math.isfinite(protonated)
        and math.isfinite(deprotonated)
        and abs((protonated + deprotonated) - 1.0) <= 2.0e-15
    ):
        raise MmcifNonpolyPhProtonationError(
            "population_evaluation_failed",
            "bounded Henderson-Hasselbalch population evaluation failed",
        )
    return protonated, deprotonated


def _derived_atom(
    atom: Atom,
    *,
    new_index: int,
    selected_state: str,
    acidic_oxygen_parent_index: int,
) -> Atom:
    metadata = dict(atom.metadata)
    metadata.update(
        {
            "ph_protonation_parent_atom_index": atom.index,
            "ph_protonation_selected_state": selected_state,
            "ph_protonation_profile_id": MMCIF_NONPOLY_PH_PROTONATION_PROFILE_ID,
        }
    )
    formal_charge = atom.formal_charge
    if selected_state == "deprotonated" and atom.index == acidic_oxygen_parent_index:
        formal_charge = -1
        metadata.update(
            {
                "ph_protonation_formal_charge_delta": -1,
                "localized_carboxylate_charge": True,
                "resonance_equivalence_interpreted": False,
            }
        )
    metadata["ph_protonation_atom_identity_sha256"] = _sha256(
        {
            "parent_atom_index": atom.index,
            "parent_prepared_atom_identity_sha256": metadata.get(
                "prepared_atom_identity_sha256", ""
            ),
            "new_atom_index": new_index,
            "element": atom.element,
            "formal_charge": formal_charge,
            "selected_state": selected_state,
        }
    )
    return replace(
        atom,
        index=new_index,
        formal_charge=formal_charge,
        metadata=metadata,
    )


def _derived_system(
    parent: AllAtomSystem,
    *,
    site: _AceticAcidSite,
    target_ph: float,
    protonated_fraction: float,
    deprotonated_fraction: float,
    selected_state: str,
) -> AllAtomSystem:
    removed_index = (
        site.acidic_hydrogen_index if selected_state == "deprotonated" else None
    )
    kept_parent_indices = tuple(
        atom.index for atom in parent.atoms if atom.index != removed_index
    )
    reindex = {
        parent_index: new_index
        for new_index, parent_index in enumerate(kept_parent_indices)
    }
    atoms = tuple(
        _derived_atom(
            parent.atoms[parent_index],
            new_index=reindex[parent_index],
            selected_state=selected_state,
            acidic_oxygen_parent_index=site.acidic_oxygen_index,
        )
        for parent_index in kept_parent_indices
    )
    bonds: list[Bond] = []
    for parent_bond in parent.bonds:
        if removed_index in {parent_bond.atom_i, parent_bond.atom_j}:
            continue
        atom_i = reindex[parent_bond.atom_i]
        atom_j = reindex[parent_bond.atom_j]
        metadata = dict(parent_bond.metadata)
        metadata.update(
            {
                "ph_protonation_parent_bond_index": parent_bond.index,
                "ph_protonation_selected_state": selected_state,
            }
        )
        metadata["ph_protonation_bond_identity_sha256"] = _sha256(
            {
                "parent_bond_index": parent_bond.index,
                "parent_prepared_bond_identity_sha256": metadata.get(
                    "prepared_bond_identity_sha256", ""
                ),
                "new_bond_index": len(bonds),
                "atom_i": min(atom_i, atom_j),
                "atom_j": max(atom_i, atom_j),
                "order": parent_bond.order,
                "selected_state": selected_state,
            }
        )
        bonds.append(
            replace(
                parent_bond,
                index=len(bonds),
                atom_i=min(atom_i, atom_j),
                atom_j=max(atom_i, atom_j),
                metadata=metadata,
            )
        )
    residues = tuple(
        replace(
            residue,
            atom_indices=tuple(
                reindex[index] for index in residue.atom_indices if index in reindex
            ),
            metadata={
                **dict(residue.metadata),
                "ph_protonation_selected_state": selected_state,
            },
        )
        for residue in parent.residues
    )
    index_tensor = torch.tensor(
        kept_parent_indices,
        dtype=torch.long,
        device=parent.coordinates.device,
    )
    coordinates = parent.coordinates.index_select(1, index_tensor).clone()
    parent_sha256 = canonical_system_sha256(parent)
    reference_sha256 = mmcif_nonpoly_ph_protonation_reference_sha256()
    operation_metadata = {
        "ph_protonation_profile_id": MMCIF_NONPOLY_PH_PROTONATION_PROFILE_ID,
        "ph_protonation_engine_version": (MMCIF_NONPOLY_PH_PROTONATION_ENGINE_VERSION),
        "ph_protonation_reference_compound_id": (
            MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID
        ),
        "ph_protonation_reference_snapshot_sha256": reference_sha256,
        "ph_protonation_parent_system_sha256": parent_sha256,
        "ph_protonation_target_ph_binary64_hex": _float_hex(target_ph),
        "ph_protonation_intrinsic_pka_binary64_hex": _float_hex(
            MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_PKA
        ),
        "ph_protonation_protonated_fraction_binary64_hex": _float_hex(
            protonated_fraction
        ),
        "ph_protonation_deprotonated_fraction_binary64_hex": _float_hex(
            deprotonated_fraction
        ),
        "ph_protonation_minimum_dominant_fraction_binary64_hex": _float_hex(
            MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION
        ),
        "ph_protonation_selected_state": selected_state,
        "ph_protonation_site_signature_sha256": site.site_signature_sha256,
        "removed_generated_hydrogen_identity_sha256": (
            site.acidic_hydrogen_identity_sha256
            if selected_state == "deprotonated"
            else ""
        ),
        "tautomer_selection_interpreted": False,
        "resonance_equivalence_interpreted": False,
        "pka_predicted": False,
        "pka_calibrated": False,
        "parameterable": False,
        "claim_safe": False,
    }
    provenance_metadata = dict(parent.provenance.metadata)
    provenance_metadata.update(operation_metadata)
    provenance = replace(
        parent.provenance,
        parser_name="bounded_mmcif_nonpoly_ph_protonation",
        parser_version=MMCIF_NONPOLY_PH_PROTONATION_ENGINE_VERSION,
        operations=(
            *parent.provenance.operations,
            "bounded_pubchem_cid_176_ph_protonation_state_selection",
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
                "target_ph_binary64_hex": _float_hex(target_ph),
                "selected_state": selected_state,
                "reference_snapshot_sha256": reference_sha256,
            }
        )
    ).hexdigest()[:16]
    system = replace(
        parent,
        system_id=f"{parent.system_id}-ph-{state_token}",
        atoms=atoms,
        bonds=tuple(bonds),
        residues=residues,
        coordinates=coordinates,
        provenance=provenance,
        metadata={**dict(parent.metadata), **operation_metadata},
    )
    validation = require_valid_all_atom_system(system)
    if validation.claim_stage.name.lower() != "contract_valid" or validation.claim_safe:
        raise MmcifNonpolyPhProtonationError(
            "unexpected_claim_promotion",
            "pH-selected systems must remain contract-valid and claim-blocked",
        )
    encoded = canonical_system_json_bytes(system)
    decoded = all_atom_system_from_canonical_json(encoded.decode("ascii"))
    if (
        canonical_system_json_bytes(decoded) != encoded
        or canonical_system_sha256(decoded) != canonical_system_sha256(system)
        or canonical_topology_sha256(decoded) != canonical_topology_sha256(system)
        or canonical_coordinates_sha256(decoded) != canonical_coordinates_sha256(system)
    ):
        raise MmcifNonpolyPhProtonationError(
            "canonical_round_trip_mismatch",
            "pH-selected canonical system did not round-trip exactly",
        )
    return system


def apply_mmcif_nonpoly_ph_protonation(
    text: str,
    *,
    instance_identity_sha256: str,
    target_ph: float,
    reference_compound_id: str = MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID,
) -> MmcifNonpolyPhProtonationSnapshot:
    """Select a dominant CID 176 protonation state or return an abstention."""

    if type(text) is not str:
        raise TypeError("mmCIF pH-protonation input must be a string")
    instance_digest = _require_digest(
        instance_identity_sha256, label="instance_identity_sha256"
    )
    if str(reference_compound_id) != MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID:
        raise MmcifNonpolyPhProtonationError(
            "unsupported_reference_compound",
            "bounded pH protonation accepts only the reviewed PubChem CID 176 identity",
        )
    target = _require_target_ph(target_ph)
    materialization = parse_mmcif_nonpoly_all_atom_systems(text)
    parent_report = _target_materialized_report(
        materialization.instance_reports, instance_digest
    )
    parent = parent_report.system
    assert parent is not None
    site = _recognize_exact_acetic_acid(parent)
    protonated_fraction, deprotonated_fraction = _population(target)
    dominant = max(protonated_fraction, deprotonated_fraction)
    selected_state = ""
    blockers: tuple[str, ...] = ()
    system: AllAtomSystem | None = None
    decision_status = _ABSTAINED_STATUS
    if dominant + 1.0e-15 < MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION:
        blockers = ("minimum_dominant_population_not_met",)
    else:
        selected_state = (
            "protonated"
            if protonated_fraction >= deprotonated_fraction
            else "deprotonated"
        )
        system = _derived_system(
            parent,
            site=site,
            target_ph=target,
            protonated_fraction=protonated_fraction,
            deprotonated_fraction=deprotonated_fraction,
            selected_state=selected_state,
        )
        decision_status = _SELECTED_STATUS
    round_trip_sha256 = (
        ""
        if system is None
        else hashlib.sha256(canonical_system_json_bytes(system)).hexdigest()
    )
    report = MmcifNonpolyPhProtonationReport(
        instance_identity_sha256=instance_digest,
        component_id=parent_report.component_id,
        reference_compound_id=MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID,
        target_ph=target,
        intrinsic_pka=MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_PKA,
        protonated_fraction=protonated_fraction,
        deprotonated_fraction=deprotonated_fraction,
        decision_status=decision_status,
        selected_state=selected_state,
        decision_blockers=blockers,
        parent_system_sha256=canonical_system_sha256(parent),
        acid_carbon_parent_index=site.acid_carbon_index,
        acidic_oxygen_parent_index=site.acidic_oxygen_index,
        carbonyl_oxygen_parent_index=site.carbonyl_oxygen_index,
        acidic_hydrogen_parent_index=site.acidic_hydrogen_index,
        acidic_hydrogen_identity_sha256=(site.acidic_hydrogen_identity_sha256),
        site_signature_sha256=site.site_signature_sha256,
        system=system,
        canonical_round_trip_sha256=round_trip_sha256,
    )
    return MmcifNonpolyPhProtonationSnapshot(
        source_sha256=materialization.source_sha256,
        parent_all_atom_system_snapshot_sha256=materialization.snapshot_sha256,
        reference_snapshot_sha256=mmcif_nonpoly_ph_protonation_reference_sha256(),
        report=report,
    )


def mmcif_nonpoly_ph_protonation_projection(
    snapshot: MmcifNonpolyPhProtonationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_PH_PROTONATION_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PH_PROTONATION_PROFILE_ID,
        "engine_version": MMCIF_NONPOLY_PH_PROTONATION_ENGINE_VERSION,
        "parent_all_atom_system_snapshot_sha256": (
            snapshot.parent_all_atom_system_snapshot_sha256
        ),
        "report": snapshot.report.to_dict(),
        **_claim_policy(),
    }


def mmcif_nonpoly_ph_protonation_source_binding(
    snapshot: MmcifNonpolyPhProtonationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_PH_PROTONATION_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "parent_all_atom_system_snapshot_sha256": (
            snapshot.parent_all_atom_system_snapshot_sha256
        ),
        "parent_all_atom_system_profile_id": (MMCIF_NONPOLY_ALL_ATOM_SYSTEM_PROFILE_ID),
        "parent_all_atom_system_materializer_version": (
            MMCIF_NONPOLY_ALL_ATOM_SYSTEM_MATERIALIZER_VERSION
        ),
        "reference_snapshot_sha256": snapshot.reference_snapshot_sha256,
        "reference": reviewed_mmcif_nonpoly_ph_protonation_reference(),
        "selection_equation": "HA_fraction=1/(1+10^(pH-pKa))",
        "minimum_dominant_fraction": (
            MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION
        ),
        "minimum_dominant_fraction_binary64_hex": _float_hex(
            MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION
        ),
        "supported_ph_interval": [
            MMCIF_NONPOLY_PH_PROTONATION_MIN_PH,
            MMCIF_NONPOLY_PH_PROTONATION_MAX_PH,
        ],
        "state_representation_policy": (
            "localized_carboxylate_without_resonance_or_tautomer_interpretation"
        ),
        "source_observed_hydrogen_policy": "never_remove",
        "generated_hydrogen_policy": "remove_exact_bound_hydroxyl_h_only",
    }


def mmcif_nonpoly_ph_protonation_document(
    snapshot: MmcifNonpolyPhProtonationSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_ph_protonation_projection(snapshot)
    binding = mmcif_nonpoly_ph_protonation_source_binding(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_PH_PROTONATION_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PH_PROTONATION_PROFILE_ID,
        "engine_version": MMCIF_NONPOLY_PH_PROTONATION_ENGINE_VERSION,
        "protonation_projection": projection,
        "source_binding": binding,
        "protonation_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def require_mmcif_nonpoly_ph_protonation_document(
    payload: object,
) -> Mapping[str, object]:
    """Verify the envelope, reference, state decision, and canonical system."""

    if not isinstance(payload, Mapping):
        raise ValueError("pH protonation document must be a mapping")
    document = dict(payload)
    projection = document.get("protonation_projection")
    binding = document.get("source_binding")
    if (
        document.get("schema_id") != MMCIF_NONPOLY_PH_PROTONATION_DOCUMENT_SCHEMA_ID
        or document.get("profile_id") != MMCIF_NONPOLY_PH_PROTONATION_PROFILE_ID
        or document.get("engine_version") != MMCIF_NONPOLY_PH_PROTONATION_ENGINE_VERSION
        or not isinstance(projection, Mapping)
        or not isinstance(binding, Mapping)
    ):
        raise ValueError("pH protonation document envelope mismatch")
    projection_dict = dict(projection)
    binding_dict = dict(binding)
    projection_sha = _sha256(projection_dict)
    binding_sha = _sha256(binding_dict)
    if (
        document.get("protonation_projection_sha256") != projection_sha
        or document.get("source_binding_sha256") != binding_sha
        or projection_dict.get("schema_id")
        != MMCIF_NONPOLY_PH_PROTONATION_PROJECTION_SCHEMA_ID
        or binding_dict.get("schema_id")
        != MMCIF_NONPOLY_PH_PROTONATION_SOURCE_BINDING_SCHEMA_ID
        or binding_dict.get("reference")
        != reviewed_mmcif_nonpoly_ph_protonation_reference()
        or binding_dict.get("reference_snapshot_sha256")
        != mmcif_nonpoly_ph_protonation_reference_sha256()
    ):
        raise ValueError("pH protonation section digest or reference mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_PH_PROTONATION_DOCUMENT_SCHEMA_ID,
            "protonation_projection_sha256": projection_sha,
            "source_binding_sha256": binding_sha,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("pH protonation snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if (
            document.get(key) is not expected
            or projection_dict.get(key) is not expected
        ):
            raise ValueError("pH protonation claim boundary mismatch")
    report_value = projection_dict.get("report")
    if not isinstance(report_value, Mapping):
        raise ValueError("pH protonation report missing")
    report = dict(report_value)
    for key in (
        "instance_identity_sha256",
        "parent_system_sha256",
        "acidic_hydrogen_identity_sha256",
        "site_signature_sha256",
    ):
        if _SHA256_RE.fullmatch(str(report.get(key, ""))) is None:
            raise ValueError("pH protonation report digest invalid")
    try:
        target_ph = float(report["target_ph"])
        intrinsic_pka = float(report["intrinsic_pka"])
        protonated_fraction = float(report["protonated_fraction"])
        deprotonated_fraction = float(report["deprotonated_fraction"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("pH protonation numeric report invalid") from exc
    if (
        report.get("target_ph_binary64_hex") != _float_hex(target_ph)
        or report.get("intrinsic_pka_binary64_hex") != _float_hex(intrinsic_pka)
        or intrinsic_pka != MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_PKA
        or report.get("protonated_fraction_binary64_hex")
        != _float_hex(protonated_fraction)
        or report.get("deprotonated_fraction_binary64_hex")
        != _float_hex(deprotonated_fraction)
        or report.get("minimum_dominant_fraction")
        != MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION
        or report.get("minimum_dominant_fraction_binary64_hex")
        != _float_hex(MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION)
        or abs((protonated_fraction + deprotonated_fraction) - 1.0) > 2.0e-15
        or report.get("reference_compound_id")
        != MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID
        or not MMCIF_NONPOLY_PH_PROTONATION_MIN_PH
        <= target_ph
        <= MMCIF_NONPOLY_PH_PROTONATION_MAX_PH
    ):
        raise ValueError("pH protonation numeric identity mismatch")
    expected_protonated, expected_deprotonated = _population(target_ph)
    if (
        protonated_fraction != expected_protonated
        or deprotonated_fraction != expected_deprotonated
    ):
        raise ValueError("pH protonation population mismatch")
    status = report.get("decision_status")
    selected_state = report.get("selected_state")
    blockers = report.get("decision_blockers")
    system_document = report.get("canonical_system_document")
    if not isinstance(blockers, list):
        raise ValueError("pH protonation blocker list invalid")
    if status == _SELECTED_STATUS:
        if (
            selected_state not in {"protonated", "deprotonated"}
            or blockers
            or report.get("state_selected") is not True
            or report.get("canonical_round_trip_verified") is not True
            or not isinstance(system_document, Mapping)
        ):
            raise ValueError("selected pH protonation report invalid")
        encoded = json.dumps(
            dict(system_document),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        system = all_atom_system_from_canonical_json(encoded)
        validation = require_valid_all_atom_system(system)
        canonical_bytes = canonical_system_json_bytes(system)
        if (
            canonical_bytes.decode("ascii") != encoded
            or report.get("system_sha256") != canonical_system_sha256(system)
            or report.get("topology_sha256") != canonical_topology_sha256(system)
            or report.get("coordinates_sha256") != canonical_coordinates_sha256(system)
            or report.get("canonical_round_trip_sha256")
            != hashlib.sha256(canonical_bytes).hexdigest()
            or system.metadata.get("ph_protonation_selected_state") != selected_state
            or system.metadata.get("ph_protonation_parent_system_sha256")
            != report.get("parent_system_sha256")
            or system.metadata.get("ph_protonation_site_signature_sha256")
            != report.get("site_signature_sha256")
            or system.metadata.get("ph_protonation_profile_id")
            != MMCIF_NONPOLY_PH_PROTONATION_PROFILE_ID
            or system.metadata.get("ph_protonation_engine_version")
            != MMCIF_NONPOLY_PH_PROTONATION_ENGINE_VERSION
            or system.metadata.get("ph_protonation_reference_compound_id")
            != MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID
            or system.metadata.get("ph_protonation_reference_snapshot_sha256")
            != document.get("reference_snapshot_sha256")
            or system.metadata.get("ph_protonation_target_ph_binary64_hex")
            != _float_hex(target_ph)
            or system.metadata.get("ph_protonation_intrinsic_pka_binary64_hex")
            != _float_hex(intrinsic_pka)
            or system.metadata.get("ph_protonation_protonated_fraction_binary64_hex")
            != _float_hex(protonated_fraction)
            or system.metadata.get("ph_protonation_deprotonated_fraction_binary64_hex")
            != _float_hex(deprotonated_fraction)
            or system.metadata.get(
                "ph_protonation_minimum_dominant_fraction_binary64_hex"
            )
            != _float_hex(MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION)
            or system.provenance.source_sha256 != document.get("source_sha256")
            or system.provenance.parser_name != "bounded_mmcif_nonpoly_ph_protonation"
            or system.provenance.parser_version
            != MMCIF_NONPOLY_PH_PROTONATION_ENGINE_VERSION
            or not system.provenance.operations
            or system.provenance.operations[-1]
            != "bounded_pubchem_cid_176_ph_protonation_state_selection"
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
            raise ValueError("selected pH protonation system identity mismatch")
        expected_atom_count = 7 if selected_state == "deprotonated" else 8
        expected_bond_count = 6 if selected_state == "deprotonated" else 7
        expected_element_counts = (
            {"C": 2, "H": 3, "O": 2}
            if selected_state == "deprotonated"
            else {"C": 2, "H": 4, "O": 2}
        )
        expected_selected_state = (
            "protonated"
            if protonated_fraction >= deprotonated_fraction
            else "deprotonated"
        )
        if (
            max(protonated_fraction, deprotonated_fraction) + 1.0e-15
            < MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION
            or selected_state != expected_selected_state
        ):
            raise ValueError("selected pH protonation population decision mismatch")
        if (
            report.get("atom_count") != expected_atom_count
            or report.get("bond_count") != expected_bond_count
            or report.get("removed_generated_hydrogen_count")
            != (1 if selected_state == "deprotonated" else 0)
            or report.get("formal_charge_delta")
            != (-1 if selected_state == "deprotonated" else 0)
            or {
                element: sum(atom.element == element for atom in system.atoms)
                for element in ("C", "H", "O")
            }
            != expected_element_counts
            or any(atom.element not in {"C", "H", "O"} for atom in system.atoms)
            or sum(bond.order == 2.0 for bond in system.bonds) != 1
            or sum(bond.order == 1.0 for bond in system.bonds)
            != expected_bond_count - 1
            or any(bond.order not in {1.0, 2.0} for bond in system.bonds)
            or any(atom.aromatic for atom in system.atoms)
            or any(bond.aromatic for bond in system.bonds)
            or sum(atom.formal_charge for atom in system.atoms)
            != (-1 if selected_state == "deprotonated" else 0)
            or any(
                _SHA256_RE.fullmatch(
                    str(atom.metadata.get("ph_protonation_atom_identity_sha256", ""))
                )
                is None
                for atom in system.atoms
            )
            or any(
                _SHA256_RE.fullmatch(
                    str(bond.metadata.get("ph_protonation_bond_identity_sha256", ""))
                )
                is None
                for bond in system.bonds
            )
        ):
            raise ValueError("selected pH protonation topology summary mismatch")
        for atom in system.atoms:
            expected_atom_identity = _sha256(
                {
                    "parent_atom_index": atom.metadata.get(
                        "ph_protonation_parent_atom_index"
                    ),
                    "parent_prepared_atom_identity_sha256": atom.metadata.get(
                        "prepared_atom_identity_sha256", ""
                    ),
                    "new_atom_index": atom.index,
                    "element": atom.element,
                    "formal_charge": atom.formal_charge,
                    "selected_state": selected_state,
                }
            )
            if (
                atom.metadata.get("ph_protonation_atom_identity_sha256")
                != expected_atom_identity
                or atom.metadata.get("ph_protonation_selected_state") != selected_state
                or atom.metadata.get("ph_protonation_profile_id")
                != MMCIF_NONPOLY_PH_PROTONATION_PROFILE_ID
            ):
                raise ValueError("selected pH protonation atom identity mismatch")
        for bond in system.bonds:
            expected_bond_identity = _sha256(
                {
                    "parent_bond_index": bond.metadata.get(
                        "ph_protonation_parent_bond_index"
                    ),
                    "parent_prepared_bond_identity_sha256": bond.metadata.get(
                        "prepared_bond_identity_sha256", ""
                    ),
                    "new_bond_index": bond.index,
                    "atom_i": bond.atom_i,
                    "atom_j": bond.atom_j,
                    "order": bond.order,
                    "selected_state": selected_state,
                }
            )
            if (
                bond.metadata.get("ph_protonation_bond_identity_sha256")
                != expected_bond_identity
                or bond.metadata.get("ph_protonation_selected_state") != selected_state
            ):
                raise ValueError("selected pH protonation bond identity mismatch")
        if selected_state == "deprotonated":
            if (
                sum(
                    atom.formal_charge == -1 and atom.element == "O"
                    for atom in system.atoms
                )
                != 1
                or any(atom.formal_charge not in {0, -1} for atom in system.atoms)
                or system.metadata.get("removed_generated_hydrogen_identity_sha256")
                != report.get("acidic_hydrogen_identity_sha256")
            ):
                raise ValueError("deprotonated pH protonation state mismatch")
        elif (
            any(atom.formal_charge != 0 for atom in system.atoms)
            or system.metadata.get("removed_generated_hydrogen_identity_sha256") != ""
        ):
            raise ValueError("protonated pH protonation state mismatch")
    elif status == _ABSTAINED_STATUS:
        if (
            selected_state != ""
            or blockers != ["minimum_dominant_population_not_met"]
            or report.get("state_selected") is not False
            or report.get("canonical_round_trip_verified") is not False
            or system_document is not None
            or any(
                report.get(key) not in {"", 0}
                for key in (
                    "system_sha256",
                    "topology_sha256",
                    "coordinates_sha256",
                    "canonical_round_trip_sha256",
                    "atom_count",
                    "bond_count",
                )
            )
            or max(protonated_fraction, deprotonated_fraction) + 1.0e-15
            >= MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION
        ):
            raise ValueError("abstained pH protonation report invalid")
    else:
        raise ValueError("pH protonation decision status invalid")
    if (
        document.get("decision_status") != status
        or document.get("selected_state") != selected_state
        or document.get("state_selected") != report.get("state_selected")
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
        or binding_dict.get("state_representation_policy")
        != "localized_carboxylate_without_resonance_or_tautomer_interpretation"
        or binding_dict.get("selection_equation") != "HA_fraction=1/(1+10^(pH-pKa))"
        or binding_dict.get("minimum_dominant_fraction")
        != MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION
        or binding_dict.get("minimum_dominant_fraction_binary64_hex")
        != _float_hex(MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION)
        or binding_dict.get("supported_ph_interval")
        != [
            MMCIF_NONPOLY_PH_PROTONATION_MIN_PH,
            MMCIF_NONPOLY_PH_PROTONATION_MAX_PH,
        ]
        or binding_dict.get("source_observed_hydrogen_policy") != "never_remove"
        or binding_dict.get("generated_hydrogen_policy")
        != "remove_exact_bound_hydroxyl_h_only"
    ):
        raise ValueError("pH protonation source binding mismatch")
    for key in (
        "source_sha256",
        "parent_all_atom_system_snapshot_sha256",
        "reference_snapshot_sha256",
    ):
        if _SHA256_RE.fullmatch(str(document.get(key, ""))) is None:
            raise ValueError("pH protonation document digest invalid")
    return payload


def mmcif_nonpoly_ph_protonation_json_bytes(
    snapshot: MmcifNonpolyPhProtonationSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_ph_protonation_document(snapshot))


def write_mmcif_nonpoly_ph_protonation_json(
    path: str | Path,
    snapshot: MmcifNonpolyPhProtonationSnapshot,
) -> Path:
    """Atomically write a private canonical pH-protonation document."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_ph_protonation_json_bytes(snapshot) + b"\n"
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
        os.replace(temporary_path, destination)
        os.chmod(destination, 0o600)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise
    return destination


__all__ = [
    "MMCIF_NONPOLY_PH_PROTONATION_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_PH_PROTONATION_ENGINE_VERSION",
    "MMCIF_NONPOLY_PH_PROTONATION_MAX_PH",
    "MMCIF_NONPOLY_PH_PROTONATION_MINIMUM_DOMINANT_FRACTION",
    "MMCIF_NONPOLY_PH_PROTONATION_MIN_PH",
    "MMCIF_NONPOLY_PH_PROTONATION_PROFILE_ID",
    "MMCIF_NONPOLY_PH_PROTONATION_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_COMPOUND_ID",
    "MMCIF_NONPOLY_PH_PROTONATION_REFERENCE_PKA",
    "MMCIF_NONPOLY_PH_PROTONATION_SOURCE_BINDING_SCHEMA_ID",
    "MmcifNonpolyPhProtonationError",
    "MmcifNonpolyPhProtonationReport",
    "MmcifNonpolyPhProtonationSnapshot",
    "apply_mmcif_nonpoly_ph_protonation",
    "mmcif_nonpoly_ph_protonation_document",
    "mmcif_nonpoly_ph_protonation_json_bytes",
    "mmcif_nonpoly_ph_protonation_projection",
    "mmcif_nonpoly_ph_protonation_reference_sha256",
    "mmcif_nonpoly_ph_protonation_source_binding",
    "require_mmcif_nonpoly_ph_protonation_document",
    "reviewed_mmcif_nonpoly_ph_protonation_reference",
    "write_mmcif_nonpoly_ph_protonation_json",
]
