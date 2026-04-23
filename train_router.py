import torch
import torch.nn as nn
import torch.nn.functional as F


class CompositeRouterLoss(nn.Module):
    """
    Training scripts가 기대하는 Router용 합성 손실.
    - mse: 예측 force vs 정답 force
    - div_penalty: 과도한 평균 편향 억제
    - clamp_penalty: 좌표가 과도하게 커지는 경우 완만한 패널티
    """

    def __init__(self, mse_weight=1.0, div_weight=0.05, clamp_weight=0.001):
        super().__init__()
        self.mse_weight = mse_weight
        self.div_weight = div_weight
        self.clamp_weight = clamp_weight

    def forward(self, pred_forces, target_forces, coords):
        mse = F.mse_loss(pred_forces, target_forces)
        div_penalty = pred_forces.mean(dim=(-1, -2)).pow(2).mean()

        if coords is None:
            clamp_penalty = torch.zeros((), device=pred_forces.device)
        else:
            clamp_penalty = (coords.abs() - 100.0).relu().mean()

        total = (
            self.mse_weight * mse
            + self.div_weight * div_penalty
            + self.clamp_weight * clamp_penalty
        )

        components = {
            "total": float(total.detach().item()),
            "mse": float(mse.detach().item()),
            "div_penalty": float(div_penalty.detach().item()),
            "clamp_penalty": float(clamp_penalty.detach().item()),
        }
        return total, components
