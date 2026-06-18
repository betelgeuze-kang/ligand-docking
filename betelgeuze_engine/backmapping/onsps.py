"""O/N/P/S H-bond 4-bead backmapping for product engine scoring evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
except Exception:  # pragma: no cover - optional
    Chem = None
    AllChem = None

MAX_ONSPS_SITES = 4
_ELEMENT_PRIORITY = {"O": 0, "N": 1, "S": 2, "P": 3}
_ACCEPTOR_ATOMIC_NUM = {8, 7, 16, 15}


@dataclass(frozen=True)
class OnspsSite:
    atom_idx: int
    element: str
    role: str
    local_xyz: np.ndarray


@dataclass(frozen=True)
class OnspsBackmapEvidence:
    site_count: int
    mapped_site_count: int
    elements: list[str]
    roles: list[str]
    role_counts: dict[str, int]
    backmap_status: str
    mapping_source: str
    input_bead_count: int
    output_shape: list[int]
    claim_safe: bool
    schema_version: str = "onsps_backmap_evidence_v1"
    abstention_reason: str = ""
    blocked_reason: str = ""
    max_onsps_sites: int = MAX_ONSPS_SITES
    thresholds: dict[str, float] = field(default_factory=lambda: {"min_input_beads": 2.0})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _role_counts(roles: list[str]) -> dict[str, int]:
    return {
        "donor": sum(1 for role in roles if role == "donor"),
        "acceptor": sum(1 for role in roles if role == "acceptor"),
        "none": sum(1 for role in roles if role == "none"),
    }


def _backmap_evidence(
    *,
    sites: list[OnspsSite],
    mapped_site_count: int,
    backmap_status: str,
    mapping_source: str,
    input_bead_count: int,
    output_shape: tuple[int, ...] | list[int],
    blocked_reason: str = "",
) -> OnspsBackmapEvidence:
    elements = [s.element for s in sites[:mapped_site_count]]
    roles = [s.role for s in sites[:mapped_site_count]]
    if not blocked_reason:
        if backmap_status == "empty_input":
            blocked_reason = "invalid_two_bead_geometry"
        elif backmap_status == "no_onsps_sites":
            blocked_reason = "no_onsps_sites"
        elif mapping_source != "rdkit_etkdg":
            blocked_reason = "onsps_fallback_not_claim_safe"
    claim_safe = bool(
        backmap_status == "ok"
        and mapping_source == "rdkit_etkdg"
        and int(input_bead_count) >= 2
        and int(mapped_site_count) > 0
        and not blocked_reason
    )
    return OnspsBackmapEvidence(
        site_count=len(sites),
        mapped_site_count=int(mapped_site_count),
        elements=elements,
        roles=roles,
        role_counts=_role_counts(roles),
        backmap_status=str(backmap_status),
        mapping_source=str(mapping_source),
        input_bead_count=int(input_bead_count),
        output_shape=[int(v) for v in output_shape],
        claim_safe=claim_safe,
        abstention_reason="" if claim_safe else blocked_reason,
        blocked_reason="" if claim_safe else blocked_reason,
    )


def _role_for_atom(atom: Any) -> str:
    z = int(atom.GetAtomicNum())
    if z not in _ACCEPTOR_ATOMIC_NUM:
        return "none"
    has_h = any(int(n.GetAtomicNum()) == 1 for n in atom.GetNeighbors())
    if has_h:
        return "donor"
    return "acceptor"


def _fallback_sites_from_smiles(smiles: str) -> list[OnspsSite]:
    smi = str(smiles or "").strip().upper()
    if not smi:
        return []
    ordered: list[tuple[str, str]] = []
    for ch in smi:
        if ch == "O":
            ordered.append(("O", "acceptor"))
        elif ch == "N":
            ordered.append(("N", "donor"))
        elif ch == "S":
            ordered.append(("S", "donor"))
        elif ch == "P":
            ordered.append(("P", "acceptor"))
    sites: list[OnspsSite] = []
    for idx, (element, role) in enumerate(ordered[:MAX_ONSPS_SITES]):
        sites.append(
            OnspsSite(
                atom_idx=int(idx),
                element=element,
                role=role,
                local_xyz=np.asarray([float(idx) * 0.8, 0.1 * float(idx), 0.0], dtype=np.float32),
            )
        )
    return sites


def _onsps_hbond_sites_from_smiles_with_source(smiles: str) -> tuple[list[OnspsSite], str]:
    smi = str(smiles or "").strip()
    if not smi:
        return [], "empty_smiles"
    if Chem is None:
        return _fallback_sites_from_smiles(smi), "fallback_smiles"
    try:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            return _fallback_sites_from_smiles(smi), "fallback_smiles"
        mol = Chem.AddHs(mol)
        params = AllChem.ETKDGv3()
        params.randomSeed = 0x4F4E
        if AllChem.EmbedMolecule(mol, params) != 0:
            return _fallback_sites_from_smiles(smi), "fallback_smiles"
        conf = mol.GetConformer()
        candidates: list[OnspsSite] = []
        for atom in mol.GetAtoms():
            z = int(atom.GetAtomicNum())
            if z == 8:
                element = "O"
            elif z == 7:
                element = "N"
            elif z == 16:
                element = "S"
            elif z == 15:
                element = "P"
            else:
                continue
            role = _role_for_atom(atom)
            if role == "none":
                continue
            pos = conf.GetAtomPosition(int(atom.GetIdx()))
            candidates.append(
                OnspsSite(
                    atom_idx=int(atom.GetIdx()),
                    element=element,
                    role=role,
                    local_xyz=np.asarray([float(pos.x), float(pos.y), float(pos.z)], dtype=np.float32),
                )
            )
        candidates.sort(
            key=lambda s: (
                _ELEMENT_PRIORITY.get(s.element, 9),
                0 if s.role == "donor" else 1,
                int(s.atom_idx),
            )
        )
        return candidates[:MAX_ONSPS_SITES], "rdkit_etkdg"
    except Exception:
        return _fallback_sites_from_smiles(smi), "fallback_smiles"


def onsps_hbond_sites_from_smiles(smiles: str) -> list[OnspsSite]:
    sites, _source = _onsps_hbond_sites_from_smiles_with_source(smiles)
    return sites


def onsps_site_count(smiles: str) -> int:
    return len(onsps_hbond_sites_from_smiles(smiles))


def _kabsch(mobile: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mobile_c = mobile - mobile.mean(axis=0, keepdims=True)
    target_c = target - target.mean(axis=0, keepdims=True)
    h = mobile_c.T @ target_c
    u, _s, vt = np.linalg.svd(h)
    r = vt.T @ u.T
    if np.linalg.det(r) < 0:
        vt[-1, :] *= -1.0
        r = vt.T @ u.T
    t = target.mean(axis=0) - (r @ mobile.mean(axis=0))
    return r.astype(np.float32), t.astype(np.float32)


def _two_bead_reference_from_sites(sites: list[OnspsSite]) -> np.ndarray:
    if not sites:
        return np.zeros((0, 3), dtype=np.float32)
    coords = np.stack([s.local_xyz for s in sites], axis=0)
    if coords.shape[0] == 1:
        return np.stack([coords[0], coords[0] + np.asarray([1.6, 0.0, 0.0], dtype=np.float32)], axis=0)
    return np.stack([coords[0], coords[min(1, coords.shape[0] - 1)]], axis=0)


def backmap_4bead_onsps(two_bead_xyz: np.ndarray, smiles: str) -> tuple[np.ndarray, dict[str, Any]]:
    """Map a 2-bead trajectory frame to up to four ONSPS H-bond beads."""
    lig = np.asarray(two_bead_xyz, dtype=np.float32)
    input_bead_count = int(lig.shape[0]) if lig.ndim == 2 else 0
    if lig.ndim != 2 or lig.shape[1] != 3 or lig.shape[0] < 2:
        evidence = _backmap_evidence(
            sites=[],
            mapped_site_count=0,
            backmap_status="empty_input",
            mapping_source="none",
            input_bead_count=input_bead_count,
            output_shape=tuple(lig.shape),
        )
        return lig, evidence.to_dict()

    sites, mapping_source = _onsps_hbond_sites_from_smiles_with_source(smiles)
    if not sites:
        out = lig[:2]
        evidence = _backmap_evidence(
            sites=[],
            mapped_site_count=0,
            backmap_status="no_onsps_sites",
            mapping_source=mapping_source,
            input_bead_count=input_bead_count,
            output_shape=tuple(out.shape),
        )
        return out, evidence.to_dict()

    ref_two = _two_bead_reference_from_sites(sites)
    mobile = ref_two
    target = lig[:2]
    rot, trans = _kabsch(mobile, target)
    mapped = []
    for site in sites:
        mapped.append((rot @ site.local_xyz) + trans)
    out = np.stack(mapped, axis=0).astype(np.float32, copy=False)
    evidence = _backmap_evidence(
        sites=sites,
        mapped_site_count=int(out.shape[0]),
        backmap_status="ok",
        mapping_source=mapping_source,
        input_bead_count=input_bead_count,
        output_shape=tuple(out.shape),
    )
    return out, evidence.to_dict()


def evaluate_onsps_backmap_evidence(two_bead_xyz: np.ndarray, smiles: str) -> OnspsBackmapEvidence:
    _mapped, meta = backmap_4bead_onsps(two_bead_xyz, smiles)
    return OnspsBackmapEvidence(
        site_count=int(meta.get("site_count") or 0),
        mapped_site_count=int(meta.get("mapped_site_count") or 0),
        elements=list(meta.get("elements") or []),
        roles=list(meta.get("roles") or []),
        role_counts=dict(meta.get("role_counts") or {}),
        backmap_status=str(meta.get("backmap_status") or "not_assessed"),
        mapping_source=str(meta.get("mapping_source") or ""),
        input_bead_count=int(meta.get("input_bead_count") or 0),
        output_shape=[int(v) for v in meta.get("output_shape") or []],
        claim_safe=bool(meta.get("claim_safe") is True),
        schema_version=str(meta.get("schema_version") or "onsps_backmap_evidence_v1"),
        abstention_reason=str(meta.get("abstention_reason") or ""),
        blocked_reason=str(meta.get("blocked_reason") or ""),
        max_onsps_sites=int(meta.get("max_onsps_sites") or MAX_ONSPS_SITES),
        thresholds=dict(meta.get("thresholds") or {"min_input_beads": 2.0}),
    )


def needs_onsps_4bead(
    *,
    smiles: str,
    family: str = "",
    rank_pct: float = 1.0,
    top_k_threshold_pct: float = 0.05,
) -> bool:
    if onsps_site_count(smiles) <= 0:
        return False
    fam = str(family or "").strip().lower().replace("-", "_")
    if fam in {"gpcr", "kinase", "ion_channel"}:
        return True
    return float(rank_pct) <= float(top_k_threshold_pct)


def hbond_angle_score(protein_xyz: np.ndarray, ligand_bead: np.ndarray, pocket_center: np.ndarray) -> float:
    prot = np.asarray(protein_xyz, dtype=np.float32)
    bead = np.asarray(ligand_bead, dtype=np.float32)
    center = np.asarray(pocket_center, dtype=np.float32)
    if prot.size == 0:
        return 0.0
    d = np.linalg.norm(prot - bead.reshape(1, 3), axis=1)
    anchor = prot[int(np.argmin(d))]
    v1 = anchor - bead
    v2 = center - bead
    n1 = float(np.linalg.norm(v1))
    n2 = float(np.linalg.norm(v2))
    if n1 <= 1e-6 or n2 <= 1e-6:
        return 0.0
    cos_val = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
    return float(max(0.0, cos_val))


__all__ = [
    "MAX_ONSPS_SITES",
    "OnspsBackmapEvidence",
    "OnspsSite",
    "backmap_4bead_onsps",
    "evaluate_onsps_backmap_evidence",
    "hbond_angle_score",
    "needs_onsps_4bead",
    "onsps_hbond_sites_from_smiles",
    "onsps_site_count",
]
