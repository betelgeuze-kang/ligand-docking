"""Shared tabular score-candidate contract; no physical or calibrated outputs."""
from __future__ import annotations

import hashlib
import math
from numbers import Real
from pathlib import Path
from typing import Any

import torch
from torch import nn

SHADOW_SCHEMA = "residual_score_shadow_v1"
MODEL_ROLE = "protein_ligand_residual_score_candidate"
REFINE_FIELDS = ("refine_tier_delta", "mm_gbsa_delta", "refine_confidence", "physics_refinement_confidence")
SCORE_COLUMNS = ("raw_score", "binding_score_composite_v4", "binding_score_composite_v5",
                 "binding_score_composite_v6", "binding_score_composite_v7")


def source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def feature_value(row: dict[str, Any], field: str, *, required: bool) -> tuple[float, float]:
    value = row.get(field)
    missing = value is None or (isinstance(value, str) and not value.strip())
    if missing:
        if required:
            raise ValueError(f"missing_required_training_feature:{field}")
        return 0.0, 1.0
    if isinstance(value, bool) or not isinstance(value, (Real, str)):
        raise ValueError(f"invalid_training_feature:{field}")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"invalid_training_feature:{field}") from exc
    if not math.isfinite(number) or abs(number) > torch.finfo(torch.float32).max:
        raise ValueError(f"invalid_training_feature:{field}")
    return number, 0.0


def feature_schema(families: list[str], refine_fields: list[str]) -> list[str]:
    if (not isinstance(families, list) or
            any(not isinstance(item, str) or not item for item in families) or
            len(set(families)) != len(families)):
        raise ValueError("invalid_residual_family_vocabulary")
    if (not isinstance(refine_fields, list) or
            any(item not in REFINE_FIELDS for item in refine_fields) or
            refine_fields != [item for item in REFINE_FIELDS if item in refine_fields]):
        raise ValueError("invalid_residual_refine_schema")
    names = ["raw_score", "mean_min_distance_A", "mean_min_distance_A_missing"]
    names.extend(f"family={item}" for item in families)
    for item in refine_fields:
        names.extend([item, f"{item}_missing"])
    return names


def encode_features(rows: list[dict[str, Any]], families: list[str], refine_fields: list[str]) -> tuple[torch.Tensor, list[str]]:
    names = feature_schema(families, refine_fields)
    encoded = []
    for row in rows:
        family = str(row.get("family") or "unknown")
        raw_score, _ = feature_value(row, "raw_score", required=True)
        distance, missing = feature_value(row, "mean_min_distance_A", required=False)
        if distance < 0:
            raise ValueError("invalid_training_feature:mean_min_distance_A")
        values = [raw_score, distance, missing]
        values.extend(1.0 if family == item else 0.0 for item in families)
        for field in refine_fields:
            values.extend(feature_value(row, field, required=False))
        encoded.append(values)
    return torch.tensor(encoded, dtype=torch.float32, device="cpu").reshape(len(rows), len(names)), names


class ResidualScoreMLP(nn.Module):
    def __init__(self, in_dim: int, hidden_dim: int):
        super().__init__()
        self.trunk = nn.Sequential(nn.Linear(in_dim, hidden_dim), nn.ReLU(),
                                   nn.Linear(hidden_dim, hidden_dim), nn.ReLU())
        self.cls_head = nn.Linear(hidden_dim, 1)
        self.delta_head = nn.Linear(hidden_dim, 1)
        self.energy_head = nn.Linear(hidden_dim, 1)
        self.force_head = nn.Linear(hidden_dim, 1)
        self.register_buffer("forbidden_missing_features", torch.zeros(in_dim, dtype=torch.bool))

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        if bool((x[..., self.forbidden_missing_features] != 0).any().item()):
            raise ValueError("unseen_training_missingness")
        h = self.trunk(x)
        return (self.cls_head(h).squeeze(-1), self.delta_head(h).squeeze(-1),
                self.energy_head(h).squeeze(-1), self.force_head(h).squeeze(-1))


def shadow_contract(*, rows: list[dict[str, Any]], families: list[str], refine_fields: list[str], hidden_dim: int) -> dict[str, Any]:
    columns = {str(row.get("score_col") or "raw_score") for row in rows}
    if len(columns) != 1 or not columns.issubset(SCORE_COLUMNS):
        raise ValueError("ambiguous_or_unsupported_residual_score_source")
    names = feature_schema(families, refine_fields)
    return {"schema_version": SHADOW_SCHEMA, "architecture": "ResidualScoreMLP_v1",
            "shared_source_sha256": source_sha256(), "feature_names": names,
            "families": list(families), "refine_feature_fields": list(refine_fields),
            "in_dim": len(names), "hidden_dim": hidden_dim, "dtype": "float32",
            "input_score_column": next(iter(columns)), "feature_stage": "post_refinement_rescoring",
            "output_semantics": "diagnostic_score_proxy_not_affinity_or_physical_energy",
            "ranking_effect": "none"}
