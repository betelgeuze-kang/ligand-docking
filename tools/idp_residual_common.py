from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn


FEATURE_NAMES = [
    "n_res",
    "residue_count_log",
    "ionic_strength",
    "pH",
    "ptm_count",
    "hydro_strength",
    "frac_gly",
    "frac_pro",
    "frac_charged",
    "frac_aromatic",
    "frac_polar",
    "frac_hydrophobic",
    "net_charge_proxy",
    "frac_disorder_promoting",
    "charge_density",
    "charge_asymmetry",
    "kappa_proxy",
    "sticker_density",
    "spacer_density",
    "sticker_spacer_ratio",
    "acidic_fraction",
    "basic_fraction",
    "branch_prior_llps_lcd",
    "branch_prior_aggregation_prone",
    "branch_prior_helix_tad",
    "off_rg_mean",
    "off_sasa_proxy_mean",
    "off_contact_persistence",
    "off_transient_helicity",
    "off_ensemble_diversity",
    "off_overcollapse_rate",
    "on_virtual_hbond_contacts_mean",
    "on_virtual_hbond_mean_distance_A",
    "on_anti_collapse_force_mean",
    "on_anti_collapse_rg_target_A",
    "on_anti_collapse_density_mean",
]
BRANCH_NAMES = ["llps_lcd", "aggregation_prone", "helix_tad"]
STATE_NAMES = [
    "expanded_disordered",
    "compact_disordered",
    "helix_enriched",
    "sticky_condensed",
]
RANKING_HEAD_NAMES = ["compactness", "helicity", "condensation"]


TARGET_NAMES = [
    "delta_rg_mean",
    "delta_sasa_proxy_mean",
    "delta_contact_persistence",
    "delta_transient_helicity",
    "delta_ensemble_diversity",
]


ANCHOR_METRIC_NAMES = [
    "rg_mean",
    "sasa_proxy_mean",
    "contact_persistence",
    "transient_helicity",
    "ensemble_diversity",
]


SIZE_HEAD_TARGETS = [
    "delta_rg_mean",
    "delta_sasa_proxy_mean",
    "delta_ensemble_diversity",
]


CONTACT_HEAD_TARGETS = [
    "delta_contact_persistence",
    "delta_transient_helicity",
]


class ResidualMLP(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, hidden_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, out_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class ResidualTwoHeadMLP(nn.Module):
    def __init__(self, in_dim: int, hidden_dim: int = 64):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        self.size_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, len(SIZE_HEAD_TARGETS)),
        )
        self.contact_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, len(CONTACT_HEAD_TARGETS)),
        )
        self.size_idx = [TARGET_NAMES.index(name) for name in SIZE_HEAD_TARGETS]
        self.contact_idx = [TARGET_NAMES.index(name) for name in CONTACT_HEAD_TARGETS]

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.shared(x)
        size_out = self.size_head(z)
        contact_out = self.contact_head(z)
        out = torch.zeros((x.shape[0], len(TARGET_NAMES)), dtype=z.dtype, device=z.device)
        out[:, self.size_idx] = size_out
        out[:, self.contact_idx] = contact_out
        return out


class BranchSelectorMoE(nn.Module):
    def __init__(self, in_dim: int, hidden_dim: int = 96):
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        self.branch_logits = nn.Linear(hidden_dim, len(BRANCH_NAMES))
        self.state_heads = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(hidden_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Linear(hidden_dim, len(STATE_NAMES)),
                )
                for _ in BRANCH_NAMES
            ]
        )
        self.llps_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )
        self.aggregation_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )
        self.compactness_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )
        self.helicity_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )
        self.condensation_heads = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(hidden_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Linear(hidden_dim, 1),
                )
                for _ in BRANCH_NAMES
            ]
        )

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        z = self.trunk(x)
        branch_logits = self.branch_logits(z)
        branch_weight = torch.softmax(branch_logits, dim=-1)
        state_logits_per_branch = torch.stack([head(z) for head in self.state_heads], dim=1)
        state_logits = torch.sum(branch_weight.unsqueeze(-1) * state_logits_per_branch, dim=1)
        condensation_per_branch = torch.stack([head(z).squeeze(-1) for head in self.condensation_heads], dim=1)
        compactness_score = self.compactness_head(z)
        helicity_score = self.helicity_head(z)
        condensation_score = torch.sum(branch_weight * condensation_per_branch, dim=-1, keepdim=True)
        return {
            "branch_logits": branch_logits,
            "state_logits": state_logits,
            "state_logits_per_branch": state_logits_per_branch,
            "llps_logit": self.llps_head(z).squeeze(-1),
            "aggregation_logit": self.aggregation_head(z).squeeze(-1),
            "ranking_scores": torch.cat([compactness_score, helicity_score, condensation_score], dim=-1),
            "branch_weight": branch_weight,
            "condensation_scores_per_branch": condensation_per_branch,
        }


def feature_vector_from_row(row: Dict[str, Any]) -> List[float]:
    return [float(row.get(name, 0.0) or 0.0) for name in FEATURE_NAMES]


def target_vector_from_row(row: Dict[str, Any]) -> List[float]:
    return [float(row.get(name, 0.0) or 0.0) for name in TARGET_NAMES]


def _safe_device(device: str) -> torch.device:
    use_cuda = torch.cuda.is_available() and str(device).lower() != "cpu"
    return torch.device("cuda" if use_cuda else "cpu")


def build_residual_model(architecture: str, in_dim: int, out_dim: int, hidden_dim: int = 64) -> nn.Module:
    arch = str(architecture or "mlp").lower()
    if arch == "branch_moe_v1":
        return BranchSelectorMoE(in_dim=in_dim, hidden_dim=max(hidden_dim, 96))
    if arch == "two_head":
        if out_dim != len(TARGET_NAMES):
            raise ValueError(f"two_head residual expects out_dim={len(TARGET_NAMES)}, got {out_dim}")
        return ResidualTwoHeadMLP(in_dim=in_dim, hidden_dim=hidden_dim)
    return ResidualMLP(in_dim=in_dim, out_dim=out_dim, hidden_dim=hidden_dim)


def load_residual_model(checkpoint_path: str, device: str = "auto") -> Tuple[nn.Module, torch.device, Dict[str, Any]]:
    dev = _safe_device(device)
    payload = torch.load(checkpoint_path, map_location=dev)
    hidden_dim = int(payload.get("hidden_dim", 64))
    architecture = str(payload.get("architecture", "mlp"))
    model = build_residual_model(
        architecture=architecture,
        in_dim=len(payload.get("feature_names", FEATURE_NAMES)),
        out_dim=len(payload.get("target_names", TARGET_NAMES)),
        hidden_dim=hidden_dim,
    ).to(dev)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    meta = {
        "feature_names": [str(v) for v in payload.get("feature_names", FEATURE_NAMES)],
        "target_names": [str(v) for v in payload.get("target_names", TARGET_NAMES)],
        "hidden_dim": hidden_dim,
        "architecture": architecture,
        "branch_names": [str(v) for v in payload.get("branch_names", BRANCH_NAMES)],
        "state_names": [str(v) for v in payload.get("state_names", STATE_NAMES)],
        "ranking_head_names": [str(v) for v in payload.get("ranking_head_names", RANKING_HEAD_NAMES)],
    }
    return model, dev, meta


def predict_residual_rows(
    rows: Sequence[Dict[str, Any]],
    checkpoint_path: str,
    device: str = "auto",
) -> Tuple[np.ndarray, Dict[str, Any]]:
    model, dev, meta = load_residual_model(checkpoint_path, device=device)
    x = np.asarray([feature_vector_from_row(row) for row in rows], dtype=np.float32)
    with torch.inference_mode():
        pred = model(torch.from_numpy(x).to(dev)).detach().cpu().numpy()
    return pred, meta


def predict_branch_rows(
    rows: Sequence[Dict[str, Any]],
    checkpoint_path: str,
    device: str = "auto",
) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
    model, dev, meta = load_residual_model(checkpoint_path, device=device)
    if str(meta.get("architecture", "")) != "branch_moe_v1":
        raise RuntimeError("checkpoint is not branch_moe_v1")
    x = np.asarray([feature_vector_from_row(row) for row in rows], dtype=np.float32)
    with torch.inference_mode():
        out = model(torch.from_numpy(x).to(dev))
        branch_logits = out["branch_logits"].detach().cpu()
        state_logits = out["state_logits"].detach().cpu()
        state_logits_per_branch = out.get("state_logits_per_branch", None)
        llps_prob = torch.sigmoid(out["llps_logit"]).detach().cpu()
        aggregation_prob = torch.sigmoid(out["aggregation_logit"]).detach().cpu()
        ranking_scores = out["ranking_scores"].detach().cpu()
        branch_weight = torch.softmax(branch_logits, dim=-1)
        state_prob = torch.softmax(state_logits, dim=-1)
        state_prob_per_branch = None
        if state_logits_per_branch is not None:
            state_prob_per_branch = torch.softmax(state_logits_per_branch.detach().cpu(), dim=-1)
    return {
        "branch_weight": branch_weight.numpy(),
        "state_prob": state_prob.numpy(),
        "state_prob_per_branch": state_prob_per_branch.numpy() if state_prob_per_branch is not None else None,
        "llps_prob": llps_prob.numpy(),
        "aggregation_prob": aggregation_prob.numpy(),
        "ranking_scores": ranking_scores.numpy(),
    }, meta
