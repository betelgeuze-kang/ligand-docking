#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional, Sequence

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from tools.idp_residual_common import FEATURE_NAMES, build_residual_model


OFF_FEATURE_BY_TARGET = {
    "delta_rg_mean": "off_rg_mean",
    "delta_sasa_proxy_mean": "off_sasa_proxy_mean",
    "delta_contact_persistence": "off_contact_persistence",
    "delta_transient_helicity": "off_transient_helicity",
    "delta_ensemble_diversity": "off_ensemble_diversity",
}


DEFAULT_OBSERVABLE_WEIGHTS = {
    "delta_rg_mean": 1.0,
    "delta_sasa_proxy_mean": 3.0,
    "delta_contact_persistence": 3.0,
    "delta_transient_helicity": 2.5,
    "delta_ensemble_diversity": 1.0,
}


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def train(args: argparse.Namespace) -> Dict[str, Any]:
    payload = np.load(str(args.input_npz), allow_pickle=False)
    x = np.asarray(payload["feature_matrix"], dtype=np.float32)
    y = np.asarray(payload["targets"], dtype=np.float32)
    feature_names = [str(v) for v in np.asarray(payload["feature_names"]).tolist()]
    target_names = [str(v) for v in np.asarray(payload["target_names"]).tolist()]
    anchor_lo = np.asarray(payload["anchor_lo_matrix"], dtype=np.float32) if "anchor_lo_matrix" in payload else np.zeros((len(x), 0), dtype=np.float32)
    anchor_hi = np.asarray(payload["anchor_hi_matrix"], dtype=np.float32) if "anchor_hi_matrix" in payload else np.zeros((len(x), 0), dtype=np.float32)
    anchor_mask = np.asarray(payload["anchor_mask_matrix"], dtype=np.float32) if "anchor_mask_matrix" in payload else np.zeros((len(x), 0), dtype=np.float32)
    anchor_metric_names = [str(v) for v in np.asarray(payload["anchor_metric_names"]).tolist()] if "anchor_metric_names" in payload else []
    if x.shape[0] <= 1:
        raise RuntimeError("need at least 2 rows for residual training")

    rng = np.random.default_rng(int(args.seed))
    idx = np.arange(len(x), dtype=np.int64)
    rng.shuffle(idx)
    cut = max(1, int(round(len(idx) * float(args.train_ratio))))
    train_idx = idx[:cut]
    val_idx = idx[cut:] if cut < len(idx) else idx[-1:]

    x_train = torch.from_numpy(x[train_idx])
    y_train = torch.from_numpy(y[train_idx])
    alo_train = torch.from_numpy(anchor_lo[train_idx]) if anchor_lo.size else torch.zeros((len(train_idx), 0), dtype=torch.float32)
    ahi_train = torch.from_numpy(anchor_hi[train_idx]) if anchor_hi.size else torch.zeros((len(train_idx), 0), dtype=torch.float32)
    amask_train = torch.from_numpy(anchor_mask[train_idx]) if anchor_mask.size else torch.zeros((len(train_idx), 0), dtype=torch.float32)
    x_val = torch.from_numpy(x[val_idx])
    y_val = torch.from_numpy(y[val_idx])
    alo_val = torch.from_numpy(anchor_lo[val_idx]) if anchor_lo.size else torch.zeros((len(val_idx), 0), dtype=torch.float32)
    ahi_val = torch.from_numpy(anchor_hi[val_idx]) if anchor_hi.size else torch.zeros((len(val_idx), 0), dtype=torch.float32)
    amask_val = torch.from_numpy(anchor_mask[val_idx]) if anchor_mask.size else torch.zeros((len(val_idx), 0), dtype=torch.float32)

    ds = TensorDataset(x_train, y_train, alo_train, ahi_train, amask_train)
    dl = DataLoader(ds, batch_size=max(int(args.batch_size), 1), shuffle=True)
    device = torch.device("cuda" if torch.cuda.is_available() and str(args.device).lower() != "cpu" else "cpu")
    model = build_residual_model(
        architecture=str(args.architecture),
        in_dim=int(x.shape[1]),
        out_dim=int(y.shape[1]),
        hidden_dim=int(args.hidden_dim),
    ).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=float(args.lr), weight_decay=float(args.weight_decay))
    anchor_weight = float(args.anchor_loss_weight)
    observable_weight = float(args.observable_loss_weight)
    target_to_feature = {
        tgt: feature_names.index(OFF_FEATURE_BY_TARGET[tgt])
        for tgt in target_names
        if OFF_FEATURE_BY_TARGET.get(tgt) in feature_names
    }
    target_weights = torch.tensor(
        [float(DEFAULT_OBSERVABLE_WEIGHTS.get(tgt, 1.0)) for tgt in target_names],
        dtype=torch.float32,
        device=device,
    )

    best = None
    best_state = None
    for epoch in range(1, int(args.epochs) + 1):
        model.train()
        for xb, yb, alo_b, ahi_b, amask_b in dl:
            xb = xb.to(device)
            yb = yb.to(device)
            alo_b = alo_b.to(device)
            ahi_b = ahi_b.to(device)
            amask_b = amask_b.to(device)
            opt.zero_grad(set_to_none=True)
            pred = model(xb)
            base_err = (pred - yb) ** 2
            loss = (base_err * target_weights.unsqueeze(0)).mean()
            corrected_cols = []
            target_corrected_cols = []
            for tgt_name in target_names:
                feat_idx = target_to_feature[tgt_name]
                tgt_idx = target_names.index(tgt_name)
                corrected_cols.append(xb[:, feat_idx] + pred[:, tgt_idx])
                target_corrected_cols.append(xb[:, feat_idx] + yb[:, tgt_idx])
            corrected = torch.stack(corrected_cols, dim=1)
            target_corrected = torch.stack(target_corrected_cols, dim=1)
            if observable_weight > 0.0:
                obs_err = (corrected - target_corrected) ** 2
                obs_loss = (obs_err * target_weights.unsqueeze(0)).mean()
                loss = loss + observable_weight * obs_loss
            if anchor_weight > 0.0 and alo_b.shape[1] > 0:
                band_violation = torch.relu(alo_b - corrected) + torch.relu(corrected - ahi_b)
                band_width = torch.clamp(ahi_b - alo_b, min=1e-6)
                band_penalty = ((band_violation / band_width) * amask_b).sum() / torch.clamp(amask_b.sum(), min=1.0)
                loss = loss + anchor_weight * band_penalty
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            pred_t = model(x_val.to(device))
            pred = pred_t.detach().cpu().numpy()
        target_np = y_val.numpy()
        mae = np.mean(np.abs(pred - target_np), axis=0)
        mae_mean = float(np.mean(mae))
        band_penalty_val = 0.0
        if anchor_weight > 0.0 and alo_val.shape[1] > 0:
            corrected_cols_val = []
            x_val_dev = x_val.to(device)
            for tgt_name in target_names:
                feat_idx = target_to_feature[tgt_name]
                corrected_cols_val.append(x_val_dev[:, feat_idx] + pred_t[:, target_names.index(tgt_name)])
            corrected_val = torch.stack(corrected_cols_val, dim=1)
            alo_val_dev = alo_val.to(device)
            ahi_val_dev = ahi_val.to(device)
            amask_val_dev = amask_val.to(device)
            band_violation_val = torch.relu(alo_val_dev - corrected_val) + torch.relu(corrected_val - ahi_val_dev)
            band_width_val = torch.clamp(ahi_val_dev - alo_val_dev, min=1e-6)
            band_penalty_val = float((((band_violation_val / band_width_val) * amask_val_dev).sum() / torch.clamp(amask_val_dev.sum(), min=1.0)).detach().cpu().item())
        if best is None or mae_mean < best["mae_mean"]:
            best = {
                "epoch": int(epoch),
                "mae_mean": mae_mean,
                "anchor_band_penalty": float(band_penalty_val),
                "observable_loss_weight": observable_weight,
                "mae_by_target": {name: float(val) for name, val in zip(target_names, mae.tolist())},
            }
            best_state = {k: v.detach().cpu() for k, v in model.state_dict().items()}

    out_ckpt = str(args.out_checkpoint)
    out_json = str(args.out_json)
    out_md = str(args.out_md)
    _ensure_parent(out_ckpt)
    _ensure_parent(out_json)
    _ensure_parent(out_md)
    torch.save(
        {
            "state_dict": best_state,
            "feature_names": feature_names,
            "target_names": target_names,
            "anchor_metric_names": anchor_metric_names,
            "hidden_dim": int(args.hidden_dim),
            "architecture": str(args.architecture),
            "anchor_loss_weight": anchor_weight,
            "observable_loss_weight": observable_weight,
            "observable_target_weights": {name: float(DEFAULT_OBSERVABLE_WEIGHTS.get(name, 1.0)) for name in target_names},
        },
        out_ckpt,
    )
    summary = {
        "ok": True,
        "input_npz": str(args.input_npz),
        "checkpoint": out_ckpt,
        "feature_dim": int(x.shape[1]),
        "target_dim": int(y.shape[1]),
        "train_rows": int(len(train_idx)),
        "val_rows": int(len(val_idx)),
        "device": str(device),
        "anchor_loss_weight": anchor_weight,
        "observable_loss_weight": observable_weight,
        "best": best,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# IDP Residual Model",
                    "",
                    f"- input_npz: `{args.input_npz}`",
                    f"- checkpoint: `{out_ckpt}`",
                    f"- train_rows: {summary['train_rows']}",
                    f"- val_rows: {summary['val_rows']}",
                    f"- device: `{summary['device']}`",
                    f"- best_epoch: {best['epoch'] if best else 0}",
                    f"- best_mae_mean: {best['mae_mean'] if best else 0.0}",
                ]
            )
            + "\n"
        )
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Train a small observable residual model from IDP benchmark dataset.")
    p.add_argument("--input-npz", type=str, required=True)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--hidden-dim", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", type=str, default="auto")
    p.add_argument("--architecture", type=str, default="two_head", choices=["mlp", "two_head"])
    p.add_argument("--anchor-loss-weight", type=float, default=0.5)
    p.add_argument("--observable-loss-weight", type=float, default=0.5)
    p.add_argument("--out-checkpoint", type=str, required=True)
    p.add_argument("--out-json", type=str, required=True)
    p.add_argument("--out-md", type=str, required=True)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = train(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
