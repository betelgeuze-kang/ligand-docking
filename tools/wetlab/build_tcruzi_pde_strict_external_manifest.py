#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from tools.generate_openmm_ca_md_references import _simulate_target

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TARGET = "T. cruzi PDE"
DEFAULT_NATIVE_PDB = "data/public_structures/selected_allatom_native_v1/t_cruzi_pde_pdb_3V94.pdb"
DEFAULT_REGISTRATION_JSON = "runs/strict_release_target_registration_packet_current.json"
DEFAULT_OUT_DIR = "runs/tcruzi_pde_strict_external_openmm"
DEFAULT_OUT_MANIFEST = "runs/tcruzi_pde_strict_external_manifest_current.csv"
DEFAULT_OUT_JSON = "runs/tcruzi_pde_strict_external_manifest_current.json"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _load_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _registration_summary(path_like: str | Path) -> dict[str, Any]:
    payload = _load_json(path_like)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    registry = (
        payload.get("strict_release_registry")
        if isinstance(payload.get("strict_release_registry"), dict)
        else {}
    )
    return {
        "ready": bool(summary.get("registration_ready")),
        "canonical_chain": _text(registry.get("canonical_chain")),
        "selected_chain_ca_count": int(registry.get("selected_chain_ca_count") or 0),
    }


def _extract_chain_atom_lines(native_pdb: Path, chain_id: str) -> list[str]:
    lines: list[str] = []
    with native_pdb.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.startswith("ATOM  "):
                continue
            if (line[21].strip() or "_") == chain_id:
                lines.append(line.rstrip("\n"))
    return lines


def _ca_count(lines: list[str]) -> int:
    return sum(1 for line in lines if line[12:16].strip() == "CA")


def _write_chain_pdb(path: Path, atom_lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(atom_lines + ["END"]) + "\n", encoding="utf-8")


def _validate_traj(path: Path, *, expected_ca_count: int) -> None:
    coords = np.load(path, mmap_mode="r")
    if coords.ndim == 3:
        actual = int(coords.shape[1])
    elif coords.ndim == 2:
        actual = int(coords.shape[0])
    else:
        raise ValueError(f"invalid_strict_external_coordinate_shape:{coords.shape}")
    if actual != int(expected_ca_count):
        raise ValueError(f"strict_external_n_atoms_mismatch:expected={expected_ca_count},actual={actual}")


def _manifest_row(row: dict[str, Any], *, chain_id: str) -> dict[str, Any]:
    return {
        "target": row.get("target", DEFAULT_TARGET),
        "path": row.get("path", ""),
        "engine": row.get("engine", "openmm"),
        "label": row.get("label", ""),
        "frame": row.get("frame", -1),
        "key": row.get("key", ""),
        "source_engine": row.get("source_engine", "openmm"),
        "source_path": row.get("source_path", row.get("path", "")),
        "source_label": row.get("source_label", ""),
        "notes": row.get("notes", "REAL_MD_OPENMM_CA_BEAD"),
        "representation": row.get("representation", "ca"),
        "bead_order": row.get("bead_order", "ca_only"),
        "canonical_chain": chain_id,
        "n_res": row.get("n_res", ""),
        "n_atoms": row.get("n_atoms", ""),
        "beads_per_residue": row.get("beads_per_residue", 1.0),
        "temperature_k": row.get("temperature_k", ""),
        "friction_ps": row.get("friction_ps", ""),
        "dt_ps": row.get("dt_ps", ""),
        "steps": row.get("steps", ""),
        "save_stride": row.get("save_stride", ""),
        "platform": row.get("platform", ""),
        "seed": row.get("seed", ""),
    }


def run_build(args: argparse.Namespace) -> dict[str, Any]:
    native_pdb = _resolve(args.native_pdb)
    registration = _registration_summary(args.registration_json)
    if not registration["ready"]:
        raise ValueError("target_registration_not_ready")
    chain_id = registration["canonical_chain"]
    if not chain_id:
        raise ValueError("canonical_chain_missing")
    expected_ca_count = int(registration["selected_chain_ca_count"])
    if expected_ca_count <= 0:
        raise ValueError("selected_chain_ca_count_missing")

    atom_lines = _extract_chain_atom_lines(native_pdb, chain_id)
    actual_ca_count = _ca_count(atom_lines)
    if actual_ca_count != expected_ca_count:
        raise ValueError(
            f"canonical_chain_ca_count_mismatch:expected={expected_ca_count},actual={actual_ca_count}"
        )

    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    chain_pdb = out_dir / f"tcruzi_pde_3v94_chain_{chain_id}.pdb"
    out_npy = out_dir / f"tcruzi_pde_chain_{chain_id}_openmm_ca_md.npy"
    _write_chain_pdb(chain_pdb, atom_lines)

    row = _simulate_target(
        target=DEFAULT_TARGET,
        pdb_path=str(chain_pdb),
        out_npy=str(out_npy),
        out_ca_projection_npy=None,
        steps=int(args.steps),
        save_stride=int(args.save_stride),
        temperature_k=float(args.temperature_k),
        friction_ps=float(args.friction_ps),
        dt_ps=float(args.dt_ps),
        sigma_nm=float(args.sigma_nm),
        epsilon_kj=float(args.epsilon_kj),
        bond_k_kj_nm2=float(args.bond_k_kj_nm2),
        angle_k_kj_rad2=float(args.angle_k_kj_rad2),
        cutoff_nm=float(args.cutoff_nm),
        platform_name=str(args.platform),
        seed=int(args.seed),
        minimize_iters=int(args.minimize_iters),
        representation="ca",
        sc_distance_nm=0.15,
        ca_mass_amu=float(args.ca_mass_amu),
        sc_mass_amu=45.0,
        sc_sigma_scale=0.95,
        sc_epsilon_scale=0.90,
        sidechain_bond_k_kj_nm2=2500.0,
        sidechain_angle_k_kj_rad2=35.0,
        exclude_local_sc_neighbors=True,
        save_ca_projection=False,
    )
    _validate_traj(out_npy, expected_ca_count=expected_ca_count)

    manifest = _resolve(args.out_manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest_row = _manifest_row(row, chain_id=chain_id)
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_row.keys()))
        writer.writeheader()
        writer.writerow(manifest_row)

    payload = {
        "schema": "tcruzi_pde_strict_external_manifest.v1",
        "summary": {
            "manifest_ready": True,
            "target": DEFAULT_TARGET,
            "canonical_chain": chain_id,
            "expected_ca_count": expected_ca_count,
            "actual_ca_count": actual_ca_count,
            "manifest_csv": str(manifest),
            "trajectory_npy": str(out_npy),
            "chain_pdb": str(chain_pdb),
        },
        "row": manifest_row,
        "safety": {
            "source_native_pdb": str(native_pdb),
            "uses_rescue_claim_manifest": False,
            "fake_pass_allowed": False,
        },
    }
    out_json = _resolve(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a real OpenMM CA strict external manifest for registered T. cruzi PDE chain B."
    )
    parser.add_argument("--native-pdb", default=DEFAULT_NATIVE_PDB)
    parser.add_argument("--registration-json", default=DEFAULT_REGISTRATION_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-manifest", default=DEFAULT_OUT_MANIFEST)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--save-stride", type=int, default=100)
    parser.add_argument("--temperature-k", type=float, default=300.0)
    parser.add_argument("--friction-ps", type=float, default=1.0)
    parser.add_argument("--dt-ps", type=float, default=0.004)
    parser.add_argument("--sigma-nm", type=float, default=0.38)
    parser.add_argument("--epsilon-kj", type=float, default=0.50)
    parser.add_argument("--bond-k-kj-nm2", type=float, default=2500.0)
    parser.add_argument("--angle-k-kj-rad2", type=float, default=40.0)
    parser.add_argument("--cutoff-nm", type=float, default=1.2)
    parser.add_argument("--platform", default="")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--minimize-iters", type=int, default=100)
    parser.add_argument("--ca-mass-amu", type=float, default=100.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_build(args)
    print(f"Wrote: {payload['summary']['manifest_csv']}")
    print(f"Wrote: {args.out_json}")
    print(f"manifest_ready={payload['summary']['manifest_ready']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
