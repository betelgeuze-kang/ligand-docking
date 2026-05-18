import torch

from tools.idp_residual_common import BRANCH_NAMES, FEATURE_NAMES, RANKING_HEAD_NAMES, STATE_NAMES, build_residual_model


def test_branch_selector_moe_shapes():
    model = build_residual_model('branch_moe_v1', in_dim=len(FEATURE_NAMES), out_dim=0, hidden_dim=64)
    x = torch.randn(5, len(FEATURE_NAMES))
    out = model(x)
    assert {
        'branch_logits',
        'state_logits',
        'llps_logit',
        'aggregation_logit',
        'ranking_scores',
    }.issubset(out.keys())
    assert out['branch_logits'].shape == (5, len(BRANCH_NAMES))
    assert out['state_logits'].shape == (5, len(STATE_NAMES))
    assert out['llps_logit'].shape == (5,)
    assert out['aggregation_logit'].shape == (5,)
    assert out['ranking_scores'].shape == (5, len(RANKING_HEAD_NAMES))
    assert out['branch_weight'].shape == (5, len(BRANCH_NAMES))
    assert out['state_logits_per_branch'].shape == (5, len(BRANCH_NAMES), len(STATE_NAMES))
