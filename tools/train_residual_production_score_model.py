#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_CSV = "runs/residual_production_supervised_dataset_current.csv"
DEFAULT_OUT_CHECKPOINT = "models/residual_production_score_model_current.pt"
DEFAULT_OUT_JSON = "runs/residual_production_score_model_current.json"
DEFAULT_OUT_MD = "runs/residual_production_score_model_current.md"
LEARNED_OUTPUT_FIELDS = ["delta_score", "corrected_score", "uncertainty"]
POLICY_OUTPUT_FIELDS = ["abstention_reason", "stage2_route_decision"]
PRODUCTION_ENERGY_FIELD = "delta_energy"
MISSING_PRODUCTION_OUTPUT_FIELDS = ["delta_energy", "delta_force"]

CLAIM_BOUNDARY = (
    "Residual production score-model trainer only; trains a local supervised score/binder candidate from the "
    "materialized residual production supervised dataset. It does not create production sidecars, bind physics "
    "guards, promote production mode, run docking, upload, submit, email, delete, or mutate external state."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _ensure_parent(path_like: str | Path) -> None:
    _resolve(path_like).parent.mkdir(parents=True, exist_ok=True)


def _auc_binary(y_true: list[int], y_score: list[float]) -> float:
    pos = sum(1 for item in y_true if item == 1)
    neg = sum(1 for item in y_true if item == 0)
    if pos <= 0 or neg <= 0:
        return 0.5
    order = sorted(range(len(y_score)), key=lambda idx: y_score[idx])
    ranks = [0.0] * len(order)
    for rank, idx in enumerate(order, start=1):
        ranks[idx] = float(rank)
    pos_rank_sum = sum(ranks[idx] for idx, item in enumerate(y_true) if item == 1)
    return float((pos_rank_sum - (pos * (pos + 1) / 2.0)) / (pos * neg))


def _pr_auc_binary(y_true: list[int], y_score: list[float]) -> float:
    pos = sum(1 for item in y_true if item == 1)
    if pos <= 0:
        return 0.0
    order = sorted(range(len(y_score)), key=lambda idx: y_score[idx], reverse=True)
    tp = 0
    fp = 0
    prev_recall = 0.0
    area = 0.0
    prev_precision = 1.0
    for idx in order:
        if y_true[idx] == 1:
            tp += 1
        else:
            fp += 1
        recall = tp / float(pos)
        precision = tp / float(max(tp + fp, 1))
        area += (recall - prev_recall) * ((precision + prev_precision) / 2.0)
        prev_recall = recall
        prev_precision = precision
    return float(area)


def _load_rows(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader]


def _family_vocab(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({str(row.get("family") or "unknown") for row in rows})


def _role_vocab(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({str(row.get("role") or "unknown") for row in rows})


def _matrix(
    rows: list[dict[str, Any]],
    families: list[str],
    roles: list[str],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, list[str]]:
    feature_names = ["raw_score", "mean_min_distance_A"]
    feature_names.extend(f"family={item}" for item in families)
    feature_names.extend(f"role={item}" for item in roles)
    xs: list[list[float]] = []
    y_cls: list[float] = []
    y_delta: list[float] = []
    y_energy: list[float] = []
    y_energy_mask: list[float] = []
    for row in rows:
        family = str(row.get("family") or "unknown")
        role = str(row.get("role") or "unknown")
        values = [
            _float(row.get("raw_score")),
            _float(row.get("mean_min_distance_A")),
        ]
        values.extend(1.0 if family == item else 0.0 for item in families)
        values.extend(1.0 if role == item else 0.0 for item in roles)
        xs.append(values)
        y_cls.append(float(_int(row.get("is_binder"))))
        y_delta.append(_float(row.get("delta_score")))
        energy = _float(row.get(PRODUCTION_ENERGY_FIELD), default=float("nan"))
        if math.isnan(energy):
            y_energy.append(0.0)
            y_energy_mask.append(0.0)
        else:
            y_energy.append(energy)
            y_energy_mask.append(1.0)
    return (
        torch.tensor(xs, dtype=torch.float32),
        torch.tensor(y_cls, dtype=torch.float32),
        torch.tensor(y_delta, dtype=torch.float32),
        torch.tensor(y_energy, dtype=torch.float32),
        torch.tensor(y_energy_mask, dtype=torch.float32),
        feature_names,
    )


class ResidualScoreMLP(nn.Module):
    def __init__(self, in_dim: int, hidden_dim: int):
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        self.cls_head = nn.Linear(hidden_dim, 1)
        self.delta_head = nn.Linear(hidden_dim, 1)
        self.energy_head = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        h = self.trunk(x)
        return self.cls_head(h).squeeze(-1), self.delta_head(h).squeeze(-1), self.energy_head(h).squeeze(-1)


def _split_indices(rows: list[dict[str, Any]], seed: int, train_ratio: float) -> tuple[list[int], list[int]]:
    generator = torch.Generator().manual_seed(seed)
    perm = torch.randperm(len(rows), generator=generator).tolist()
    cut = max(1, min(len(perm) - 1, int(round(len(perm) * train_ratio))))
    return perm[:cut], perm[cut:]


def train_residual_production_score_model(
    *,
    input_csv: str = DEFAULT_INPUT_CSV,
    out_checkpoint: str = DEFAULT_OUT_CHECKPOINT,
    epochs: int = 20,
    hidden_dim: int = 64,
    batch_size: int = 256,
    lr: float = 1e-3,
    weight_decay: float = 1e-5,
    train_ratio: float = 0.8,
    seed: int = 42,
    device_name: str = "auto",
) -> dict[str, Any]:
    rows = _load_rows(input_csv)
    if len(rows) < 2:
        raise RuntimeError("need at least two rows for score-model training")
    families = _family_vocab(rows)
    roles = _role_vocab(rows)
    x, y_cls, y_delta, y_energy, y_energy_mask, feature_names = _matrix(rows, families, roles)
    train_idx, val_idx = _split_indices(rows, seed=seed, train_ratio=train_ratio)
    x_train = x[train_idx]
    y_cls_train = y_cls[train_idx]
    y_delta_train = y_delta[train_idx]
    y_energy_train = y_energy[train_idx]
    y_energy_mask_train = y_energy_mask[train_idx]
    x_val = x[val_idx]
    y_cls_val = y_cls[val_idx]
    y_delta_val = y_delta[val_idx]
    y_energy_val = y_energy[val_idx]
    y_energy_mask_val = y_energy_mask[val_idx]
    energy_label_rows = int(y_energy_mask.sum().item())
    delta_energy_head_trained = energy_label_rows >= max(10, min(100, len(rows) // 10))

    x_mean = x_train.mean(dim=0)
    x_std = x_train.std(dim=0).clamp_min(1e-6)
    x_train_n = (x_train - x_mean) / x_std
    x_val_n = (x_val - x_mean) / x_std

    device = torch.device("cuda" if torch.cuda.is_available() and device_name.lower() != "cpu" else "cpu")
    model = ResidualScoreMLP(in_dim=x.shape[1], hidden_dim=hidden_dim).to(device)
    ds = TensorDataset(x_train_n, y_cls_train, y_delta_train, y_energy_train, y_energy_mask_train)
    dl = DataLoader(ds, batch_size=max(1, batch_size), shuffle=True)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    cls_loss = nn.BCEWithLogitsLoss()
    delta_loss = nn.SmoothL1Loss()
    energy_loss = nn.SmoothL1Loss(reduction="none")
    best: dict[str, Any] | None = None
    best_state: dict[str, torch.Tensor] | None = None

    for epoch in range(1, epochs + 1):
        model.train()
        for xb, yb_cls, yb_delta, yb_energy, yb_energy_mask in dl:
            xb = xb.to(device)
            yb_cls = yb_cls.to(device)
            yb_delta = yb_delta.to(device)
            yb_energy = yb_energy.to(device)
            yb_energy_mask = yb_energy_mask.to(device)
            opt.zero_grad(set_to_none=True)
            logits, delta, energy = model(xb)
            loss = cls_loss(logits, yb_cls) + 0.2 * delta_loss(delta, yb_delta)
            if float(yb_energy_mask.sum().item()) > 0.0:
                energy_error = (energy_loss(energy, yb_energy) * yb_energy_mask).sum() / yb_energy_mask.sum().clamp_min(1.0)
                loss = loss + 0.1 * energy_error
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            logits, delta, energy = model(x_val_n.to(device))
            probs = torch.sigmoid(logits).detach().cpu().tolist()
            delta_pred = delta.detach().cpu()
            energy_pred = energy.detach().cpu()
        y_true = [int(v) for v in y_cls_val.tolist()]
        auc = _auc_binary(y_true, probs)
        pr_auc = _pr_auc_binary(y_true, probs)
        rmse = float(torch.sqrt(torch.mean((delta_pred - y_delta_val) ** 2)).item())
        if float(y_energy_mask_val.sum().item()) > 0.0:
            energy_rmse = float(
                torch.sqrt(torch.sum(((energy_pred - y_energy_val) * y_energy_mask_val) ** 2) / y_energy_mask_val.sum()).item()
            )
        else:
            energy_rmse = 0.0
        score = pr_auc - 0.01 * math.log1p(rmse)
        if best is None or score > float(best["score"]):
            best = {"epoch": epoch, "auc": auc, "pr_auc": pr_auc, "delta_rmse": rmse, "energy_rmse": energy_rmse, "score": score}
            best_state = {key: value.detach().cpu() for key, value in model.state_dict().items()}

    learned_output_fields = list(LEARNED_OUTPUT_FIELDS)
    missing_production_output_fields = list(MISSING_PRODUCTION_OUTPUT_FIELDS)
    if delta_energy_head_trained:
        learned_output_fields.append(PRODUCTION_ENERGY_FIELD)
        missing_production_output_fields = [field for field in missing_production_output_fields if field != PRODUCTION_ENERGY_FIELD]
    _ensure_parent(out_checkpoint)
    torch.save(
        {
            "state_dict": best_state,
            "feature_names": feature_names,
            "families": families,
            "roles": roles,
            "x_mean": x_mean,
            "x_std": x_std,
            "model_role": "protein_ligand_residual_score_candidate",
            "output_fields": learned_output_fields + POLICY_OUTPUT_FIELDS,
            "learned_output_fields": learned_output_fields,
            "policy_output_fields": POLICY_OUTPUT_FIELDS,
            "delta_energy_head_trained": delta_energy_head_trained,
            "delta_energy_label_rows": energy_label_rows,
        },
        _resolve(out_checkpoint),
    )
    summary = {
        "ok": True,
        "packet_type": "residual_production_score_model",
        "status": "residual_production_score_model_trained",
        "input_csv": input_csv,
        "checkpoint": str(_resolve(out_checkpoint)),
        "train_rows": len(train_idx),
        "val_rows": len(val_idx),
        "feature_dim": len(feature_names),
        "target_count": len({str(row.get("target") or "") for row in rows}),
        "family_count": len(families),
        "device": str(device),
        "best": best or {},
        "model_role": "protein_ligand_residual_score_candidate",
        "production_checkpoint_ready": False,
        "learned_output_fields": learned_output_fields,
        "delta_energy_head_trained": delta_energy_head_trained,
        "delta_energy_label_rows": energy_label_rows,
        "policy_output_fields": POLICY_OUTPUT_FIELDS,
        "policy_output_adapter_ready": True,
        "missing_production_output_fields": missing_production_output_fields,
        "execution_enabled": False,
        "training_executed": True,
        "checkpoint_created": True,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Attach production sidecar/output-head evidence only after delta_force, uncertainty calibration, and physics guard are validated."
            if delta_energy_head_trained
            else "Attach production sidecar/output-head evidence only after delta_energy, delta_force, uncertainty calibration, and physics guard are validated."
        ),
    }
    return summary


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    _ensure_parent(path_like)
    _resolve(path_like).write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    _ensure_parent(path_like)
    best = payload.get("best") if isinstance(payload.get("best"), dict) else {}
    lines = [
        "# Residual Production Score Model",
        "",
        f"- status: `{payload['status']}`",
        f"- checkpoint: `{payload['checkpoint']}`",
        f"- train_rows: `{payload['train_rows']}`",
        f"- val_rows: `{payload['val_rows']}`",
        f"- feature_dim: `{payload['feature_dim']}`",
        f"- best_epoch: `{best.get('epoch')}`",
        f"- best_auc: `{best.get('auc')}`",
        f"- best_pr_auc: `{best.get('pr_auc')}`",
        f"- best_delta_rmse: `{best.get('delta_rmse')}`",
        f"- best_energy_rmse: `{best.get('energy_rmse')}`",
        f"- delta_energy_head_trained: `{payload['delta_energy_head_trained']}`",
        f"- delta_energy_label_rows: `{payload['delta_energy_label_rows']}`",
        f"- learned_output_fields: `{','.join(payload['learned_output_fields'])}`",
        f"- production_checkpoint_ready: `{payload['production_checkpoint_ready']}`",
        f"- missing_production_output_fields: `{','.join(payload['missing_production_output_fields'])}`",
        "",
        "## Claim Boundary",
        "",
        payload["claim_boundary"],
        "",
        "## Next Step",
        "",
        f"- {payload['next_required_step']}",
        "",
    ]
    _resolve(path_like).write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a local residual score/binder candidate from the supervised residual dataset.")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--out-checkpoint", default=DEFAULT_OUT_CHECKPOINT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = train_residual_production_score_model(
        input_csv=args.input_csv,
        out_checkpoint=args.out_checkpoint,
        epochs=args.epochs,
        hidden_dim=args.hidden_dim,
        batch_size=args.batch_size,
        lr=args.lr,
        weight_decay=args.weight_decay,
        train_ratio=args.train_ratio,
        seed=args.seed,
        device_name=args.device,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
