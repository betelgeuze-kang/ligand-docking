#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from betelgeuze_engine.benchmark import run_runtime_scaling_benchmark, write_runtime_scaling_svg

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/runtime_neighbor_release_scaling_current.json"
DEFAULT_OUT_MD = "runs/runtime_neighbor_release_scaling_current.md"
DEFAULT_OUT_SVG = "runs/runtime_neighbor_release_scaling_current.svg"
DEFAULT_RELEASE_ATOM_COUNTS = (1000, 2000, 4000, 8000)

CLAIM_BOUNDARY = (
    "Runtime neighbor release scaling gate only. It runs the internal fixed-density cell-list "
    "product forcefield probe, writes compact JSON/MD/SVG evidence, and does not dispatch workflows, "
    "submit jobs, mutate billing, deploy, publish, upload, delete files, or promote product claims."
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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    s = payload["summary"]
    lines = [
        "# Runtime Neighbor Release Scaling",
        "",
        f"- status: `{s['status']}`",
        f"- ready: `{s['ready']}`",
        f"- release_atom_counts_ready: `{s['release_atom_counts_ready']}`",
        f"- atom_counts: `{','.join(str(v) for v in s['atom_counts'])}`",
        f"- release_atom_counts: `{','.join(str(v) for v in s['release_atom_counts'])}`",
        f"- neighbor_pair_count_slope: `{s['neighbor_pair_count_slope']:.6f}`",
        f"- neighbor_pair_count_r2: `{s['neighbor_pair_count_r2']:.6f}`",
        f"- duration_slope: `{s['duration_slope']:.6f}`",
        f"- duration_r2: `{s['duration_r2']:.6f}`",
        f"- max_memory_peak_mb_per_atom: `{s['max_memory_peak_mb_per_atom']:.6f}`",
        f"- total_rebuild_count: `{s['total_rebuild_count']}`",
        f"- total_rebuild_duration_sec: `{s['total_rebuild_duration_sec']:.6f}`",
        f"- nxn_allocation_observed: `{s['nxn_allocation_observed']}`",
        f"- fixed_density_ready: `{s['fixed_density_ready']}`",
        f"- max_density_relative_error: `{s['max_density_relative_error']:.12g}`",
        "",
        "## Rows",
        "",
    ]
    for row in payload["rows"]:
        lines.extend(
            [
                f"### N={row['atom_count']}",
                "",
                f"- row_ready: `{row['row_ready']}`",
                f"- pair_count: `{row['neighbor_pair_count']}`",
                f"- duration_per_repeat_sec: `{row['duration_per_repeat_sec']:.6f}`",
                f"- memory_peak_mb_per_atom: `{row['memory_peak_mb_per_atom']:.6f}`",
                f"- rebuild_count: `{row.get('rebuild_count', 0)}`",
                f"- provider_overflow: `{row['neighbor_provider_overflow']}`",
                f"- nxn_allocation_observed: `{row['nxn_allocation_observed']}`",
                "",
            ]
        )
    lines.extend(["## Blockers", ""])
    blockers = payload.get("blockers") or []
    lines.extend(f"- `{code}`" for code in blockers) if blockers else lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", payload["claim_boundary"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _blockers(summary: dict[str, Any], *, require_release_counts: bool) -> list[str]:
    blockers: list[str] = []
    if summary.get("ready") is not True:
        blockers.append("runtime_neighbor_scaling_not_ready")
    if summary.get("fixed_density_ready") is not True:
        blockers.append("fixed_density_not_ready")
    if summary.get("nxn_allocation_observed") is not False:
        blockers.append("nxn_allocation_observed")
    if summary.get("memory_per_atom_linear_ready") is not True:
        blockers.append("memory_per_atom_linear_not_ready")
    if require_release_counts and summary.get("release_atom_counts_ready") is not True:
        blockers.append("release_atom_counts_not_covered")
    if float(summary.get("neighbor_pair_count_slope") or 0.0) < 0.85:
        blockers.append("neighbor_pair_count_slope_low")
    if float(summary.get("neighbor_pair_count_slope") or 0.0) > 1.15:
        blockers.append("neighbor_pair_count_slope_high")
    if float(summary.get("neighbor_pair_count_r2") or 0.0) < 0.98:
        blockers.append("neighbor_pair_count_r2_low")
    return list(dict.fromkeys(blockers))


def build_payload(
    *,
    atom_counts: list[int],
    release_atom_counts: list[int],
    repeats: int,
    warmup_repeats: int,
    cutoff: float,
    skin: float,
    max_neighbor_count: int,
    max_atoms_per_cell: int,
    rebuild_stride: int,
    target_number_density: float,
    out_svg: str | Path,
    require_release_counts: bool,
) -> dict[str, Any]:
    result = run_runtime_scaling_benchmark(
        atom_counts=atom_counts,
        release_atom_counts=release_atom_counts,
        repeats=repeats,
        warmup_repeats=warmup_repeats,
        cutoff=cutoff,
        skin=skin,
        max_neighbor_count=max_neighbor_count,
        max_atoms_per_cell=max_atoms_per_cell,
        rebuild_stride=rebuild_stride,
        target_number_density=target_number_density,
    )
    scaling = result.to_dict()
    plot = write_runtime_scaling_svg(scaling, _resolve(out_svg), title="AI-MD Runtime Neighbor Release Scaling")
    scaling.update(plot)
    blockers = _blockers(scaling, require_release_counts=require_release_counts)
    status = "runtime_neighbor_release_scaling_ready" if not blockers else "blocked_runtime_neighbor_release_scaling"
    summary = {
        "status": status,
        "ready": not blockers,
        "atom_counts": list(scaling["atom_counts"]),
        "release_atom_counts": list(scaling["release_atom_counts"]),
        "release_atom_counts_ready": bool(scaling["release_atom_counts_ready"]),
        "fixed_density_ready": bool(scaling["fixed_density_ready"]),
        "target_number_density": float(scaling["target_number_density"]),
        "max_density_relative_error": float(scaling["max_density_relative_error"]),
        "nxn_allocation_observed": bool(scaling["nxn_allocation_observed"]),
        "memory_per_atom_linear_ready": bool(scaling["memory_per_atom_linear_ready"]),
        "max_memory_peak_mb_per_atom": float(scaling["max_memory_peak_mb_per_atom"]),
        "neighbor_pair_count_slope": float(scaling["neighbor_pair_count_slope"]),
        "neighbor_pair_count_r2": float(scaling["neighbor_pair_count_r2"]),
        "duration_slope": float(scaling["duration_slope"]),
        "duration_r2": float(scaling["duration_r2"]),
        "total_rebuild_count": int(scaling["total_rebuild_count"]),
        "total_rebuild_duration_sec": float(scaling["total_rebuild_duration_sec"]),
        "plot_path": str(scaling["plot_path"]),
        "plot_ready": bool(scaling["plot_ready"]),
        "blocker_count": len(blockers),
    }
    return {
        "packet_type": "runtime_neighbor_release_scaling",
        "schema_version": "runtime_neighbor_release_scaling_v1",
        "summary": summary,
        "rows": list(scaling["rows"]),
        "runtime_scaling": scaling,
        "blockers": blockers,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run fixed-density release-scale neighbor scaling gate.")
    parser.add_argument("--atom-counts", type=_parse_counts, default=list(DEFAULT_RELEASE_ATOM_COUNTS))
    parser.add_argument("--release-atom-counts", type=_parse_counts, default=list(DEFAULT_RELEASE_ATOM_COUNTS))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup-repeats", type=int, default=1)
    parser.add_argument("--cutoff", type=float, default=3.1)
    parser.add_argument("--skin", type=float, default=0.0)
    parser.add_argument("--max-neighbor-count", type=int, default=16)
    parser.add_argument("--max-atoms-per-cell", type=int, default=16)
    parser.add_argument("--rebuild-stride", type=int, default=3)
    parser.add_argument("--target-number-density", type=float, default=1.0 / 27.0)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-svg", default=DEFAULT_OUT_SVG)
    parser.add_argument(
        "--allow-partial-release-counts",
        action="store_true",
        help="Write blocked evidence but return success even when the configured release counts are not covered.",
    )
    args = parser.parse_args(argv)
    payload = build_payload(
        atom_counts=list(args.atom_counts),
        release_atom_counts=list(args.release_atom_counts),
        repeats=int(args.repeats),
        warmup_repeats=int(args.warmup_repeats),
        cutoff=float(args.cutoff),
        skin=float(args.skin),
        max_neighbor_count=int(args.max_neighbor_count),
        max_atoms_per_cell=int(args.max_atoms_per_cell),
        rebuild_stride=int(args.rebuild_stride),
        target_number_density=float(args.target_number_density),
        out_svg=args.out_svg,
        require_release_counts=not bool(args.allow_partial_release_counts),
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    return 0 if payload["summary"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
