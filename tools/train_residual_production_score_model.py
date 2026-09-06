#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
from itertools import groupby
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
TRAINER_REVISION = "score-integrity-v2"
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
    """Descending threshold groups: ties are one threshold, never row ordered."""
    if not y_true or len(y_true) != len(y_score):
        raise ValueError("binary metric inputs must be nonempty and have equal length")
    if any(value not in (0, 1) for value in y_true):
        raise ValueError("binary labels must be 0 or 1")
    if any(not math.isfinite(value) for value in y_score):
        raise ValueError("binary scores must be finite")
    pairs = sorted(zip(y_score, y_true), key=lambda pair: pair[0], reverse=True)
    result = []
    for _score, members in groupby(pairs, key=lambda pair: pair[0]):
        labels = [label for _, label in members]
        result.append((sum(labels), len(labels) - sum(labels)))
    return result


def _auc_binary(y_true: list[int], y_score: list[float]) -> float:
    groups = _score_groups(y_true, y_score)
    pos, neg = sum(y_true), len(y_true) - sum(y_true)
    if not pos or not neg:
        # Legacy scalar fallback. Reports separately identify undefined ROC-AUC.
        return 0.5
    higher_pos = 0
    wins = 0.0
    for group_pos, group_neg in groups:
        wins += group_neg * (higher_pos + 0.5 * group_pos)
        higher_pos += group_pos
    return wins / (pos * neg)


def _precision_recall_areas(y_true: list[int], y_score: list[float]) -> tuple[float, float]:
    groups = _score_groups(y_true, y_score)
    pos = sum(y_true)
    if not pos:
        return 0.0, 0.0
    tp = fp = 0
    prev_recall, prev_precision = 0.0, 1.0
    trapezoid = average_precision = 0.0
    for group_pos, group_neg in groups:
        tp += group_pos
        fp += group_neg
        recall, precision = tp / pos, tp / (tp + fp)
        delta_recall = recall - prev_recall
        trapezoid += delta_recall * (precision + prev_precision) / 2.0
        average_precision += delta_recall * precision
        prev_recall, prev_precision = recall, precision
    return trapezoid, average_precision


def _pr_auc_binary(y_true: list[int], y_score: list[float]) -> float:
    """Threshold-grouped trapezoidal PR-AUC, explicitly not average precision."""
    return _precision_recall_areas(y_true, y_score)[0]


def _average_precision_binary(y_true: list[int], y_score: list[float]) -> float:
    return _precision_recall_areas(y_true, y_score)[1]


def _snapshot_state(model: nn.Module) -> dict[str, torch.Tensor]:
    """CPU storage must not alias the live model after selecting the best epoch."""
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
        if any(row.get(field) is not None and str(row.get(field)).strip().lower() not in {"", "nan", "none"} for row in rows):
            present.append(field)
    return present


def _required_number(row: dict[str, Any], field: str) -> float:
    raw = row.get(field)
    if isinstance(raw, bool) or raw is None or not str(raw).strip():
        raise ValueError(f"missing or invalid {field}")
    try:
        number = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not math.isfinite(number):
        raise ValueError(f"nonfinite {field}")
    return number


def _matrix(
    rows: list[dict[str, Any]],
    families: list[str],
    roles: list[str],
    *, refine_fields: list[str] | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, list[str]]:
    if refine_fields is None:
        refine_fields = _refine_feature_fields(rows)
    feature_names = ["raw_score", "mean_min_distance_A"]
    feature_names.extend(f"family={item}" for item in families)
    feature_names.extend(f"role={item}" for item in roles)
    feature_names.extend(refine_fields)
    xs: list[list[float]] = []
    y_cls: list[float] = []
    y_delta: list[float] = []
    y_energy: list[float] = []
    y_energy_mask: list[float] = []
    for row in rows:
        family = str(row.get("family") or "unknown")
        role = str(row.get("role") or "unknown")
        values = [
            _required_number(row, "raw_score"),
            _float(row.get("mean_min_distance_A")),
        ]
        values.extend(1.0 if family == item else 0.0 for item in families)
        values.extend(1.0 if role == item else 0.0 for item in roles)
        for field in refine_fields:
            values.append(_float(row.get(field)))
        xs.append(values)
        binder = _required_number(row, "is_binder")
        if binder not in (0.0, 1.0):
            raise ValueError("binder labels must be binary")
        y_cls.append(binder)
        y_delta.append(_required_number(row, "delta_score"))
        energy_raw = row.get(PRODUCTION_ENERGY_FIELD)
        if (energy_raw is None or str(energy_raw).strip().lower() in {"", "nan", "none"}) and str(row.get(REFINE_TIER_LABEL_FIELD) or "").strip():
            energy_raw = row.get(REFINE_TIER_LABEL_FIELD)
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
    """Keep repeated target/ligand observations together; not scaffold holdout."""
    if not math.isfinite(train_ratio) or not 0.0 < train_ratio < 1.0:
        raise ValueError("train_ratio must be finite and strictly between zero and one")
    groups: dict[tuple[str, str], list[int]] = {}
    for index, row in enumerate(rows):
        key = (str(row.get("target") or "").strip(), str(row.get("ligand_id") or "").strip())
        if not all(key):
            raise ValueError("target and ligand_id are required for grouped validation")
        groups.setdefault(key, []).append(index)
    keys = sorted(groups)
    if len(keys) < 2:
        raise ValueError("need at least two target/ligand groups for validation")
    generator = torch.Generator().manual_seed(seed)
    perm = torch.randperm(len(keys), generator=generator).tolist()
    cut = max(1, min(len(keys) - 1, int(round(len(keys) * train_ratio))))
    train_keys = {keys[index] for index in perm[:cut]}
    train_idx = sorted(index for key in train_keys for index in groups[key])
    val_idx = sorted(index for key in keys if key not in train_keys for index in groups[key])
    return train_idx, val_idx


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
    if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
        raise ValueError("epochs must be a positive integer")
    if hidden_dim < 1 or batch_size < 1:
        raise ValueError("hidden_dim and batch_size must be positive")
    if not math.isfinite(lr) or lr <= 0 or not math.isfinite(weight_decay) or weight_decay < 0:
        raise ValueError("invalid optimizer hyperparameters")
    rows = _load_rows(input_csv)
    if len(rows) < 2:
        raise RuntimeError("need at least two rows for score-model training")
    train_idx, val_idx = _split_indices(rows, seed=seed, train_ratio=train_ratio)
    training_rows = [rows[index] for index in train_idx]
    families = _family_vocab(training_rows)
    # Source/partition role is provenance, not a predictive molecular feature.
    roles: list[str] = []
    refine_fields = _refine_feature_fields(training_rows)
    refine_tier_label_rows = sum(
        1 for row in rows if str(row.get(REFINE_TIER_LABEL_FIELD) or "").strip() not in {"", "nan", "none"}
    )
    x, y_cls, y_delta, y_energy, y_energy_mask, feature_names = _matrix(rows, families, roles, refine_fields=refine_fields)
    for name, values in (("features", x), ("labels", y_cls), ("score targets", y_delta), ("energy targets", y_energy)):
        if not bool(torch.isfinite(values).all()):
            raise ValueError(f"nonfinite {name} in training dataset")
    if not bool(((y_cls == 0) | (y_cls == 1)).all()):
        raise ValueError("binder labels must be binary")
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
    energy_train_label_rows = int(y_energy_mask_train.sum().item())
    delta_energy_head_trained = energy_train_label_rows >= max(10, min(100, len(rows) // 10))
    force_derivation_ready = _force_derivation_validation_ready(force_derivation_json)
    force_label_rows = sum(
        1 for row in rows
        if math.isfinite(_float(row.get(PRODUCTION_FORCE_FIELD), default=float("nan")))
    )
    # A scalar tabular head with no force loss is not an atomwise force model.
    # External derivation receipts describe other evidence, not training here.
    delta_force_head_supervised = False
    delta_force_head_derivation_stub = False
    delta_force_head_trained = False

    x_mean = x_train.mean(dim=0)
    x_std = x_train.std(dim=0, unbiased=False).clamp_min(1e-6)
    x_train_n = (x_train - x_mean) / x_std
    x_val_n = (x_val - x_mean) / x_std

    device = torch.device("cuda" if torch.cuda.is_available() and device_name.lower() != "cpu" else "cpu")
    # Initialize on CPU with a local RNG scope, then transfer. CPU replay is
    # deterministic within an environment; no cross-device parity is asserted.
    with torch.random.fork_rng(devices=[]):
        torch.random.default_generator.manual_seed(seed)
        model = ResidualScoreMLP(in_dim=x.shape[1], hidden_dim=hidden_dim)
    model = model.to(device)
    model.force_head.requires_grad_(False)
    ds = TensorDataset(x_train_n, y_cls_train, y_delta_train, y_energy_train, y_energy_mask_train)
    dl = DataLoader(ds, batch_size=batch_size, shuffle=True, generator=torch.Generator().manual_seed(seed))
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
            if not bool(torch.isfinite(loss)):
                raise ValueError("nonfinite training loss; checkpoint was not written")
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
            raise ValueError("nonfinite validation error; checkpoint was not written")
        score = average_precision - 0.01 * math.log1p(rmse)
        if best is None or score > float(best["score"]):
            best = {"epoch": epoch, "auc": auc, "pr_auc": pr_auc, "average_precision": average_precision, "roc_auc_defined": len(set(y_true)) == 2, "delta_rmse": rmse, "energy_rmse": energy_rmse, "score": score}
            best_state = _snapshot_state(model)

    learned_output_fields = list(LEARNED_OUTPUT_FIELDS)
    missing_production_output_fields = list(MISSING_PRODUCTION_OUTPUT_FIELDS)
    if delta_energy_head_trained:
        learned_output_fields.append(PRODUCTION_ENERGY_FIELD)
        missing_production_output_fields = [field for field in missing_production_output_fields if field != PRODUCTION_ENERGY_FIELD]
    if delta_force_head_trained:
        learned_output_fields.append(PRODUCTION_FORCE_FIELD)
        missing_production_output_fields = [field for field in missing_production_output_fields if field != PRODUCTION_FORCE_FIELD]
    production_checkpoint_ready = not missing_production_output_fields
    _ensure_parent(out_checkpoint)
    torch.save(
        {
            "state_dict": best_state,
            "trainer_revision": TRAINER_REVISION,
            "selection_metric": "average_precision_minus_log_delta_rmse",
            "uncertainty_calibrated": False,
            "delta_energy_train_label_rows": energy_train_label_rows,
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
        "ok": True,
        "trainer_revision": TRAINER_REVISION,
        "selection_metric": "average_precision_minus_log_delta_rmse",
        "metric_definitions": {"pr_auc": "threshold_grouped_trapezoid", "average_precision": "recall_weighted_precision"},
        "uncertainty_calibrated": False,
        "delta_energy_train_label_rows": energy_train_label_rows,
        "validation_scope": "target_ligand_grouped_internal_not_family_or_scaffold_holdout",
        "feature_stage": "post_docking_or_post_refinement_not_early_screening",
        "role_feature_used": False,
        "delta_energy_physical_validation": "not_assessed_label_units_and_pairing_require_validation",
        "force_training_status": "not_implemented_no_force_loss",
        "checkpoint_sha256": hashlib.sha256(_resolve(out_checkpoint).read_bytes()).hexdigest(),
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
    fingerprint["trainer_revision"] = TRAINER_REVISION
    fingerprint["trainer_source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    fingerprint["torch_version"] = str(torch.__version__)
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
            and payload.get("trainer_revision") == TRAINER_REVISION
            and payload.get("checkpoint_sha256") == hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
            and payload.get("delta_force_head_trained") is False
            and payload.get("production_checkpoint_ready") is False
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
