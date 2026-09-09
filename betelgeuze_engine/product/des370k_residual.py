"""Small energy-only fragment residual experiment; never a dynamics force model.

The unchanged V2 cross evaluator owns baseline energies and atom forces. This
module supplies a separately identified shadow energy prediction. Features are
available after coordinate preparation and V2 scoring, not before docking.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
from rdkit import Chem
from sklearn.linear_model import Ridge

from .des370k_interaction import MODEL_CONFIG, PARAMETER_PROFILE, sha

SCHEMA_ID = "betelgeuze.des370k_energy_residual_shadow/1.0.0"
SPLIT_SALT = "des370k-monomer-connectivity-development-20260909-v1"
PAIR_TYPES = tuple(itertools.combinations_with_replacement(("C", "H", "N", "O"), 2))
CENTERS = (2., 3., 4., 5., 6., 8.)
FEATURE_NAMES = tuple(f"pair_{a}{b}_gaussian_center_{c:g}A_width_1A" for a, b in PAIR_TYPES
                      for c in CENTERS) + ("v2_cross_lennard_jones", "v2_cross_coulomb")


def monomer_identity(smiles):
    """Group stereoisomers together without changing the evaluated source state."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("invalid_monomer_smiles")
    Chem.RemoveStereochemistry(mol)
    return Chem.MolToSmiles(Chem.RemoveHs(mol), canonical=True, isomericSmiles=True)


def monomer_role(identity):
    value = int(sha([SPLIT_SALT, identity])[:16], 16) % 100
    return "fit" if value < 60 else "calibration" if value < 80 else "development"


def geometry_features(score):
    row = score["native_record"]
    expected_geometry = sha({key: row[key] for key in (
        "xyz", "elements", "smiles0", "smiles1", "natoms0", "natoms1", "charge0", "charge1")})
    if (score["provenance"]["native_row_geometry_sha256"] != expected_geometry
            or score["provenance"]["parameter_source"]["profile"] != PARAMETER_PROFILE
            or any(score["baseline"]["model"].get(k) != v for k, v in MODEL_CONFIG.items())):
        raise ValueError("geometry_or_baseline_profile_mismatch")
    n0 = int(row["natoms0"])
    xyz = np.asarray([float(v) for v in row["xyz"].split()]).reshape(-1, 3)
    elements = row["elements"].split()
    distances = np.linalg.norm(xyz[:n0, None, :] - xyz[None, n0:, :], axis=-1)
    values = np.zeros((len(PAIR_TYPES), len(CENTERS)), dtype=np.float64)
    for i, first in enumerate(elements[:n0]):
        for j, second in enumerate(elements[n0:]):
            pair = PAIR_TYPES.index(tuple(sorted((first, second))))
            values[pair] += np.exp(-0.5 * (distances[i, j] - CENTERS) ** 2)
    quantities = score["baseline"]["quantities"]
    result = np.r_[values.ravel(), quantities["cross_lennard_jones_kcal_per_mol"],
                   quantities["cross_screened_coulomb_kcal_per_mol"]]
    if result.shape != (len(FEATURE_NAMES),) or not np.isfinite(result).all():
        raise ValueError("invalid_or_nonfinite_geometry_features")
    return result


def fit_energy_residual(rows, *, runtime_sha256, plan_sha256):
    """Fit fixed-alpha Ridge only on explicitly admitted fit rows."""
    if not rows or len(rows) < 2:
        raise ValueError("at_least_two_fit_rows_required")
    seen = set()
    for row in rows:
        if row.get("role") != "fit" or row.get("evaluation_only") is not False:
            raise ValueError("nonfit_or_evaluation_row")
        if row.get("evidence_kind") != "external_computed_reference":
            raise ValueError("incorrect_reference_evidence_kind")
        if row["geometry_sha256"] in seen:
            raise ValueError("duplicate_fit_geometry")
        seen.add(row["geometry_sha256"])
    x = np.asarray([r["features"] for r in rows], dtype=np.float64)
    y = np.asarray([r["reference_kcal_per_mol"] - r["baseline_kcal_per_mol"] for r in rows])
    if x.shape != (len(rows), len(FEATURE_NAMES)) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("invalid_fit_values")
    center, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale < 1e-12] = 1.0  # constant columns remain centered zero, not missing data
    model = Ridge(alpha=10., fit_intercept=True, solver="cholesky")
    model.fit((x - center) / scale, y)
    checkpoint = {
        "schema_id": SCHEMA_ID, "runtime_sha256": runtime_sha256, "plan_sha256": plan_sha256,
        "parameter_profile": PARAMETER_PROFILE, "model_config": MODEL_CONFIG,
        "feature_names": list(FEATURE_NAMES), "available_at_stage": "after_native_geometry_and_v2_cross_scoring",
        "target_quantity": "CCSD(T)_CBS_interaction_energy_minus_declared_v2_cross_energy_kcal_per_mol",
        "alpha": 10., "center": center.tolist(), "scale": scale.tolist(),
        "coefficients": model.coef_.tolist(), "intercept": float(model.intercept_),
        "fit_rows": len(rows), "fit_records_sha256": sha(rows),
        "force_residual": None, "uncertainty": None, "uncertainty_calibrated": False,
        "mode": "shadow_only", "scientifically_validated": False, "customer_execution": False,
    }
    checkpoint["checkpoint_sha256"] = sha(checkpoint)
    return checkpoint


def predict_energy_residual(score, checkpoint, *, runtime_sha256, plan_sha256):
    payload = {k: v for k, v in checkpoint.items() if k != "checkpoint_sha256"}
    if sha(payload) != checkpoint.get("checkpoint_sha256"):
        raise ValueError("checkpoint_hash_mismatch")
    if (checkpoint["schema_id"] != SCHEMA_ID or checkpoint["runtime_sha256"] != runtime_sha256
            or checkpoint["plan_sha256"] != plan_sha256
            or checkpoint["feature_names"] != list(FEATURE_NAMES)
            or checkpoint["parameter_profile"] != PARAMETER_PROFILE
            or checkpoint["model_config"] != MODEL_CONFIG):
        raise ValueError("checkpoint_runtime_or_contract_mismatch")
    features = geometry_features(score)
    standardized = (features - checkpoint["center"]) / checkpoint["scale"]
    residual = float(standardized @ checkpoint["coefficients"] + checkpoint["intercept"])
    baseline = score["baseline"]["quantities"]["cross_total_kcal_per_mol"]
    corrected = baseline + residual
    if not math.isfinite(residual) or not math.isfinite(corrected):
        raise ValueError("nonfinite_shadow_prediction")
    # A declared uncalibrated diagnostic, not a correctness probability or a
    # cheap-selector skip rule. Baseline is preserved even if correction abstains.
    maximum = float(np.max(np.abs(standardized)))
    out_of_domain = maximum > 10.0
    return {"baseline_kcal_per_mol": baseline, "raw_shadow_residual_kcal_per_mol": residual,
            "raw_shadow_energy_kcal_per_mol": corrected,
            "supported_shadow_energy_kcal_per_mol": None if out_of_domain else corrected,
            "status": "abstained" if out_of_domain else "shadow_prediction",
            "reason": "feature_z_exceeds_predeclared_10" if out_of_domain else None,
            "max_absolute_feature_z": maximum, "diagnostic_calibrated": False,
            "checkpoint_sha256": checkpoint["checkpoint_sha256"], "evidence_kind": "AI_prediction",
            "force_labels": None, "uncertainty": None, "uncertainty_calibrated": False,
            "baseline_selection_changed": False, "customer_execution": False}
