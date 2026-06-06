"""O/N/P/S H-bond 4-bead backmapping for scoring-stage refinement."""

from __future__ import annotations

from dataclasses import dataclass
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


def onsps_hbond_sites_from_smiles(smiles: str) -> list[OnspsSite]:
    smi = str(smiles or "").strip()
    if not smi:
        return []
    if Chem is None:
        return _fallback_sites_from_smiles(smi)
    try:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            return _fallback_sites_from_smiles(smi)
        mol = Chem.AddHs(mol)
        params = AllChem.ETKDGv3()
        params.randomSeed = 0x4F4E
        if AllChem.EmbedMolecule(mol, params) != 0:
            return _fallback_sites_from_smiles(smi)
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
        return candidates[:MAX_ONSPS_SITES]
    except Exception:
        return _fallback_sites_from_smiles(smi)


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
    meta: dict[str, Any] = {
        "site_count": 0,
        "elements": [],
        "roles": [],
        "backmap_status": "empty_input",
    }
    if lig.ndim != 2 or lig.shape[1] != 3 or lig.shape[0] < 2:
        return lig, meta

    sites = onsps_hbond_sites_from_smiles(smiles)
    if not sites:
        meta["backmap_status"] = "no_onsps_sites"
        return lig[:2], meta

    ref_two = _two_bead_reference_from_sites(sites)
    mobile = ref_two
    target = lig[:2]
    rot, trans = _kabsch(mobile, target)
    mapped = []
    for site in sites:
        mapped.append((rot @ site.local_xyz) + trans)
    out = np.stack(mapped, axis=0).astype(np.float32, copy=False)
    meta.update(
        {
            "site_count": int(out.shape[0]),
            "elements": [s.element for s in sites[: out.shape[0]]],
            "roles": [s.role for s in sites[: out.shape[0]]],
            "backmap_status": "ok",
        }
    )
    return out, meta


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
