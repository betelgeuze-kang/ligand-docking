from __future__ import annotations

import numpy as np

from core.pocket_detection import detect_pocket_geometric


def test_geometric_pocket_grid_and_distance_working_set_are_bounded() -> None:
    axis = np.linspace(0.0, 1000.0, 200, dtype=np.float64)
    coords = np.stack([axis, np.mod(axis * 1.7, 700.0), np.mod(axis * 2.3, 500.0)], axis=1)

    result = detect_pocket_geometric(
        coords,
        grid_spacing_a=2.5,
        max_grid_points=512,
        distance_batch_size=32,
    )

    assert result["status"] == "pocket_ready"
    assert result["grid_point_count"] <= 512
    assert result["distance_batch_size"] == 32
    assert result["effective_grid_spacing_a"] > result["requested_grid_spacing_a"]
