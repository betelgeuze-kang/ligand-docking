#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

import torch

_THIS_FILE = Path(__file__).resolve()
ROOT = Path(os.environ.get("BETELGEUZE_REPO_ROOT") or (Path.cwd() if len(_THIS_FILE.parents) < 3 else _THIS_FILE.parents[2]))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from betelgeuze_engine.benchmark.runtime_scaling import _fixed_density_coords
from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.neighbor import (
    CellListNeighborProvider,
    NeighborPairs,
    NeighborProviderConfig,
    RustHipNeighborProvider,
)
from betelgeuze_engine.physics.terms.legacy_lj import LegacyLJTerm

DEFAULT_OUT_JSON = "runs/rust_hip_neighbor_provider_parity_current.json"
DEFAULT_OUT_MD = "runs/rust_hip_neighbor_provider_parity_current.md"
DEFAULT_ATOM_COUNTS = (216, 1000)

CLAIM_BOUNDARY = (
    "Rust/HIP neighbor-provider parity gate only. It compares the internal CPU cell-list "
    "provider with the real Rust/HIP provider on fixed-density coordinates and writes compact "
    "local evidence. It does not dispatch workflows, submit jobs, mutate billing, deploy, "
    "publish, upload, delete files, or promote product claims."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _parse_counts(value: str) -> list[int]:
    counts: list[int] = []
    for part in str(value or "").replace(";", ",").split(","):
        text = part.strip()
        if not text:
            continue
        counts.append(int(text))
    if not counts:
        raise argparse.ArgumentTypeError("atom count list must not be empty")
    if any(count < 4 for count in counts):
        raise argparse.ArgumentTypeError("atom counts must be >= 4")
    return counts


def pair_distance_map(pairs: NeighborPairs) -> dict[tuple[int, int, int], float]:
    """Return directed pair distances keyed by batch/source/destination."""

    if pairs.idx.ndim != 3 or pairs.dist.shape != pairs.idx.shape or pairs.mask.shape != pairs.idx.shape:
        raise ValueError("neighbor pairs must have matching [B, N, K] idx/dist/mask shapes")
    idx = pairs.idx.detach().cpu()
    dist = pairs.dist.detach().cpu()
    mask = pairs.mask.detach().cpu().bool()
    mapping: dict[tuple[int, int, int], float] = {}
    batch_count, atom_count, width = mask.shape
    for batch_idx in range(int(batch_count)):
        for source_idx in range(int(atom_count)):
            for slot in range(int(width)):
                if not bool(mask[batch_idx, source_idx, slot].item()):
                    continue
                target_idx = int(idx[batch_idx, source_idx, slot].item())
                mapping[(batch_idx, source_idx, target_idx)] = float(dist[batch_idx, source_idx, slot].item())
    return mapping


def compare_pair_distance_maps(
    reference: dict[tuple[int, int, int], float],
    candidate: dict[tuple[int, int, int], float],
    *,
    distance_abs_tol: float,
) -> dict[str, Any]:
    reference_keys = set(reference)
    candidate_keys = set(candidate)
    missing = sorted(reference_keys - candidate_keys)
    extra = sorted(candidate_keys - reference_keys)
    common = sorted(reference_keys & candidate_keys)
    deltas = [abs(float(reference[key]) - float(candidate[key])) for key in common]
    max_delta = max(deltas) if deltas else 0.0
    return {
        "ready": not missing and not extra and max_delta <= float(distance_abs_tol),
        "reference_pair_count": len(reference_keys),
        "candidate_pair_count": len(candidate_keys),
        "common_pair_count": len(common),
        "missing_pair_count": len(missing),
        "extra_pair_count": len(extra),
        "max_distance_abs_delta": float(max_delta),
        "distance_abs_tol": float(distance_abs_tol),
        "missing_pair_sample": [list(key) for key in missing[:10]],
        "extra_pair_sample": [list(key) for key in extra[:10]],
    }


def _state(coords: torch.Tensor) -> EngineState:
    atom_count = int(coords.shape[1])
    return EngineState(
        coords=coords,
        atom_types=torch.arange(atom_count, dtype=torch.long, device=coords.device) % 4,
        metadata={
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "hbond_evidence_status": "not_applicable",
            "claim_safe": True,
            "blocked_reason": "",
        },
    )


def _force_error(cpu_forces: torch.Tensor, hip_forces: torch.Tensor) -> float:
    if cpu_forces.shape != hip_forces.shape:
        return math.inf
    return float((cpu_forces.detach().cpu() - hip_forces.detach().cpu()).abs().max().item())


def _energy_error(cpu_energy: torch.Tensor, hip_energy: torch.Tensor) -> tuple[float, float]:
    cpu = cpu_energy.detach().cpu().to(dtype=torch.float64)
    hip = hip_energy.detach().cpu().to(dtype=torch.float64)
    if cpu.shape != hip.shape:
        return math.inf, math.inf
    abs_delta = float((cpu - hip).abs().max().item())
    denom = max(float(cpu.abs().max().item()), 1.0)
    return abs_delta, abs_delta / denom


def _blocked_payload(reason: str, *, atom_counts: list[int]) -> dict[str, Any]:
    return {
        "packet_type": "rust_hip_neighbor_provider_parity",
        "schema_version": "rust_hip_neighbor_provider_parity_v1",
        "summary": {
            "status": "blocked_rust_hip_neighbor_provider_parity",
            "ready": False,
            "atom_counts": list(atom_counts),
            "row_count": 0,
            "blocker_count": 1,
            "cuda_available": bool(torch.cuda.is_available()),
            "blocker": str(reason),
        },
        "rows": [],
        "blockers": [str(reason)],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(
    *,
    atom_counts: list[int],
    cutoff: float,
    skin: float,
    max_neighbor_count: int,
    max_atoms_per_cell: int,
    target_number_density: float,
    distance_abs_tol: float,
    energy_abs_tol: float,
    energy_rel_tol: float,
    force_abs_tol: float,
    require_cuda: bool = True,
) -> dict[str, Any]:
    counts = [int(value) for value in atom_counts]
    if not counts or any(value < 4 for value in counts):
        raise ValueError("atom_counts must contain values >= 4")
    if not bool(torch.cuda.is_available()):
        return _blocked_payload("cuda_unavailable", atom_counts=counts)

    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    term = LegacyLJTerm(sigma=1.0, epsilon=0.2, cutoff=float(cutoff), name="legacy_lj")
    for atom_count in counts:
        coords_cpu, box_size, spacing, observed_density = _fixed_density_coords(
            atom_count,
            target_number_density=float(target_number_density),
            dtype=torch.float32,
        )
        config = NeighborProviderConfig(
            cutoff=float(cutoff),
            skin=float(skin),
            max_neighbor_count=int(max_neighbor_count),
            max_atoms_per_cell=int(max_atoms_per_cell),
            box_size=float(box_size),
        )
        cpu_pairs = CellListNeighborProvider(config).build(coords_cpu, step=0)
        if bool(cpu_pairs.diagnostics.get("overflow") is True):
            blockers.append(f"cpu_neighbor_provider_overflow_n{atom_count}")
            continue

        coords_hip = coords_cpu.to(device=torch.device("cuda"))
        hip_pairs = RustHipNeighborProvider(config).build(coords_hip, step=0)
        hip_diagnostics = dict(hip_pairs.diagnostics)
        hip_blocked = bool(
            hip_diagnostics.get("overflow") is True
            or hip_diagnostics.get("status") != "neighbor_provider_ready"
            or hip_diagnostics.get("nxn_allocation_observed") is True
        )

        pair_compare = compare_pair_distance_maps(
            pair_distance_map(cpu_pairs),
            pair_distance_map(hip_pairs),
            distance_abs_tol=float(distance_abs_tol),
        )
        cpu_result = term.energy_forces(_state(coords_cpu), pairs=cpu_pairs)
        hip_result = term.energy_forces(_state(coords_hip), pairs=hip_pairs)
        energy_abs_error, energy_rel_error = _energy_error(cpu_result.energy, hip_result.energy)
        force_abs_error = _force_error(cpu_result.forces, hip_result.forces)
        row_ready = bool(
            not hip_blocked
            and pair_compare["ready"] is True
            and energy_abs_error <= float(energy_abs_tol)
            and energy_rel_error <= float(energy_rel_tol)
            and force_abs_error <= float(force_abs_tol)
        )
        row_blockers: list[str] = []
        if hip_blocked:
            row_blockers.append("rust_hip_neighbor_provider_blocked")
        if pair_compare["ready"] is not True:
            row_blockers.append("pair_set_or_distance_mismatch")
        if energy_abs_error > float(energy_abs_tol) or energy_rel_error > float(energy_rel_tol):
            row_blockers.append("energy_mismatch")
        if force_abs_error > float(force_abs_tol):
            row_blockers.append("force_mismatch")
        blockers.extend(f"n{atom_count}_{code}" for code in row_blockers)
        rows.append(
            {
                "atom_count": int(atom_count),
                "row_ready": row_ready,
                "box_size": float(box_size),
                "grid_spacing": float(spacing),
                "target_number_density": float(target_number_density),
                "observed_number_density": float(observed_density),
                "cpu_neighbor_source": str(cpu_pairs.source),
                "rust_hip_neighbor_source": str(hip_pairs.source),
                "cpu_pair_count": int(cpu_pairs.pair_count()),
                "rust_hip_pair_count": int(hip_pairs.pair_count()),
                "cpu_nxn_allocation_observed": bool(cpu_pairs.diagnostics.get("nxn_allocation_observed") is True),
                "rust_hip_nxn_allocation_observed": bool(
                    hip_diagnostics.get("nxn_allocation_observed") is True
                ),
                "rust_hip_provider_status": str(hip_diagnostics.get("status") or ""),
                "rust_hip_provider_overflow": bool(hip_diagnostics.get("overflow") is True),
                "rust_hip_backend_stats": dict(hip_diagnostics.get("backend_stats") or {}),
                "pair_compare": pair_compare,
                "energy_abs_error": float(energy_abs_error),
                "energy_rel_error": float(energy_rel_error),
                "force_abs_error": float(force_abs_error),
                "energy_abs_tol": float(energy_abs_tol),
                "energy_rel_tol": float(energy_rel_tol),
                "force_abs_tol": float(force_abs_tol),
                "blockers": row_blockers,
            }
        )

    blockers = list(dict.fromkeys(blockers))
    ready = bool(rows) and not blockers and len(rows) == len(counts)
    status = "rust_hip_neighbor_provider_parity_ready" if ready else "blocked_rust_hip_neighbor_provider_parity"
    return {
        "packet_type": "rust_hip_neighbor_provider_parity",
        "schema_version": "rust_hip_neighbor_provider_parity_v1",
        "summary": {
            "status": status,
            "ready": ready,
            "atom_counts": counts,
            "row_count": len(rows),
            "all_rows_ready": all(bool(row.get("row_ready") is True) for row in rows),
            "cuda_available": bool(torch.cuda.is_available()),
            "min_atom_count": min(counts),
            "max_atom_count": max(counts),
            "max_distance_abs_delta": max(
                [float(row["pair_compare"]["max_distance_abs_delta"]) for row in rows] or [math.inf]
            ),
            "max_energy_abs_error": max([float(row["energy_abs_error"]) for row in rows] or [math.inf]),
            "max_energy_rel_error": max([float(row["energy_rel_error"]) for row in rows] or [math.inf]),
            "max_force_abs_error": max([float(row["force_abs_error"]) for row in rows] or [math.inf]),
            "nxn_allocation_observed": any(
                bool(row.get("cpu_nxn_allocation_observed") is True)
                or bool(row.get("rust_hip_nxn_allocation_observed") is True)
                for row in rows
            ),
            "blocker_count": len(blockers),
        },
        "rows": rows,
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = payload["summary"]
    lines = [
        "# Rust/HIP Neighbor Provider Parity",
        "",
        f"- status: `{summary['status']}`",
        f"- ready: `{summary['ready']}`",
        f"- cuda_available: `{summary['cuda_available']}`",
        f"- atom_counts: `{','.join(str(v) for v in summary['atom_counts'])}`",
        f"- max_distance_abs_delta: `{summary.get('max_distance_abs_delta', 0.0):.8g}`",
        f"- max_energy_abs_error: `{summary.get('max_energy_abs_error', 0.0):.8g}`",
        f"- max_energy_rel_error: `{summary.get('max_energy_rel_error', 0.0):.8g}`",
        f"- max_force_abs_error: `{summary.get('max_force_abs_error', 0.0):.8g}`",
        f"- nxn_allocation_observed: `{summary.get('nxn_allocation_observed', False)}`",
        "",
        "## Rows",
        "",
    ]
    for row in payload.get("rows", []):
        pair_compare = row["pair_compare"]
        lines.extend(
            [
                f"### N={row['atom_count']}",
                "",
                f"- row_ready: `{row['row_ready']}`",
                f"- cpu_pair_count: `{row['cpu_pair_count']}`",
                f"- rust_hip_pair_count: `{row['rust_hip_pair_count']}`",
                f"- rust_hip_provider_status: `{row['rust_hip_provider_status']}`",
                f"- rust_hip_provider_overflow: `{row['rust_hip_provider_overflow']}`",
                f"- missing_pair_count: `{pair_compare['missing_pair_count']}`",
                f"- extra_pair_count: `{pair_compare['extra_pair_count']}`",
                f"- max_distance_abs_delta: `{pair_compare['max_distance_abs_delta']:.8g}`",
                f"- energy_abs_error: `{row['energy_abs_error']:.8g}`",
                f"- energy_rel_error: `{row['energy_rel_error']:.8g}`",
                f"- force_abs_error: `{row['force_abs_error']:.8g}`",
                "",
            ]
        )
    lines.extend(["## Blockers", ""])
    blockers = payload.get("blockers") or []
    lines.extend(f"- `{code}`" for code in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", payload["claim_boundary"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Rust/HIP neighbor-provider parity evidence gate.")
    parser.add_argument("--atom-counts", type=_parse_counts, default=list(DEFAULT_ATOM_COUNTS))
    parser.add_argument("--cutoff", type=float, default=3.1)
    parser.add_argument("--skin", type=float, default=0.0)
    parser.add_argument("--max-neighbor-count", type=int, default=16)
    parser.add_argument("--max-atoms-per-cell", type=int, default=16)
    parser.add_argument("--target-number-density", type=float, default=1.0 / 27.0)
    parser.add_argument("--distance-abs-tol", type=float, default=1e-4)
    parser.add_argument("--energy-abs-tol", type=float, default=1e-4)
    parser.add_argument("--energy-rel-tol", type=float, default=1e-5)
    parser.add_argument("--force-abs-tol", type=float, default=1e-3)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument(
        "--allow-unavailable",
        action="store_true",
        help="Write blocked evidence but return success when CUDA/Rust-HIP is unavailable.",
    )
    args = parser.parse_args(argv)
    payload = build_payload(
        atom_counts=list(args.atom_counts),
        cutoff=float(args.cutoff),
        skin=float(args.skin),
        max_neighbor_count=int(args.max_neighbor_count),
        max_atoms_per_cell=int(args.max_atoms_per_cell),
        target_number_density=float(args.target_number_density),
        distance_abs_tol=float(args.distance_abs_tol),
        energy_abs_tol=float(args.energy_abs_tol),
        energy_rel_tol=float(args.energy_rel_tol),
        force_abs_tol=float(args.force_abs_tol),
        require_cuda=not bool(args.allow_unavailable),
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    return 0 if payload["summary"]["ready"] or bool(args.allow_unavailable) else 1


if __name__ == "__main__":
    raise SystemExit(main())
