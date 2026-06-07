#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional, Sequence

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _auc_binary(y_true: np.ndarray, y_score: np.ndarray) -> float:
    y = np.asarray(y_true, dtype=np.int32)
    s = np.asarray(y_score, dtype=np.float64)
    pos = int(np.sum(y == 1))
    neg = int(np.sum(y == 0))
    if pos <= 0 or neg <= 0:
        return 0.5
    order = np.argsort(s)
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(s) + 1, dtype=np.float64)
    pos_ranks = ranks[y == 1]
    return float((pos_ranks.sum() - (pos * (pos + 1) / 2.0)) / (pos * neg))


def _pr_auc_binary(y_true: np.ndarray, y_score: np.ndarray) -> float:
    y = np.asarray(y_true, dtype=np.int32)
    s = np.asarray(y_score, dtype=np.float64)
    pos = int(np.sum(y == 1))
    if pos <= 0:
        return 0.0
    order = np.argsort(-s)
    y = y[order]
    tp = np.cumsum(y == 1)
    fp = np.cumsum(y == 0)
    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / float(pos)
    precision = np.concatenate([[1.0], precision])
    recall = np.concatenate([[0.0], recall])
    return float(np.trapz(precision, recall))


class AuxMLP(nn.Module):
    def __init__(self, in_dim: int, hidden_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def _mask_from_roles(roles: np.ndarray, role_csv: str) -> np.ndarray:
    wanted = {x.strip() for x in str(role_csv).split(",") if x.strip()}
    if not wanted:
        return np.zeros((len(roles),), dtype=bool)
    return np.asarray([str(r) in wanted for r in roles], dtype=bool)


def train(args: argparse.Namespace) -> Dict[str, Any]:
    if str(getattr(args, "input_csv", "")).strip():
        import pandas as pd

        df = pd.read_csv(str(args.input_csv))
        feature_names = [
            "n_frames",
            "ligand_atom_count",
            "protein_res_count",
            "mean_min_distance_A",
            "min_min_distance_A",
            "final_min_distance_A",
            "contact_fraction_4p5A",
            "contact_fraction_6A",
            "contact_fraction_8A",
            "centroid_path_A",
            "mean_step_A",
            "max_step_A",
            "centroid_dispersion_A",
            "final_shift_A",
            "affinity_hint",
            "k_attr",
            "protein_repulse",
            "sim_fps",
        ]
        for c in feature_names + ["is_binder", "role"]:
            if c not in df.columns:
                raise ValueError(f"input_csv missing required column: {c}")
        x = df[feature_names].fillna(0.0).to_numpy(dtype=np.float32, copy=True)
        y = df["is_binder"].to_numpy(dtype=np.int64, copy=True)
        roles = df["role"].astype(str).to_numpy(dtype=np.str_)
        input_descriptor = str(args.input_csv)
    else:
        if (not str(args.input_npz).strip()) or (not os.path.exists(str(args.input_npz))):
            raise ValueError("provide --input-csv or valid --input-npz")
        payload = np.load(str(args.input_npz), allow_pickle=False)
        x = np.asarray(payload["feature_matrix"], dtype=np.float32)
        y = np.asarray(payload["labels"], dtype=np.int64)
        roles = np.asarray(payload["roles"]).astype(str) if "roles" in payload.files else np.asarray([""] * len(x))
        feature_names = [str(v) for v in np.asarray(payload["feature_names"]).tolist()]
        input_descriptor = str(args.input_npz)

    labeled_mask = y >= 0
    x = x[labeled_mask]
    y = y[labeled_mask]
    roles = roles[labeled_mask]
    if x.shape[0] <= 0:
        raise RuntimeError("no labeled samples in trajectory aux dataset")

    train_mask = _mask_from_roles(roles, str(args.train_roles))
    val_mask = _mask_from_roles(roles, str(args.val_roles))
    if not np.any(train_mask) or not np.any(val_mask):
        rng = np.random.default_rng(int(args.seed))
        idx = np.arange(len(x), dtype=np.int64)
        rng.shuffle(idx)
        cut = max(1, int(round(len(idx) * float(args.train_ratio))))
        train_idx = idx[:cut]
        val_idx = idx[cut:] if cut < len(idx) else idx[-max(1, len(idx) // 5):]
        train_mask = np.zeros((len(x),), dtype=bool)
        val_mask = np.zeros((len(x),), dtype=bool)
        train_mask[train_idx] = True
        val_mask[val_idx] = True

    x_train = torch.from_numpy(x[train_mask])
    y_train = torch.from_numpy(y[train_mask].astype(np.float32))
    x_val = torch.from_numpy(x[val_mask])
    y_val_np = y[val_mask].astype(np.int32)

    ds = TensorDataset(x_train, y_train)
    dl = DataLoader(ds, batch_size=max(int(args.batch_size), 1), shuffle=True)
    device = torch.device("cuda" if torch.cuda.is_available() and str(args.device).lower() != "cpu" else "cpu")
    model = AuxMLP(in_dim=int(x.shape[1]), hidden_dim=int(args.hidden_dim)).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=float(args.lr), weight_decay=float(args.weight_decay))
    loss_fn = nn.BCEWithLogitsLoss()

    best = None
    best_state = None
    for epoch in range(1, int(args.epochs) + 1):
        model.train()
        for xb, yb in dl:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad(set_to_none=True)
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            val_logits = model(x_val.to(device)).detach().cpu().numpy()
        val_prob = 1.0 / (1.0 + np.exp(-val_logits))
        auc = _auc_binary(y_val_np, val_prob)
        pr_auc = _pr_auc_binary(y_val_np, val_prob)
        score = (auc + pr_auc) / 2.0
        if best is None or score > best["score"]:
            best = {
                "epoch": int(epoch),
                "auc": float(auc),
                "pr_auc": float(pr_auc),
                "score": float(score),
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
            "input_npz": input_descriptor,
            "hidden_dim": int(args.hidden_dim),
        },
        out_ckpt,
    )
    summary = {
        "ok": True,
        "input_npz": input_descriptor,
        "checkpoint": out_ckpt,
        "feature_dim": int(x.shape[1]),
        "train_rows": int(np.sum(train_mask)),
        "val_rows": int(np.sum(val_mask)),
        "device": str(device),
        "best": best,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# Ligand Trajectory Aux Model",
                    "",
                    f"- input_npz: `{input_descriptor}`",
                    f"- checkpoint: `{out_ckpt}`",
                    f"- train_rows: {summary['train_rows']}",
                    f"- val_rows: {summary['val_rows']}",
                    f"- device: `{summary['device']}`",
                    f"- best_epoch: {best['epoch'] if best else 0}",
                    f"- best_auc: {best['auc'] if best else 0.0}",
                    f"- best_pr_auc: {best['pr_auc'] if best else 0.0}",
                ]
            )
            + "\n"
        )
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Train a lightweight auxiliary classifier from ligand trajectory npz features.")
    p.add_argument("--input-npz", type=str, default="")
    p.add_argument("--input-csv", type=str, default="")
    p.add_argument("--train-roles", type=str, default="fit,train")
    p.add_argument("--val-roles", type=str, default="far_ood_eval,eval,val")
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--hidden-dim", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", type=str, default="auto")
    p.add_argument("--out-checkpoint", type=str, required=True)
    p.add_argument("--out-json", type=str, required=True)
    p.add_argument("--out-md", type=str, required=True)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    train(args)


if __name__ == "__main__":
    main()
