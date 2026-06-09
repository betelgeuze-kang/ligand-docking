#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def resolve_path(path_like: str | Path, *, root: Path | None = None) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    base = root or ROOT
    return base / path


def read_json(path_like: str | Path, *, root: Path | None = None) -> dict[str, Any]:
    path = resolve_path(path_like, root=root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_summary(packet: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(packet, dict):
        return {}
    summary = packet.get("summary")
    if isinstance(summary, dict):
        return summary
    return packet


def sha256_file(path_like: str | Path, *, root: Path | None = None) -> str:
    path = resolve_path(path_like, root=root)
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_score_model_train_fingerprint(
    *,
    input_csv: str | Path,
    force_derivation_json: str | Path,
    epochs: int,
    hidden_dim: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    train_ratio: float,
    seed: int,
    root: Path | None = None,
) -> dict[str, Any]:
    return {
        "input_csv_sha256": sha256_file(input_csv, root=root),
        "force_derivation_json_sha256": sha256_file(force_derivation_json, root=root),
        "epochs": int(epochs),
        "hidden_dim": int(hidden_dim),
        "batch_size": int(batch_size),
        "lr": float(lr),
        "weight_decay": float(weight_decay),
        "train_ratio": float(train_ratio),
        "seed": int(seed),
    }


def fingerprint_digest(fingerprint: dict[str, Any]) -> str:
    canonical = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
