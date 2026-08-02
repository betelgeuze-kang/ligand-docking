"""Deterministic ligand conformer ensemble with provenance (P1-4).

The previous conformer path returned a bare coordinate array: no stable
identity per conformer, no energy filter, no recorded generation parameters. A
downstream pose could therefore not be traced back to the conformer it came
from, and a high-energy embedding artifact was indistinguishable from a real
low-energy conformer.

This module produces an ensemble where every conformer carries:

- a deterministic ``conformer_id`` derived from the input identity, the exact
  generation parameters, and the coordinates;
- a force-field energy plus the relative energy used by the filter;
- an RMSD-diversity decision (symmetry-aware best-RMS when RDKit provides it);
- provenance: SMILES, seed, method, force field, thresholds, RDKit version.

Determinism is a contract here, not a side effect: the same inputs must yield
the same coordinates and the same ids, so a benchmark row can be replayed.
Macrocycles are routed out through the same unsupported lane as rotor
perception rather than embedded as if they were rigid.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from betelgeuze_engine.chemistry.rotor_perception import (
    STATUS_UNSUPPORTED_MACROCYCLE,
    perceive_ligand_rotors,
)

try:
    from rdkit import Chem, rdBase  # type: ignore
    from rdkit.Chem import AllChem, rdDistGeom, rdMolAlign  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    Chem = None
    rdBase = None
    AllChem = None
    rdDistGeom = None
    rdMolAlign = None

CONFORMER_ENSEMBLE_SCHEMA_VERSION = "ligand_conformer_ensemble_v1"

ENSEMBLE_METHOD = "rdkit_etkdgv3_deterministic_seeded"

DEFAULT_SEED = 0xC0FFEE
DEFAULT_MAX_CONFORMERS = 16
DEFAULT_ENERGY_WINDOW_KCAL_MOL = 10.0
DEFAULT_RMSD_DIVERSITY_A = 0.5

STATUS_READY = "conformer_ensemble_ready"
STATUS_UNSUPPORTED_MACROCYCLE_LANE = STATUS_UNSUPPORTED_MACROCYCLE
STATUS_BLOCKED_NO_RDKIT = "blocked_rdkit_unavailable"
STATUS_BLOCKED_INVALID = "blocked_invalid_smiles"
STATUS_BLOCKED_EMBED_FAILED = "blocked_embedding_failed"

#: Energies are internal force-field values, not calibrated strain estimates.
CLAIM_BOUNDARY = (
    "Deterministic internal conformer ensemble with force-field energies and RMSD diversity filtering only. "
    "Energies are uncalibrated MMFF/UFF values for ranking and filtering; this is not a benchmarked "
    "conformer-accuracy claim, a strain-energy measurement, or ring-closure sampling."
)


@dataclass(frozen=True)
class ConformerRecord:
    """One retained or rejected conformer with its identity and energy."""

    conformer_index: int
    conformer_id: str
    energy_kcal_mol: float | None
    relative_energy_kcal_mol: float | None
    force_field: str
    converged: bool
    retained: bool
    rejection_reason: str
    min_rmsd_to_retained_a: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConformerEnsemble:
    """Deterministic conformer ensemble plus provenance."""

    smiles: str
    status: str
    provenance: dict[str, Any]
    records: tuple[ConformerRecord, ...] = ()
    coordinates: np.ndarray | None = None
    blockers: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ready(self) -> bool:
        return self.status == STATUS_READY

    @property
    def retained_records(self) -> tuple[ConformerRecord, ...]:
        return tuple(record for record in self.records if record.retained)

    @property
    def conformer_ids(self) -> tuple[str, ...]:
        return tuple(record.conformer_id for record in self.retained_records)

    def to_dict(self) -> dict[str, Any]:
        retained = self.retained_records
        energies = [
            record.energy_kcal_mol for record in retained if record.energy_kcal_mol is not None
        ]
        return {
            "schema_version": CONFORMER_ENSEMBLE_SCHEMA_VERSION,
            "smiles": self.smiles,
            "status": self.status,
            "ready": self.ready,
            "generated_conformer_count": len(self.records),
            "retained_conformer_count": len(retained),
            "rejected_conformer_count": len(self.records) - len(retained),
            "conformer_ids": list(self.conformer_ids),
            "min_energy_kcal_mol": min(energies) if energies else None,
            "max_retained_energy_kcal_mol": max(energies) if energies else None,
            "rejection_reasons": sorted(
                {record.rejection_reason for record in self.records if record.rejection_reason}
            ),
            "conformers": [record.to_dict() for record in self.records],
            "provenance": dict(self.provenance),
            "blockers": list(self.blockers),
            "claim_boundary": CLAIM_BOUNDARY,
        }


def _rdkit_version() -> str:
    if rdBase is None:
        return ""
    return str(getattr(rdBase, "rdkitVersion", "") or "")


def _provenance(
    *,
    smiles: str,
    seed: int,
    max_conformers: int,
    energy_window_kcal_mol: float,
    rmsd_diversity_a: float,
    force_field: str = "",
) -> dict[str, Any]:
    payload = {
        "method": ENSEMBLE_METHOD,
        "smiles": str(smiles),
        "seed": int(seed),
        "max_conformers": int(max_conformers),
        "energy_window_kcal_mol": float(energy_window_kcal_mol),
        "rmsd_diversity_a": float(rmsd_diversity_a),
        "force_field": str(force_field),
        "rdkit_version": _rdkit_version(),
        "deterministic": True,
    }
    payload["parameter_digest"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in payload.items() if key != "force_field"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return payload


def _conformer_id(*, parameter_digest: str, index: int, coords: np.ndarray) -> str:
    """Deterministic id bound to both the parameters and the geometry."""

    rounded = np.round(np.asarray(coords, dtype=np.float64), 4)
    payload = json.dumps(
        {
            "parameter_digest": str(parameter_digest),
            "conformer_index": int(index),
            "coords": rounded.tolist(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _blocked(
    smiles: str,
    *,
    status: str,
    reason: str,
    provenance: dict[str, Any],
) -> ConformerEnsemble:
    return ConformerEnsemble(
        smiles=smiles,
        status=status,
        provenance=provenance,
        blockers=(reason,),
    )


def _optimize(mol: Any) -> tuple[str, list[tuple[int, float]]]:
    """Optimize every conformer with MMFF, falling back to UFF.

    Returns the force-field name and ``(converged_flag, energy)`` per conformer.
    An empty result means no force field applied, which the caller reports as a
    missing energy rather than a zero energy.
    """

    if AllChem is None:
        return "", []
    try:
        if AllChem.MMFFHasAllMoleculeParams(mol):
            results = AllChem.MMFFOptimizeMoleculeConfs(mol, numThreads=1, maxIters=400)
            return "mmff94", [(int(flag), float(energy)) for flag, energy in results]
    except Exception:
        pass
    try:
        results = AllChem.UFFOptimizeMoleculeConfs(mol, numThreads=1, maxIters=400)
        return "uff", [(int(flag), float(energy)) for flag, energy in results]
    except Exception:
        return "", []


def _best_rms(mol: Any, prb_id: int, ref_id: int) -> float:
    """Symmetry-aware RMSD when available, plain atom-order RMSD otherwise."""

    if rdMolAlign is not None:
        try:
            return float(rdMolAlign.GetBestRMS(mol, mol, prbId=int(prb_id), refId=int(ref_id)))
        except Exception:
            pass
    left = np.asarray(mol.GetConformer(int(prb_id)).GetPositions(), dtype=np.float64)
    right = np.asarray(mol.GetConformer(int(ref_id)).GetPositions(), dtype=np.float64)
    n = min(left.shape[0], right.shape[0])
    if n <= 0:
        return float("inf")
    return float(np.sqrt(np.mean(np.sum((left[:n] - right[:n]) ** 2, axis=1))))


def generate_conformer_ensemble(
    smiles: str,
    *,
    max_conformers: int = DEFAULT_MAX_CONFORMERS,
    seed: int = DEFAULT_SEED,
    energy_window_kcal_mol: float = DEFAULT_ENERGY_WINDOW_KCAL_MOL,
    rmsd_diversity_a: float = DEFAULT_RMSD_DIVERSITY_A,
    allow_macrocycle: bool = False,
) -> ConformerEnsemble:
    """Build a deterministic, energy-filtered, diversity-filtered ensemble."""

    smi = str(smiles or "").strip()
    requested = max(int(max_conformers), 1)
    provenance = _provenance(
        smiles=smi,
        seed=int(seed),
        max_conformers=requested,
        energy_window_kcal_mol=float(energy_window_kcal_mol),
        rmsd_diversity_a=float(rmsd_diversity_a),
    )
    if not smi:
        return _blocked(
            smi, status=STATUS_BLOCKED_INVALID, reason="empty_smiles", provenance=provenance
        )
    if Chem is None or rdDistGeom is None:
        return _blocked(
            smi,
            status=STATUS_BLOCKED_NO_RDKIT,
            reason="rdkit_unavailable_conformer_ensemble",
            provenance=provenance,
        )

    perception = perceive_ligand_rotors(smi)
    if perception.status == STATUS_UNSUPPORTED_MACROCYCLE and not allow_macrocycle:
        return _blocked(
            smi,
            status=STATUS_UNSUPPORTED_MACROCYCLE_LANE,
            reason="macrocycle_requires_ring_closure_sampling",
            provenance=provenance,
        )

    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return _blocked(
            smi, status=STATUS_BLOCKED_INVALID, reason="invalid_smiles", provenance=provenance
        )
    mol = Chem.AddHs(mol)
    params = rdDistGeom.ETKDGv3()
    params.randomSeed = int(seed)
    # Diversity is applied explicitly below so the rejection is recorded rather
    # than hidden inside the embedder, and numThreads=1 keeps output ordering
    # reproducible.
    params.pruneRmsThresh = -1.0
    params.numThreads = 1
    conf_ids = list(rdDistGeom.EmbedMultipleConfs(mol, numConfs=requested, params=params))
    if not conf_ids:
        return _blocked(
            smi,
            status=STATUS_BLOCKED_EMBED_FAILED,
            reason="etkdg_embedding_produced_no_conformers",
            provenance=provenance,
        )

    force_field, optimization = _optimize(mol)
    provenance = dict(provenance)
    provenance["force_field"] = force_field

    energies: dict[int, float | None] = {}
    converged: dict[int, bool] = {}
    for position, conf_id in enumerate(conf_ids):
        if position < len(optimization):
            flag, energy = optimization[position]
            energies[int(conf_id)] = float(energy) if math.isfinite(float(energy)) else None
            converged[int(conf_id)] = flag == 0
        else:
            energies[int(conf_id)] = None
            converged[int(conf_id)] = False

    finite = [value for value in energies.values() if value is not None]
    min_energy = min(finite) if finite else None

    heavy = Chem.RemoveHs(mol)
    # Rank by energy so the diversity filter keeps the lowest-energy member of
    # each cluster instead of whichever one the embedder happened to emit first.
    ordered = sorted(
        conf_ids,
        key=lambda cid: (
            energies[int(cid)] if energies[int(cid)] is not None else float("inf"),
            int(cid),
        ),
    )

    records: list[ConformerRecord] = []
    retained_ids: list[int] = []
    retained_coords: list[np.ndarray] = []
    for conf_id in ordered:
        energy = energies[int(conf_id)]
        relative = None if (energy is None or min_energy is None) else float(energy - min_energy)
        coords = np.asarray(heavy.GetConformer(int(conf_id)).GetPositions(), dtype=np.float64)
        rejection = ""
        min_rmsd: float | None = None
        if relative is not None and relative > float(energy_window_kcal_mol):
            rejection = "energy_window_exceeded"
        else:
            for retained_id in retained_ids:
                rmsd = _best_rms(heavy, int(conf_id), int(retained_id))
                min_rmsd = rmsd if min_rmsd is None else min(min_rmsd, rmsd)
            if min_rmsd is not None and min_rmsd < float(rmsd_diversity_a):
                rejection = "rmsd_duplicate_of_retained_conformer"
        retained = not rejection
        records.append(
            ConformerRecord(
                conformer_index=int(conf_id),
                conformer_id=_conformer_id(
                    parameter_digest=str(provenance["parameter_digest"]),
                    index=int(conf_id),
                    coords=coords,
                ),
                energy_kcal_mol=energy,
                relative_energy_kcal_mol=relative,
                force_field=force_field,
                converged=bool(converged[int(conf_id)]),
                retained=retained,
                rejection_reason=rejection,
                min_rmsd_to_retained_a=min_rmsd,
            )
        )
        if retained:
            retained_ids.append(int(conf_id))
            retained_coords.append(coords.astype(np.float32))

    coordinates = (
        np.asarray(retained_coords, dtype=np.float32) if retained_coords else None
    )
    return ConformerEnsemble(
        smiles=smi,
        status=STATUS_READY,
        provenance=provenance,
        records=tuple(records),
        coordinates=coordinates,
    )


__all__ = [
    "CLAIM_BOUNDARY",
    "CONFORMER_ENSEMBLE_SCHEMA_VERSION",
    "DEFAULT_ENERGY_WINDOW_KCAL_MOL",
    "DEFAULT_MAX_CONFORMERS",
    "DEFAULT_RMSD_DIVERSITY_A",
    "DEFAULT_SEED",
    "ENSEMBLE_METHOD",
    "ConformerEnsemble",
    "ConformerRecord",
    "STATUS_BLOCKED_EMBED_FAILED",
    "STATUS_BLOCKED_INVALID",
    "STATUS_BLOCKED_NO_RDKIT",
    "STATUS_READY",
    "STATUS_UNSUPPORTED_MACROCYCLE_LANE",
    "generate_conformer_ensemble",
]
