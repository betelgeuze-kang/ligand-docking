from __future__ import annotations

from dataclasses import dataclass
from html import escape
import math
from pathlib import Path
import time
from typing import Any, Iterable

import torch

from betelgeuze_engine.contracts.result import TermResult
from betelgeuze_engine.contracts.state import EngineState
from betelgeuze_engine.physics.forcefield import ProductForceField
from betelgeuze_engine.physics.neighbor import NeighborPairs
from betelgeuze_engine.physics.term_claim_metadata import term_claim_metadata


@dataclass(frozen=True)
class RuntimeScalingResult:
    """Compact evidence packet for capped-neighbor product forcefield scaling."""

    ready: bool
    status: str
    rows: list[dict[str, Any]]
    atom_counts: list[int]
    neighbor_pair_counts: list[int]
    duration_slope: float
    duration_r2: float
    neighbor_pair_count_slope: float
    neighbor_pair_count_r2: float
    max_neighbor_count: int
    forcefield_contract_ready: bool
    neighbor_cap_scaling_ready: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "status": self.status,
            "rows": list(self.rows),
            "atom_counts": list(self.atom_counts),
            "neighbor_pair_counts": list(self.neighbor_pair_counts),
            "duration_slope": float(self.duration_slope),
            "duration_r2": float(self.duration_r2),
            "neighbor_pair_count_slope": float(self.neighbor_pair_count_slope),
            "neighbor_pair_count_r2": float(self.neighbor_pair_count_r2),
            "max_neighbor_count": int(self.max_neighbor_count),
            "forcefield_contract_ready": bool(self.forcefield_contract_ready),
            "neighbor_cap_scaling_ready": bool(self.neighbor_cap_scaling_ready),
        }


class _LinearProbeTerm:
    name = "runtime_scaling_linear_probe"

    def energy_forces(self, state: EngineState, pairs: NeighborPairs | None = None) -> TermResult:
        if pairs is None:
            raise ValueError("runtime scaling probe requires provided neighbor pairs")
        coords = state.coords.detach()
        mask = pairs.mask.to(dtype=coords.dtype, device=coords.device)
        weights = mask.sum(dim=-1).clamp_min(1.0).unsqueeze(-1)
        centered = coords - coords.mean(dim=1, keepdim=True)
        energy = 0.5 * (centered.pow(2) * weights).sum(dim=(1, 2)) / coords.shape[1]
        forces = -(centered * weights) / coords.shape[1]
        active_pair_count = int(pairs.mask.sum().detach().cpu().item())
        metadata = term_claim_metadata(
            state=state,
            term_name=self.name,
            status="pass",
            extras={
                "force_term_active_pair_count": active_pair_count,
                "runtime_scaling_probe": True,
            },
        )
        return TermResult(
            energy=energy,
            forces=forces,
            diagnostics={
                "term": self.name,
                "status": "pass",
                "active_pair_count": active_pair_count,
                "runtime_scaling_probe": True,
            },
            claim_metadata=metadata,
        )


def build_capped_neighbor_pairs(coords: torch.Tensor, *, max_neighbor_count: int = 4) -> NeighborPairs:
    if coords.ndim != 3 or coords.shape[-1] != 3:
        raise ValueError("coords must have shape [B, N, 3]")
    if int(max_neighbor_count) < 1:
        raise ValueError("max_neighbor_count must be positive")
    batch, atom_count, _ = coords.shape
    device = coords.device
    idx = torch.arange(atom_count, device=device).view(1, 1, atom_count).expand(batch, atom_count, atom_count)
    diff = coords.unsqueeze(2) - coords.unsqueeze(1)
    dist = diff.norm(dim=-1)
    mask = torch.zeros((batch, atom_count, atom_count), dtype=torch.bool, device=device)
    half_window = max(1, int(max_neighbor_count) // 2)
    for offset in range(1, half_window + 1):
        src = torch.arange(0, atom_count - offset, device=device)
        dst = src + offset
        mask[:, src, dst] = True
        mask[:, dst, src] = True
    return NeighborPairs(idx=idx, dist=dist, mask=mask)


def _fit_log_slope(x_values: Iterable[float], y_values: Iterable[float]) -> tuple[float, float]:
    xs = [float(v) for v in x_values]
    ys = [float(v) for v in y_values]
    clean = [
        (math.log(x), math.log(y))
        for x, y in zip(xs, ys)
        if math.isfinite(x) and math.isfinite(y) and x > 0.0 and y > 0.0
    ]
    if len(clean) < 2:
        return 0.0, 0.0
    log_x = torch.tensor([row[0] for row in clean], dtype=torch.float64)
    log_y = torch.tensor([row[1] for row in clean], dtype=torch.float64)
    x_centered = log_x - log_x.mean()
    y_centered = log_y - log_y.mean()
    denom = float((x_centered.pow(2)).sum().item())
    if denom <= 0.0:
        return 0.0, 0.0
    slope = float((x_centered * y_centered).sum().item() / denom)
    intercept = float(log_y.mean().item() - slope * log_x.mean().item())
    pred = slope * log_x + intercept
    ss_res = float((log_y - pred).pow(2).sum().item())
    ss_tot = float((log_y - log_y.mean()).pow(2).sum().item())
    r2 = 1.0 if ss_tot <= 0.0 else max(0.0, 1.0 - (ss_res / ss_tot))
    return slope, r2


def _plot_points(
    x_values: list[float],
    y_values: list[float],
    *,
    x0: float,
    y0: float,
    width: float,
    height: float,
) -> list[tuple[float, float]]:
    clean_x = [float(v) for v in x_values if math.isfinite(float(v)) and float(v) > 0.0]
    clean_y = [float(v) for v in y_values if math.isfinite(float(v)) and float(v) > 0.0]
    if not clean_x or not clean_y:
        return []
    min_x, max_x = min(clean_x), max(clean_x)
    min_y, max_y = min(clean_y), max(clean_y)
    log_min_x, log_max_x = math.log(min_x), math.log(max_x)
    log_min_y, log_max_y = math.log(min_y), math.log(max_y)
    if log_max_x <= log_min_x:
        log_max_x = log_min_x + 1.0
    if log_max_y <= log_min_y:
        log_max_y = log_min_y + 1.0
    points: list[tuple[float, float]] = []
    for x, y in zip(x_values, y_values):
        if not (math.isfinite(x) and math.isfinite(y) and x > 0.0 and y > 0.0):
            continue
        px = x0 + ((math.log(x) - log_min_x) / (log_max_x - log_min_x)) * width
        py = y0 + height - ((math.log(y) - log_min_y) / (log_max_y - log_min_y)) * height
        points.append((px, py))
    return points


def write_runtime_scaling_svg(
    result: RuntimeScalingResult | dict[str, Any],
    path: str | Path,
    *,
    title: str = "AI-MD Runtime Neighbor-Cap Scaling",
) -> dict[str, Any]:
    """Write a dependency-free SVG plot for the runtime scaling evidence bundle."""
    packet = result.to_dict() if isinstance(result, RuntimeScalingResult) else dict(result)
    rows = [row for row in packet.get("rows", []) if isinstance(row, dict)]
    atom_counts = [float(row.get("atom_count") or 0.0) for row in rows]
    pair_counts = [float(row.get("neighbor_pair_count") or 0.0) for row in rows]
    durations = [float(row.get("duration_per_repeat_sec") or 0.0) for row in rows]
    if len(rows) < 3:
        raise ValueError("runtime scaling SVG requires at least three rows")

    left = _plot_points(atom_counts, pair_counts, x0=76.0, y0=96.0, width=300.0, height=210.0)
    right = _plot_points(atom_counts, durations, x0=466.0, y0=96.0, width=300.0, height=210.0)
    if len(left) < 3 or len(right) < 3:
        raise ValueError("runtime scaling SVG requires finite positive plot values")

    def polyline(points: list[tuple[float, float]]) -> str:
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)

    def circles(points: list[tuple[float, float]], color: str) -> str:
        return "\n".join(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" fill="{color}" />'
            for x, y in points
        )

    safe_title = escape(str(title))
    pair_slope = float(packet.get("neighbor_pair_count_slope") or 0.0)
    pair_r2 = float(packet.get("neighbor_pair_count_r2") or 0.0)
    duration_slope = float(packet.get("duration_slope") or 0.0)
    duration_r2 = float(packet.get("duration_r2") or 0.0)
    ready = bool(packet.get("ready") is True)
    claim_boundary = (
        "Pair-count scaling is the gated evidence; duration trend is advisory microbenchmark telemetry."
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="840" height="420" viewBox="0 0 840 420" role="img" aria-label="{safe_title}">
<rect width="840" height="420" fill="#ffffff"/>
<text x="32" y="34" font-family="Arial, sans-serif" font-size="20" font-weight="700" fill="#111827">{safe_title}</text>
<text x="32" y="58" font-family="Arial, sans-serif" font-size="12" fill="#374151">status={escape(str(packet.get("status") or ""))}; ready={str(ready).lower()}</text>
<g transform="translate(0,0)">
  <rect x="64" y="82" width="326" height="250" fill="#f8fafc" stroke="#cbd5e1"/>
  <line x1="76" y1="306" x2="376" y2="306" stroke="#334155"/>
  <line x1="76" y1="96" x2="76" y2="306" stroke="#334155"/>
  <text x="88" y="112" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="#0f172a">Capped neighbor pairs</text>
  <text x="88" y="130" font-family="Arial, sans-serif" font-size="12" fill="#475569">slope={pair_slope:.3f}; R2={pair_r2:.3f}</text>
  <polyline points="{polyline(left)}" fill="none" stroke="#2563eb" stroke-width="2.5"/>
  {circles(left, "#2563eb")}
  <text x="170" y="326" font-family="Arial, sans-serif" font-size="11" fill="#475569">atom count (log scale)</text>
  <text x="12" y="215" transform="rotate(-90 12 215)" font-family="Arial, sans-serif" font-size="11" fill="#475569">neighbor pair count</text>
</g>
<g transform="translate(0,0)">
  <rect x="454" y="82" width="326" height="250" fill="#f8fafc" stroke="#cbd5e1"/>
  <line x1="466" y1="306" x2="766" y2="306" stroke="#334155"/>
  <line x1="466" y1="96" x2="466" y2="306" stroke="#334155"/>
  <text x="478" y="112" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="#0f172a">Duration per repeat</text>
  <text x="478" y="130" font-family="Arial, sans-serif" font-size="12" fill="#475569">slope={duration_slope:.3f}; R2={duration_r2:.3f}; advisory</text>
  <polyline points="{polyline(right)}" fill="none" stroke="#059669" stroke-width="2.5"/>
  {circles(right, "#059669")}
  <text x="560" y="326" font-family="Arial, sans-serif" font-size="11" fill="#475569">atom count (log scale)</text>
  <text x="404" y="218" transform="rotate(-90 404 218)" font-family="Arial, sans-serif" font-size="11" fill="#475569">seconds / repeat</text>
</g>
<text x="32" y="370" font-family="Arial, sans-serif" font-size="12" fill="#374151">{escape(claim_boundary)}</text>
<text x="32" y="390" font-family="Arial, sans-serif" font-size="11" fill="#64748b">atom_counts={escape(','.join(str(int(v)) for v in atom_counts))}; max_neighbor_count={int(packet.get("max_neighbor_count") or 0)}</text>
</svg>
"""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    return {
        "plot_path": str(out),
        "plot_format": "svg",
        "plot_ready": out.exists() and out.stat().st_size > 0,
        "plot_role": "runtime_neighbor_cap_scaling_plot",
        "plot_claim_boundary": claim_boundary,
    }


def _coords(atom_count: int, *, dtype: torch.dtype = torch.float64) -> torch.Tensor:
    axis = torch.arange(atom_count, dtype=dtype).view(1, atom_count, 1)
    return torch.cat(
        [
            axis * 1.5,
            torch.sin(axis * 0.17),
            torch.cos(axis * 0.11),
        ],
        dim=-1,
    )


def run_runtime_scaling_benchmark(
    *,
    atom_counts: Iterable[int] = (8, 16, 32, 64, 128),
    max_neighbor_count: int = 4,
    repeats: int = 3,
) -> RuntimeScalingResult:
    counts = [int(value) for value in atom_counts]
    if not counts or any(value < 4 for value in counts):
        raise ValueError("atom_counts must contain values >= 4")
    if int(repeats) < 1:
        raise ValueError("repeats must be positive")

    forcefield = ProductForceField(terms=[_LinearProbeTerm()], name="runtime_scaling_probe_forcefield")
    rows: list[dict[str, Any]] = []
    forcefield_contract_ready = True
    for atom_count in counts:
        coords = _coords(atom_count)
        atom_types = torch.arange(atom_count, dtype=torch.long) % 4
        pairs = build_capped_neighbor_pairs(coords, max_neighbor_count=max_neighbor_count)
        state = EngineState(
            coords=coords,
            atom_types=atom_types,
            metadata={
                "topology_fidelity": "sequence_mapped",
                "ligand_topology_valid": True,
                "hbond_evidence_status": "not_applicable",
                "claim_safe": True,
                "blocked_reason": "",
            },
        )
        start = time.perf_counter()
        last_result = None
        for _ in range(int(repeats)):
            last_result = forcefield.energy_forces(state, pairs=pairs)
        duration = float(time.perf_counter() - start)
        result = last_result
        if result is None:
            forcefield_contract_ready = False
            continue
        pair_count = int(pairs.mask.sum().detach().cpu().item())
        row_ready = bool(
            result.claim_metadata.get("claim_safe") is True
            and result.diagnostics.get("neighbor_pairs_provided") is True
            and result.diagnostics.get("neighbor_source") == "provided"
            and torch.isfinite(result.energy).all().item()
            and torch.isfinite(result.forces).all().item()
            and pair_count <= int(max_neighbor_count) * atom_count
        )
        forcefield_contract_ready = forcefield_contract_ready and row_ready
        rows.append(
            {
                "atom_count": atom_count,
                "repeat_count": int(repeats),
                "duration_sec": duration,
                "duration_per_repeat_sec": duration / float(repeats),
                "neighbor_pair_count": pair_count,
                "max_neighbor_count": int(max_neighbor_count),
                "neighbor_pairs_provided": result.diagnostics.get("neighbor_pairs_provided") is True,
                "neighbor_source": str(result.diagnostics.get("neighbor_source") or ""),
                "energy_finite": bool(torch.isfinite(result.energy).all().item()),
                "forces_finite": bool(torch.isfinite(result.forces).all().item()),
                "claim_safe": result.claim_metadata.get("claim_safe") is True,
                "row_ready": row_ready,
            }
        )

    pair_counts = [int(row["neighbor_pair_count"]) for row in rows]
    durations = [float(row["duration_per_repeat_sec"]) for row in rows]
    pair_slope, pair_r2 = _fit_log_slope(counts[: len(pair_counts)], pair_counts)
    duration_slope, duration_r2 = _fit_log_slope(counts[: len(durations)], durations)
    neighbor_cap_scaling_ready = bool(
        len(rows) == len(counts)
        and all(row.get("row_ready") is True for row in rows)
        and 0.85 <= pair_slope <= 1.15
        and pair_r2 >= 0.98
    )
    ready = bool(forcefield_contract_ready and neighbor_cap_scaling_ready)
    return RuntimeScalingResult(
        ready=ready,
        status="runtime_neighbor_cap_scaling_ready" if ready else "blocked_runtime_neighbor_cap_scaling",
        rows=rows,
        atom_counts=counts,
        neighbor_pair_counts=pair_counts,
        duration_slope=duration_slope,
        duration_r2=duration_r2,
        neighbor_pair_count_slope=pair_slope,
        neighbor_pair_count_r2=pair_r2,
        max_neighbor_count=int(max_neighbor_count),
        forcefield_contract_ready=forcefield_contract_ready,
        neighbor_cap_scaling_ready=neighbor_cap_scaling_ready,
    )
