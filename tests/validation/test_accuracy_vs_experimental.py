# tests/validation/test_accuracy_vs_experimental.py

import pytest
import torch
from tools.pdb_loader import load_native_structure
from run_validation import calculate_rg, calculate_sasa_proxy, run_target
from core.definitions import ResearchConstants

SMALL_PROTEIN_TARGETS = list(ResearchConstants.CHALLENGES.keys())


def _calculate_rmsd(coords_a, coords_b):
    if coords_a.shape != coords_b.shape:
        raise ValueError(f"Shape mismatch: {coords_a.shape} vs {coords_b.shape}")
    diff = coords_a - coords_b
    return torch.sqrt(diff.pow(2).sum(dim=-1).mean()).item()


@pytest.mark.parametrize(
    ("target", "rmsd_threshold", "rg_delta_threshold", "sasa_delta_threshold", "energy_drift_ratio_threshold"),
    [
        ("Chignolin", 2.0, 1.0, 80.0, 0.30),
        ("Trp_Cage", 2.0, 1.0, 120.0, 0.30),
        ("Villin_HP35", 2.0, 1.0, 180.0, 0.30),
        ("BBA5", 2.0, 1.0, 120.0, 0.30),
        ("FSD_1", 2.0, 1.0, 140.0, 0.30),
        ("WW_Domain_FiP35", 2.0, 1.0, 180.0, 0.30),
        ("Crambin", 2.0, 1.0, 200.0, 0.30),
        ("Protein_A_Bdomain", 2.0, 1.0, 260.0, 0.30),
        ("GB1_Mini", 2.0, 1.0, 240.0, 0.30),
        ("Ubiquitin_Mini", 2.0, 1.0, 300.0, 0.30),
    ],
)
def test_refinement_accuracy_vs_native(
    target,
    rmsd_threshold,
    rg_delta_threshold,
    sasa_delta_threshold,
    energy_drift_ratio_threshold,
):
    """run_target 결과가 native 구조와 충분히 가까운지 확인한다."""
    _ = ResearchConstants.CHALLENGES[target]

    native_coords, seq = load_native_structure(target)
    if native_coords is None:
        pytest.skip(f"Native structure for {target} not found, skipping test.")

    result = run_target(target, steps=100, noise_scale=0.02, seed=42, return_metrics=True)
    assert isinstance(result, tuple) and len(result) == 2
    result_coords, metrics = result

    assert isinstance(result_coords, torch.Tensor)
    assert result_coords.shape == native_coords.shape
    assert isinstance(metrics, dict)

    calculated_rmsd = _calculate_rmsd(result_coords, native_coords)
    native_rg = calculate_rg(native_coords)
    result_rg = calculate_rg(result_coords)
    rg_delta = abs(result_rg - native_rg)
    native_sasa = calculate_sasa_proxy(native_coords)
    result_sasa = calculate_sasa_proxy(result_coords)
    sasa_delta = abs(result_sasa - native_sasa)
    energy_drift_ratio = float(metrics["energy_drift_ratio"])

    assert calculated_rmsd < rmsd_threshold, (
        f"{target} RMSD ({calculated_rmsd:.3f} Å) exceeds threshold {rmsd_threshold:.3f} Å."
    )
    assert rg_delta < rg_delta_threshold, (
        f"{target} |ΔRg| ({rg_delta:.3f} Å) exceeds threshold {rg_delta_threshold:.3f} Å. "
        f"(native={native_rg:.3f}, result={result_rg:.3f})"
    )
    assert sasa_delta < sasa_delta_threshold, (
        f"{target} |ΔSASA_proxy| ({sasa_delta:.3f}) exceeds threshold {sasa_delta_threshold:.3f}. "
        f"(native={native_sasa:.3f}, result={result_sasa:.3f})"
    )
    assert energy_drift_ratio < energy_drift_ratio_threshold, (
        f"{target} energy drift ratio ({energy_drift_ratio:.6f}) exceeds threshold "
        f"{energy_drift_ratio_threshold:.6f}."
    )


def test_small_protein_target_set_size_is_ten():
    assert len(SMALL_PROTEIN_TARGETS) == 10


@pytest.mark.parametrize("target", SMALL_PROTEIN_TARGETS)
def test_small_protein_native_structure_presence_and_length(target):
    t_conf = ResearchConstants.CHALLENGES[target]
    coords, _ = load_native_structure(target)
    assert coords is not None, f"Native structure missing for target: {target}"
    assert coords.shape[0] == t_conf["n_res"], (
        f"Native residue count mismatch for {target}: "
        f"expected={t_conf['n_res']}, actual={coords.shape[0]}"
    )
