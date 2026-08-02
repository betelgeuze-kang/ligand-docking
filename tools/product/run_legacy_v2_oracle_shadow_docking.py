#!/usr/bin/env python3
"""Run legacy / V2 / offline-oracle surfaces on one canonical prepared input (P1-1, P1-9).

The canonical preparation packet, the engine adapters, the common result bundle,
and the shadow record all existed as libraries, but no entry point actually ran
them, so nothing outside the test suite proved the three engine surfaces consume
the same prepared input. This tool is that entry point:

    receptor PDB + ligand SMILES
        -> Canonical Preparation Service (one packet)
        -> legacy_product adapter (active)
        -> engine_v2 adapter (shadow)
        -> external_oracle adapter (offline baseline, abstains when absent)
        -> ShadowExecutionRecord + pairwise deltas

It is offline and read-only with respect to external state: it never downloads or
installs a docking binary. A missing offline baseline is recorded as an
abstention, and a blocked packet produces a blocked record rather than a partial
comparison, so a shadow delta can never be reported from unequal inputs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

from betelgeuze_engine.scoring.local_refinement import RefinementParameters
from betelgeuze_product.engine_adapters import (
    AdapterBudget,
    available_external_oracle_binaries,
    run_engine_v2_adapter,
    run_external_oracle_adapter,
    run_legacy_adapter,
)
from betelgeuze_product.preparation_service import build_preparation_packet
from betelgeuze_product.shadow_execution import (
    ACTIVE_SURFACE,
    build_shadow_execution_record,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUT_JSON = "runs/legacy_v2_oracle_shadow_docking_run_current.json"
DEFAULT_OUT_MD = "runs/legacy_v2_oracle_shadow_docking_run_current.md"
DEFAULT_BENCHMARK_PROFILE = "internal_diagnostic_profile"
DEFAULT_CLAIM_SCOPE = "restricted_internal"

CLAIM_BOUNDARY = (
    "Diagnostic shadow execution on operator-supplied inputs. The legacy surface is active; engine_v2 and the "
    "external oracle are shadow-only and can never be promoted. Pairwise deltas are single-case diagnostics on "
    "one prepared input, not a benchmark result, an accuracy claim, or a winner declaration."
)


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _receptor_payload(receptor_pdb: str, target_id: str) -> dict[str, Any]:
    path = _resolve(receptor_pdb)
    if not path.is_file():
        raise SystemExit(f"receptor_pdb_not_found:{path}")
    return {
        "pdb_content": path.read_text(encoding="utf-8", errors="ignore"),
        "target_id": target_id,
    }


def run_shadow_docking(
    *,
    receptor_pdb: str,
    ligand_smiles: str,
    target_id: str = "",
    ligand_id: str = "",
    max_conformers: int = 6,
    seed: int = 7,
    candidate_budget: int | None = None,
    benchmark_profile: str = DEFAULT_BENCHMARK_PROFILE,
    claim_scope: str = DEFAULT_CLAIM_SCOPE,
) -> dict[str, Any]:
    """Prepare once, run all three surfaces, and return the shadow record payload."""

    started = time.perf_counter()
    packet = build_preparation_packet(
        receptor_payload=_receptor_payload(receptor_pdb, target_id),
        ligand_smiles=ligand_smiles,
        target_id=target_id,
        ligand_id=ligand_id,
        root=ROOT,
        max_conformers=int(max_conformers),
        seed=int(seed),
    )
    preparation_seconds = time.perf_counter() - started

    # One budget object for every surface: an unequal budget is the classic way a
    # shadow comparison silently stops being a comparison.
    shared_budget = (
        None if candidate_budget is None else AdapterBudget(candidate_budget=int(candidate_budget))
    )
    v2_budget = (
        None
        if candidate_budget is None
        else AdapterBudget(
            candidate_budget=int(candidate_budget),
            refinement=RefinementParameters(),
        )
    )

    surface_runtimes: dict[str, float] = {}

    def _timed(label: str, fn: Any, **kwargs: Any) -> Any:
        mark = time.perf_counter()
        bundle = fn(packet, **kwargs)
        surface_runtimes[label] = round(time.perf_counter() - mark, 6)
        return bundle

    common = {"benchmark_profile": benchmark_profile, "claim_scope": claim_scope}
    legacy = _timed("legacy_product", run_legacy_adapter, budget=shared_budget, **common)
    engine_v2 = _timed("engine_v2", run_engine_v2_adapter, budget=v2_budget, **common)
    oracle = _timed("external_oracle", run_external_oracle_adapter, budget=v2_budget, **common)

    record = build_shadow_execution_record(
        packet=packet,
        bundles=[legacy, engine_v2, oracle],
        served_engine_surface=ACTIVE_SURFACE,
    )
    payload = record.to_dict()
    payload["generated_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    payload["inputs"] = {
        "receptor_pdb": str(receptor_pdb),
        "ligand_smiles": str(ligand_smiles),
        "target_id": str(target_id),
        "ligand_id": str(ligand_id),
        "max_conformers": int(max_conformers),
        "seed": int(seed),
        "candidate_budget": None if candidate_budget is None else int(candidate_budget),
        "benchmark_profile": str(benchmark_profile),
        "claim_scope": str(claim_scope),
    }
    payload["preparation"] = {
        "ready": packet.ready,
        "blockers": list(packet.blockers),
        "prepared_input_hash": packet.prepared_input_hash,
        "receptor_atom_count": int(packet.receptor.atom_count),
        "ligand_atom_count": int(packet.ligand.atom_count),
        "ligand_atom_element_count": len(packet.ligand.atom_elements),
        "conformer_count": len(packet.ligand.conformer_coordinates),
        "conformer_coordinates_carried": bool(packet.ligand.conformer_coordinates),
        "preparation_seconds": round(preparation_seconds, 6),
    }
    payload["surface_runtime_seconds"] = surface_runtimes
    payload["offline_baseline"] = {
        "available_binaries": list(available_external_oracle_binaries()),
        "installs_binaries": False,
    }
    payload["claim_boundary"] = CLAIM_BOUNDARY
    return payload


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_markdown(path: str | Path, payload: dict[str, Any]) -> None:
    target = _resolve(path)
    lines = [
        "# Legacy / V2 / Oracle Shadow Docking Run",
        "",
        f"- generated_at_utc: {payload['generated_at_utc']}",
        f"- status: {payload['status']}",
        f"- prepared_input_hash: {payload['prepared_input_hash']}",
        f"- active_engine_surface: {payload['active_engine_surface']}",
        f"- claim_promotion_allowed: {payload['claim_promotion_allowed']}",
        f"- executed_surface_count: {payload['executed_surface_count']}",
        "",
        "## Surfaces",
        "",
        "| engine_surface | status | pose_count | top_score | abstained | runtime_s |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for surface, result in sorted(payload["results"].items()):
        poses = result["pose_ensemble"]["poses"]
        top = f"{poses[0]['total_score']:.6f}" if poses else "-"
        lines.append(
            "| %s | %s | %d | %s | %s | %s |"
            % (
                surface,
                result["status"],
                len(poses),
                top,
                result["uncertainty"].get("abstained"),
                payload["surface_runtime_seconds"].get(surface, "-"),
            )
        )
    lines += ["", "## Pairwise Deltas", "", "| left | right | left_top | right_top | delta |", "| --- | --- | --- | --- | --- |"]
    for delta in payload["pairwise_deltas"]:
        lines.append(
            "| %s | %s | %s | %s | %s |"
            % (
                delta["left_engine_surface"],
                delta["right_engine_surface"],
                delta["left_top_score"],
                delta["right_top_score"],
                delta["top_score_delta"],
            )
        )
    lines += ["", "## Claim Boundary", "", payload["claim_boundary"], ""]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run legacy/V2/oracle surfaces on one canonical prepared input."
    )
    parser.add_argument("--receptor-pdb", required=True)
    parser.add_argument("--ligand-smiles", required=True)
    parser.add_argument("--target-id", default="")
    parser.add_argument("--ligand-id", default="")
    parser.add_argument("--max-conformers", type=int, default=6)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--candidate-budget", type=int, default=None)
    parser.add_argument("--benchmark-profile", default=DEFAULT_BENCHMARK_PROFILE)
    parser.add_argument("--claim-scope", default=DEFAULT_CLAIM_SCOPE)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_shadow_docking(
        receptor_pdb=args.receptor_pdb,
        ligand_smiles=args.ligand_smiles,
        target_id=args.target_id,
        ligand_id=args.ligand_id,
        max_conformers=args.max_conformers,
        seed=args.seed,
        candidate_budget=args.candidate_budget,
        benchmark_profile=args.benchmark_profile,
        claim_scope=args.claim_scope,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "prepared_input_hash": payload["prepared_input_hash"],
                "executed_surface_count": payload["executed_surface_count"],
                "pairwise_delta_count": len(payload["pairwise_deltas"]),
                "violations": payload["violations"],
                "offline_baseline_binaries": payload["offline_baseline"]["available_binaries"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "shadow_execution_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
