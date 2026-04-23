import torch

from theory.branches.idp_logic import IDPLogic
from tools.idp_3bead_common import build_mock_top, knn_nb_data


def _run_target(target_name: str):
    device = torch.device('cpu')
    mod = IDPLogic(device)
    coords = torch.randn(1, 12, 3)
    top = build_mock_top(12, device)
    nb = knn_nb_data(coords, 4)
    sim_params = {
        'idp_virtual_hbond_enabled': 1,
        'target_name': target_name,
        'idp_branch_profile': {'llps_lcd': 0.2, 'aggregation_prone': 0.7, 'helix_tad': 0.1},
        'sequence_features': {'frac_aromatic': 0.12, 'charge_density': 0.25, 'sticker_spacer_ratio': 1.1, 'acidic_fraction': 0.1, 'basic_fraction': 0.1},
        'ionic_strength': 0.15,
        'pH': 7.2,
        'ptm_count': 0.0,
        'hydro_strength': 1.0,
    }
    _f, info = mod(coords, top=top, nb_data=nb, pe=None, sim_params=sim_params)
    return info


def test_tau_override_changes_conditional_scale():
    tau = _run_target('tau_k18')
    generic = _run_target('generic_idp')
    assert tau['conditional_anti_collapse_scale'] > generic['conditional_anti_collapse_scale']


def test_hnrnpa1_override_reduces_virtual_hbond_scale():
    hnrnpa1 = _run_target('hnrnpa1_lcd')
    generic = _run_target('generic_idp')
    assert hnrnpa1['conditional_virtual_hbond_scale'] < generic['conditional_virtual_hbond_scale']
