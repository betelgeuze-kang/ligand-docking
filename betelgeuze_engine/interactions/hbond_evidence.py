from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from betelgeuze_engine.backmapping.onsps import (
    MAX_ONSPS_SITES,
    ONSPS_BACKMAP_SCHEMA_VERSION,
    backmap_4bead_onsps,
    hbond_angle_score,
    onsps_hbond_sites_from_smiles,
)
from betelgeuze_engine.contracts.claim import default_claim_metadata

try:
    from rdkit import Chem  # type: ignore
except Exception:  # pragma: no cover
    Chem = None

HBOND_EVIDENCE_SCHEMA_VERSION = "hbond_evidence_v1"
HBOND_CLAIM_METADATA_SCHEMA_VERSION = "hbond_claim_metadata_v1"


def _onsps_metadata_schema_ready(metadata: dict[str, Any]) -> bool:
    return bool(
        isinstance(metadata, dict)
        and metadata.get("schema_version") == ONSPS_BACKMAP_SCHEMA_VERSION
        and "site_count" in metadata
        and "mapped_site_count" in metadata
        and "claim_safe" in metadata
        and "blocked_reason" in metadata
    )


@dataclass
class HbondEvidence:
    site_count: int
    donor_site_count: int
    acceptor_site_count: int
    donor_acceptor_pairs: list[dict[str, Any]]
    distance_pass_count: int
    angle_pass_count: int
    distance_pass_fraction: float
    angle_pass_fraction: float
    unsatisfied_donor_count: int
    unsatisfied_acceptor_count: int
    overanchoring_flag: bool
    missing_expected_anchor_flag: bool
    geometry_evaluated: bool
    geometry_complete: bool
    hbond_confidence: float
    claim_safe: bool
    status: str = "not_assessed"
    schema_version: str = HBOND_EVIDENCE_SCHEMA_VERSION
    abstention_reason: str = ""
    blocked_reason: str = ""
    thresholds: dict[str, float] = field(default_factory=dict)
    onsps_backmap_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def schema_ready(self) -> bool:
        """Return whether the evidence carries the product H-bond/ONSPS schema surface."""
        return bool(
            self.schema_version == HBOND_EVIDENCE_SCHEMA_VERSION
            and self.site_count >= 0
            and self.donor_site_count >= 0
            and self.acceptor_site_count >= 0
            and self.distance_pass_count >= 0
            and self.angle_pass_count >= 0
            and self.unsatisfied_donor_count >= 0
            and self.unsatisfied_acceptor_count >= 0
            and isinstance(self.donor_acceptor_pairs, list)
            and _onsps_metadata_schema_ready(self.onsps_backmap_metadata)
        )

    def to_claim_metadata(
        self,
        *,
        topology_fidelity: str = "not_assessed",
        ligand_topology_valid: bool = False,
        force_residual_applied: bool = False,
        product_claim_promoted: bool = False,
        extra_blocked_reasons: list[str] | None = None,
    ) -> dict[str, Any]:
        """Convert H-bond evidence into the shared product claim metadata contract.

        H-bond evidence can prove the interaction schema is ready, but it should not
        promote a product claim by itself. Callers must opt in with
        ``product_claim_promoted`` after topology, manifest, and runner gates pass.
        """
        blockers: list[str] = []
        schema_ready = self.schema_ready()
        if str(topology_fidelity or "") != "sequence_mapped":
            blockers.append("topology_not_sequence_mapped")
        if not ligand_topology_valid:
            blockers.append("ligand_topology_invalid")
        if not schema_ready:
            blockers.append("hbond_evidence_schema_not_ready")
        if self.status != "pass" or not self.claim_safe:
            blockers.append(str(self.blocked_reason or "hbond_evidence_review_required"))
        if not product_claim_promoted:
            blockers.append("hbond_evidence_not_product_claim_promoted")
        if extra_blocked_reasons:
            blockers.extend(str(reason) for reason in extra_blocked_reasons if str(reason or ""))
        blockers = list(dict.fromkeys(reason for reason in blockers if reason))
        claim_safe = bool(product_claim_promoted and not blockers)
        onsps_meta = self.onsps_backmap_metadata if isinstance(self.onsps_backmap_metadata, dict) else {}
        return default_claim_metadata(
            topology_fidelity=str(topology_fidelity or "not_assessed"),
            ligand_topology_valid=bool(ligand_topology_valid),
            hbond_evidence_status=str(self.status or "not_assessed"),
            force_residual_applied=bool(force_residual_applied),
            claim_safe=claim_safe,
            blocked_reason="" if claim_safe else ";".join(blockers),
            hbond_claim_metadata_schema_version=HBOND_CLAIM_METADATA_SCHEMA_VERSION,
            hbond_evidence_schema_version=str(self.schema_version),
            hbond_evidence_schema_ready=schema_ready,
            hbond_claim_safe=bool(self.claim_safe),
            hbond_site_count=int(self.site_count),
            hbond_donor_site_count=int(self.donor_site_count),
            hbond_acceptor_site_count=int(self.acceptor_site_count),
            hbond_distance_pass_count=int(self.distance_pass_count),
            hbond_angle_pass_count=int(self.angle_pass_count),
            hbond_distance_pass_fraction=float(self.distance_pass_fraction),
            hbond_angle_pass_fraction=float(self.angle_pass_fraction),
            hbond_unsatisfied_donor_count=int(self.unsatisfied_donor_count),
            hbond_unsatisfied_acceptor_count=int(self.unsatisfied_acceptor_count),
            hbond_overanchoring_flag=bool(self.overanchoring_flag),
            hbond_missing_expected_anchor_flag=bool(self.missing_expected_anchor_flag),
            hbond_geometry_evaluated=bool(self.geometry_evaluated),
            hbond_geometry_complete=bool(self.geometry_complete),
            hbond_confidence=float(self.hbond_confidence),
            onsps_backmap_schema_version=str(
                onsps_meta.get("schema_version") or ONSPS_BACKMAP_SCHEMA_VERSION
            ),
            onsps_backmap_metadata_schema_ready=_onsps_metadata_schema_ready(onsps_meta),
            onsps_backmap_claim_safe=bool(onsps_meta.get("claim_safe") is True),
            onsps_backmap_status=str(onsps_meta.get("backmap_status") or ""),
            onsps_backmap_source=str(onsps_meta.get("mapping_source") or ""),
            onsps_backmap_blocked_reason=str(onsps_meta.get("blocked_reason") or ""),
            onsps_backmap_site_count=int(onsps_meta.get("site_count") or 0),
            onsps_backmap_mapped_site_count=int(onsps_meta.get("mapped_site_count") or 0),
        )


def _invalid_smiles(smiles: str) -> bool:
    smi = str(smiles or "").strip()
    if not smi:
        return True
    if Chem is None:
        return False
    return Chem.MolFromSmiles(smi) is None


def _thresholds(
    *,
    min_distance: float,
    max_distance: float,
    overanchor_distance: float,
    angle_threshold: float,
) -> dict[str, float]:
    return {
        "min_distance": float(min_distance),
        "max_distance": float(max_distance),
        "overanchor_distance": float(overanchor_distance),
        "angle_threshold": float(angle_threshold),
        "claim_safe_confidence_min": 0.5,
    }


def _onsps_backmap_not_claim_safe_metadata(
    blocked_reason: str,
    *,
    backmap_status: str = "not_evaluated",
    site_count: int = 0,
) -> dict[str, Any]:
    reason = str(blocked_reason or "onsps_backmap_not_evaluated")
    return {
        "schema_version": ONSPS_BACKMAP_SCHEMA_VERSION,
        "site_count": int(site_count),
        "mapped_site_count": 0,
        "elements": [],
        "roles": [],
        "role_counts": {"donor": 0, "acceptor": 0, "none": 0},
        "backmap_status": str(backmap_status or "not_evaluated"),
        "mapping_source": "",
        "input_bead_count": 0,
        "output_shape": [],
        "claim_safe": False,
        "abstention_reason": reason,
        "blocked_reason": reason,
        "max_onsps_sites": MAX_ONSPS_SITES,
        "thresholds": {"min_input_beads": 2.0},
    }


def _blocked_reason(
    *,
    site_count: int,
    protein_present: bool,
    distance_pass: int,
    confidence: float,
    overanchoring: bool,
    missing_anchor: bool,
    onsps_blocked_reason: str = "",
) -> str:
    if site_count <= 0:
        return "no_hbond_sites"
    if not protein_present:
        return "pose_geometry_missing"
    if onsps_blocked_reason:
        return onsps_blocked_reason
    if overanchoring:
        return "overanchored_decoy"
    if missing_anchor or distance_pass <= 0:
        return "missing_expected_anchor"
    if confidence < 0.5:
        return "low_hbond_confidence"
    return ""


def evaluate_hbond_evidence(
    *,
    smiles: str,
    protein_xyz: np.ndarray | None = None,
    ligand_xyz: np.ndarray | None = None,
    pocket_center: np.ndarray | None = None,
    min_distance: float = 2.4,
    max_distance: float = 3.5,
    overanchor_distance: float = 2.1,
    angle_threshold: float = 0.55,
) -> HbondEvidence:
    if _invalid_smiles(smiles):
        return HbondEvidence(
            site_count=0,
            donor_site_count=0,
            acceptor_site_count=0,
            donor_acceptor_pairs=[],
            distance_pass_count=0,
            angle_pass_count=0,
            distance_pass_fraction=0.0,
            angle_pass_fraction=0.0,
            unsatisfied_donor_count=0,
            unsatisfied_acceptor_count=0,
            overanchoring_flag=False,
            missing_expected_anchor_flag=True,
            geometry_evaluated=False,
            geometry_complete=False,
            hbond_confidence=0.0,
            claim_safe=False,
            status="invalid_smiles",
            abstention_reason="invalid_smiles",
            blocked_reason="invalid_smiles",
            thresholds=_thresholds(
                min_distance=min_distance,
                max_distance=max_distance,
                overanchor_distance=overanchor_distance,
                angle_threshold=angle_threshold,
            ),
            onsps_backmap_metadata=_onsps_backmap_not_claim_safe_metadata(
                "invalid_smiles",
                backmap_status="invalid_smiles",
            ),
        )

    sites = onsps_hbond_sites_from_smiles(smiles)
    site_count = len(sites)
    donor_site_count = sum(1 for site in sites if str(site.role) == "donor")
    acceptor_site_count = sum(1 for site in sites if str(site.role) == "acceptor")
    ligand_sites = np.asarray(ligand_xyz, dtype=np.float32) if ligand_xyz is not None else np.zeros((0, 3), dtype=np.float32)
    onsps_backmap_metadata: dict[str, Any] = _onsps_backmap_not_claim_safe_metadata(
        "ligand_geometry_missing",
        site_count=site_count,
    )
    if ligand_sites.ndim == 2 and ligand_sites.shape[0] == 2 and site_count:
        ligand_sites, onsps_backmap_metadata = backmap_4bead_onsps(ligand_sites, smiles)
    elif site_count <= 0:
        onsps_backmap_metadata = _onsps_backmap_not_claim_safe_metadata(
            "no_hbond_sites",
            backmap_status="no_onsps_sites",
            site_count=site_count,
        )
    protein = np.asarray(protein_xyz, dtype=np.float32) if protein_xyz is not None else np.zeros((0, 3), dtype=np.float32)
    center = np.asarray(pocket_center, dtype=np.float32) if pocket_center is not None else None
    geometry_evaluated = bool(protein.size and ligand_sites.ndim == 2 and ligand_sites.shape[0] > 0)
    geometry_complete = bool(
        site_count > 0
        and protein.size
        and ligand_sites.ndim == 2
        and int(ligand_sites.shape[0]) >= int(site_count)
    )

    pairs: list[dict[str, Any]] = []
    distance_pass = 0
    angle_pass = 0
    overanchoring = False
    unsatisfied_donor = 0
    unsatisfied_acceptor = 0
    for i, site in enumerate(sites):
        role = str(site.role)
        dist = float("inf")
        angle = 0.0
        if protein.size and ligand_sites.ndim == 2 and i < ligand_sites.shape[0]:
            d = np.linalg.norm(protein - ligand_sites[i].reshape(1, 3), axis=1)
            dist = float(np.min(d))
            if center is not None:
                angle = float(hbond_angle_score(protein, ligand_sites[i], center))
        dist_ok = bool(float(min_distance) <= dist <= float(max_distance))
        angle_ok = bool(angle >= float(angle_threshold)) if center is not None and protein.size else False
        if dist < float(overanchor_distance):
            overanchoring = True
        if dist_ok:
            distance_pass += 1
        if angle_ok:
            angle_pass += 1
        if not dist_ok:
            if role == "donor":
                unsatisfied_donor += 1
            elif role == "acceptor":
                unsatisfied_acceptor += 1
        pairs.append(
            {
                "site_index": int(i),
                "atom_idx": int(site.atom_idx),
                "element": str(site.element),
                "role": role,
                "nearest_distance": dist,
                "distance_pass": dist_ok,
                "angle_score": angle,
                "angle_pass": angle_ok,
            }
        )

    denom = max(site_count, 1)
    distance_fraction = float(distance_pass / denom)
    angle_fraction = float(angle_pass / denom)
    missing_anchor = bool(site_count > 0 and distance_pass == 0 and protein.size)
    confidence = float(max(0.0, min(1.0, 0.65 * distance_fraction + 0.35 * angle_fraction)))
    onsps_required = bool(
        onsps_backmap_metadata
        and str(onsps_backmap_metadata.get("backmap_status") or "") not in {"not_evaluated", "no_onsps_sites"}
    )
    onsps_claim_safe = bool(not onsps_required or onsps_backmap_metadata.get("claim_safe") is True)
    onsps_blocked_reason = "" if onsps_claim_safe else str(
        onsps_backmap_metadata.get("blocked_reason") or "onsps_backmap_not_claim_safe"
    )
    claim_safe = bool(
        site_count > 0
        and confidence >= 0.5
        and not overanchoring
        and not missing_anchor
        and onsps_claim_safe
    )
    blocked = "" if claim_safe else _blocked_reason(
        site_count=site_count,
        protein_present=bool(protein.size),
        distance_pass=distance_pass,
        confidence=confidence,
        overanchoring=overanchoring,
        missing_anchor=missing_anchor,
        onsps_blocked_reason=onsps_blocked_reason,
    )
    return HbondEvidence(
        site_count=site_count,
        donor_site_count=int(donor_site_count),
        acceptor_site_count=int(acceptor_site_count),
        donor_acceptor_pairs=pairs,
        distance_pass_count=int(distance_pass),
        angle_pass_count=int(angle_pass),
        distance_pass_fraction=distance_fraction,
        angle_pass_fraction=angle_fraction,
        unsatisfied_donor_count=int(unsatisfied_donor),
        unsatisfied_acceptor_count=int(unsatisfied_acceptor),
        overanchoring_flag=overanchoring,
        missing_expected_anchor_flag=missing_anchor,
        geometry_evaluated=geometry_evaluated,
        geometry_complete=geometry_complete,
        hbond_confidence=confidence,
        claim_safe=claim_safe,
        status="pass" if claim_safe else "review",
        abstention_reason="" if claim_safe else blocked,
        blocked_reason=blocked,
        thresholds=_thresholds(
            min_distance=min_distance,
            max_distance=max_distance,
            overanchor_distance=overanchor_distance,
            angle_threshold=angle_threshold,
        ),
        onsps_backmap_metadata=onsps_backmap_metadata,
    )
