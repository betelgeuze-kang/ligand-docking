#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

try:  # pragma: no cover - optional dependency path is covered by tests when installed.
    import openmm as mm  # type: ignore
    from openmm import unit  # type: ignore
except Exception:  # pragma: no cover
    mm = None  # type: ignore
    unit = None  # type: ignore

try:  # pragma: no cover - optional dependency path is covered by tests when installed.
    from rdkit import Chem  # type: ignore
    from rdkit.Chem import AllChem  # type: ignore
    from rdkit.Geometry import Point3D  # type: ignore
except Exception:  # pragma: no cover
    Chem = None  # type: ignore
    AllChem = None  # type: ignore
    Point3D = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT_CSV = "runs/gpcr_drd2_pseudo_allatom_repair_rows_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_drd2_local_minimization_survival_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_drd2_local_minimization_survival_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_drd2_local_minimization_survival_current.md"
DEFAULT_POSITIVE_LIGAND = "CHEMBL301265"

DEFAULT_RMSD_THRESHOLD_A = 2.0
DEFAULT_SURVIVAL_MIN = 0.55
DEFAULT_MAX_FRAMES_PER_ROW = 24
DEFAULT_LIGAND_POSE_RESTRAINT_K_KJ_MOL_NM2 = 2500.0

OPENMM_CUSTOM_ENGINE = "openmm_custom_protein_ligand_bounded"
OPENMM_LIGAND_ONLY_ENGINE = "openmm_custom_ligand_only_bounded"
RDKIT_LIGAND_ONLY_ENGINE = "rdkit_uff_ligand_only"

GENERIC_PROTEIN_ATOMIC_NUMBER = 6

ATOMIC_NUMBER_TO_ELEMENT = {
    1: "H",
    6: "C",
    7: "N",
    8: "O",
    9: "F",
    15: "P",
    16: "S",
    17: "Cl",
    35: "Br",
    53: "I",
}
ELEMENT_TO_ATOMIC_NUMBER = {value.upper(): key for key, value in ATOMIC_NUMBER_TO_ELEMENT.items()}

VDW_SIGMA_NM = {
    1: 0.250,
    6: 0.340,
    7: 0.325,
    8: 0.305,
    9: 0.295,
    15: 0.374,
    16: 0.356,
    17: 0.347,
    35: 0.365,
    53: 0.400,
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "t", "yes", "y"}


def _float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, dict, np.ndarray)):
        return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True)
    if isinstance(value, np.generic):
        return value.item()
    return value


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_cell(row.get(key)) for key in fieldnames})


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(payload), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _frame_indices(frame_count: int, max_frames: int) -> list[int]:
    count = int(max(frame_count, 0))
    limit = int(max(max_frames, 1))
    if count <= 0:
        return []
    if count <= limit:
        return list(range(count))
    raw = np.linspace(0, count - 1, num=limit)
    indices: list[int] = []
    for value in raw:
        idx = int(round(float(value)))
        idx = int(min(max(idx, 0), count - 1))
        if idx not in indices:
            indices.append(idx)
    cursor = 0
    while len(indices) < limit and cursor < count:
        if cursor not in indices:
            indices.append(cursor)
        cursor += 1
    return sorted(indices)


def _absolute_rmsd_A(reference: np.ndarray, mobile: np.ndarray) -> float:
    ref = np.asarray(reference, dtype=float)
    mob = np.asarray(mobile, dtype=float)
    return float(np.sqrt(np.mean(np.sum((mob - ref) ** 2, axis=1))))


def _aligned_rmsd_A(reference: np.ndarray, mobile: np.ndarray) -> float:
    ref = np.asarray(reference, dtype=float)
    mob = np.asarray(mobile, dtype=float)
    if ref.shape[0] <= 1:
        return _absolute_rmsd_A(ref, mob)
    ref_cent = ref - ref.mean(axis=0, keepdims=True)
    mob_cent = mob - mob.mean(axis=0, keepdims=True)
    cov = mob_cent.T @ ref_cent
    u, _s, vt = np.linalg.svd(cov)
    reflect = np.eye(3)
    reflect[2, 2] = np.sign(np.linalg.det(u @ vt)) or 1.0
    rotation = u @ reflect @ vt
    aligned = mob_cent @ rotation
    return float(np.sqrt(np.mean(np.sum((aligned - ref_cent) ** 2, axis=1))))


def _normal_quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"median": None, "p90": None, "max": None}
    arr = np.asarray(values, dtype=float)
    return {
        "median": float(np.median(arr)),
        "p90": float(np.percentile(arr, 90)),
        "max": float(np.max(arr)),
    }


def _atomic_numbers_from_elements(elements: np.ndarray, expected_count: int) -> list[int] | None:
    if elements.shape[0] != expected_count:
        return None
    out: list[int] = []
    for item in elements:
        key = str(item).strip().upper()
        atomic = ELEMENT_TO_ATOMIC_NUMBER.get(key)
        if atomic is None:
            return None
        out.append(int(atomic))
    return out


def _atomic_numbers_from_smiles(smiles: str, expected_count: int) -> list[int] | None:
    if Chem is None:
        return None
    mol = Chem.MolFromSmiles(_text(smiles))
    if mol is None:
        return None
    atomic_numbers = [int(atom.GetAtomicNum()) for atom in mol.GetAtoms() if atom.GetAtomicNum() > 1]
    return atomic_numbers if len(atomic_numbers) == expected_count else None


def _ligand_atomic_numbers(
    arrays: dict[str, np.ndarray],
    smiles: str,
    ligand_atom_count: int,
) -> tuple[list[int], list[str]]:
    blockers: list[str] = []
    if "ligand_atom_atomic_numbers" in arrays:
        values = np.asarray(arrays["ligand_atom_atomic_numbers"]).reshape(-1)
        if values.shape[0] == ligand_atom_count:
            out = [int(value) for value in values]
            if all(value > 0 for value in out):
                return out, blockers
    if "ligand_atom_elements" in arrays:
        from_elements = _atomic_numbers_from_elements(np.asarray(arrays["ligand_atom_elements"]).reshape(-1), ligand_atom_count)
        if from_elements is not None:
            return from_elements, blockers
    from_smiles = _atomic_numbers_from_smiles(smiles, ligand_atom_count)
    if from_smiles is not None:
        blockers.append("ligand_atom_types_inferred_from_smiles")
        return from_smiles, blockers
    blockers.append("ligand_atom_types_missing_default_generic_carbon")
    return [6] * int(ligand_atom_count), blockers


def _protein_atomic_numbers(arrays: dict[str, np.ndarray], protein_atom_count: int) -> tuple[list[int], list[str]]:
    blockers: list[str] = []
    if protein_atom_count <= 0:
        return [], blockers
    if "protein_atom_atomic_numbers" in arrays:
        values = np.asarray(arrays["protein_atom_atomic_numbers"]).reshape(-1)
        if values.shape[0] == protein_atom_count:
            out = [int(value) for value in values]
            if all(value > 0 for value in out):
                return out, blockers
    if "protein_atom_elements" in arrays:
        from_elements = _atomic_numbers_from_elements(np.asarray(arrays["protein_atom_elements"]).reshape(-1), protein_atom_count)
        if from_elements is not None:
            return from_elements, blockers
    blockers.append("protein_atom_types_missing_generic_vdw")
    return [GENERIC_PROTEIN_ATOMIC_NUMBER] * int(protein_atom_count), blockers


def _load_npz_arrays(path_text: str) -> tuple[dict[str, np.ndarray] | None, str]:
    path = _resolve(path_text) if path_text else None
    if path is None or not path.exists():
        return None, "trajectory_npz_missing"
    try:
        with np.load(str(path), allow_pickle=False) as npz:
            arrays = {key: np.asarray(npz[key]) for key in npz.files}
    except Exception as exc:
        return None, f"trajectory_npz_unreadable:{type(exc).__name__}"
    return arrays, "ok"


def _select_engine(requested: str, has_protein: bool) -> tuple[str | None, list[str]]:
    engine = str(requested or "auto").strip().lower()
    blockers: list[str] = []
    if engine == "auto":
        if mm is not None:
            return OPENMM_CUSTOM_ENGINE if has_protein else OPENMM_LIGAND_ONLY_ENGINE, blockers
        if Chem is not None and AllChem is not None:
            blockers.append("openmm_unavailable_used_rdkit_ligand_only")
            return RDKIT_LIGAND_ONLY_ENGINE, blockers
        return None, ["minimization_engine_unavailable"]
    if engine in {"openmm_custom", OPENMM_CUSTOM_ENGINE}:
        if mm is None:
            return None, ["openmm_unavailable"]
        return OPENMM_CUSTOM_ENGINE if has_protein else OPENMM_LIGAND_ONLY_ENGINE, blockers
    if engine in {"rdkit_uff", "rdkit_uff_ligand_only", RDKIT_LIGAND_ONLY_ENGINE}:
        if Chem is None or AllChem is None or Point3D is None:
            return None, ["rdkit_unavailable"]
        return RDKIT_LIGAND_ONLY_ENGINE, blockers
    return None, [f"unknown_engine:{engine}"]


def _vdw_sigma(atomic_number: int) -> float:
    return float(VDW_SIGMA_NM.get(int(atomic_number), VDW_SIGMA_NM[6]))


def _build_openmm_system(
    *,
    ligand_coords_A: np.ndarray,
    protein_coords_A: np.ndarray | None,
    ligand_atomic_numbers: list[int],
    protein_atomic_numbers: list[int],
    basic_indices: list[int],
    anchor_indices: list[int],
    ligand_pose_restraint_k_kj_mol_nm2: float,
    ligand_internal_k_kj_mol_nm2: float,
    protein_restraint_k_kj_mol_nm2: float,
    salt_bridge_k_kj_mol_nm2: float,
    salt_bridge_distance_A: float,
    vdw_epsilon_kj_mol: float,
    vdw_cutoff_nm: float,
    softcore_nm: float,
) -> Any:
    if mm is None or unit is None:  # pragma: no cover
        raise RuntimeError("OpenMM is not available")
    ligand_nm = np.asarray(ligand_coords_A, dtype=float) / 10.0
    protein_nm = (
        np.asarray(protein_coords_A, dtype=float) / 10.0
        if protein_coords_A is not None and np.asarray(protein_coords_A).size
        else np.zeros((0, 3), dtype=float)
    )
    n_ligand = int(ligand_nm.shape[0])
    n_protein = int(protein_nm.shape[0])
    coords_nm = np.concatenate([ligand_nm, protein_nm], axis=0)

    system = mm.System()
    for _idx in range(n_ligand):
        system.addParticle(12.0 * unit.dalton)
    for _idx in range(n_protein):
        system.addParticle(12.0 * unit.dalton)

    if float(ligand_pose_restraint_k_kj_mol_nm2) > 0.0:
        ligand_restraint = mm.CustomExternalForce("0.5*k*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
        ligand_restraint.addPerParticleParameter("x0")
        ligand_restraint.addPerParticleParameter("y0")
        ligand_restraint.addPerParticleParameter("z0")
        ligand_restraint.addPerParticleParameter("k")
        for i in range(n_ligand):
            x0, y0, z0 = [float(v) for v in ligand_nm[i]]
            ligand_restraint.addParticle(i, [x0, y0, z0, float(ligand_pose_restraint_k_kj_mol_nm2)])
        system.addForce(ligand_restraint)

    internal = mm.CustomBondForce("0.5*k*(r-r0)^2")
    internal.addPerBondParameter("r0")
    internal.addPerBondParameter("k")
    for i in range(n_ligand):
        for j in range(i + 1, n_ligand):
            distance = float(np.linalg.norm(ligand_nm[i] - ligand_nm[j]))
            if distance > 1e-5:
                internal.addBond(i, j, [distance, float(ligand_internal_k_kj_mol_nm2)])
    system.addForce(internal)

    if n_protein:
        protein_restraint = mm.CustomExternalForce("0.5*k*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
        protein_restraint.addPerParticleParameter("x0")
        protein_restraint.addPerParticleParameter("y0")
        protein_restraint.addPerParticleParameter("z0")
        protein_restraint.addPerParticleParameter("k")
        for j in range(n_protein):
            idx = n_ligand + j
            x0, y0, z0 = [float(v) for v in protein_nm[j]]
            protein_restraint.addParticle(idx, [x0, y0, z0, float(protein_restraint_k_kj_mol_nm2)])
        system.addForce(protein_restraint)

        nonbonded = mm.CustomNonbondedForce(
            "4*epsilon*((sigma/rs)^12-(sigma/rs)^6);"
            "rs=sqrt(r*r+softcore*softcore);"
            "sigma=0.5*(sigma1+sigma2);"
            "epsilon=sqrt(epsilon1*epsilon2)"
        )
        nonbonded.addPerParticleParameter("sigma")
        nonbonded.addPerParticleParameter("epsilon")
        nonbonded.addGlobalParameter("softcore", float(softcore_nm))
        nonbonded.setNonbondedMethod(mm.CustomNonbondedForce.CutoffNonPeriodic)
        nonbonded.setCutoffDistance(float(vdw_cutoff_nm) * unit.nanometer)
        nonbonded.setUseLongRangeCorrection(False)
        for atomic in ligand_atomic_numbers:
            nonbonded.addParticle([_vdw_sigma(int(atomic)), float(vdw_epsilon_kj_mol)])
        for atomic in protein_atomic_numbers:
            nonbonded.addParticle([_vdw_sigma(int(atomic)), float(vdw_epsilon_kj_mol)])
        nonbonded.addInteractionGroup(set(range(n_ligand)), set(range(n_ligand, n_ligand + n_protein)))
        system.addForce(nonbonded)

        valid_basic = [int(idx) for idx in basic_indices if 0 <= int(idx) < n_ligand]
        valid_anchor = [int(idx) for idx in anchor_indices if 0 <= int(idx) < n_protein]
        if valid_basic and valid_anchor:
            salt = mm.CustomBondForce("0.5*k*(r-r0)^2")
            salt.addPerBondParameter("r0")
            salt.addPerBondParameter("k")
            target_nm = float(salt_bridge_distance_A) / 10.0
            for basic in valid_basic:
                for anchor in valid_anchor:
                    salt.addBond(basic, n_ligand + anchor, [target_nm, float(salt_bridge_k_kj_mol_nm2)])
            system.addForce(salt)

    return system, coords_nm


def _openmm_minimize_frame(
    *,
    ligand_coords_A: np.ndarray,
    protein_coords_A: np.ndarray | None,
    ligand_atomic_numbers: list[int],
    protein_atomic_numbers: list[int],
    basic_indices: list[int],
    anchor_indices: list[int],
    max_iterations: int,
    tolerance_kj_mol_nm: float,
    ligand_pose_restraint_k_kj_mol_nm2: float,
    ligand_internal_k_kj_mol_nm2: float,
    protein_restraint_k_kj_mol_nm2: float,
    salt_bridge_k_kj_mol_nm2: float,
    salt_bridge_distance_A: float,
    vdw_epsilon_kj_mol: float,
    vdw_cutoff_nm: float,
    softcore_nm: float,
) -> dict[str, Any]:
    if mm is None or unit is None:  # pragma: no cover
        return {"ok": False, "reason": "openmm_unavailable"}
    n_ligand = int(np.asarray(ligand_coords_A).shape[0])
    try:
        system, coords_nm = _build_openmm_system(
            ligand_coords_A=ligand_coords_A,
            protein_coords_A=protein_coords_A,
            ligand_atomic_numbers=ligand_atomic_numbers,
            protein_atomic_numbers=protein_atomic_numbers,
            basic_indices=basic_indices,
            anchor_indices=anchor_indices,
            ligand_pose_restraint_k_kj_mol_nm2=ligand_pose_restraint_k_kj_mol_nm2,
            ligand_internal_k_kj_mol_nm2=ligand_internal_k_kj_mol_nm2,
            protein_restraint_k_kj_mol_nm2=protein_restraint_k_kj_mol_nm2,
            salt_bridge_k_kj_mol_nm2=salt_bridge_k_kj_mol_nm2,
            salt_bridge_distance_A=salt_bridge_distance_A,
            vdw_epsilon_kj_mol=vdw_epsilon_kj_mol,
            vdw_cutoff_nm=vdw_cutoff_nm,
            softcore_nm=softcore_nm,
        )
        integrator = mm.VerletIntegrator(0.001 * unit.picoseconds)
        context = mm.Context(system, integrator)
        context.setPositions(coords_nm * unit.nanometer)
        state0 = context.getState(getEnergy=True)
        energy_before = float(state0.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole))
        mm.LocalEnergyMinimizer.minimize(
            context,
            float(tolerance_kj_mol_nm) * unit.kilojoule_per_mole / unit.nanometer,
            int(max(max_iterations, 1)),
        )
        state1 = context.getState(getEnergy=True, getPositions=True)
        energy_after = float(state1.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole))
        positions = state1.getPositions(asNumpy=True).value_in_unit(unit.angstrom)
        minimized = np.asarray(positions[:n_ligand], dtype=np.float64)
        del context, integrator
        return {
            "ok": True,
            "minimized_ligand_coords_A": minimized,
            "energy_before_kj_mol": energy_before,
            "energy_after_kj_mol": energy_after,
        }
    except Exception as exc:
        return {"ok": False, "reason": f"openmm_minimization_failed:{type(exc).__name__}"}


def _rdkit_mol_for_frame(smiles: str, coords_A: np.ndarray) -> Any:
    if Chem is None or Point3D is None:  # pragma: no cover
        return None
    mol = Chem.MolFromSmiles(_text(smiles))
    if mol is None:
        return None
    heavy_atoms = [atom for atom in mol.GetAtoms() if atom.GetAtomicNum() > 1]
    if len(heavy_atoms) != int(coords_A.shape[0]):
        return None
    mol = Chem.Mol(mol)
    conf = Chem.Conformer(int(coords_A.shape[0]))
    for idx, xyz in enumerate(np.asarray(coords_A, dtype=float)):
        conf.SetAtomPosition(int(idx), Point3D(float(xyz[0]), float(xyz[1]), float(xyz[2])))
    mol.RemoveAllConformers()
    mol.AddConformer(conf, assignId=True)
    return mol


def _rdkit_uff_minimize_frame(*, smiles: str, ligand_coords_A: np.ndarray, max_iterations: int) -> dict[str, Any]:
    if Chem is None or AllChem is None or Point3D is None:  # pragma: no cover
        return {"ok": False, "reason": "rdkit_unavailable"}
    try:
        mol = _rdkit_mol_for_frame(smiles, np.asarray(ligand_coords_A, dtype=float))
        if mol is None:
            return {"ok": False, "reason": "rdkit_molecule_unavailable_or_atom_count_mismatch"}
        if not bool(AllChem.UFFHasAllMoleculeParams(mol)):
            return {"ok": False, "reason": "rdkit_uff_parameters_unavailable"}
        ff = AllChem.UFFGetMoleculeForceField(mol, confId=0)
        if ff is None:
            return {"ok": False, "reason": "rdkit_uff_forcefield_unavailable"}
        energy_before = float(ff.CalcEnergy())
        rc = int(ff.Minimize(maxIts=int(max(max_iterations, 1))))
        energy_after = float(ff.CalcEnergy())
        conf = mol.GetConformer()
        minimized = []
        for atom_idx in range(mol.GetNumAtoms()):
            atom = mol.GetAtomWithIdx(atom_idx)
            if atom.GetAtomicNum() <= 1:
                continue
            pos = conf.GetAtomPosition(atom_idx)
            minimized.append([float(pos.x), float(pos.y), float(pos.z)])
        return {
            "ok": rc in (0, 1),
            "reason": "ok" if rc in (0, 1) else f"rdkit_uff_minimize_rc:{rc}",
            "minimized_ligand_coords_A": np.asarray(minimized, dtype=np.float64),
            "energy_before_kj_mol": energy_before,
            "energy_after_kj_mol": energy_after,
        }
    except Exception as exc:
        return {"ok": False, "reason": f"rdkit_uff_minimization_failed:{type(exc).__name__}"}


def _scope_for_engine(engine_kind: str, has_protein: bool) -> str:
    if engine_kind == RDKIT_LIGAND_ONLY_ENGINE or not has_protein:
        return "ligand_only"
    if engine_kind == OPENMM_CUSTOM_ENGINE:
        return "bounded_custom_protein_ligand_not_full_forcefield"
    return "none"


def _engine_limitation_blockers(engine_kind: str, has_protein: bool) -> list[str]:
    if engine_kind == OPENMM_CUSTOM_ENGINE and has_protein:
        return [
            "full_protein_ligand_forcefield_parameterization_unavailable",
            "custom_force_minimizer_not_equivalent_to_full_protein_ligand_forcefield",
            "protein_coordinates_restrained_to_input_frame",
        ]
    if engine_kind in {OPENMM_LIGAND_ONLY_ENGINE, RDKIT_LIGAND_ONLY_ENGINE} or not has_protein:
        return [
            "ligand_only_not_protein_ligand_minimization",
            "ligand_only_evidence_not_promoted_to_broad_or_commercial_hard_gate",
        ]
    return []


def _evaluate_row(
    row: dict[str, str],
    *,
    requested_engine: str,
    positive_ligand: str,
    rmsd_threshold_A: float,
    survival_min: float,
    max_frames_per_row: int,
    openmm_max_iterations: int,
    rdkit_max_iterations: int,
    tolerance_kj_mol_nm: float,
    ligand_pose_restraint_k_kj_mol_nm2: float,
    ligand_internal_k_kj_mol_nm2: float,
    protein_restraint_k_kj_mol_nm2: float,
    salt_bridge_k_kj_mol_nm2: float,
    salt_bridge_distance_A: float,
    vdw_epsilon_kj_mol: float,
    vdw_cutoff_nm: float,
    softcore_nm: float,
) -> dict[str, Any]:
    target = _text(row.get("target"))
    ligand_id = _text(row.get("ligand_id"))
    smiles = _text(row.get("ligand_smiles") or row.get("smiles"))
    trajectory_npz = _text(row.get("trajectory_npz"))
    is_positive = _truthy(row.get("is_positive")) or ligand_id == positive_ligand
    base: dict[str, Any] = {
        "target": target,
        "ligand_id": ligand_id,
        "is_positive": bool(is_positive),
        "engine_kind": "",
        "requested_engine": requested_engine,
        "survival_fraction": None,
        "rmsd_threshold_A": float(rmsd_threshold_A),
        "frame_count": 0,
        "attempted_frame_count": 0,
        "minimized_frame_count": 0,
        "survived_frame_count": 0,
        "failed_frame_count": 0,
        "survival_claim_scope": "none",
        "local_minimization_survival_gate_pass": False,
        "rmsd_alignment_mode": "",
        "trajectory_npz": trajectory_npz,
        "ligand_atom_count": 0,
        "protein_atom_count": 0,
        "frame_indices_minimized": [],
        "rmsd_A_median": None,
        "rmsd_A_p90": None,
        "rmsd_A_max": None,
        "energy_before_kj_mol_median": None,
        "energy_after_kj_mol_median": None,
        "blockers": [],
        "frame_failures": [],
    }

    arrays, load_reason = _load_npz_arrays(trajectory_npz)
    if arrays is None:
        return {**base, "blockers": [load_reason]}

    ligand_frames = np.asarray(arrays.get("ligand_frames", np.zeros((0, 0, 3), dtype=np.float32)), dtype=float)
    if ligand_frames.ndim != 3 or ligand_frames.shape[0] <= 0 or ligand_frames.shape[1] <= 0 or ligand_frames.shape[2] != 3:
        return {**base, "blockers": ["ligand_frames_invalid"]}
    frame_count = int(ligand_frames.shape[0])
    ligand_atom_count = int(ligand_frames.shape[1])

    protein_frames: np.ndarray | None = None
    if "protein_atom_frames" in arrays:
        maybe_protein = np.asarray(arrays["protein_atom_frames"], dtype=float)
        if maybe_protein.ndim == 3 and maybe_protein.shape[0] >= frame_count and maybe_protein.shape[2] == 3:
            protein_frames = maybe_protein
    if protein_frames is None and "ligand_backmapping_static_anchor_coords" in arrays:
        static_anchor = np.asarray(arrays["ligand_backmapping_static_anchor_coords"], dtype=float)
        if static_anchor.ndim == 2 and static_anchor.shape[0] > 0 and static_anchor.shape[1] == 3:
            protein_frames = np.repeat(static_anchor[None, :, :], frame_count, axis=0)
    has_protein = bool(protein_frames is not None and protein_frames.shape[1] > 0)
    protein_atom_count = int(protein_frames.shape[1]) if has_protein and protein_frames is not None else 0
    engine_kind, engine_blockers = _select_engine(requested_engine, has_protein)
    if engine_kind is None:
        return {
            **base,
            "frame_count": frame_count,
            "ligand_atom_count": ligand_atom_count,
            "protein_atom_count": protein_atom_count,
            "blockers": engine_blockers,
        }

    ligand_atomic_numbers, ligand_type_blockers = _ligand_atomic_numbers(arrays, smiles, ligand_atom_count)
    protein_atomic_numbers, protein_type_blockers = _protein_atomic_numbers(arrays, protein_atom_count)
    basic_indices = [int(idx) for idx in np.asarray(arrays.get("ligand_basic_amine_atom_indices", []), dtype=int).reshape(-1)]
    anchor_indices = [int(idx) for idx in np.asarray(arrays.get("ligand_backmapping_anchor_atom_indices", []), dtype=int).reshape(-1)]
    if has_protein and not anchor_indices and "ligand_backmapping_static_anchor_coords" in arrays:
        anchor_indices = list(range(protein_atom_count))
    selected_indices = _frame_indices(frame_count, max_frames_per_row)

    rmsds: list[float] = []
    energy_before_values: list[float] = []
    energy_after_values: list[float] = []
    frame_failures: list[dict[str, Any]] = []
    survived = 0
    minimized = 0
    alignment_mode = "protein_frame_absolute" if engine_kind == OPENMM_CUSTOM_ENGINE and has_protein else "ligand_heavy_atom_kabsch"

    for frame_idx in selected_indices:
        ligand_coords = np.asarray(ligand_frames[frame_idx], dtype=float)
        if not np.isfinite(ligand_coords).all():
            frame_failures.append({"frame_index": int(frame_idx), "reason": "ligand_frame_nonfinite"})
            continue
        protein_coords = None
        if has_protein and protein_frames is not None:
            protein_coords = np.asarray(protein_frames[frame_idx], dtype=float)
            if not np.isfinite(protein_coords).all():
                frame_failures.append({"frame_index": int(frame_idx), "reason": "protein_frame_nonfinite"})
                continue
        if engine_kind in {OPENMM_CUSTOM_ENGINE, OPENMM_LIGAND_ONLY_ENGINE}:
            result = _openmm_minimize_frame(
                ligand_coords_A=ligand_coords,
                protein_coords_A=protein_coords if engine_kind == OPENMM_CUSTOM_ENGINE else None,
                ligand_atomic_numbers=ligand_atomic_numbers,
                protein_atomic_numbers=protein_atomic_numbers if engine_kind == OPENMM_CUSTOM_ENGINE else [],
                basic_indices=basic_indices,
                anchor_indices=anchor_indices if engine_kind == OPENMM_CUSTOM_ENGINE else [],
                max_iterations=openmm_max_iterations,
                tolerance_kj_mol_nm=tolerance_kj_mol_nm,
                ligand_pose_restraint_k_kj_mol_nm2=ligand_pose_restraint_k_kj_mol_nm2,
                ligand_internal_k_kj_mol_nm2=ligand_internal_k_kj_mol_nm2,
                protein_restraint_k_kj_mol_nm2=protein_restraint_k_kj_mol_nm2,
                salt_bridge_k_kj_mol_nm2=salt_bridge_k_kj_mol_nm2,
                salt_bridge_distance_A=salt_bridge_distance_A,
                vdw_epsilon_kj_mol=vdw_epsilon_kj_mol,
                vdw_cutoff_nm=vdw_cutoff_nm,
                softcore_nm=softcore_nm,
            )
        else:
            result = _rdkit_uff_minimize_frame(
                smiles=smiles,
                ligand_coords_A=ligand_coords,
                max_iterations=rdkit_max_iterations,
            )
        if not result.get("ok"):
            frame_failures.append({"frame_index": int(frame_idx), "reason": str(result.get("reason") or "minimization_failed")})
            continue
        minimized_coords = np.asarray(result["minimized_ligand_coords_A"], dtype=float)
        if minimized_coords.shape != ligand_coords.shape or not np.isfinite(minimized_coords).all():
            frame_failures.append({"frame_index": int(frame_idx), "reason": "minimized_ligand_frame_invalid"})
            continue
        rmsd = (
            _absolute_rmsd_A(ligand_coords, minimized_coords)
            if alignment_mode == "protein_frame_absolute"
            else _aligned_rmsd_A(ligand_coords, minimized_coords)
        )
        rmsds.append(float(rmsd))
        energy_before = _float(result.get("energy_before_kj_mol"))
        energy_after = _float(result.get("energy_after_kj_mol"))
        if energy_before is not None:
            energy_before_values.append(float(energy_before))
        if energy_after is not None:
            energy_after_values.append(float(energy_after))
        minimized += 1
        if rmsd <= float(rmsd_threshold_A):
            survived += 1

    attempted = int(len(selected_indices))
    failed = int(attempted - minimized)
    survival_fraction = float(survived / attempted) if attempted else None
    rmsd_summary = _normal_quantiles(rmsds)
    before_summary = _normal_quantiles(energy_before_values)
    after_summary = _normal_quantiles(energy_after_values)
    blockers = sorted(
        set(
            engine_blockers
            + ligand_type_blockers
            + protein_type_blockers
            + _engine_limitation_blockers(engine_kind, has_protein)
        )
    )
    if failed:
        blockers.append("one_or_more_frame_minimizations_failed")
    if survival_fraction is None:
        blockers.append("local_minimization_survival_unmeasured")
    elif survival_fraction < float(survival_min):
        blockers.append("local_minimization_survival_below_min")
    scope = _scope_for_engine(engine_kind, has_protein)
    return {
        **base,
        "engine_kind": engine_kind,
        "survival_fraction": survival_fraction,
        "frame_count": frame_count,
        "attempted_frame_count": attempted,
        "minimized_frame_count": minimized,
        "survived_frame_count": int(survived),
        "failed_frame_count": failed,
        "survival_claim_scope": scope,
        "local_minimization_survival_gate_pass": bool(
            survival_fraction is not None
            and survival_fraction >= float(survival_min)
            and failed == 0
            and scope not in {"none"}
        ),
        "rmsd_alignment_mode": alignment_mode,
        "ligand_atom_count": ligand_atom_count,
        "protein_atom_count": protein_atom_count,
        "frame_indices_minimized": [int(idx) for idx in selected_indices],
        "rmsd_A_median": rmsd_summary["median"],
        "rmsd_A_p90": rmsd_summary["p90"],
        "rmsd_A_max": rmsd_summary["max"],
        "energy_before_kj_mol_median": before_summary["median"],
        "energy_after_kj_mol_median": after_summary["median"],
        "blockers": sorted(set(blockers)),
        "frame_failures": frame_failures,
    }


def build_survival(
    *,
    input_csv: str | Path = DEFAULT_INPUT_CSV,
    requested_engine: str = "auto",
    positive_ligand: str = DEFAULT_POSITIVE_LIGAND,
    rmsd_threshold_A: float = DEFAULT_RMSD_THRESHOLD_A,
    survival_min: float = DEFAULT_SURVIVAL_MIN,
    max_frames_per_row: int = DEFAULT_MAX_FRAMES_PER_ROW,
    openmm_max_iterations: int = 200,
    rdkit_max_iterations: int = 200,
    tolerance_kj_mol_nm: float = 10.0,
    ligand_pose_restraint_k_kj_mol_nm2: float = DEFAULT_LIGAND_POSE_RESTRAINT_K_KJ_MOL_NM2,
    ligand_internal_k_kj_mol_nm2: float = 2500.0,
    protein_restraint_k_kj_mol_nm2: float = 50000.0,
    salt_bridge_k_kj_mol_nm2: float = 500.0,
    salt_bridge_distance_A: float = 3.2,
    vdw_epsilon_kj_mol: float = 0.05,
    vdw_cutoff_nm: float = 1.2,
    softcore_nm: float = 0.02,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    input_rows = _read_csv(input_csv)
    rows = [
        _evaluate_row(
            row,
            requested_engine=requested_engine,
            positive_ligand=positive_ligand,
            rmsd_threshold_A=float(rmsd_threshold_A),
            survival_min=float(survival_min),
            max_frames_per_row=int(max_frames_per_row),
            openmm_max_iterations=int(openmm_max_iterations),
            rdkit_max_iterations=int(rdkit_max_iterations),
            tolerance_kj_mol_nm=float(tolerance_kj_mol_nm),
            ligand_pose_restraint_k_kj_mol_nm2=float(ligand_pose_restraint_k_kj_mol_nm2),
            ligand_internal_k_kj_mol_nm2=float(ligand_internal_k_kj_mol_nm2),
            protein_restraint_k_kj_mol_nm2=float(protein_restraint_k_kj_mol_nm2),
            salt_bridge_k_kj_mol_nm2=float(salt_bridge_k_kj_mol_nm2),
            salt_bridge_distance_A=float(salt_bridge_distance_A),
            vdw_epsilon_kj_mol=float(vdw_epsilon_kj_mol),
            vdw_cutoff_nm=float(vdw_cutoff_nm),
            softcore_nm=float(softcore_nm),
        )
        for row in input_rows
    ]
    positive_rows = [row for row in rows if row.get("is_positive")]
    positive = positive_rows[0] if positive_rows else {}
    measured_rows = [row for row in rows if row.get("survival_fraction") is not None]
    positive_fraction = positive.get("survival_fraction")
    positive_engine_kind = _text(positive.get("engine_kind"))
    positive_scope = _text(positive.get("survival_claim_scope"))
    positive_blockers = list(positive.get("blockers") or [])
    hard_decoy_rebuild_evidence_allowed = bool(
        positive_fraction is not None
        and float(positive_fraction) >= float(survival_min)
        and positive_scope == "full_protein_ligand_forcefield"
        and not positive_blockers
    )
    claim_boundary_note = (
        "This packet measures bounded local-minimization survival only. OpenMM custom-force rows are not equivalent "
        "to fully parameterized protein-ligand forcefield minimization; ligand-only RDKit/UFF rows are ligand_only "
        "evidence and must not be promoted to broad/commercial hard gates."
    )
    status = "local_minimization_survival_unmeasured"
    if measured_rows:
        status = "bounded_local_minimization_survival_measured"
    if input_rows and len(measured_rows) < len(input_rows):
        status = "bounded_local_minimization_survival_partial"
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "input_csv": _artifact(input_csv),
        "input_row_count": int(len(input_rows)),
        "measured_row_count": int(len(measured_rows)),
        "requested_engine": str(requested_engine),
        "engine_kinds": sorted({_text(row.get("engine_kind")) for row in rows if _text(row.get("engine_kind"))}),
        "positive_ligand_id": positive_ligand,
        "positive_local_minimization_survival_fraction": positive_fraction,
        "positive_engine_kind": positive_engine_kind or None,
        "positive_blockers": positive_blockers,
        "rmsd_threshold_A": float(rmsd_threshold_A),
        "local_minimization_survival_min": float(survival_min),
        "max_frames_per_row": int(max_frames_per_row),
        "ligand_pose_restraint_k_kj_mol_nm2": float(ligand_pose_restraint_k_kj_mol_nm2),
        "hard_decoy_rebuild_evidence_allowed": hard_decoy_rebuild_evidence_allowed,
        "broad_commercial_hard_gate_evidence_allowed": False,
        "claim_boundary": claim_boundary_note,
        "forcefield_parameterization_boundary": (
            "No full DRD2 protein-ligand forcefield parameterization is claimed by this tool. Generic/custom "
            "protein-ligand forces and protein coordinate restraints are recorded as blockers."
        ),
    }
    claim_boundary = {
        "fake_pass_allowed": False,
        "proxy_metric_substitution_allowed": False,
        "hard_decoy_rebuild_evidence_allowed": hard_decoy_rebuild_evidence_allowed,
        "broad_commercial_hard_gate_evidence_allowed": False,
        "full_protein_ligand_forcefield_minimization_claimed": False,
        "bounded_custom_force_not_equivalent_to_full_forcefield": any(
            row.get("engine_kind") == OPENMM_CUSTOM_ENGINE for row in rows
        ),
        "ligand_only_evidence_not_promoted": any(row.get("survival_claim_scope") == "ligand_only" for row in rows),
        "claim_boundary_note": claim_boundary_note,
    }
    return {
        "packet_type": "gpcr_drd2_local_minimization_survival",
        "summary": summary,
        "claim_boundary": claim_boundary,
        "engine_parameters": {
            "openmm_max_iterations": int(openmm_max_iterations),
            "rdkit_max_iterations": int(rdkit_max_iterations),
            "tolerance_kj_mol_nm": float(tolerance_kj_mol_nm),
            "ligand_internal_k_kj_mol_nm2": float(ligand_internal_k_kj_mol_nm2),
            "protein_restraint_k_kj_mol_nm2": float(protein_restraint_k_kj_mol_nm2),
            "salt_bridge_k_kj_mol_nm2": float(salt_bridge_k_kj_mol_nm2),
            "salt_bridge_distance_A": float(salt_bridge_distance_A),
            "vdw_epsilon_kj_mol": float(vdw_epsilon_kj_mol),
            "vdw_cutoff_nm": float(vdw_cutoff_nm),
            "softcore_nm": float(softcore_nm),
        },
        "rows": rows,
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# GPCR DRD2 Local-Minimization Survival",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- requested_engine: `{summary['requested_engine']}`",
        f"- engine_kinds: `{', '.join(summary['engine_kinds']) or 'none'}`",
        f"- positive_ligand_id: `{summary['positive_ligand_id']}`",
        f"- positive_local_minimization_survival_fraction: `{summary['positive_local_minimization_survival_fraction']}`",
        f"- positive_engine_kind: `{summary['positive_engine_kind']}`",
        f"- rmsd_threshold_A: `{summary['rmsd_threshold_A']}`",
        f"- hard_decoy_rebuild_evidence_allowed: `{str(summary['hard_decoy_rebuild_evidence_allowed']).lower()}`",
        "",
        "## Claim Boundary",
        "",
        summary["claim_boundary"],
        "",
        "## Positive Blockers",
        "",
    ]
    blockers = summary.get("positive_blockers") or []
    lines.extend([f"- `{blocker}`" for blocker in blockers] or ["- none"])
    lines.extend(["", "## Rows", ""])
    lines.append(
        "| Ligand | Engine | Scope | Frames | Minimized | Survival | RMSD p90 A | Blockers |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---|")
    for row in payload["rows"]:
        blockers_text = ", ".join(f"`{item}`" for item in list(row.get("blockers") or [])[:4]) or "none"
        lines.append(
            f"| `{row['ligand_id']}` | `{row['engine_kind']}` | `{row['survival_claim_scope']}` | "
            f"`{row['frame_count']}` | `{row['minimized_frame_count']}` | `{row['survival_fraction']}` | "
            f"`{row['rmsd_A_p90']}` | {blockers_text} |"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure bounded DRD2 pseudo-allatom local-minimization survival.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument(
        "--engine",
        default="auto",
        choices=["auto", "openmm_custom", OPENMM_CUSTOM_ENGINE, "rdkit_uff", RDKIT_LIGAND_ONLY_ENGINE],
    )
    parser.add_argument("--positive-ligand", default=DEFAULT_POSITIVE_LIGAND)
    parser.add_argument("--rmsd-threshold-A", type=float, default=DEFAULT_RMSD_THRESHOLD_A)
    parser.add_argument("--survival-min", type=float, default=DEFAULT_SURVIVAL_MIN)
    parser.add_argument("--max-frames-per-row", type=int, default=DEFAULT_MAX_FRAMES_PER_ROW)
    parser.add_argument("--openmm-max-iterations", type=int, default=200)
    parser.add_argument("--rdkit-max-iterations", type=int, default=200)
    parser.add_argument("--tolerance-kj-mol-nm", type=float, default=10.0)
    parser.add_argument(
        "--ligand-pose-restraint-k-kj-mol-nm2",
        type=float,
        default=DEFAULT_LIGAND_POSE_RESTRAINT_K_KJ_MOL_NM2,
    )
    parser.add_argument("--ligand-internal-k-kj-mol-nm2", type=float, default=2500.0)
    parser.add_argument("--protein-restraint-k-kj-mol-nm2", type=float, default=50000.0)
    parser.add_argument("--salt-bridge-k-kj-mol-nm2", type=float, default=500.0)
    parser.add_argument("--salt-bridge-distance-A", type=float, default=3.2)
    parser.add_argument("--vdw-epsilon-kj-mol", type=float, default=0.05)
    parser.add_argument("--vdw-cutoff-nm", type=float, default=1.2)
    parser.add_argument("--softcore-nm", type=float, default=0.02)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_survival(
        input_csv=args.input_csv,
        requested_engine=args.engine,
        positive_ligand=args.positive_ligand,
        rmsd_threshold_A=float(args.rmsd_threshold_A),
        survival_min=float(args.survival_min),
        max_frames_per_row=int(args.max_frames_per_row),
        openmm_max_iterations=int(args.openmm_max_iterations),
        rdkit_max_iterations=int(args.rdkit_max_iterations),
        tolerance_kj_mol_nm=float(args.tolerance_kj_mol_nm),
        ligand_pose_restraint_k_kj_mol_nm2=float(args.ligand_pose_restraint_k_kj_mol_nm2),
        ligand_internal_k_kj_mol_nm2=float(args.ligand_internal_k_kj_mol_nm2),
        protein_restraint_k_kj_mol_nm2=float(args.protein_restraint_k_kj_mol_nm2),
        salt_bridge_k_kj_mol_nm2=float(args.salt_bridge_k_kj_mol_nm2),
        salt_bridge_distance_A=float(args.salt_bridge_distance_A),
        vdw_epsilon_kj_mol=float(args.vdw_epsilon_kj_mol),
        vdw_cutoff_nm=float(args.vdw_cutoff_nm),
        softcore_nm=float(args.softcore_nm),
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(_jsonable(payload["summary"]), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
