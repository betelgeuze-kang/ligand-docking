"""Structure quality metrics: clash, Ramachandran proxy, LDDT-PLI, DockQ, TM-score proxies."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from betelgeuze_product.legacy_input_contract import (
    REASON_MISSING_REQUIRED_FIELD,
    LegacyInputPolicy as _LegacyInputPolicy,
    LegacyInputContractError,
    LegacyInputPolicy,
    strict_coordinate,
)

_LENIENT_COORDINATE_POLICY = _LegacyInputPolicy(compatibility_mode=True)

STRUCTURE_METRICS_CLAIM_BOUNDARY = (
    "Internal geometry proxies for structure quality reporting. "
    "Not validated MolProbity/OpenStructure parity."
)
STRUCTURE_QUALITY_CALIBRATION_STATUS = "internal_structure_quality_proxy_uncalibrated"

_VDW_RADII = {"H": 1.20, "C": 1.70, "N": 1.55, "O": 1.52, "S": 1.80, "P": 1.80, "DEFAULT": 1.70}


def _radius(element: str) -> float:
    return float(_VDW_RADII.get(str(element or "").upper()[:1], _VDW_RADII["DEFAULT"]))


def _parse_coordinate_columns(columns: list[Any]) -> tuple[float, float, float] | None:
    """Try to parse a coordinate triple without failing closed.

    Used to distinguish "this layout did not apply" (fixed-width columns are
    misaligned, so the whitespace layout should be tried) from "the coordinate
    is genuinely invalid".
    """

    return strict_coordinate(
        columns, field="pdb_atom_xyz", policy=_LENIENT_COORDINATE_POLICY
    )


def _strict_pdb_field(
    value: str,
    *,
    field: str,
    line_number: int,
    policy: LegacyInputPolicy,
    default: str,
) -> str:
    """Return a required PDB column, failing closed instead of placeholdering.

    The legacy parser substituted ``UNK``/``_``/``0`` for absent columns, which
    silently turned a malformed record into an analyzable atom.
    """

    text = str(value or "").strip()
    if text:
        return text
    if policy.compatibility_mode:
        return default
    raise LegacyInputContractError(
        REASON_MISSING_REQUIRED_FIELD, f"field={field} line={line_number}"
    )


def parse_pdb_atoms_with_coords(
    text: str,
    *,
    policy: LegacyInputPolicy | None = None,
) -> list[dict[str, Any]]:
    """Parse ``ATOM``/``HETATM`` rows into atoms with coordinates.

    With ``policy=None`` the historical lenient behaviour is kept for internal
    analysis tooling: unparseable coordinates and absent columns are skipped or
    placeholdered. Product intake passes a fail-closed
    :class:`~betelgeuze_product.legacy_input_contract.LegacyInputPolicy`, which
    turns those cases into
    :class:`~betelgeuze_product.legacy_input_contract.LegacyInputContractError`
    instead of a partially parsed structure.
    """

    active_policy = policy if policy is not None else LegacyInputPolicy(compatibility_mode=True)
    atoms: list[dict[str, Any]] = []
    for line_number, line in enumerate(str(text or "").splitlines(), start=1):
        record = line[:6].strip().upper()
        if record not in {"ATOM", "HETATM"}:
            continue
        columns = [line[30:38], line[38:46], line[46:54]]
        coordinate = _parse_coordinate_columns(columns)
        if coordinate is None:
            # Fixed-width columns did not apply (common in relaxed/legacy PDB
            # writers); try the whitespace layout before deciding the row is bad.
            fields = line.split()
            coordinate = _parse_coordinate_columns(fields[6:9] if len(fields) >= 9 else [])
        if coordinate is None:
            # Neither layout yields a usable coordinate: this is a real invalid
            # coordinate, so honor the caller's policy.
            coordinate = strict_coordinate(
                columns,
                field=f"pdb_atom_xyz(line={line_number})",
                policy=active_policy,
            )
        if coordinate is None:
            continue
        x, y, z = coordinate
        atom_name = line[12:16].strip() if len(line) >= 16 else ""
        resname = _strict_pdb_field(
            line[17:20] if len(line) >= 20 else "",
            field="resname",
            line_number=line_number,
            policy=active_policy,
            default="UNK",
        )
        chain_id = _strict_pdb_field(
            line[21:22] if len(line) >= 22 else "",
            field="chain_id",
            line_number=line_number,
            policy=active_policy,
            default="_",
        )
        resseq = _strict_pdb_field(
            line[22:26] if len(line) >= 26 else "",
            field="residue_id",
            line_number=line_number,
            policy=active_policy,
            default="0",
        )
        element = _strict_pdb_field(
            (line[76:78].strip() if len(line) >= 78 else "") or atom_name[:1],
            field="element",
            line_number=line_number,
            policy=active_policy,
            default=atom_name[:1],
        )
        atoms.append(
            {
                "record": record,
                "atom_name": atom_name.upper(),
                "resname": resname.upper(),
                "chain_id": chain_id,
                "residue_id": resseq,
                "element": element.upper(),
                "xyz": np.asarray([x, y, z], dtype=np.float64),
            }
        )
    return atoms


def coords_and_elements(atoms: list[dict[str, Any]]) -> tuple[np.ndarray, list[str]]:
    if not atoms:
        return np.zeros((0, 3), dtype=np.float64), []
    coords = np.stack([np.asarray(a["xyz"], dtype=np.float64) for a in atoms], axis=0)
    elements = [str(a.get("element", "C")) for a in atoms]
    return coords, elements


def molprobity_clashscore_proxy(
    coords: np.ndarray,
    elements: list[str] | None = None,
    *,
    clash_tolerance_a: float = 0.4,
    sample_cap: int = 800,
) -> float:
    """Lower is better. Counts VdW clash pairs per 1000 atoms (MolProbity-like scale)."""
    pts = np.asarray(coords, dtype=np.float64)
    n = pts.shape[0]
    if n < 2:
        return 0.0
    elems = elements or ["C"] * n
    idx = np.arange(n)
    if n > int(sample_cap):
        rng = np.random.default_rng(0)
        idx = np.sort(rng.choice(n, size=int(sample_cap), replace=False))
        pts = pts[idx]
        elems = [elems[int(i)] for i in idx]
        n = pts.shape[0]
    diff = pts[:, None, :] - pts[None, :, :]
    dist = np.linalg.norm(diff, axis=-1)
    tri = np.triu(np.ones((n, n), dtype=bool), k=1)
    clash_count = 0
    for i in range(n):
        for j in range(i + 1, n):
            if not tri[i, j]:
                continue
            cutoff = _radius(elems[i]) + _radius(elems[j]) - float(clash_tolerance_a)
            if dist[i, j] < cutoff:
                clash_count += 1
    return float(1000.0 * clash_count / max(n, 1))


def ramachandran_outlier_fraction(atoms: list[dict[str, Any]]) -> float | None:
    """Phi/psi outlier fraction from sequential CA atoms (proxy)."""
    ca = [a for a in atoms if str(a.get("atom_name", "")).upper() == "CA" and str(a.get("record", "")) == "ATOM"]
    if len(ca) < 4:
        return None
    outliers = 0
    total = 0
    for i in range(1, len(ca) - 2):
        p0 = ca[i - 1]["xyz"]
        p1 = ca[i]["xyz"]
        p2 = ca[i + 1]["xyz"]
        p3 = ca[i + 2]["xyz"]
        phi = _dihedral(p0, p1, p2, p3)
        psi = _dihedral(p1, p2, p3, ca[min(i + 3, len(ca) - 1)]["xyz"])
        total += 1
        if _ramachandran_outlier(phi, psi):
            outliers += 1
    return float(outliers / max(total, 1))


def _dihedral(p0, p1, p2, p3) -> float:
    b0 = np.asarray(p1, dtype=np.float64) - np.asarray(p0, dtype=np.float64)
    b1 = np.asarray(p2, dtype=np.float64) - np.asarray(p1, dtype=np.float64)
    b2 = np.asarray(p3, dtype=np.float64) - np.asarray(p2, dtype=np.float64)
    b1n = b1 / (np.linalg.norm(b1) + 1e-8)
    v = b0 - np.dot(b0, b1n) * b1n
    w = b2 - np.dot(b2, b1n) * b1n
    x = np.dot(v, w)
    y = np.linalg.norm(np.cross(b1n, v)) * np.linalg.norm(w) * np.sign(np.dot(np.cross(b1n, v), w))
    return float(math.degrees(math.atan2(y, x)))


def _ramachandran_outlier(phi_deg: float, psi_deg: float) -> bool:
    # Allowed core (very coarse): beta sheet + alpha helix bands
    in_beta = -180.0 <= phi_deg <= -60.0 and 90.0 <= psi_deg <= 180.0
    in_alpha = -120.0 <= phi_deg <= -30.0 and -80.0 <= psi_deg <= 40.0
    in_left = 30.0 <= phi_deg <= 100.0 and -40.0 <= psi_deg <= 60.0
    return not (in_beta or in_alpha or in_left)


def lddt_pli_proxy(model_coords: np.ndarray, reference_coords: np.ndarray, *, cutoff_a: float = 10.0) -> float | None:
    """Local distance difference test proxy (0–1, higher better)."""
    m = np.asarray(model_coords, dtype=np.float64)
    r = np.asarray(reference_coords, dtype=np.float64)
    n = min(m.shape[0], r.shape[0])
    if n < 2:
        return None
    m = m[:n]
    r = r[:n]
    dm = np.linalg.norm(m[:, None, :] - m[None, :, :], axis=-1)
    dr = np.linalg.norm(r[:, None, :] - r[None, :, :], axis=-1)
    local_scores: list[float] = []
    for i in range(n):
        neighbors = np.where((dm[i] > 0.0) & (dm[i] < float(cutoff_a)))[0]
        if neighbors.size == 0:
            continue
        diffs = np.abs(dm[i, neighbors] - dr[i, neighbors])
        scored = np.where(diffs < 0.5, 1.0, np.where(diffs < 1.0, 0.5, np.where(diffs < 2.0, 0.25, 0.0)))
        local_scores.append(float(np.mean(scored)))
    return float(np.mean(local_scores)) if local_scores else None


def kabsch_rmsd(a: np.ndarray, b: np.ndarray) -> float | None:
    aa = np.asarray(a, dtype=np.float64)
    bb = np.asarray(b, dtype=np.float64)
    n = min(aa.shape[0], bb.shape[0])
    if n < 1:
        return None
    aa = aa[:n] - aa[:n].mean(axis=0)
    bb = bb[:n] - bb[:n].mean(axis=0)
    h = aa.T @ bb
    u, _, vt = np.linalg.svd(h)
    r = vt.T @ u.T
    if np.linalg.det(r) < 0:
        vt[-1, :] *= -1
        r = vt.T @ u.T
    aligned = aa @ r
    return float(np.sqrt(np.mean(np.sum((aligned - bb) ** 2, axis=1))))


def tm_score_proxy(coords_a: np.ndarray, coords_b: np.ndarray) -> float | None:
    rmsd = kabsch_rmsd(coords_a, coords_b)
    if rmsd is None:
        return None
    n = min(coords_a.shape[0], coords_b.shape[0])
    d0 = 1.24 * (max(n, 15) - 15) ** (1.0 / 3.0) - 1.8
    d0 = max(float(d0), 0.5)
    return float(1.0 / (1.0 + (rmsd / d0) ** 2))


def dockq_proxy(
    model_coords: np.ndarray,
    reference_coords: np.ndarray,
    *,
    native_contact_cutoff_a: float = 5.0,
) -> float | None:
    """Simplified DockQ proxy from contact fraction + interface RMSD."""
    m = np.asarray(model_coords, dtype=np.float64)
    r = np.asarray(reference_coords, dtype=np.float64)
    n = min(m.shape[0], r.shape[0])
    if n < 2:
        return None
    m = m[:n]
    r = r[:n]
    dm = np.linalg.norm(m[:, None, :] - m[None, :, :], axis=-1)
    dr = np.linalg.norm(r[:, None, :] - r[None, :, :], axis=-1)
    native = dr < float(native_contact_cutoff_a)
    model_contacts = dm < float(native_contact_cutoff_a)
    native_pairs = np.sum(np.triu(native, k=1))
    if native_pairs <= 0:
        return None
    preserved = np.sum(np.triu(native & model_contacts, k=1))
    fnat = float(preserved / native_pairs)
    irms = kabsch_rmsd(m, r) or 999.0
    lrms = float(np.linalg.norm(m.mean(axis=0) - r.mean(axis=0)))
    return float(0.724 * fnat + 0.0130 * lrms + 0.0180 * irms + 0.0020)


def interface_contact_coverage(
    receptor_coords: np.ndarray,
    ligand_coords: np.ndarray,
    *,
    contact_cutoff_a: float = 5.0,
) -> dict[str, Any]:
    """Report simple receptor-ligand interface contact coverage."""
    rec = np.asarray(receptor_coords, dtype=np.float64)
    lig = np.asarray(ligand_coords, dtype=np.float64)
    if rec.size == 0 or lig.size == 0:
        return {
            "status": "blocked_interface_contact_coverage",
            "contact_count": 0,
            "receptor_contact_atom_count": 0,
            "ligand_contact_atom_count": 0,
            "interface_contact_fraction": 0.0,
            "min_interface_distance_a": None,
        }
    d = np.linalg.norm(rec[:, None, :] - lig[None, :, :], axis=-1)
    contacts = d <= float(contact_cutoff_a)
    contact_count = int(np.sum(contacts))
    receptor_contact_atom_count = int(np.sum(np.any(contacts, axis=1)))
    ligand_contact_atom_count = int(np.sum(np.any(contacts, axis=0)))
    total_pairs = int(max(d.size, 1))
    return {
        "status": "interface_contact_coverage_ready" if contact_count > 0 else "blocked_interface_contact_coverage",
        "contact_count": contact_count,
        "receptor_contact_atom_count": receptor_contact_atom_count,
        "ligand_contact_atom_count": ligand_contact_atom_count,
        "interface_contact_fraction": float(contact_count / total_pairs),
        "min_interface_distance_a": float(np.min(d)) if d.size else None,
    }


def structure_quality_claim_guard_report(
    atoms: list[dict[str, Any]],
    *,
    receptor_coords: np.ndarray | None = None,
    ligand_coords: np.ndarray | None = None,
    reference_atoms: list[dict[str, Any]] | None = None,
    molprobity_external_available: bool = False,
    openstructure_external_available: bool = False,
    native_complex_benchmark_ready: bool = False,
    max_clashscore_proxy: float = 50.0,
    min_interface_contacts: int = 1,
) -> dict[str, Any]:
    """Report structure-quality/interface coverage while keeping external parity claim fail-closed."""
    quality = evaluate_structure_quality(atoms, reference_atoms=reference_atoms)
    rec = np.asarray(receptor_coords, dtype=np.float64) if receptor_coords is not None else np.zeros((0, 3))
    lig = np.asarray(ligand_coords, dtype=np.float64) if ligand_coords is not None else np.zeros((0, 3))
    interface = interface_contact_coverage(rec, lig)
    clash = quality.get("molprobity_clashscore")
    clash_proxy_ready = clash is not None and float(clash) <= float(max_clashscore_proxy)
    interface_ready = int(interface["contact_count"]) >= int(min_interface_contacts)
    reference_metric_ready = bool(
        quality.get("lddt_pli") is not None
        and quality.get("dockq_proxy") is not None
        and quality.get("tm_score_proxy") is not None
    )
    claim_ready = False
    blockers: list[str] = []
    if not clash_proxy_ready:
        blockers.append("clashscore_proxy_threshold_not_met")
    if not interface_ready:
        blockers.append("interface_contact_coverage_not_ready")
    if not reference_metric_ready:
        blockers.append("native_reference_metrics_missing")
    if not molprobity_external_available:
        blockers.append("external_molprobity_not_available")
    if not openstructure_external_available:
        blockers.append("external_openstructure_not_available")
    if not native_complex_benchmark_ready:
        blockers.append("native_complex_benchmark_not_ready")
    blockers.append("structure_quality_proxy_not_external_parity")
    return {
        "status": "claim_grade_structure_quality_ready" if claim_ready else "blocked_structure_quality_claim",
        "calibration_status": STRUCTURE_QUALITY_CALIBRATION_STATUS,
        "structure_quality_proxy_surface_ready": bool(clash_proxy_ready and interface_ready),
        "claim_grade_structure_quality_ready": claim_ready,
        "molprobity_clashscore_proxy": clash,
        "clashscore_proxy_ready": clash_proxy_ready,
        "ramachandran_outlier_fraction": quality.get("ramachandran_outlier_fraction"),
        "reference_metric_surface_ready": reference_metric_ready,
        "lddt_pli": quality.get("lddt_pli"),
        "dockq_proxy": quality.get("dockq_proxy"),
        "tm_score_proxy": quality.get("tm_score_proxy"),
        "interface": interface,
        "molprobity_external_available": bool(molprobity_external_available),
        "openstructure_external_available": bool(openstructure_external_available),
        "native_complex_benchmark_ready": bool(native_complex_benchmark_ready),
        "blockers": blockers,
        "claim_boundary": STRUCTURE_METRICS_CLAIM_BOUNDARY,
    }


def evaluate_structure_quality(
    atoms: list[dict[str, Any]],
    *,
    reference_atoms: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    coords, elements = coords_and_elements(atoms)
    quality: dict[str, Any] = {
        "molprobity_clashscore": molprobity_clashscore_proxy(coords, elements) if coords.size else None,
        "ramachandran_outlier_fraction": ramachandran_outlier_fraction(atoms),
        "claim_boundary": STRUCTURE_METRICS_CLAIM_BOUNDARY,
    }
    if reference_atoms:
        ref_coords, _ = coords_and_elements(reference_atoms)
        quality["lddt_pli"] = lddt_pli_proxy(coords, ref_coords)
        quality["dockq_proxy"] = dockq_proxy(coords, ref_coords)
        quality["tm_score_proxy"] = tm_score_proxy(coords, ref_coords)
    return quality
