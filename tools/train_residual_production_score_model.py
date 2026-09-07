#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from tools.builder_json_utils import (
    build_score_model_train_fingerprint,
    fingerprint_digest,
    read_json as _read_json_util,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_CSV = "runs/residual_production_supervised_dataset_current.csv"
DEFAULT_OUT_CHECKPOINT = "models/residual_production_score_model_current.pt"
DEFAULT_OUT_JSON = "runs/residual_production_score_model_current.json"
DEFAULT_OUT_MD = "runs/residual_production_score_model_current.md"
DEFAULT_FORCE_DERIVATION_JSON = "/dev/null"
PRODUCTION_FORCE_DERIVATION_JSON = "runs/residual_force_derivation_validation_current.json"
DEFAULT_TRAIN_FINGERPRINT_JSON = "runs/residual_production_score_model_train_fingerprint_current.json"
TRAINER_CONTRACT_VERSION = "score_candidate_integrity_v2"
LEARNED_OUTPUT_FIELDS = ["delta_score", "corrected_score"]
POLICY_OUTPUT_FIELDS = ["abstention_reason", "stage2_route_decision"]
PRODUCTION_ENERGY_FIELD = "delta_energy"
PRODUCTION_FORCE_FIELD = "delta_force"
REFINE_TIER_LABEL_FIELD = "refine_tier_label"
REFINE_TIER_FEATURE_FIELDS = (
    "refine_tier_delta",
    "mm_gbsa_delta",
    "refine_confidence",
    "physics_refinement_confidence",
)
MISSING_PRODUCTION_OUTPUT_FIELDS = ["delta_energy", "delta_force", "uncertainty"]

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


def _read_json_summary(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else payload if isinstance(payload, dict) else {}


def _force_derivation_validation_ready(path_like: str | Path) -> bool:
    text = str(path_like or "").strip()
    if not text or text in {"/dev/null", "none", "skip"}:
        return False
    summary = _read_json_summary(path_like)
    return summary.get("delta_force_derivation_validation_ready") is True


def _score_groups(y_true: list[int], y_score: list[float]) -> list[tuple[int, int]]:
    """Positive/negative counts at each descending, tied score threshold."""
    if len(y_true) != len(y_score) or not y_true:
        raise ValueError("metrics require equally sized, nonempty labels and scores")
    if any(label not in (0, 1) for label in y_true):
        raise ValueError("metrics require binary labels")
    if any(not math.isfinite(score) for score in y_score):
        raise ValueError("metrics require finite scores")
    order = sorted(range(len(y_score)), key=lambda idx: y_score[idx], reverse=True)
    groups: list[tuple[int, int]] = []
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and y_score[order[stop]] == y_score[order[start]]:
            stop += 1
        positives = sum(y_true[idx] == 1 for idx in order[start:stop])
        groups.append((positives, stop - start - positives))
        start = stop
    return groups


def _auc_binary(y_true: list[int], y_score: list[float]) -> float | None:
    groups = _score_groups(y_true, y_score)
    pos = sum(p for p, _ in groups)
    neg = sum(n for _, n in groups)
    if not pos or not neg:
        return None  # Undefined is not evidence of chance-level performance.
    positives_above = 0
    concordant = 0.0
    for p, n in groups:
        concordant += n * (positives_above + 0.5 * p)
        positives_above += p
    return float(concordant / (pos * neg))


def _pr_auc_binary(y_true: list[int], y_score: list[float]) -> float | None:
    """Trapezoidal PR area at distinct thresholds, not average precision."""
    groups = _score_groups(y_true, y_score)
    pos = sum(p for p, _ in groups)
    if not pos:
        return None
    tp = fp = 0
    prev_recall, prev_precision, area = 0.0, 1.0, 0.0
    for p, n in groups:
        tp += p
        fp += n
        recall, precision = tp / pos, tp / (tp + fp)
        area += (recall - prev_recall) * (precision + prev_precision) / 2.0
        prev_recall, prev_precision = recall, precision
    return float(area)


def _average_precision_binary(y_true: list[int], y_score: list[float]) -> float | None:
    groups = _score_groups(y_true, y_score)
    pos = sum(p for p, _ in groups)
    if not pos:
        return None
    tp = fp = 0
    area = 0.0
    for p, n in groups:
        tp += p
        fp += n
        area += (p / pos) * (tp / (tp + fp))
    return float(area)


def _snapshot_state_dict(model: nn.Module) -> dict[str, torch.Tensor]:
    # .cpu() aliases CPU tensors: each value must own an immutable snapshot.
    return {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}


def _load_rows(path_like: str | Path) -> list[dict[str, Any]]:
    path = _resolve(path_like)
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [dict(row) for row in reader]


def _family_vocab(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({str(row.get("family") or "unknown") for row in rows})


def _role_vocab(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({str(row.get("role") or "unknown") for row in rows})


def _refine_feature_fields(rows: list[dict[str, Any]]) -> list[str]:
    present: list[str] = []
    for field in REFINE_TIER_FEATURE_FIELDS:
        if any(str(row.get(field) or "").strip() not in {"", "nan", "none"} for row in rows):
            present.append(field)
    return present


def _matrix(
    rows: list[dict[str, Any]],
    families: list[str],
    roles: list[str],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, list[str]]:
    refine_fields = _refine_feature_fields(rows)
    feature_names = ["raw_score", "mean_min_distance_A"]
    feature_names.extend(f"family={item}" for item in families)
    # role describes labels/splits, not an inference-time molecular feature.
    feature_names.extend(refine_fields)
    xs: list[list[float]] = []
    y_cls: list[float] = []
    y_delta: list[float] = []
    y_energy: list[float] = []
    y_energy_mask: list[float] = []
    for row in rows:
        family = str(row.get("family") or "unknown")
        values = [
            _float(row.get("raw_score")),
            _float(row.get("mean_min_distance_A")),
        ]
        values.extend(1.0 if family == item else 0.0 for item in families)
        for field in refine_fields:
            values.append(_float(row.get(field)))
        xs.append(values)
        binder = _float(row.get("is_binder"), default=float("nan"))
        residual = _float(row.get("delta_score"), default=float("nan"))
        if binder not in (0.0, 1.0) or not math.isfinite(residual):
            raise ValueError("is_binder must be binary and delta_score must be finite")
        y_cls.append(binder)
        y_delta.append(residual)
        energy_raw = row.get(PRODUCTION_ENERGY_FIELD)
        # Refine-tier labels are a different target, not automatically delta-E.
        energy = _float(energy_raw, default=float("nan"))
        if not math.isfinite(energy):
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
        self.force_head = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        h = self.trunk(x)
        return (
            self.cls_head(h).squeeze(-1),
            self.delta_head(h).squeeze(-1),
            self.energy_head(h).squeeze(-1),
            self.force_head(h).squeeze(-1),
        )


def _split_indices(rows: list[dict[str, Any]], seed: int, train_ratio: float) -> tuple[list[int], list[int]]:
    """Keep all rows of one ligand ID together across targets/poses/runs.

    This is not scaffold or target-held-out validation: different IDs may still
    describe the same chemistry. Such identity normalization belongs upstream.
    """
    if not math.isfinite(train_ratio) or not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must lie strictly between zero and one")
    grouped: dict[str, list[int]] = {}
    for idx, row in enumerate(rows):
        ligand = str(row.get("ligand_id") or "").strip()
        if not ligand:
            raise ValueError("ligand_id is required for grouped train/validation splitting")
        grouped.setdefault(ligand, []).append(idx)
    keys = sorted(grouped)
    if len(keys) < 2:
        raise ValueError("need at least two ligand groups for training and validation")
    generator = torch.Generator().manual_seed(seed)
    perm = torch.randperm(len(keys), generator=generator).tolist()
    cut = max(1, min(len(keys) - 1, int(round(len(keys) * train_ratio))))
    train = [idx for k in perm[:cut] for idx in grouped[keys[k]]]
    val = [idx for k in perm[cut:] for idx in grouped[keys[k]]]
    return train, val


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
    force_derivation_json: str = DEFAULT_FORCE_DERIVATION_JSON,
) -> dict[str, Any]:
    for name, value in (("epochs", epochs), ("hidden_dim", hidden_dim), ("batch_size", batch_size)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if not math.isfinite(lr) or lr <= 0 or not math.isfinite(weight_decay) or weight_decay < 0:
        raise ValueError("lr must be positive and weight_decay nonnegative, both finite")
    rows = _load_rows(input_csv)
    if len(rows) < 2:
        raise RuntimeError("need at least two rows for score-model training")
    train_idx, val_idx = _split_indices(rows, seed=seed, train_ratio=train_ratio)
    families = _family_vocab([rows[idx] for idx in train_idx])
    roles: list[str] = []
    refine_fields = _refine_feature_fields(rows)
    refine_tier_label_rows = sum(
        1 for row in rows if str(row.get(REFINE_TIER_LABEL_FIELD) or "").strip() not in {"", "nan", "none"}
    )
    x, y_cls, y_delta, y_energy, y_energy_mask, feature_names = _matrix(rows, families, roles)
    if not all(torch.isfinite(t).all() for t in (x, y_cls, y_delta, y_energy)):
        raise ValueError("training features and labels must be finite and float32-representable")
    if not torch.all((y_cls == 0) | (y_cls == 1)):
        raise ValueError("is_binder labels must be binary")
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
    energy_train_rows = int(y_energy_mask_train.sum().item())
    delta_energy_head_trained = energy_train_rows >= max(10, min(100, len(train_idx) // 10))
    force_derivation_ready = _force_derivation_validation_ready(force_derivation_json)
    force_label_rows = sum(
        math.isfinite(_float(row.get(PRODUCTION_FORCE_FIELD), default=float("nan")))
        for row in rows
    )
    # The scalar force output has no force loss, and the tabular features have
    # no coordinate derivative. Neither labels nor an external receipt train it.
    delta_force_head_supervised = False
    delta_force_head_derivation_stub = False
    delta_force_head_trained = False

    x_mean = x_train.mean(dim=0)
    x_std = x_train.std(dim=0, unbiased=False).clamp_min(1e-6)
    x_train_n = (x_train - x_mean) / x_std
    x_val_n = (x_val - x_mean) / x_std

    device = torch.device("cuda" if torch.cuda.is_available() and device_name.lower() != "cpu" else "cpu")
    torch.manual_seed(seed)
    model = ResidualScoreMLP(in_dim=x.shape[1], hidden_dim=hidden_dim).to(device)
    model.force_head.requires_grad_(False)  # preserve checkpoint shape, never advertise it as trained
    ds = TensorDataset(x_train_n, y_cls_train, y_delta_train, y_energy_train, y_energy_mask_train)
    dl = DataLoader(ds, batch_size=max(1, batch_size), shuffle=True, generator=torch.Generator().manual_seed(seed))
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
            logits, delta, energy, _force = model(xb)
            loss = cls_loss(logits, yb_cls) + 0.2 * delta_loss(delta, yb_delta)
            if float(yb_energy_mask.sum().item()) > 0.0:
                energy_error = (energy_loss(energy, yb_energy) * yb_energy_mask).sum() / yb_energy_mask.sum().clamp_min(1.0)
                loss = loss + 0.1 * energy_error
            if not torch.isfinite(loss):
                raise ValueError("nonfinite_training_loss")
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            logits, delta, energy, _force = model(x_val_n.to(device))
            probs = torch.sigmoid(logits).detach().cpu().tolist()
            delta_pred = delta.detach().cpu()
            energy_pred = energy.detach().cpu()
        y_true = [int(v) for v in y_cls_val.tolist()]
        auc = _auc_binary(y_true, probs)
        pr_auc = _pr_auc_binary(y_true, probs)
        average_precision = _average_precision_binary(y_true, probs)
        rmse = float(torch.sqrt(torch.mean((delta_pred - y_delta_val) ** 2)).item())
        if float(y_energy_mask_val.sum().item()) > 0.0:
            energy_rmse = float(
                torch.sqrt(torch.sum(((energy_pred - y_energy_val) * y_energy_mask_val) ** 2) / y_energy_mask_val.sum()).item()
            )
        else:
            energy_rmse = None
        if not math.isfinite(rmse) or (energy_rmse is not None and not math.isfinite(energy_rmse)):
            raise ValueError("nonfinite_validation_error")
        score = (average_precision if average_precision is not None else 0.0) - 0.01 * math.log1p(rmse)
        if best is None or score > float(best["score"]):
            best = {"epoch": epoch, "auc": auc, "pr_auc": pr_auc, "average_precision": average_precision, "delta_rmse": rmse, "energy_rmse": energy_rmse, "score": score}
            best_state = _snapshot_state_dict(model)

    learned_output_fields = list(LEARNED_OUTPUT_FIELDS)
    missing_production_output_fields = list(MISSING_PRODUCTION_OUTPUT_FIELDS)
    if delta_energy_head_trained:
        learned_output_fields.append(PRODUCTION_ENERGY_FIELD)
        missing_production_output_fields = [field for field in missing_production_output_fields if field != PRODUCTION_ENERGY_FIELD]
    if delta_force_head_trained:
        learned_output_fields.append(PRODUCTION_FORCE_FIELD)
        missing_production_output_fields = [field for field in missing_production_output_fields if field != PRODUCTION_FORCE_FIELD]
    production_checkpoint_ready = False  # force and calibrated uncertainty are not implemented here
    evidence = {
        "trainer_contract_version": TRAINER_CONTRACT_VERSION,
        "split_policy": "ligand_id_grouped_v1",
        "feature_stage": "post_refinement_rescoring",
        "role_features_used": False,
        "uncertainty_calibrated": False,
        "physical_energy_residual_validated": False,
        "delta_force_training_status": "not_implemented_no_force_loss_or_coordinate_gradient",
        "delta_energy_train_label_rows": energy_train_rows,
        "delta_energy_validation_label_rows": int(y_energy_mask_val.sum().item()),
        "metric_definitions": {"auc": "tie_aware_roc_auc", "pr_auc": "trapezoidal_pr_area",
                               "average_precision": "noninterpolated_average_precision"},
    }
    _ensure_parent(out_checkpoint)
    torch.save(
        {
            **evidence,
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
            "delta_force_head_trained": delta_force_head_trained,
            "delta_force_head_supervised": delta_force_head_supervised,
            "delta_force_head_derivation_stub": delta_force_head_derivation_stub,
            "delta_force_label_rows": force_label_rows,
            "delta_force_derivation_validation_ready": force_derivation_ready,
        },
        _resolve(out_checkpoint),
    )
    summary = {
        **evidence,
        "checkpoint_sha256": hashlib.sha256(_resolve(out_checkpoint).read_bytes()).hexdigest(),
        "ok": True,
        "packet_type": "residual_production_score_model",
        "status": "residual_production_score_model_trained",
        "input_csv": input_csv,
        "checkpoint": str(_resolve(out_checkpoint)),
        "train_rows": len(train_idx),
        "val_rows": len(val_idx),
        "feature_dim": len(feature_names),
        "feature_names": feature_names,
        "refine_tier_feature_fields": refine_fields,
        "refine_tier_label_rows": refine_tier_label_rows,
        "target_count": len({str(row.get("target") or "") for row in rows}),
        "family_count": len(families),
        "device": str(device),
        "best": best or {},
        "model_role": "protein_ligand_residual_score_candidate",
        "production_checkpoint_ready": production_checkpoint_ready,
        "learned_output_fields": learned_output_fields,
        "delta_energy_head_trained": delta_energy_head_trained,
        "delta_energy_label_rows": energy_label_rows,
        "delta_force_head_trained": delta_force_head_trained,
        "delta_force_head_supervised": delta_force_head_supervised,
        "delta_force_head_derivation_stub": delta_force_head_derivation_stub,
        "delta_force_label_rows": force_label_rows,
        "delta_force_derivation_validation_ready": force_derivation_ready,
        "policy_output_fields": POLICY_OUTPUT_FIELDS,
        "policy_output_adapter_ready": True,
        "missing_production_output_fields": missing_production_output_fields,
        "execution_enabled": False,
        "training_executed": True,
        "training_skipped": False,
        "checkpoint_created": True,
        "model_promoted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Rerun checkpoint sidecar/preflight and production promotion gates."
            if production_checkpoint_ready
            else (
                "Attach production sidecar/output-head evidence only after delta_force, uncertainty calibration, and physics guard are validated."
                if delta_energy_head_trained
                else "Attach production sidecar/output-head evidence only after delta_energy, delta_force, uncertainty calibration, and physics guard are validated."
            )
        ),
    }
    return summary


def build_train_fingerprint(
    *,
    input_csv: str = DEFAULT_INPUT_CSV,
    force_derivation_json: str = DEFAULT_FORCE_DERIVATION_JSON,
    epochs: int = 20,
    hidden_dim: int = 64,
    batch_size: int = 256,
    lr: float = 1e-3,
    weight_decay: float = 1e-5,
    train_ratio: float = 0.8,
    seed: int = 42,
) -> dict[str, Any]:
    fingerprint = build_score_model_train_fingerprint(
        input_csv=input_csv,
        force_derivation_json=force_derivation_json,
        epochs=epochs,
        hidden_dim=hidden_dim,
        batch_size=batch_size,
        lr=lr,
        weight_decay=weight_decay,
        train_ratio=train_ratio,
        seed=seed,
        root=ROOT,
    )
    fingerprint["trainer_contract_version"] = TRAINER_CONTRACT_VERSION
    fingerprint["trainer_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    fingerprint["digest"] = fingerprint_digest(fingerprint)
    return fingerprint


def try_skip_training(
    *,
    input_csv: str,
    out_checkpoint: str,
    out_json: str,
    force_derivation_json: str,
    fingerprint_json: str,
    epochs: int,
    hidden_dim: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    train_ratio: float,
    seed: int,
) -> dict[str, Any] | None:
    fingerprint = build_train_fingerprint(
        input_csv=input_csv,
        force_derivation_json=force_derivation_json,
        epochs=epochs,
        hidden_dim=hidden_dim,
        batch_size=batch_size,
        lr=lr,
        weight_decay=weight_decay,
        train_ratio=train_ratio,
        seed=seed,
    )
    stored = _read_json_util(fingerprint_json, root=ROOT)
    checkpoint_path = _resolve(out_checkpoint)
    summary_path = _resolve(out_json)
    if (
        stored.get("digest") == fingerprint["digest"]
        and checkpoint_path.exists()
        and summary_path.exists()
    ):
        payload = _read_json_util(summary_path, root=ROOT)
        if (
            str(payload.get("status") or "") == "residual_production_score_model_trained"
            and payload.get("trainer_contract_version") == TRAINER_CONTRACT_VERSION
            and payload.get("production_checkpoint_ready") is False
            and payload.get("delta_force_head_trained") is False
            and payload.get("uncertainty_calibrated") is False
            and payload.get("checkpoint_sha256") == hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
        ):
            skipped = dict(payload)
            skipped["training_skipped"] = True
            skipped["training_executed"] = False
            skipped["training_skip_reason"] = "inputs_unchanged"
            skipped["train_fingerprint_digest"] = fingerprint["digest"]
            return skipped
    return None


def write_train_fingerprint(path_like: str | Path, fingerprint: dict[str, Any]) -> None:
    _ensure_parent(path_like)
    _resolve(path_like).write_text(
        json.dumps(fingerprint, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
        f"- best_average_precision: `{best.get('average_precision')}`",
        f"- best_delta_rmse: `{best.get('delta_rmse')}`",
        f"- best_energy_rmse: `{best.get('energy_rmse')}`",
        f"- delta_energy_head_trained: `{payload['delta_energy_head_trained']}`",
        f"- delta_energy_label_rows: `{payload['delta_energy_label_rows']}`",
        f"- delta_force_head_trained: `{payload['delta_force_head_trained']}`",
        f"- delta_force_head_supervised: `{payload['delta_force_head_supervised']}`",
        f"- delta_force_head_derivation_stub: `{payload['delta_force_head_derivation_stub']}`",
        f"- delta_force_label_rows: `{payload['delta_force_label_rows']}`",
        f"- delta_force_derivation_validation_ready: `{payload['delta_force_derivation_validation_ready']}`",
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
    parser.add_argument("--force-derivation-json", default=DEFAULT_FORCE_DERIVATION_JSON)
    parser.add_argument("--train-fingerprint-json", default=DEFAULT_TRAIN_FINGERPRINT_JSON)
    parser.add_argument("--skip-if-unchanged", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload: dict[str, Any] | None = None
    if args.skip_if_unchanged:
        payload = try_skip_training(
            input_csv=args.input_csv,
            out_checkpoint=args.out_checkpoint,
            out_json=args.out_json,
            force_derivation_json=args.force_derivation_json,
            fingerprint_json=args.train_fingerprint_json,
            epochs=args.epochs,
            hidden_dim=args.hidden_dim,
            batch_size=args.batch_size,
            lr=args.lr,
            weight_decay=args.weight_decay,
            train_ratio=args.train_ratio,
            seed=args.seed,
        )
    if payload is None:
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
            force_derivation_json=args.force_derivation_json,
        )
        write_train_fingerprint(
            args.train_fingerprint_json,
            build_train_fingerprint(
                input_csv=args.input_csv,
                force_derivation_json=args.force_derivation_json,
                epochs=args.epochs,
                hidden_dim=args.hidden_dim,
                batch_size=args.batch_size,
                lr=args.lr,
                weight_decay=args.weight_decay,
                train_ratio=args.train_ratio,
                seed=args.seed,
            ),
        )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
