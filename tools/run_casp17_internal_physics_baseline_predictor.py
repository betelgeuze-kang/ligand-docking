#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_OUT_JSON = "runs/casp17_internal_physics_baseline_predictor_current.json"
DEFAULT_OUT_CSV = "runs/casp17_internal_physics_baseline_predictor_current.csv"
DEFAULT_OUT_MD = "runs/casp17_internal_physics_baseline_predictor_current.md"

AA1_TO_3 = {
    "A": "ALA",
    "R": "ARG",
    "N": "ASN",
    "D": "ASP",
    "C": "CYS",
    "Q": "GLN",
    "E": "GLU",
    "G": "GLY",
    "H": "HIS",
    "I": "ILE",
    "L": "LEU",
    "K": "LYS",
    "M": "MET",
    "F": "PHE",
    "P": "PRO",
    "S": "SER",
    "T": "THR",
    "W": "TRP",
    "Y": "TYR",
    "V": "VAL",
    "B": "ASX",
    "Z": "GLX",
    "X": "UNK",
    "U": "CYS",
    "O": "LYS",
}
AA3_TO_1 = {value: key for key, value in AA1_TO_3.items() if key in "ARNDCQEGHILKMFPSTWYV"}
AA3_TO_1.update({"ASX": "B", "GLX": "Z", "UNK": "X"})

HYDROPHOBIC = set("AVILMFWYCP")
POSITIVE = set("KRH")
NEGATIVE = set("DE")
AROMATIC = set("FYW H".replace(" ", ""))
POLAR = set("STNQCYH")
HELIX_FAVOR = set("ALEKMQRIH")
STRAND_FAVOR = set("VIFYWTC")
BREAKERS = set("PG")
CHAIN_IDS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def _sequence_composition(sequence: str) -> dict[str, float]:
    n_res = max(len(sequence), 1)
    positive = sum(1 for aa in sequence if aa in POSITIVE)
    negative = sum(1 for aa in sequence if aa in NEGATIVE)
    return {
        "hydrophobic_fraction": sum(1 for aa in sequence if aa in HYDROPHOBIC) / n_res,
        "charged_fraction": (positive + negative) / n_res,
        "net_charge_fraction": abs(positive - negative) / n_res,
        "breaker_fraction": sum(1 for aa in sequence if aa in BREAKERS) / n_res,
    }


def sequence_compaction_scale(sequence: str) -> float:
    comp = _sequence_composition(sequence)
    scale = (
        1.0
        - 0.24 * (comp["hydrophobic_fraction"] - 0.35)
        + 0.38 * comp["net_charge_fraction"]
        + 0.12 * comp["charged_fraction"]
        + 0.18 * comp["breaker_fraction"]
    )
    return max(0.78, min(1.34, float(scale)))


def sequence_target_rg(sequence: str) -> float:
    n_res = max(len(sequence), 1)
    base = max(7.5, 2.10 * (float(n_res) ** 0.38))
    return base * sequence_compaction_scale(sequence)


@dataclass(frozen=True)
class FastaChain:
    header: str
    chain_id: str
    sequence: str


@dataclass
class ChainResult:
    chain: FastaChain
    coords: torch.Tensor
    confidence: torch.Tensor
    energy: float
    ensemble_size: int
    secondary: str
    metrics: dict[str, Any]
    ranked_coords: list[torch.Tensor] = field(default_factory=list)
    ranked_confidences: list[torch.Tensor] = field(default_factory=list)
    ranked_energies: list[float] = field(default_factory=list)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["target_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Internal Physics Baseline Predictor",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- target: `{summary['target_id']}`",
        f"- predictor status: `{summary['predictor_status']}`",
        f"- backend kind: `{summary['backend_kind']}`",
        f"- device: `{summary['device']}`",
        f"- GPU detected: `{summary['gpu_detected']}`",
        f"- chains / residues: `{summary['chain_count']}/{summary['residue_count']}`",
        f"- ensemble / steps: `{summary['ensemble_size']}/{summary['steps']}`",
        f"- raw PDB: `{summary['raw_pdb']}`",
        f"- runtime JSON: `{summary['runtime_json']}`",
        f"- metrics JSON: `{summary['metrics_json']}`",
        "",
        "## Blockers",
        "",
    ]
    blockers = payload.get("blockers", [])
    if blockers:
        lines.extend(f"- `{blocker['code']}`: {blocker['reason']}" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def parse_fasta(path_like: str | Path) -> list[FastaChain]:
    path = _resolve(path_like)
    chains: list[tuple[str, list[str]]] = []
    header = ""
    seq_parts: list[str] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header or seq_parts:
                chains.append((header, seq_parts))
            header = line[1:].strip()
            seq_parts = []
            continue
        seq_parts.append(re.sub(r"[^A-Za-z]", "", line).upper())
    if header or seq_parts:
        chains.append((header, seq_parts))
    parsed: list[FastaChain] = []
    for index, (chain_header, parts) in enumerate(chains):
        if index >= len(CHAIN_IDS):
            raise ValueError(f"too many FASTA chains for one-character PDB chain IDs: {len(chains)}")
        sequence = "".join(parts)
        if not sequence:
            continue
        normalized = "".join(char if char in AA1_TO_3 else "X" for char in sequence)
        parsed.append(FastaChain(header=chain_header or f"chain_{index + 1}", chain_id=CHAIN_IDS[index], sequence=normalized))
    if not parsed:
        raise ValueError(f"no FASTA sequence entries found: {_artifact(path)}")
    return parsed


def infer_secondary_structure(sequence: str) -> str:
    calls: list[str] = []
    for index, residue in enumerate(sequence):
        left = max(0, index - 3)
        right = min(len(sequence), index + 4)
        window = sequence[left:right]
        den = max(len(window), 1)
        breaker_fraction = sum(1 for aa in window if aa in BREAKERS) / den
        helix_score = sum(1 for aa in window if aa in HELIX_FAVOR) / den - 0.75 * breaker_fraction
        strand_score = sum(1 for aa in window if aa in STRAND_FAVOR) / den - 0.50 * breaker_fraction
        if residue in BREAKERS:
            calls.append("C")
        elif helix_score >= 0.43 and helix_score >= strand_score:
            calls.append("H")
        elif strand_score >= 0.38:
            calls.append("E")
        else:
            calls.append("C")

    smoothed = calls[:]
    for index in range(1, len(calls) - 1):
        if calls[index - 1] == calls[index + 1] != calls[index]:
            smoothed[index] = calls[index - 1]
    return "".join(smoothed)


def _unit(value: torch.Tensor, fallback: torch.Tensor) -> torch.Tensor:
    norm = torch.linalg.norm(value)
    if float(norm.item()) < 1e-6:
        return fallback.to(device=value.device, dtype=value.dtype)
    return value / norm


def _torch_generator(seed: int) -> torch.Generator:
    gen = torch.Generator(device="cpu")
    gen.manual_seed(int(seed))
    return gen


def _random_unit_vectors(count: int, seed: int) -> torch.Tensor:
    gen = _torch_generator(seed)
    vectors = torch.randn((max(count, 1), 3), generator=gen, dtype=torch.float32)
    vectors = vectors / torch.linalg.norm(vectors, dim=-1, keepdim=True).clamp_min(1e-6)
    return vectors[:count]


def _helix_coords(n_res: int) -> torch.Tensor:
    index = torch.arange(n_res, dtype=torch.float32)
    theta = index * math.radians(100.0)
    coords = torch.stack(
        [
            1.50 * index,
            2.30 * torch.cos(theta),
            2.30 * torch.sin(theta),
        ],
        dim=-1,
    )
    return coords


def _strand_coords(n_res: int) -> torch.Tensor:
    index = torch.arange(n_res, dtype=torch.float32)
    coords = torch.stack(
        [
            3.55 * index,
            torch.where((index.long() % 2) == 0, torch.tensor(0.95), torch.tensor(-0.95)),
            0.35 * torch.sin(index * math.pi * 0.5),
        ],
        dim=-1,
    )
    return coords


def _random_walk_coords(n_res: int, seed: int, *, compact: bool) -> torch.Tensor:
    if n_res <= 1:
        return torch.zeros((n_res, 3), dtype=torch.float32)
    directions = _random_unit_vectors(n_res - 1, seed=seed)
    if compact:
        for index in range(1, directions.shape[0]):
            inward = -torch.sum(directions[:index], dim=0)
            directions[index] = _unit(0.65 * directions[index] + 0.35 * inward, directions[index])
    steps = 3.80 * directions
    coords = torch.cat([torch.zeros((1, 3), dtype=torch.float32), torch.cumsum(steps, dim=0)], dim=0)
    if compact and n_res > 8:
        center = coords.mean(dim=0, keepdim=True)
        coords = center + 0.55 * (coords - center)
        coords = _project_ca_bonds(coords, target=3.80, iterations=3)
    return coords


def _mixed_coords(sequence: str, secondary: str, seed: int) -> torch.Tensor:
    n_res = len(sequence)
    if n_res <= 1:
        return torch.zeros((n_res, 3), dtype=torch.float32)
    gen_dirs = _random_unit_vectors(n_res - 1, seed=seed)
    coords = torch.zeros((n_res, 3), dtype=torch.float32)
    direction = torch.tensor([1.0, 0.0, 0.0], dtype=torch.float32)
    normal = torch.tensor([0.0, 1.0, 0.0], dtype=torch.float32)
    binormal = torch.tensor([0.0, 0.0, 1.0], dtype=torch.float32)
    for index in range(1, n_res):
        call = secondary[index - 1]
        if call == "H":
            angle = math.radians(100.0)
            direction = _unit(0.42 * direction + 0.58 * (math.cos(angle) * normal + math.sin(angle) * binormal), direction)
        elif call == "E":
            direction = _unit(0.82 * torch.tensor([1.0, 0.0, 0.0]) + 0.18 * ((-1.0) ** index) * normal, direction)
        else:
            direction = _unit(0.70 * direction + 0.30 * gen_dirs[index - 1], direction)
        coords[index] = coords[index - 1] + 3.80 * direction
        tangent = _unit(direction, torch.tensor([1.0, 0.0, 0.0]))
        normal = _unit(torch.cross(binormal, tangent, dim=0), normal)
        binormal = _unit(torch.cross(tangent, normal, dim=0), binormal)
    return coords


def make_initial_coords(sequence: str, secondary: str, mode: str, seed: int, device: torch.device) -> torch.Tensor:
    n_res = len(sequence)
    if mode == "helix":
        coords = _helix_coords(n_res)
    elif mode == "strand":
        coords = _strand_coords(n_res)
    elif mode == "compact":
        coords = _random_walk_coords(n_res, seed=seed, compact=True)
    elif mode == "random":
        coords = _random_walk_coords(n_res, seed=seed, compact=False)
    else:
        coords = _mixed_coords(sequence, secondary, seed=seed)
    coords = coords - coords.mean(dim=0, keepdim=True)
    return coords.to(device=device)


def _project_ca_bonds(coords: torch.Tensor, *, target: float, iterations: int) -> torch.Tensor:
    projected = coords.clone()
    for _ in range(max(0, int(iterations))):
        for index in range(1, int(projected.shape[0])):
            step = projected[index] - projected[index - 1]
            projected[index] = projected[index - 1] + target * _unit(step, torch.tensor([1.0, 0.0, 0.0], dtype=projected.dtype))
        projected = projected - projected.mean(dim=0, keepdim=True)
    return projected


def _repair_ca_bond_window(coords: torch.Tensor, *, min_dist: float, max_dist: float, target: float, iterations: int) -> torch.Tensor:
    repaired = coords.clone()
    fallback = torch.tensor([1.0, 0.0, 0.0], dtype=repaired.dtype)
    for _ in range(max(0, int(iterations))):
        changed = False
        for index in range(1, int(repaired.shape[0])):
            step = repaired[index] - repaired[index - 1]
            distance = float(torch.linalg.norm(step).item())
            if min_dist <= distance <= max_dist:
                continue
            direction = _unit(step, fallback)
            desired = max(float(min_dist), min(float(max_dist), float(target)))
            midpoint = 0.5 * (repaired[index] + repaired[index - 1])
            repaired[index - 1] = midpoint - 0.5 * desired * direction
            repaired[index] = midpoint + 0.5 * desired * direction
            changed = True
        repaired = repaired - repaired.mean(dim=0, keepdim=True)
        if not changed:
            break
    return repaired


def _nonlocal_ca_close_contact_count(coords: torch.Tensor, *, threshold: float) -> int:
    n_res = int(coords.shape[0])
    if n_res <= 2:
        return 0
    count = 0
    for left in range(n_res):
        for right in range(left + 2, n_res):
            if float(torch.linalg.norm(coords[left] - coords[right]).item()) < float(threshold):
                count += 1
    return count


def _ranked_candidate_quality_score(coords: torch.Tensor, sequence: str, raw_energy: float) -> float:
    n_res = int(coords.shape[0])
    if n_res <= 1:
        return float(raw_energy)
    ca_dist = torch.linalg.norm(coords[1:] - coords[:-1], dim=-1)
    continuity_violations = int(((ca_dist < 2.0) | (ca_dist > 8.0)).sum().item())
    centered = coords - coords.mean(dim=0, keepdim=True)
    rg = float(torch.sqrt(torch.mean(torch.sum(centered * centered, dim=-1))).item())
    target_rg = max(sequence_target_rg(sequence), 1e-6)
    rg_ratio = max(rg / target_rg, 1e-6)
    max_abs = float(torch.max(torch.abs(coords)).item()) if coords.numel() else 0.0

    dist = torch.cdist(coords.float(), coords.float()).clamp_min(1e-6)
    indices = torch.arange(n_res)
    nonlocal_mask = torch.triu((torch.abs(indices.view(-1, 1) - indices.view(1, -1)) > 1), diagonal=1)
    nonlocal_dist = dist[nonlocal_mask]
    severe_close = int((nonlocal_dist < 0.80).sum().item())
    close_15 = int((nonlocal_dist < 1.50).sum().item())
    close_20 = int((nonlocal_dist < 2.00).sum().item())
    coordinate_overflow = max(0.0, max_abs - 950.0)

    return float(
        0.01 * raw_energy
        + 100_000_000.0 * severe_close
        + 1_000_000.0 * close_15
        + 10_000.0 * close_20
        + 500_000.0 * continuity_violations
        + 250_000.0 * coordinate_overflow
        + 2_500.0 * abs(math.log(rg_ratio))
    )


def _polish_ca_geometry(coords: torch.Tensor, *, steps: int) -> torch.Tensor:
    n_res = int(coords.shape[0])
    if n_res <= 2:
        return coords
    with torch.enable_grad():
        polished = coords.clone().float().requires_grad_(True)
        optimizer = torch.optim.Adam([polished], lr=0.03)
        indices = torch.arange(n_res)
        pair_mask = (torch.abs(indices.view(-1, 1) - indices.view(1, -1)) > 1) & torch.triu(
            torch.ones((n_res, n_res), dtype=torch.bool),
            diagonal=1,
        )
        for _ in range(max(0, int(steps))):
            optimizer.zero_grad(set_to_none=True)
            bond = torch.linalg.norm(polished[1:] - polished[:-1], dim=-1).clamp_min(1e-6)
            dist = torch.cdist(polished, polished).clamp_min(1e-6)
            nonlocal_dist = dist[pair_mask]
            loss = (
                20.0 * torch.mean((bond - 3.80) ** 2)
                + 120.0 * torch.mean(torch.relu(2.05 - nonlocal_dist) ** 2)
                + 30.0 * torch.mean(torch.relu(bond - 4.75) ** 2)
                + 30.0 * torch.mean(torch.relu(3.05 - bond) ** 2)
            )
            if not torch.isfinite(loss):
                break
            loss.backward()
            torch.nn.utils.clip_grad_norm_([polished], max_norm=50.0)
            optimizer.step()
            with torch.no_grad():
                polished -= polished.mean(dim=0, keepdim=True)
        return polished.detach()


def _sequence_flags(sequence: str, device: torch.device) -> dict[str, torch.Tensor]:
    return {
        "hydrophobic": torch.tensor([aa in HYDROPHOBIC for aa in sequence], dtype=torch.float32, device=device),
        "positive": torch.tensor([aa in POSITIVE for aa in sequence], dtype=torch.float32, device=device),
        "negative": torch.tensor([aa in NEGATIVE for aa in sequence], dtype=torch.float32, device=device),
        "aromatic": torch.tensor([aa in AROMATIC for aa in sequence], dtype=torch.float32, device=device),
        "polar": torch.tensor([aa in POLAR for aa in sequence], dtype=torch.float32, device=device),
    }


def _sample_pairs(sequence: str, *, seed: int, max_pairs: int, device: torch.device) -> dict[str, torch.Tensor]:
    n_res = len(sequence)
    if n_res <= 8 or max_pairs <= 0:
        empty_i = torch.empty((0,), dtype=torch.long, device=device)
        empty_f = torch.empty((0,), dtype=torch.float32, device=device)
        return {"i": empty_i, "j": empty_i, "hyd": empty_f, "opp": empty_f, "same": empty_f, "arom": empty_f}
    rng = random.Random(int(seed))
    pairs: set[tuple[int, int]] = set()
    attempts = 0
    target = min(int(max_pairs), max(n_res * 6, 128))
    while len(pairs) < target and attempts < target * 60:
        attempts += 1
        i = rng.randrange(0, n_res)
        j = rng.randrange(0, n_res)
        if abs(i - j) < 5:
            continue
        if i > j:
            i, j = j, i
        pairs.add((i, j))
    ordered = sorted(pairs)
    if not ordered:
        empty_i = torch.empty((0,), dtype=torch.long, device=device)
        empty_f = torch.empty((0,), dtype=torch.float32, device=device)
        return {"i": empty_i, "j": empty_i, "hyd": empty_f, "opp": empty_f, "same": empty_f, "arom": empty_f}
    i_tensor = torch.tensor([i for i, _j in ordered], dtype=torch.long, device=device)
    j_tensor = torch.tensor([j for _i, j in ordered], dtype=torch.long, device=device)
    flags = _sequence_flags(sequence, device=device)
    hyd = flags["hydrophobic"]
    pos = flags["positive"]
    neg = flags["negative"]
    arom = flags["aromatic"]
    hyd_pair = hyd[i_tensor] * hyd[j_tensor]
    opp_pair = (pos[i_tensor] * neg[j_tensor]) + (neg[i_tensor] * pos[j_tensor])
    same_pair = (pos[i_tensor] * pos[j_tensor]) + (neg[i_tensor] * neg[j_tensor])
    arom_pair = arom[i_tensor] * arom[j_tensor]
    return {"i": i_tensor, "j": j_tensor, "hyd": hyd_pair, "opp": opp_pair, "same": same_pair, "arom": arom_pair}


def _energy_batch(coords: torch.Tensor, sequence: str, secondary: str, pair_data: dict[str, torch.Tensor]) -> torch.Tensor:
    batch, n_res, _xyz = coords.shape
    eps = torch.tensor(1e-6, dtype=coords.dtype, device=coords.device)
    energies = torch.zeros((batch,), dtype=coords.dtype, device=coords.device)
    if n_res > 1:
        bond = torch.linalg.norm(coords[:, 1:, :] - coords[:, :-1, :], dim=-1).clamp_min(eps)
        energies = energies + 24.0 * torch.mean((bond - 3.80) ** 2, dim=-1)
    if n_res > 2:
        i2 = torch.linalg.norm(coords[:, 2:, :] - coords[:, :-2, :], dim=-1).clamp_min(eps)
        ss_mid = torch.tensor(
            [5.45 if call == "H" else 6.80 if call == "E" else 5.95 for call in secondary[1:-1]],
            dtype=coords.dtype,
            device=coords.device,
        )
        energies = energies + 2.4 * torch.mean((i2 - ss_mid.view(1, -1)) ** 2, dim=-1)
    helix_indices = [index for index in range(0, max(n_res - 4, 0)) if secondary[index : index + 5].count("H") >= 4]
    if helix_indices:
        h_i = torch.tensor(helix_indices, dtype=torch.long, device=coords.device)
        h_j = h_i + 4
        h_dist = torch.linalg.norm(coords[:, h_i, :] - coords[:, h_j, :], dim=-1).clamp_min(eps)
        energies = energies + 1.1 * torch.mean((h_dist - 6.05) ** 2, dim=-1)
    pair_i = pair_data["i"]
    if int(pair_i.numel()) > 0:
        pair_j = pair_data["j"]
        vec = coords[:, pair_i, :] - coords[:, pair_j, :]
        dist = torch.linalg.norm(vec, dim=-1).clamp_min(eps)
        hyd = pair_data["hyd"].view(1, -1)
        opp = pair_data["opp"].view(1, -1)
        same = pair_data["same"].view(1, -1)
        arom = pair_data["arom"].view(1, -1)
        energies = energies + 1.8 * torch.mean(torch.relu(4.20 - dist) ** 2, dim=-1)
        energies = energies + 0.065 * torch.mean(hyd * torch.relu(dist - 8.20) ** 2, dim=-1)
        energies = energies + 0.035 * torch.mean(arom * torch.relu(dist - 6.20) ** 2, dim=-1)
        energies = energies + 0.050 * torch.mean(opp * torch.relu(dist - 7.00) ** 2, dim=-1)
        energies = energies + 0.070 * torch.mean(same * torch.relu(8.50 - dist) ** 2, dim=-1)
    centered = coords - coords.mean(dim=1, keepdim=True)
    rg = torch.sqrt(torch.mean(torch.sum(centered * centered, dim=-1), dim=-1).clamp_min(eps))
    target_rg = torch.tensor(sequence_target_rg(sequence), dtype=coords.dtype, device=coords.device)
    energies = energies + 0.055 * (rg - target_rg) ** 2
    return energies


def _finalize_coords(coords: torch.Tensor, *, heavy_polish: bool = True) -> torch.Tensor:
    projected = _project_ca_bonds(coords.detach().float().cpu(), target=3.80, iterations=2)
    projected = _declash_ca_coords(projected, min_dist=2.60, iterations=36)
    projected = _project_ca_bonds(projected, target=3.80, iterations=2)
    projected = _declash_ca_coords(projected, min_dist=2.20, iterations=48)
    projected = _repair_ca_bond_window(projected, min_dist=3.05, max_dist=4.75, target=3.80, iterations=3)
    projected = _declash_ca_coords(projected, min_dist=1.60, iterations=36)
    projected = _repair_ca_bond_window(projected, min_dist=3.05, max_dist=4.75, target=3.80, iterations=2)
    if heavy_polish and int(projected.shape[0]) <= 800 and _nonlocal_ca_close_contact_count(projected, threshold=2.0) > 0:
        projected = _polish_ca_geometry(projected, steps=400)
        projected = _repair_ca_bond_window(projected, min_dist=3.05, max_dist=4.75, target=3.80, iterations=2)
    projected = _declash_ca_coords(projected, min_dist=1.25, iterations=24)
    projected = _repair_ca_bond_window(projected, min_dist=3.05, max_dist=4.75, target=3.80, iterations=1)
    return projected


def _declash_ca_coords(coords: torch.Tensor, *, min_dist: float, iterations: int) -> torch.Tensor:
    if int(coords.shape[0]) <= 2:
        return coords
    out = coords.clone()
    for _ in range(max(0, int(iterations))):
        dist = torch.cdist(out, out)
        n_res = int(out.shape[0])
        seq_index = torch.arange(n_res)
        seq_sep = torch.abs(seq_index.view(-1, 1) - seq_index.view(1, -1))
        mask = torch.triu((dist < float(min_dist)) & (seq_sep > 1), diagonal=1)
        pairs = torch.nonzero(mask, as_tuple=False)
        if int(pairs.numel()) == 0:
            break
        for left, right in pairs[:2000].tolist():
            delta = out[right] - out[left]
            norm = torch.linalg.norm(delta)
            if float(norm.item()) < 1e-6:
                angle = 2.399963229728653 * float(left + right + 1)
                direction = torch.tensor([math.cos(angle), math.sin(angle), 0.37], dtype=out.dtype)
                direction = direction / torch.linalg.norm(direction).clamp_min(1e-6)
            else:
                direction = delta / norm
            push = 0.5 * (float(min_dist) - min(float(norm.item()), float(min_dist)) + 0.05)
            out[left] -= push * direction
            out[right] += push * direction
        out = out - out.mean(dim=0, keepdim=True)
    return out


def _residue_confidence(final_ensemble: torch.Tensor, best_index: int, sequence: str) -> torch.Tensor:
    centered = final_ensemble - final_ensemble.mean(dim=1, keepdim=True)
    best = centered[best_index : best_index + 1]
    residue_spread = torch.sqrt(torch.mean(torch.sum((centered - best) ** 2, dim=-1), dim=0).clamp_min(0.0))
    scale = torch.quantile(residue_spread, 0.85).clamp_min(1.0)
    spread_penalty = torch.clamp(residue_spread / scale, 0.0, 2.0)
    confidence = 83.0 - 28.0 * spread_penalty
    if len(sequence) > 0:
        seq_variation = torch.tensor(
            [
                4.0 if aa in HELIX_FAVOR else -3.0 if aa in BREAKERS else 2.0 if aa in HYDROPHOBIC else 0.0
                for aa in sequence
            ],
            dtype=torch.float32,
        )
        wave = 3.5 * torch.sin(torch.arange(len(sequence), dtype=torch.float32) * 0.173)
        confidence = confidence.cpu() + seq_variation + wave
    return torch.clamp(confidence.float(), 12.0, 94.0)


def _chain_metrics(coords: torch.Tensor, confidence: torch.Tensor, secondary: str, energy: float, sequence: str) -> dict[str, Any]:
    centered = coords - coords.mean(dim=0, keepdim=True)
    rg = torch.sqrt(torch.mean(torch.sum(centered * centered, dim=-1))).item() if coords.numel() else 0.0
    target_rg = sequence_target_rg(sequence)
    comp = _sequence_composition(sequence)
    if coords.shape[0] > 1:
        ca_dist = torch.linalg.norm(coords[1:] - coords[:-1], dim=-1)
        ca_min = float(ca_dist.min().item())
        ca_max = float(ca_dist.max().item())
        ca_mean = float(ca_dist.mean().item())
    else:
        ca_min = ca_max = ca_mean = 0.0
    return {
        "residue_count": int(coords.shape[0]),
        "energy": round(float(energy), 6),
        "rg_A": round(float(rg), 3),
        "target_rg_A": round(float(target_rg), 3),
        "rg_ratio": round(float(rg) / target_rg if target_rg else 0.0, 3),
        "sequence_compaction_scale": round(sequence_compaction_scale(sequence), 3),
        "hydrophobic_fraction": round(comp["hydrophobic_fraction"], 6),
        "charged_fraction": round(comp["charged_fraction"], 6),
        "net_charge_fraction": round(comp["net_charge_fraction"], 6),
        "breaker_fraction": round(comp["breaker_fraction"], 6),
        "ca_distance_min_A": round(ca_min, 3),
        "ca_distance_mean_A": round(ca_mean, 3),
        "ca_distance_max_A": round(ca_max, 3),
        "confidence_min": round(float(confidence.min().item()), 3) if confidence.numel() else 0.0,
        "confidence_mean": round(float(confidence.mean().item()), 3) if confidence.numel() else 0.0,
        "confidence_max": round(float(confidence.max().item()), 3) if confidence.numel() else 0.0,
        "secondary_helix_fraction": round(secondary.count("H") / max(len(secondary), 1), 6),
        "secondary_strand_fraction": round(secondary.count("E") / max(len(secondary), 1), 6),
        "secondary_coil_fraction": round(secondary.count("C") / max(len(secondary), 1), 6),
    }


def predict_chain(
    chain: FastaChain,
    *,
    ensemble_size: int,
    steps: int,
    device: torch.device,
    seed: int,
    max_pairs: int,
) -> ChainResult:
    sequence = chain.sequence
    secondary = infer_secondary_structure(sequence)
    modes = ("mixed", "helix", "strand", "compact", "random")
    starts = [
        make_initial_coords(sequence, secondary, modes[index % len(modes)], seed + index * 9973, device=device)
        for index in range(max(1, int(ensemble_size)))
    ]
    coords = torch.stack(starts, dim=0).float().to(device=device)
    coords.requires_grad_(True)
    pair_data = _sample_pairs(sequence, seed=seed + 17, max_pairs=max_pairs, device=device)
    optimizer = torch.optim.Adam([coords], lr=0.045)
    last_energy = torch.zeros((coords.shape[0],), dtype=torch.float32, device=device)
    for step in range(max(0, int(steps))):
        optimizer.zero_grad(set_to_none=True)
        energies = _energy_batch(coords, sequence, secondary, pair_data)
        loss = energies.mean()
        if not torch.isfinite(loss):
            break
        loss.backward()
        torch.nn.utils.clip_grad_norm_([coords], max_norm=40.0)
        optimizer.step()
        with torch.no_grad():
            coords -= coords.mean(dim=1, keepdim=True)
            if step % 50 == 49:
                coords.clamp_(min=-9500.0, max=9500.0)
        last_energy = energies.detach()
    with torch.no_grad():
        energies = _energy_batch(coords, sequence, secondary, pair_data).detach() if int(steps) >= 0 else last_energy
        energy_ranked_indices = torch.argsort(energies).detach().cpu().tolist()
        final_ensemble = torch.stack([_finalize_coords(coords[index], heavy_polish=False) for index in range(coords.shape[0])], dim=0)
        scored_indices = sorted(
            (int(index) for index in energy_ranked_indices),
            key=lambda index: _ranked_candidate_quality_score(
                final_ensemble[index],
                sequence,
                float(energies[index].detach().cpu().item()),
            ),
        )
        best_index = int(scored_indices[0])
        best_coords = _finalize_coords(final_ensemble[best_index], heavy_polish=True)
        confidence = _residue_confidence(final_ensemble, best_index, sequence)
        best_energy = float(energies[best_index].detach().cpu().item())
        ranked_coords: list[torch.Tensor] = []
        ranked_confidences: list[torch.Tensor] = []
        ranked_energies: list[float] = []
        for candidate_index in scored_indices[: min(5, len(scored_indices))]:
            candidate_index = int(candidate_index)
            ranked_coords.append(_finalize_coords(final_ensemble[candidate_index], heavy_polish=True).detach().cpu().float())
            ranked_confidences.append(_residue_confidence(final_ensemble, candidate_index, sequence).detach().cpu().float())
            ranked_energies.append(float(energies[candidate_index].detach().cpu().item()))
    metrics = _chain_metrics(best_coords, confidence, secondary, best_energy, sequence)
    return ChainResult(
        chain=chain,
        coords=best_coords,
        confidence=confidence,
        energy=best_energy,
        ensemble_size=int(coords.shape[0]),
        secondary=secondary,
        metrics=metrics,
        ranked_coords=ranked_coords,
        ranked_confidences=ranked_confidences,
        ranked_energies=ranked_energies,
    )


def _chain_radius(coords: torch.Tensor) -> float:
    if coords.numel() == 0:
        return 0.0
    centered = coords - coords.mean(dim=0, keepdim=True)
    return float(torch.linalg.norm(centered, dim=-1).max().item())


def _sample_interchain_pairs(chain_results: list[ChainResult], *, seed: int, max_pairs_per_chain_pair: int, device: torch.device) -> dict[str, torch.Tensor]:
    rng = random.Random(int(seed))
    left_chain: list[int] = []
    right_chain: list[int] = []
    left_res: list[int] = []
    right_res: list[int] = []
    favorable: list[float] = []
    for c1 in range(len(chain_results)):
        for c2 in range(c1 + 1, len(chain_results)):
            seq1 = chain_results[c1].chain.sequence
            seq2 = chain_results[c2].chain.sequence
            count = min(int(max_pairs_per_chain_pair), max(len(seq1), len(seq2), 1) * 2)
            for _ in range(count):
                i = rng.randrange(0, len(seq1))
                j = rng.randrange(0, len(seq2))
                aa_i = seq1[i]
                aa_j = seq2[j]
                fav = float(
                    (aa_i in HYDROPHOBIC and aa_j in HYDROPHOBIC)
                    or (aa_i in AROMATIC and aa_j in AROMATIC)
                    or (aa_i in POSITIVE and aa_j in NEGATIVE)
                    or (aa_i in NEGATIVE and aa_j in POSITIVE)
                )
                left_chain.append(c1)
                right_chain.append(c2)
                left_res.append(i)
                right_res.append(j)
                favorable.append(fav)
    return {
        "left_chain": torch.tensor(left_chain, dtype=torch.long, device=device),
        "right_chain": torch.tensor(right_chain, dtype=torch.long, device=device),
        "left_res": torch.tensor(left_res, dtype=torch.long, device=device),
        "right_res": torch.tensor(right_res, dtype=torch.long, device=device),
        "favorable": torch.tensor(favorable, dtype=torch.float32, device=device),
    }


def _sample_chain_coords(coords: torch.Tensor, *, max_points: int, device: torch.device) -> torch.Tensor:
    if int(coords.shape[0]) <= int(max_points):
        return coords.to(device=device)
    indices = torch.linspace(0, int(coords.shape[0]) - 1, steps=int(max_points)).round().long()
    return coords[indices].to(device=device)


def dock_chains(chain_results: list[ChainResult], *, steps: int, seed: int, device: torch.device) -> None:
    if len(chain_results) <= 1:
        return
    radii = [_chain_radius(result.coords) for result in chain_results]
    base_radius = max(max(radii) * 0.68, 14.0)
    translations = []
    for index, _result in enumerate(chain_results):
        angle = 2.0 * math.pi * index / max(len(chain_results), 1)
        translations.append([base_radius * math.cos(angle), base_radius * math.sin(angle), 6.0 * (index % 3)])
    trans = torch.tensor(translations, dtype=torch.float32, device=device, requires_grad=True)
    coords_by_chain = [result.coords.to(device=device) for result in chain_results]
    sampled_by_chain = [_sample_chain_coords(result.coords, max_points=192, device=device) for result in chain_results]
    pair_data = _sample_interchain_pairs(chain_results, seed=seed, max_pairs_per_chain_pair=384, device=device)
    left_base = right_base = None
    if int(pair_data["left_chain"].numel()) > 0:
        lc_list = pair_data["left_chain"].cpu().tolist()
        rc_list = pair_data["right_chain"].cpu().tolist()
        lr_list = pair_data["left_res"].cpu().tolist()
        rr_list = pair_data["right_res"].cpu().tolist()
        left_base = torch.stack([coords_by_chain[int(c)][int(r)] for c, r in zip(lc_list, lr_list)], dim=0).to(device=device)
        right_base = torch.stack([coords_by_chain[int(c)][int(r)] for c, r in zip(rc_list, rr_list)], dim=0).to(device=device)
    optimizer = torch.optim.Adam([trans], lr=0.08)
    for _step in range(max(0, min(int(steps), 300))):
        optimizer.zero_grad(set_to_none=True)
        energy = torch.zeros((), dtype=torch.float32, device=device)
        for c1 in range(len(chain_results)):
            for c2 in range(c1 + 1, len(chain_results)):
                center_dist = torch.linalg.norm(trans[c1] - trans[c2]).clamp_min(1e-6)
                target = torch.tensor(max(9.0, 0.52 * (radii[c1] + radii[c2]) + 4.0), dtype=torch.float32, device=device)
                energy = energy + 0.015 * (center_dist - target) ** 2
                left_sample = sampled_by_chain[c1] + trans[c1]
                right_sample = sampled_by_chain[c2] + trans[c2]
                dist_matrix = torch.cdist(left_sample, right_sample).clamp_min(1e-6)
                flat_dist = dist_matrix.reshape(-1)
                k = min(24, int(flat_dist.numel()))
                nearest = torch.topk(flat_dist, k=k, largest=False).values
                min_dist = nearest[0]
                energy = energy + 10.0 * torch.relu(3.80 - min_dist) ** 2
                energy = energy + 0.120 * torch.mean(torch.relu(4.20 - dist_matrix) ** 2)
                energy = energy + 0.060 * torch.mean(torch.relu(4.80 - nearest) ** 2)
                energy = energy + 0.018 * torch.mean(torch.relu(nearest - 10.50) ** 2)
                energy = energy + 0.080 * torch.relu(min_dist - 8.80) ** 2
        if left_base is not None and right_base is not None:
            lc = pair_data["left_chain"]
            rc = pair_data["right_chain"]
            left = left_base + trans[lc]
            right = right_base + trans[rc]
            dist = torch.linalg.norm(left - right, dim=-1).clamp_min(1e-6)
            favorable = pair_data["favorable"]
            energy = energy + 1.5 * torch.mean(torch.relu(5.0 - dist) ** 2)
            energy = energy + 0.025 * torch.mean(favorable * torch.relu(dist - 10.0) ** 2)
        if not torch.isfinite(energy):
            break
        energy.backward()
        torch.nn.utils.clip_grad_norm_([trans], max_norm=30.0)
        optimizer.step()
        with torch.no_grad():
            trans -= trans.mean(dim=0, keepdim=True)
    with torch.no_grad():
        for _iteration in range(96):
            moved = False
            for c1 in range(len(chain_results)):
                for c2 in range(c1 + 1, len(chain_results)):
                    left_full = coords_by_chain[c1] + trans[c1]
                    right_full = coords_by_chain[c2] + trans[c2]
                    dist_matrix = torch.cdist(left_full, right_full).clamp_min(1e-6)
                    violation = dist_matrix < 3.20
                    if not bool(violation.any().item()):
                        continue
                    pairs = torch.nonzero(violation, as_tuple=False)
                    if int(pairs.shape[0]) > 4096:
                        pairs = pairs[:4096]
                    deltas = right_full[pairs[:, 1]] - left_full[pairs[:, 0]]
                    distances = torch.linalg.norm(deltas, dim=-1).clamp_min(1e-6)
                    directions = deltas / distances.view(-1, 1)
                    direction = directions.mean(dim=0)
                    if float(torch.linalg.norm(direction).item()) < 1e-6:
                        direction = trans[c2] - trans[c1]
                    direction = direction / torch.linalg.norm(direction).clamp_min(1e-6)
                    mean_overlap = torch.mean(torch.relu(3.25 - distances))
                    push = float(torch.clamp(mean_overlap * 0.75, min=0.05, max=2.50).item())
                    trans[c1] -= push * direction
                    trans[c2] += push * direction
                    moved = True
            trans -= trans.mean(dim=0, keepdim=True)
            if not moved:
                break
        for _iteration in range(192):
            moved = False
            for c1 in range(len(chain_results)):
                for c2 in range(c1 + 1, len(chain_results)):
                    left_full = coords_by_chain[c1] + trans[c1]
                    right_full = coords_by_chain[c2] + trans[c2]
                    dist_matrix = torch.cdist(left_full, right_full).clamp_min(1e-6)
                    min_distance, flat_index = torch.min(dist_matrix.reshape(-1), dim=0)
                    if float(min_distance.item()) >= 3.25:
                        continue
                    left_index = flat_index // dist_matrix.shape[1]
                    right_index = flat_index % dist_matrix.shape[1]
                    delta = right_full[right_index] - left_full[left_index]
                    direction = delta / torch.linalg.norm(delta).clamp_min(1e-6)
                    if float(torch.linalg.norm(direction).item()) < 1e-6:
                        direction = trans[c2] - trans[c1]
                        direction = direction / torch.linalg.norm(direction).clamp_min(1e-6)
                    push = float(torch.clamp((3.35 - min_distance) * 0.55, min=0.03, max=2.25).item())
                    trans[c1] -= push * direction
                    trans[c2] += push * direction
                    moved = True
            trans -= trans.mean(dim=0, keepdim=True)
            if not moved:
                break
        for _iteration in range(512):
            best: tuple[float, int, int, int, int] | None = None
            for c1 in range(len(chain_results)):
                for c2 in range(c1 + 1, len(chain_results)):
                    left_full = coords_by_chain[c1] + trans[c1]
                    right_full = coords_by_chain[c2] + trans[c2]
                    dist_matrix = torch.cdist(left_full, right_full).clamp_min(1e-6)
                    min_distance, flat_index = torch.min(dist_matrix.reshape(-1), dim=0)
                    distance = float(min_distance.item())
                    if best is None or distance < best[0]:
                        best = (distance, c1, c2, int((flat_index // dist_matrix.shape[1]).item()), int((flat_index % dist_matrix.shape[1]).item()))
            if best is None or best[0] >= 3.25:
                break
            distance, c1, c2, left_index, right_index = best
            left_full = coords_by_chain[c1] + trans[c1]
            right_full = coords_by_chain[c2] + trans[c2]
            delta = right_full[right_index] - left_full[left_index]
            if float(torch.linalg.norm(delta).item()) < 1e-6:
                delta = trans[c2] - trans[c1]
            direction = delta / torch.linalg.norm(delta).clamp_min(1e-6)
            push = float(torch.clamp(torch.tensor((3.35 - distance) * 0.70), min=0.05, max=2.50).item())
            trans[c1] -= push * direction
            trans[c2] += push * direction
            trans -= trans.mean(dim=0, keepdim=True)
        for index, result in enumerate(chain_results):
            result.coords = (result.coords.to(device=device) + trans[index]).detach().cpu()
        _enforce_interchain_ca_floor(chain_results, min_distance=3.20, target_distance=3.35, iterations=768)


def _enforce_interchain_ca_floor(
    chain_results: list[ChainResult],
    *,
    min_distance: float,
    target_distance: float,
    iterations: int,
) -> None:
    if len(chain_results) <= 1:
        return
    for _iteration in range(max(0, int(iterations))):
        best: tuple[float, int, int, int, int] | None = None
        for c1 in range(len(chain_results)):
            for c2 in range(c1 + 1, len(chain_results)):
                left = chain_results[c1].coords.float()
                right = chain_results[c2].coords.float()
                if left.numel() == 0 or right.numel() == 0:
                    continue
                dist_matrix = torch.cdist(left, right).clamp_min(1e-6)
                min_dist, flat_index = torch.min(dist_matrix.reshape(-1), dim=0)
                distance = float(min_dist.item())
                if best is None or distance < best[0]:
                    best = (
                        distance,
                        c1,
                        c2,
                        int((flat_index // dist_matrix.shape[1]).item()),
                        int((flat_index % dist_matrix.shape[1]).item()),
                    )
        if best is None or best[0] >= float(min_distance):
            break

        distance, c1, c2, left_index, right_index = best
        left = chain_results[c1].coords.float()
        right = chain_results[c2].coords.float()
        delta = right[right_index] - left[left_index]
        if float(torch.linalg.norm(delta).item()) < 1e-6:
            delta = right.mean(dim=0) - left.mean(dim=0)
        if float(torch.linalg.norm(delta).item()) < 1e-6:
            delta = torch.tensor([1.0, 0.0, 0.0], dtype=torch.float32)
        direction = delta / torch.linalg.norm(delta).clamp_min(1e-6)
        gap = max(0.0, float(target_distance) - distance)
        shift = min(max(gap * 0.5 + 0.02, 0.04), 3.0)
        chain_results[c1].coords = (chain_results[c1].coords.float() - shift * direction).detach().cpu()
        chain_results[c2].coords = (chain_results[c2].coords.float() + shift * direction).detach().cpu()
    _expand_chain_centers_until_floor(chain_results, min_distance=float(min_distance), step=0.18, iterations=256)


def _expand_chain_centers_until_floor(
    chain_results: list[ChainResult],
    *,
    min_distance: float,
    step: float,
    iterations: int,
) -> None:
    if len(chain_results) <= 1:
        return
    for _iteration in range(max(0, int(iterations))):
        min_observed = float("inf")
        for c1 in range(len(chain_results)):
            for c2 in range(c1 + 1, len(chain_results)):
                left = chain_results[c1].coords.float()
                right = chain_results[c2].coords.float()
                if left.numel() == 0 or right.numel() == 0:
                    continue
                pair_min = float(torch.cdist(left, right).min().item())
                min_observed = min(min_observed, pair_min)
        if not math.isfinite(min_observed) or min_observed >= float(min_distance):
            break

        centers = torch.stack([result.coords.float().mean(dim=0) for result in chain_results], dim=0)
        assembly_center = centers.mean(dim=0)
        for index, result in enumerate(chain_results):
            direction = centers[index] - assembly_center
            if float(torch.linalg.norm(direction).item()) < 1e-6:
                angle = 2.0 * math.pi * index / max(len(chain_results), 1)
                direction = torch.tensor([math.cos(angle), math.sin(angle), 0.0], dtype=torch.float32)
            direction = direction / torch.linalg.norm(direction).clamp_min(1e-6)
            result.coords = (result.coords.float() + float(step) * direction).detach().cpu()


def assembly_metrics(chain_results: list[ChainResult]) -> dict[str, Any]:
    chain_count = len(chain_results)
    if chain_count <= 1:
        return {
            "chain_count": chain_count,
            "chain_pair_count": 0,
            "interchain_ca_contact_count_12A": 0,
            "chain_pairs_with_contacts_12A": 0,
            "min_interchain_ca_distance_A": 0.0,
            "interchain_ca_clash_count_3A": 0,
            "interface_plausibility_status": "not_applicable",
        }
    contact_count = 0
    pair_with_contacts = 0
    clash_count = 0
    min_distance = float("inf")
    pair_count = 0
    for left_index in range(chain_count):
        for right_index in range(left_index + 1, chain_count):
            pair_count += 1
            left = chain_results[left_index].coords.float()
            right = chain_results[right_index].coords.float()
            if left.numel() == 0 or right.numel() == 0:
                continue
            dist = torch.cdist(left, right)
            pair_min = float(dist.min().item())
            min_distance = min(min_distance, pair_min)
            pair_contacts = int((dist <= 12.0).sum().item())
            contact_count += pair_contacts
            pair_with_contacts += int(pair_contacts > 0)
            clash_count += int((dist < 3.0).sum().item())
    plausible = contact_count > 0 and clash_count == 0 and (not math.isfinite(min_distance) or min_distance >= 3.0)
    return {
        "chain_count": chain_count,
        "chain_pair_count": pair_count,
        "interchain_ca_contact_count_12A": contact_count,
        "chain_pairs_with_contacts_12A": pair_with_contacts,
        "min_interchain_ca_distance_A": round(0.0 if not math.isfinite(min_distance) else min_distance, 3),
        "interchain_ca_clash_count_3A": clash_count,
        "interface_plausibility_status": "pass" if plausible else "review",
    }


def _local_frame(coords: torch.Tensor, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    n_res = int(coords.shape[0])
    if n_res <= 1:
        tangent = torch.tensor([1.0, 0.0, 0.0], dtype=torch.float32)
    elif index == 0:
        tangent = coords[1] - coords[0]
    elif index == n_res - 1:
        tangent = coords[-1] - coords[-2]
    else:
        tangent = coords[index + 1] - coords[index - 1]
    tangent = _unit(tangent.float(), torch.tensor([1.0, 0.0, 0.0]))
    ref = torch.tensor([0.0, 0.0, 1.0], dtype=torch.float32)
    if float(torch.linalg.norm(torch.cross(tangent, ref, dim=0)).item()) < 1e-4:
        ref = torch.tensor([0.0, 1.0, 0.0], dtype=torch.float32)
    normal = _unit(torch.cross(tangent, ref, dim=0), torch.tensor([0.0, 1.0, 0.0]))
    binormal = _unit(torch.cross(tangent, normal, dim=0), torch.tensor([0.0, 0.0, 1.0]))
    return tangent, normal, binormal


def _atom_line(
    serial: int,
    atom_name: str,
    resname: str,
    chain_id: str,
    resseq: int,
    coord: torch.Tensor,
    b_factor: float,
    element: str,
) -> str:
    x, y, z = [float(value) for value in coord.tolist()]
    return (
        f"ATOM  {serial:5d} {atom_name:<4} {resname:>3} {chain_id:1}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{float(b_factor):6.2f}          {element:>2}  "
    )


def write_raw_pdb(path_like: str | Path, target_id: str, chain_results: list[ChainResult], *, emit_backbone_atoms: bool = False) -> int:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"REMARK CASP17 INTERNAL PHYSICS BASELINE TARGET {target_id}",
        "REMARK SOURCE INTERNAL TORCH COARSE-GRAIN ENSEMBLE; NO EXTERNAL PREDICTOR OR TEMPLATE STRUCTURE",
    ]
    if emit_backbone_atoms:
        lines.append("REMARK BACKBONE_ATOMS CA-ANCHORED COMPACT PSEUDO-BACKBONE; NOT ALL-ATOM REFINEMENT")
    serial = 1
    for result in chain_results:
        coords = result.coords.detach().cpu().float()
        confidence = result.confidence.detach().cpu().float()
        seq = result.chain.sequence
        for index, aa in enumerate(seq):
            ca = coords[index]
            resname = AA1_TO_3.get(aa, "UNK")
            b_factor = float(confidence[index].item())
            if emit_backbone_atoms:
                tangent, normal, binormal = _local_frame(coords, index)
                atoms = [
                    ("N", ca - 0.10 * tangent + 0.04 * normal, "N"),
                    ("CA", ca, "C"),
                    ("C", ca + 0.10 * tangent + 0.04 * normal, "C"),
                    ("O", ca + 0.12 * tangent + 0.08 * normal, "O"),
                ]
                if aa != "G":
                    atoms.append(("CB", ca + 0.12 * binormal - 0.03 * tangent, "C"))
            else:
                atoms = [("CA", ca, "C")]
            for atom_name, atom_coord, element in atoms:
                lines.append(_atom_line(serial, atom_name, resname, result.chain.chain_id, index + 1, atom_coord, b_factor, element))
                serial += 1
        lines.append(f"TER   {serial:5d}      {AA1_TO_3.get(seq[-1], 'UNK'):>3} {result.chain.chain_id:1}{len(seq):4d}")
        serial += 1
    lines.append("END")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return serial - 1


def _ranked_clone(result: ChainResult, rank_index: int) -> ChainResult:
    coords = result.ranked_coords[rank_index] if rank_index < len(result.ranked_coords) else result.coords.detach().cpu().float()
    confidence = (
        result.ranked_confidences[rank_index]
        if rank_index < len(result.ranked_confidences)
        else result.confidence.detach().cpu().float()
    )
    energy = result.ranked_energies[rank_index] if rank_index < len(result.ranked_energies) else result.energy
    metrics = _chain_metrics(coords, confidence, result.secondary, float(energy), result.chain.sequence)
    return ChainResult(
        chain=result.chain,
        coords=coords.clone(),
        confidence=confidence.clone(),
        energy=float(energy),
        ensemble_size=result.ensemble_size,
        secondary=result.secondary,
        metrics=metrics,
        ranked_coords=[],
        ranked_confidences=[],
        ranked_energies=[],
    )


def write_ranked_raw_pdbs(
    dir_like: str | Path,
    target_id: str,
    chain_results: list[ChainResult],
    *,
    count: int,
    emit_backbone_atoms: bool = False,
    docking_steps: int = 0,
    seed: int = 0,
    device: torch.device | None = None,
) -> list[dict[str, Any]]:
    out_dir = _resolve(dir_like)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    rank_count = max(0, min(5, int(count)))
    for rank_index in range(rank_count):
        ranked_results = [_ranked_clone(result, rank_index) for result in chain_results]
        if len(ranked_results) > 1 and int(docking_steps) > 0 and device is not None:
            dock_chains(ranked_results, steps=int(docking_steps), seed=int(seed) + rank_index * 1009, device=device)
        out_pdb = out_dir / f"{target_id}_model_{rank_index + 1}.pdb"
        atom_or_ter_count = write_raw_pdb(out_pdb, target_id, ranked_results, emit_backbone_atoms=emit_backbone_atoms)
        energies = [float(result.energy) for result in ranked_results]
        confidences = [
            float(result.confidence.detach().cpu().float().mean().item())
            for result in ranked_results
            if result.confidence.numel()
        ]
        rows.append(
            {
                "rank": rank_index + 1,
                "raw_pdb": _artifact(out_pdb),
                "atom_or_ter_count": atom_or_ter_count,
                "chain_count": len(ranked_results),
                "energy_sum": round(sum(energies), 3),
                "confidence_mean": round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
            }
        )
    return rows


def _gpu_probe() -> dict[str, Any]:
    try:
        available = bool(torch.cuda.is_available())
        device_count = int(torch.cuda.device_count()) if available else 0
        names = [str(torch.cuda.get_device_name(index)) for index in range(device_count)]
        return {
            "torch_present": True,
            "cuda_available": available,
            "gpu_detected": available,
            "device_count": device_count,
            "device_names": names,
            "gpu_names": names,
            "torch_version": _text(getattr(torch, "__version__", "")),
        }
    except Exception as exc:  # noqa: BLE001 - runtime evidence should preserve probe failure.
        return {
            "torch_present": True,
            "cuda_available": False,
            "gpu_detected": False,
            "device_count": 0,
            "device_names": [],
            "gpu_names": [],
            "torch_version": _text(getattr(torch, "__version__", "")),
            "error": str(exc)[:300],
        }


def _select_device(device_arg: str, *, allow_cpu: bool) -> tuple[torch.device | None, dict[str, Any], list[dict[str, str]]]:
    gpu = _gpu_probe()
    requested = _text(device_arg).lower() or "auto"
    blockers: list[dict[str, str]] = []
    if requested == "auto":
        if gpu.get("cuda_available") is True:
            return torch.device("cuda"), gpu, blockers
        if allow_cpu:
            return torch.device("cpu"), gpu, blockers
        blockers.append(_blocker("gpu_required_for_internal_physics", "Internal CASP17 generation requires GPU evidence unless --allow-cpu is set for tests/smoke."))
        return None, gpu, blockers
    if requested in {"cuda", "gpu"}:
        if gpu.get("cuda_available") is True:
            return torch.device("cuda"), gpu, blockers
        blockers.append(_blocker("requested_gpu_unavailable", "Requested CUDA/ROCm torch device is unavailable."))
        return None, gpu, blockers
    if requested == "cpu":
        if allow_cpu:
            return torch.device("cpu"), gpu, blockers
        blockers.append(_blocker("cpu_not_allowed", "CPU execution is only allowed with --allow-cpu for tests/smoke artifacts."))
        return None, gpu, blockers
    blockers.append(_blocker("unsupported_device", f"Unsupported device `{device_arg}`."))
    return None, gpu, blockers


def _preset_values(args: argparse.Namespace) -> tuple[int, int, int, int]:
    preset = _text(args.quality_preset) or "casp17_quality"
    if preset == "smoke":
        ensemble_default, steps_default, max_pairs_default, docking_default = 3, 35, 256, 35
    elif preset == "fast":
        ensemble_default, steps_default, max_pairs_default, docking_default = 8, 400, 1800, 120
    else:
        ensemble_default, steps_default, max_pairs_default, docking_default = 32, 2500, 6000, 240
    ensemble_size = int(args.ensemble_size) if int(args.ensemble_size) > 0 else ensemble_default
    steps = int(args.steps) if int(args.steps) > 0 else steps_default
    max_pairs = int(args.max_pairs) if int(args.max_pairs) > 0 else max_pairs_default
    docking_steps = int(args.docking_steps) if int(args.docking_steps) >= 0 else docking_default
    return ensemble_size, steps, max_pairs, docking_steps


def build_prediction(args: argparse.Namespace) -> dict[str, Any]:
    target_id = _text(args.target_id).upper()
    fasta = _resolve(args.fasta)
    out_dir = _resolve(args.out_dir or f"runs/casp17_prediction_jobs_current/{target_id}")
    raw_pdb = _resolve(args.raw_pdb or out_dir / f"{target_id}_model_1.pdb")
    runtime_json = _resolve(args.runtime_json or out_dir / "backend_runtime.json")
    metrics_json = _resolve(args.metrics_json or out_dir / "internal_physics_metrics.json")
    ranked_raw_dir = _resolve(args.ranked_raw_dir) if _text(args.ranked_raw_dir) else out_dir / "ranked_raw_models"
    out_dir.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, str]] = []

    if not target_id:
        blockers.append(_blocker("missing_target_id", "Target id is required."))
    if not fasta.exists():
        blockers.append(_blocker("fasta_missing", "Target FASTA file is missing."))
    device, gpu, device_blockers = _select_device(args.device, allow_cpu=bool(args.allow_cpu))
    blockers.extend(device_blockers)

    chains: list[FastaChain] = []
    if not blockers:
        try:
            chains = parse_fasta(fasta)
        except Exception as exc:  # noqa: BLE001 - keep fail-closed packet.
            blockers.append(_blocker("fasta_parse_failed", f"{type(exc).__name__}: {exc}"))

    ensemble_size, steps, max_pairs, docking_steps = _preset_values(args)
    started_at = ""
    finished_at = ""
    chain_results: list[ChainResult] = []
    atom_or_ter_count = 0
    ranked_raw_rows: list[dict[str, Any]] = []
    if not blockers and device is not None:
        started_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        base_seed = int(args.seed)
        for index, chain in enumerate(chains):
            chain_results.append(
                predict_chain(
                    chain,
                    ensemble_size=ensemble_size,
                    steps=steps,
                    device=device,
                    seed=base_seed + index * 100003,
                    max_pairs=max_pairs,
                )
            )
        dock_chains(chain_results, steps=docking_steps, seed=base_seed + 777, device=device)
        assembly = assembly_metrics(chain_results)
        atom_or_ter_count = write_raw_pdb(raw_pdb, target_id, chain_results, emit_backbone_atoms=bool(args.emit_backbone_atoms))
        if int(args.ranked_raw_count) > 0:
            ranked_raw_rows = write_ranked_raw_pdbs(
                ranked_raw_dir,
                target_id,
                chain_results,
                count=int(args.ranked_raw_count),
                emit_backbone_atoms=bool(args.emit_backbone_atoms),
                docking_steps=docking_steps,
                seed=base_seed + 9001,
                device=device,
            )
        finished_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    else:
        assembly = assembly_metrics(chain_results)

    residue_count = sum(len(chain.sequence) for chain in chains)
    chain_rows = [
        {
            "chain_id": result.chain.chain_id,
            "header": result.chain.header,
            "sequence_length": len(result.chain.sequence),
            **result.metrics,
        }
        for result in chain_results
    ]
    metrics_payload = {
        "summary": {
            "packet_type": "casp17_internal_physics_metrics",
            "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "target_id": target_id,
            "chain_count": len(chains),
            "residue_count": residue_count,
            "ensemble_size": ensemble_size,
            "steps": steps,
            "max_pairs": max_pairs,
            "docking_steps": docking_steps,
            "raw_pdb": _artifact(raw_pdb),
            "ranked_raw_dir": _artifact(ranked_raw_dir) if ranked_raw_rows else "",
            "ranked_raw_count": len(ranked_raw_rows),
            "interface_plausibility_status": assembly.get("interface_plausibility_status", ""),
            "interchain_ca_contact_count_12A": assembly.get("interchain_ca_contact_count_12A", 0),
            "interchain_ca_clash_count_3A": assembly.get("interchain_ca_clash_count_3A", 0),
            "claim_boundary": "Internal coarse-grain physics baseline metrics only; not true CASP accuracy evidence.",
        },
        "chains": chain_rows,
        "assembly": assembly,
        "ranked_raw_models": ranked_raw_rows,
    }
    if not blockers:
        _write_json(metrics_json, metrics_payload)

    runtime_payload = {
        "summary": {
            "packet_type": "casp17_internal_physics_runtime",
            "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "target_id": target_id,
            "backend_kind": "internal_physics",
            "job_status": "completed" if not blockers else "blocked",
            "started_at_local": started_at,
            "finished_at_local": finished_at,
            "device": str(device) if device is not None else "",
            "gpu_detected": bool(gpu.get("gpu_detected")),
            "gpu_names": gpu.get("gpu_names", []),
            "torch_version": gpu.get("torch_version", ""),
            "raw_pdb": _artifact(raw_pdb),
            "raw_pdb_exists": raw_pdb.exists(),
            "ranked_raw_dir": _artifact(ranked_raw_dir) if ranked_raw_rows else "",
            "ranked_raw_count": len(ranked_raw_rows),
            "metrics_json": _artifact(metrics_json),
            "chain_count": len(chains),
            "residue_count": residue_count,
            "ensemble_size": ensemble_size,
            "steps": steps,
            "interface_plausibility_status": assembly.get("interface_plausibility_status", ""),
            "interchain_ca_contact_count_12A": assembly.get("interchain_ca_contact_count_12A", 0),
            "interchain_ca_clash_count_3A": assembly.get("interchain_ca_clash_count_3A", 0),
            "allow_cpu": bool(args.allow_cpu),
            "claim_boundary": "Internal torch/coarse-grain physics runtime evidence only; no external predictor, template, public structure, or official CASP submission evidence.",
        },
        "runtime": {
            "backend_kind": "internal_physics",
            "gpu_detected": bool(gpu.get("gpu_detected")),
            "gpu_names": gpu.get("gpu_names", []),
            "torch_cuda": {
                "torch_present": bool(gpu.get("torch_present")),
                "cuda_available": bool(gpu.get("cuda_available")),
                "device_count": int(gpu.get("device_count", 0) or 0),
                "device_names": gpu.get("device_names", []),
                "torch_version": gpu.get("torch_version", ""),
            },
        },
    }
    _write_json(runtime_json, runtime_payload)

    summary = {
        "packet_type": "casp17_internal_physics_baseline_predictor",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "target_id": target_id,
        "predictor_status": "pass" if not blockers else "blocked",
        "backend_kind": "internal_physics",
        "fasta": _artifact(fasta),
        "out_dir": _artifact(out_dir),
        "raw_pdb": _artifact(raw_pdb),
        "runtime_json": _artifact(runtime_json),
        "metrics_json": _artifact(metrics_json),
        "raw_pdb_exists": raw_pdb.exists(),
        "ranked_raw_dir": _artifact(ranked_raw_dir) if ranked_raw_rows else "",
        "ranked_raw_count": len(ranked_raw_rows),
        "atom_or_ter_record_count": atom_or_ter_count,
        "device": runtime_payload["summary"]["device"],
        "gpu_detected": bool(gpu.get("gpu_detected")),
        "gpu_names": gpu.get("gpu_names", []),
        "chain_count": len(chains),
        "residue_count": residue_count,
        "ensemble_size": ensemble_size,
        "steps": steps,
        "blocker_count": len(blockers),
        "claim_boundary": "CASP17 internal physics baseline generation only; not external predictor output, public/template structure, accepted submission, or accuracy claim.",
    }
    return {"summary": summary, "blockers": blockers, "chains": chain_rows}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a CASP17 raw PDB using only the repo's internal torch/coarse-grain physics baseline.")
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--fasta", required=True)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--raw-pdb", default="")
    parser.add_argument("--runtime-json", default="")
    parser.add_argument("--metrics-json", default="")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--ensemble-size", type=int, default=0)
    parser.add_argument("--steps", type=int, default=0)
    parser.add_argument("--quality-preset", choices=["casp17_quality", "fast", "smoke"], default="casp17_quality")
    parser.add_argument("--max-pairs", type=int, default=0)
    parser.add_argument("--docking-steps", type=int, default=-1)
    parser.add_argument("--seed", type=int, default=17017)
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--emit-backbone-atoms", action="store_true")
    parser.add_argument("--ranked-raw-dir", default="")
    parser.add_argument("--ranked-raw-count", type=int, default=0)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_prediction(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, [payload["summary"]])
    _write_md(args.out_md, payload)
    if payload["blockers"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
