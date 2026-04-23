#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, Optional, Sequence

import numpy as np
import torch
import torch.nn.functional as F

from tools.idp_residual_common import BRANCH_NAMES, RANKING_HEAD_NAMES, STATE_NAMES, build_residual_model


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _average_precision(y_true: np.ndarray, y_score: np.ndarray) -> float:
    order = np.argsort(-y_score)
    y = y_true[order]
    tp = np.cumsum(y)
    fp = np.cumsum(1.0 - y)
    precision = tp / np.maximum(tp + fp, 1.0)
    if float(y.sum()) <= 0.0:
        return 0.0
    return float((precision * y).sum() / y.sum())


def _balanced_class_weight(labels: np.ndarray, n_classes: int) -> np.ndarray:
    counts = np.bincount(labels.astype(np.int64), minlength=n_classes).astype(np.float32)
    total = float(counts.sum())
    weights = np.ones(n_classes, dtype=np.float32)
    for idx, count in enumerate(counts):
        if count > 0.0:
            weights[idx] = total / (float(n_classes) * float(count))
    weights /= max(float(weights.mean()), 1e-6)
    return weights.astype(np.float32)


def _binary_pos_weight(flags: np.ndarray) -> float:
    pos = float(np.sum(flags > 0.5))
    neg = float(np.sum(flags <= 0.5))
    if pos <= 0.0 or neg <= 0.0:
        return 1.0
    return max(neg / pos, 1.0)


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    _ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def train(args: argparse.Namespace) -> Dict[str, Any]:
    payload = np.load(str(args.input_npz), allow_pickle=False)
    x = np.asarray(payload["feature_matrix"], dtype=np.float32)
    branch_priors = np.asarray(payload["branch_priors"], dtype=np.float32)
    branch_labels = np.asarray(payload["branch_labels"], dtype=np.int64)
    state_labels = np.asarray(payload["state_labels"], dtype=np.int64)
    llps_flags = np.asarray(payload["llps_flags"], dtype=np.float32)
    aggregation_flags = np.asarray(payload["aggregation_flags"], dtype=np.float32)
    ranking_targets = np.asarray(payload["ranking_targets"], dtype=np.float32)
    pair_left = np.asarray(payload["pair_left"], dtype=np.int64)
    pair_right = np.asarray(payload["pair_right"], dtype=np.int64)
    pair_label = np.asarray(payload["pair_label"], dtype=np.float32)
    feature_names = [str(v) for v in np.asarray(payload["feature_names"]).tolist()]
    if len(x) <= 1:
        raise RuntimeError("need at least 2 rows for branch training")

    seed = int(args.seed)
    started = time.time()
    rng = np.random.default_rng(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if bool(args.deterministic):
        try:
            torch.use_deterministic_algorithms(True, warn_only=True)
        except Exception:
            pass
        if hasattr(torch.backends, "cudnn"):
            try:
                torch.backends.cudnn.deterministic = True
                torch.backends.cudnn.benchmark = False
            except Exception:
                pass
    idx = np.arange(len(x), dtype=np.int64)
    rng.shuffle(idx)
    cut = max(1, int(round(len(idx) * float(args.train_ratio))))
    train_idx = idx[:cut]
    val_idx = idx[cut:] if cut < len(idx) else idx[-1:]

    train_mask = np.zeros(len(x), dtype=bool)
    train_mask[train_idx] = True
    val_mask = np.zeros(len(x), dtype=bool)
    val_mask[val_idx] = True
    pair_train_mask = train_mask[pair_left] & train_mask[pair_right]
    pair_val_mask = val_mask[pair_left] & val_mask[pair_right]

    branch_weight_np = _balanced_class_weight(branch_labels[train_idx], len(BRANCH_NAMES))
    state_weight_np = _balanced_class_weight(state_labels[train_idx], len(STATE_NAMES))
    llps_pos_weight = _binary_pos_weight(llps_flags[train_idx])
    agg_pos_weight = _binary_pos_weight(aggregation_flags[train_idx])
    rank_head_weights = np.asarray([1.25, 1.85, 1.65], dtype=np.float32)

    requested_device = str(args.device).strip().lower()
    if requested_device in {"", "auto"}:
        requested_device = "cuda"
    if requested_device == "cpu":
        raise SystemExit("IDP branch trainer CPU mode is disabled; use ROCm/Torch cuda device.")
    if not requested_device.startswith("cuda"):
        raise SystemExit(f"Unsupported IDP branch trainer device: {requested_device}")
    if not torch.cuda.is_available():
        raise SystemExit("IDP branch trainer requires GPU, but torch.cuda.is_available() is false.")
    device = torch.device("cuda")
    model = build_residual_model("branch_moe_v1", in_dim=int(x.shape[1]), out_dim=0, hidden_dim=int(args.hidden_dim)).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=float(args.lr), weight_decay=float(args.weight_decay))
    total_epochs = int(args.epochs)
    patience = int(args.patience)
    min_delta = float(args.min_delta)
    progress_json = os.path.splitext(str(args.out_json))[0] + "_progress.json"

    xt = torch.from_numpy(x).to(device)
    branch_prior_t = torch.from_numpy(branch_priors).to(device)
    branch_labels_t = torch.from_numpy(branch_labels).to(device)
    state_labels_t = torch.from_numpy(state_labels).to(device)
    llps_t = torch.from_numpy(llps_flags).to(device)
    agg_t = torch.from_numpy(aggregation_flags).to(device)
    ranking_t = torch.from_numpy(ranking_targets).to(device)
    pair_left_t = torch.from_numpy(pair_left).to(device)
    pair_right_t = torch.from_numpy(pair_right).to(device)
    pair_label_t = torch.from_numpy(pair_label).to(device)
    train_idx_t = torch.from_numpy(train_idx).to(device)
    val_idx_t = torch.from_numpy(val_idx).to(device)
    pair_train_idx = torch.from_numpy(np.where(pair_train_mask)[0]).to(device)
    pair_val_idx = torch.from_numpy(np.where(pair_val_mask)[0]).to(device)
    branch_weight_t = torch.from_numpy(branch_weight_np).to(device)
    state_weight_t = torch.from_numpy(state_weight_np).to(device)
    llps_pos_weight_t = torch.tensor(llps_pos_weight, dtype=torch.float32, device=device)
    agg_pos_weight_t = torch.tensor(agg_pos_weight, dtype=torch.float32, device=device)
    rank_head_weight_t = torch.from_numpy(rank_head_weights).to(device)

    best = None
    best_state = None
    best_score = float("-inf")
    bad_epochs = 0
    epochs_completed = 0
    _write_json(
        progress_json,
        {
            "status": "running",
            "device": str(device),
            "epoch": 0,
            "total_epochs": total_epochs,
            "progress_ratio": 0.0,
            "best_score": None,
            "best_epoch": None,
            "bad_epochs": 0,
            "patience": patience,
            "elapsed_sec": 0.0,
            "train_rows": int(len(train_idx)),
            "val_rows": int(len(val_idx)),
        },
    )
    for epoch in range(1, total_epochs + 1):
        model.train()
        opt.zero_grad(set_to_none=True)
        out_full = model(xt)
        branch_logits = out_full["branch_logits"][train_idx_t]
        state_logits = out_full["state_logits"][train_idx_t]
        branch_targets = branch_labels_t[train_idx_t]
        state_targets = state_labels_t[train_idx_t]
        branch_prior_train = branch_prior_t[train_idx_t]
        branch_row_weight = 1.0 + 1.35 * branch_prior_train[:, 1] + 0.25 * branch_prior_train[:, 2]
        branch_prob = torch.softmax(branch_logits, dim=-1)
        branch_ce = F.cross_entropy(branch_logits, branch_targets, weight=branch_weight_t, reduction="none")
        branch_loss = torch.mean(branch_ce * branch_row_weight)
        prior_loss = F.kl_div(
            F.log_softmax(branch_logits, dim=-1),
            branch_prior_train,
            reduction="batchmean",
        )
        state_loss = F.cross_entropy(state_logits, state_targets, weight=state_weight_t)
        state_logits_per_branch = out_full.get("state_logits_per_branch")
        if state_logits_per_branch is not None:
            train_branch_state_logits = state_logits_per_branch[train_idx_t]
            branch_state_logits = train_branch_state_logits[
                torch.arange(train_branch_state_logits.shape[0], device=device), branch_targets
            ]
            branch_state_loss = F.cross_entropy(branch_state_logits, state_targets, weight=state_weight_t)
            state_loss = 0.40 * state_loss + 0.60 * branch_state_loss
        agg_mask = branch_prior_train[:, 1] >= torch.maximum(branch_prior_train[:, 0], branch_prior_train[:, 2])
        agg_mask = agg_mask & (branch_prior_train[:, 1] >= 0.45)
        llps_mask = branch_prior_train[:, 0] >= torch.maximum(branch_prior_train[:, 1], branch_prior_train[:, 2])
        llps_mask = llps_mask & (branch_prior_train[:, 0] >= 0.45)
        helix_mask = branch_prior_train[:, 2] >= torch.maximum(branch_prior_train[:, 0], branch_prior_train[:, 1])
        helix_mask = helix_mask & (branch_prior_train[:, 2] >= 0.45)
        route_loss = torch.tensor(0.0, device=device)
        if bool(torch.any(agg_mask)):
            agg_delta = branch_prob[agg_mask, 1] - torch.maximum(branch_prob[agg_mask, 0], branch_prob[agg_mask, 2])
            agg_margin = F.relu(0.20 - agg_delta)
            route_loss = route_loss + torch.mean(agg_margin * (1.0 + 2.4 * branch_prior_train[agg_mask, 1]))
            agg_llps_penalty = torch.mean(branch_prob[agg_mask, 0] * (1.0 + 1.8 * branch_prior_train[agg_mask, 1]))
            agg_helix_penalty = torch.mean(branch_prob[agg_mask, 2] * (1.0 + 2.6 * branch_prior_train[agg_mask, 1]))
            route_loss = route_loss + 0.85 * agg_llps_penalty + 1.25 * agg_helix_penalty
        if bool(torch.any(llps_mask)):
            llps_delta = branch_prob[llps_mask, 0] - torch.maximum(branch_prob[llps_mask, 1], branch_prob[llps_mask, 2])
            llps_margin = F.relu(0.12 - llps_delta)
            route_loss = route_loss + 0.40 * torch.mean(llps_margin * (1.0 + 1.4 * branch_prior_train[llps_mask, 0]))
        if bool(torch.any(helix_mask)):
            helix_delta = branch_prob[helix_mask, 2] - torch.maximum(branch_prob[helix_mask, 0], branch_prob[helix_mask, 1])
            helix_margin = F.relu(0.10 - helix_delta)
            route_loss = route_loss + 0.30 * torch.mean(helix_margin * (1.0 + 1.2 * branch_prior_train[helix_mask, 2]))
        llps_loss = F.binary_cross_entropy_with_logits(
            out_full["llps_logit"][train_idx_t],
            llps_t[train_idx_t],
            pos_weight=llps_pos_weight_t,
        )
        agg_loss = F.binary_cross_entropy_with_logits(
            out_full["aggregation_logit"][train_idx_t],
            agg_t[train_idx_t],
            pos_weight=agg_pos_weight_t,
        )
        ranking_scores_full = out_full["ranking_scores"]
        rank_reg_loss = torch.mean(
            torch.square(ranking_scores_full[train_idx_t] - ranking_t[train_idx_t]) * rank_head_weight_t.view(1, -1)
        )
        rank_pair_loss = torch.tensor(0.0, device=device)
        if int(pair_train_idx.numel()) > 0:
            pl = pair_left_t[pair_train_idx]
            pr = pair_right_t[pair_train_idx]
            pair_true = pair_label_t[pair_train_idx]
            pred_left = ranking_scores_full[pl]
            pred_right = ranking_scores_full[pr]
            pair_logits = pred_left - pred_right
            pair_bce = F.binary_cross_entropy_with_logits(pair_logits, pair_true, reduction="none")
            rank_pair_loss = torch.mean(pair_bce * rank_head_weight_t.view(1, -1))
        loss = (
            1.95 * branch_loss
            + 0.35 * prior_loss
            + 1.20 * route_loss
            + 1.25 * state_loss
            + 0.70 * llps_loss
            + 1.35 * agg_loss
            + 0.60 * rank_reg_loss
            + 1.45 * rank_pair_loss
        )
        loss.backward()
        opt.step()
        epochs_completed = epoch

        model.eval()
        with torch.no_grad():
            out_val_full = model(xt)
            branch_pred = torch.argmax(out_val_full["branch_logits"][val_idx_t], dim=-1).detach().cpu().numpy()
            state_pred = torch.argmax(out_val_full["state_logits"][val_idx_t], dim=-1).detach().cpu().numpy()
            branch_acc = float((branch_pred == branch_labels[val_idx]).mean()) if len(val_idx) else 0.0
            state_acc = float((state_pred == state_labels[val_idx]).mean()) if len(val_idx) else 0.0
            llps_prob = torch.sigmoid(out_val_full["llps_logit"][val_idx_t]).detach().cpu().numpy()
            agg_prob = torch.sigmoid(out_val_full["aggregation_logit"][val_idx_t]).detach().cpu().numpy()
            llps_ap = _average_precision(llps_flags[val_idx], llps_prob) if len(val_idx) else 0.0
            agg_ap = _average_precision(aggregation_flags[val_idx], agg_prob) if len(val_idx) else 0.0
            pair_auc = 0.0
            if int(pair_val_idx.numel()) > 0:
                pl = pair_left_t[pair_val_idx]
                pr = pair_right_t[pair_val_idx]
                pair_true = pair_label[pair_val_mask]
                pred_pair = (out_val_full["ranking_scores"][pl] - out_val_full["ranking_scores"][pr]).detach().cpu().numpy()
                pair_auc = float(((pred_pair > 0).astype(np.float32) == pair_true).mean())
            score = 0.35 * branch_acc + 0.25 * state_acc + 0.20 * llps_ap + 0.20 * agg_ap + 0.20 * pair_auc
        improved = score > (best_score + min_delta)
        if improved:
            best_score = float(score)
            bad_epochs = 0
            best = {
                "epoch": int(epoch),
                "score": float(score),
                "branch_acc": branch_acc,
                "state_acc": state_acc,
                "llps_pr_auc": llps_ap,
                "aggregation_pr_auc": agg_ap,
                "pairwise_acc": pair_auc,
            }
            best_state = {k: v.detach().cpu() for k, v in model.state_dict().items()}
        else:
            bad_epochs += 1
        _write_json(
            progress_json,
            {
                "status": "running",
                "device": str(device),
                "epoch": int(epoch),
                "total_epochs": total_epochs,
                "progress_ratio": float(epoch / max(total_epochs, 1)),
                "best_score": None if best is None else float(best["score"]),
                "best_epoch": None if best is None else int(best["epoch"]),
                "bad_epochs": int(bad_epochs),
                "patience": patience,
                "elapsed_sec": float(time.time() - started),
                "train_rows": int(len(train_idx)),
                "val_rows": int(len(val_idx)),
                "loss": float(loss.detach().cpu().item()),
                "branch_acc": float(branch_acc),
                "state_acc": float(state_acc),
                "llps_pr_auc": float(llps_ap),
                "aggregation_pr_auc": float(agg_ap),
                "pairwise_acc": float(pair_auc),
            },
        )
        if bad_epochs >= patience:
            break

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
            "branch_names": BRANCH_NAMES,
            "state_names": STATE_NAMES,
            "ranking_head_names": RANKING_HEAD_NAMES,
            "hidden_dim": int(args.hidden_dim),
            "architecture": "branch_moe_v1",
        },
        out_ckpt,
    )
    summary = {
        "ok": True,
        "input_npz": str(args.input_npz),
        "checkpoint": out_ckpt,
        "feature_dim": int(x.shape[1]),
        "train_rows": int(len(train_idx)),
        "val_rows": int(len(val_idx)),
        "device": str(device),
        "epochs_completed": int(epochs_completed),
        "max_epochs": int(total_epochs),
        "stopped_early": bool(epochs_completed < total_epochs),
        "best": best,
    }
    _write_json(out_json, summary)
    _write_json(
        progress_json,
        {
            "status": "done",
            "device": str(device),
            "epoch": int(epochs_completed),
            "total_epochs": total_epochs,
            "progress_ratio": 1.0,
            "best_score": None if best is None else float(best["score"]),
            "best_epoch": None if best is None else int(best["epoch"]),
            "bad_epochs": int(bad_epochs),
            "patience": patience,
            "elapsed_sec": float(time.time() - started),
            "train_rows": int(len(train_idx)),
            "val_rows": int(len(val_idx)),
        },
    )
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# IDP Branch Model",
                    "",
                    f"- checkpoint: `{out_ckpt}`",
                    f"- train_rows: {summary['train_rows']}",
                    f"- val_rows: {summary['val_rows']}",
                    f"- device: `{summary['device']}`",
                    f"- best_score: {best['score'] if best else 0.0}",
                ]
            ) + "\n"
        )
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Train branch/state/ranking IDP model.")
    p.add_argument("--input-npz", type=str, required=True)
    p.add_argument("--train-ratio", type=float, default=0.8)
    p.add_argument("--epochs", type=int, default=80)
    p.add_argument("--hidden-dim", type=int, default=96)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=1e-5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--patience", type=int, default=12)
    p.add_argument("--min-delta", type=float, default=1e-4)
    p.add_argument("--deterministic", action="store_true")
    p.add_argument("--device", type=str, default="cuda")
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
