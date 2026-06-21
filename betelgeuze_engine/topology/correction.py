"""Bounded topology correction features for scoring-stage refinement."""

from __future__ import annotations

from typing import Any

import numpy as np

TOPOLOGY_CORRECTION_CONTRACT = "topology_score_correction_bounded_v1"
DEFAULT_MAX_ABS_DELTA_SCORE = 1.0


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


def _clip_delta(delta: float, max_abs_delta_score: float) -> float:
    cap = float(max(max_abs_delta_score, 0.0))
    return float(np.clip(float(delta), -cap, cap))


def topo_correction_delta(features: np.ndarray, *, weights: np.ndarray | None = None) -> float:
    """Linear topology score correction before product cap application."""
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


def summarize_topo_correction(
    meta: dict[str, Any],
    score_2bead: float,
    score_4bead: float,
    *,
    max_abs_delta_score: float = DEFAULT_MAX_ABS_DELTA_SCORE,
) -> dict[str, Any]:
    site_count = int(meta.get("site_count", 0) or 0)
    distances_raw = meta.get("onsps_min_distances", meta.get("min_distances", []))
    angles_raw = meta.get("onsps_angle_scores", meta.get("angle_scores", []))
    if isinstance(distances_raw, (list, tuple)) and distances_raw:
        distances = [float(x) for x in distances_raw]
    else:
        distances = [2.5 + 0.1 * i for i in range(site_count)]
    if isinstance(angles_raw, (list, tuple)) and angles_raw:
        angles = [float(x) for x in angles_raw]
    else:
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
    raw_delta = topo_correction_delta(features)
    capped_delta = _clip_delta(raw_delta, max_abs_delta_score)
    within_cap = bool(abs(float(raw_delta)) <= float(max(max_abs_delta_score, 0.0)) + 1e-7)
    return {
        "topology_correction_contract": TOPOLOGY_CORRECTION_CONTRACT,
        "topology_correction_scope": "score_ranking_heuristic",
        "topology_correction_physical_force_claim": False,
        "topology_correction_policy_caps": {
            "max_abs_delta_score": float(max(max_abs_delta_score, 0.0)),
        },
        "topology_correction_raw_delta": float(raw_delta),
        "topology_correction_delta_within_cap": within_cap,
        "topology_correction_bounded": True,
        "topo_feature_dim": int(features.size),
        "topo_correction_delta": float(capped_delta),
        "delta_backmap": float(score_4bead - score_2bead),
    }
