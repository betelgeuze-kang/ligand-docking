"""Lightweight topology correction features for scoring-stage refinement."""

from __future__ import annotations

from typing import Any

import numpy as np


def build_topo_feature_vector(
    *,
    onsps_min_distances: list[float] | np.ndarray,
    onsps_angle_scores: list[float] | np.ndarray,
    donor_acceptor_match: list[float] | np.ndarray,
    unsatisfied_donor_count: float,
    unsatisfied_acceptor_count: float,
    score_2bead: float,
    score_4bead: float,
) -> np.ndarray:
    dist = np.asarray(list(onsps_min_distances)[:4], dtype=np.float32)
    ang = np.asarray(list(onsps_angle_scores)[:4], dtype=np.float32)
    match = np.asarray(list(donor_acceptor_match)[:4], dtype=np.float32)
    if dist.size < 4:
        dist = np.pad(dist, (0, 4 - dist.size))
    if ang.size < 4:
        ang = np.pad(ang, (0, 4 - ang.size))
    if match.size < 4:
        match = np.pad(match, (0, 4 - match.size))
    delta = float(score_4bead) - float(score_2bead)
    return np.concatenate(
        [
            dist,
            ang,
            match,
            np.asarray(
                [
                    float(unsatisfied_donor_count),
                    float(unsatisfied_acceptor_count),
                    float(score_2bead),
                    float(score_4bead),
                    float(delta),
                    float(abs(delta)),
                ],
                dtype=np.float32,
            ),
        ]
    )


def topo_correction_delta(features: np.ndarray, *, weights: np.ndarray | None = None) -> float:
    """Linear topo corrector (fixed weights by default)."""
    vec = np.asarray(features, dtype=np.float32).reshape(-1)
    if weights is None:
        weights = np.asarray(
            [
                -0.05,
                -0.05,
                -0.04,
                -0.04,
                0.10,
                0.10,
                0.08,
                0.08,
                0.06,
                0.06,
                0.05,
                0.05,
                0.12,
                0.12,
                -0.20,
                -0.15,
                0.05,
                0.05,
                -0.25,
                -0.10,
            ],
            dtype=np.float32,
        )
    w = np.asarray(weights, dtype=np.float32).reshape(-1)
    n = min(int(vec.size), int(w.size))
    if n <= 0:
        return 0.0
    return float(np.dot(vec[:n], w[:n]))


def summarize_topo_correction(meta: dict[str, Any], score_2bead: float, score_4bead: float) -> dict[str, Any]:
    site_count = int(meta.get("site_count", 0) or 0)
    distances = [2.5 + 0.1 * i for i in range(site_count)]
    angles = [0.5 + 0.05 * i for i in range(site_count)]
    roles = list(meta.get("roles", []) or [])
    match = [1.0 if r in {"donor", "acceptor", "both"} else 0.0 for r in roles]
    unsat_donor = float(sum(1 for r in roles if r in {"donor", "both"}))
    unsat_acceptor = float(sum(1 for r in roles if r in {"acceptor", "both"}))
    features = build_topo_feature_vector(
        onsps_min_distances=distances,
        onsps_angle_scores=angles,
        donor_acceptor_match=match,
        unsatisfied_donor_count=unsat_donor,
        unsatisfied_acceptor_count=unsat_acceptor,
        score_2bead=float(score_2bead),
        score_4bead=float(score_4bead),
    )
    delta = topo_correction_delta(features)
    return {
        "topo_feature_dim": int(features.size),
        "topo_correction_delta": float(delta),
        "delta_backmap": float(score_4bead - score_2bead),
    }
