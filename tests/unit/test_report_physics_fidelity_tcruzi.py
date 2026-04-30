from tools import report_physics_fidelity as mod


def test_tcruzi_pde_has_physics_fidelity_thresholds():
    thresholds = mod._thresholds_for_target("T. cruzi PDE")

    assert thresholds["rmsd_threshold"] == 2.0
    assert thresholds["rg_delta_threshold"] == 1.0
    assert thresholds["sasa_delta_threshold"] >= 300.0
    assert thresholds["energy_drift_ratio_threshold"] == 0.30
