"""Independent 80-decimal scalar energy differentiation; no product imports."""

import json
import math
from pathlib import Path
import mpmath as mp
import numpy as np

mp.mp.dps = 80


def oracle(coords, k=17.0):
    # Preserve arbitrary-precision perturbations used by mp.diff.
    vals = [mp.mpf(float(x)) for x in np.asarray(coords).ravel()]

    def energy(*x):
        u = [x[j] - x[3 + j] for j in range(3)]
        v = [x[6 + j] - x[3 + j] for j in range(3)]
        cross = [
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        ]
        d = mp.atan2(
            mp.sqrt(sum(c * c for c in cross)), -sum(a * b for a, b in zip(u, v))
        )
        return mp.mpf(k) * d * d / 2

    f = []
    for j in range(9):
        order = [0] * 9
        order[j] = 1
        f.append(float(-mp.diff(energy, tuple(vals), tuple(order))))
    return float(energy(*vals)), np.array(f).reshape(3, 3).tolist()


if __name__ == "__main__":
    cases = []
    rng = np.random.default_rng(128731)
    rotations = [np.eye(3)]
    for _ in range(3):
        q, r = np.linalg.qr(rng.normal(size=(3, 3)))
        q *= np.sign(np.linalg.det(q))
        rotations.append(q)
    for eps in [0.0, 1e-14, 1e-12, 1e-10, 1e-8, 1e-6, 1e-4, 1e-2, 0.2, 1.0]:
        for plane in range(12):
            phi = 2 * math.pi * plane / 12
            xyz = np.array(
                [
                    [1.7, 0, 0],
                    [0, 0, 0],
                    [
                        -0.61 * math.cos(eps),
                        0.61 * math.sin(eps) * math.cos(phi),
                        0.61 * math.sin(eps) * math.sin(phi),
                    ],
                ]
            )
            for rotation_index, q in enumerate(rotations):
                coords = xyz @ q.T
                # Keep tiny endpoint approaches observable, add translations to non-tiny cases.
                if eps >= 1e-6:
                    coords += np.array([0.32, -0.77, 1.12])
                energy, forces = oracle(coords)
                cases.append(
                    dict(
                        eps=eps,
                        plane=plane,
                        rotation=rotation_index,
                        k=17.0,
                        coords=coords.tolist(),
                        energy=energy,
                        forces=forces,
                    )
                )
    switch = 2 * math.asin(0.01 / 2)
    for eps in [
        switch * (1 + d) for d in [-1e-6, -1e-10, -1e-14, 0, 1e-14, 1e-10, 1e-6]
    ] + [math.pi - 1e-3, math.pi - 1e-6, math.pi - 1e-10]:
        coords = np.array(
            [
                [1.7, 0, 0],
                [0, 0, 0],
                [
                    -0.61 * math.cos(eps),
                    0.61 * math.sin(eps) * 0.6,
                    0.61 * math.sin(eps) * 0.8,
                ],
            ]
        )
        energy, forces = oracle(coords)
        cases.append(
            dict(
                eps=eps,
                plane="switch_or_parallel",
                rotation=0,
                k=17.0,
                coords=coords.tolist(),
                energy=energy,
                forces=forces,
            )
        )
    path = (
        Path(__file__).resolve().parents[1]
        / "tests/fixtures/linear_angle_independent_oracle.json"
    )
    path.write_text(
        json.dumps(
            dict(
                precision_digits=80,
                oracle="mpmath independent scalar potential coordinate derivatives",
                cases=cases,
            ),
            indent=2,
        )
        + "\n"
    )
    print(f"{len(cases)} independent reference cases written to {path}")
