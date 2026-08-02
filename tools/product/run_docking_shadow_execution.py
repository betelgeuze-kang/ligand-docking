#!/usr/bin/env python3
"""Run one case through the canonical packet and every engine surface (P1-9, §17).

Until now the §17 pieces existed but nothing executed them end to end, so no
artifact proved that legacy and V2 actually consumed the same prepared input.
This tool is that execution path::

    receptor + ligand
        -> Canonical Preparation Service   (preparation_service)
        -> legacy_product adapter          (active)
        -> engine_v2 adapter               (shadow)
        -> external_oracle record          (offline, operator-supplied)
        -> shadow execution record + pairwise deltas

What it does not do is as important as what it does:

- it never runs Vina/GNINA/Smina. The oracle side is *recorded* from operator
  rows produced offline on licensed binaries;
- it never fetches a structure or a dataset. Receptor and ligand come from the
  caller;
- it never promotes a result. The legacy surface stays active by construction and
  the record is diagnostic evidence for one case, not a benchmark claim.

A case whose preparation is blocked still emits a complete artifact with a
counted failure, so a hard case cannot quietly drop out of a denominator.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from betelgeuze_product.engine_adapters import (  # noqa: E402
    ENGINE_V2_BUDGET,
    LEGACY_BUDGET,
    AdapterBudget,
    run_engine_v2_adapter,
    run_legacy_adapter,
)
from betelgeuze_product.external_oracle_bundle import (  # noqa: E402
    build_external_oracle_run,
    record_external_oracle_bundle,
)
from betelgeuze_product.preparation_service import build_preparation_packet  # noqa: E402
from betelgeuze_product.shadow_execution import (  # noqa: E402
    ACTIVE_SURFACE,
    build_shadow_execution_record,
)
from betelgeuze_engine.scoring.local_refinement import RefinementParameters  # noqa: E402

DEFAULT_OUT_JSON = "runs/docking_shadow_execution_current.json"
DEFAULT_OUT_CSV = "runs/docking_shadow_execution_current.csv"
DEFAULT_OUT_MD = "runs/docking_shadow_execution_current.md"

PACKET_TYPE = "docking_shadow_execution"
SCHEMA_VERSION = "docking_shadow_execution_run_v1"

STATUS_READY = "docking_shadow_execution_ready"
STATUS_BLOCKED = "blocked_docking_shadow_execution"

CLAIM_BOUNDARY = (
    "Single-case shadow execution over the canonical preparation packet. It runs the internal legacy and V2 "
    "surfaces offline at an identical candidate budget and records an operator-supplied offline oracle result. "
    "It does not run Vina/GNINA/Smina, download datasets, fetch structures, emit customer poses, promote any "
    "claim, or mutate external state. One case is diagnostic evidence, not a benchmark result."
)

READ_ONLY_FLAGS = {
    "datasets_downloaded": False,
    "structures_fetched": False,
    "baseline_executed_in_process": False,
    "customer_results_emitted": False,
    "claim_promotion_allowed": False,
    "external_state_mutated": False,
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path)


def _read_receptor_payload(
    *, pdb_path: str, target_id: str
) -> tuple[dict[str, Any], list[str]]:
    """Load the receptor exactly as given; a missing file is a named blocker."""

    text = str(pdb_path or "").strip()
    if not text:
        return {}, ["receptor_pdb_path_missing"]
    candidate = _resolve(text)
    if not candidate.is_file():
        return {}, [f"receptor_pdb_not_found:{candidate.name}"]
    return (
        {
            "pdb_content": candidate.read_text(encoding="utf-8", errors="ignore"),
            "target_id": target_id,
        },
        [],
    )


def _read_oracle_inputs(
    *, receipt_json: str, rows_csv: str
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Read the operator's offline oracle receipt and pose rows.

    Absent inputs are not an error here: the two internal surfaces still form a
    valid pair. The shadow record reports which surfaces were present.
    """

    blockers: list[str] = []
    receipt: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    receipt_text = str(receipt_json or "").strip()
    if receipt_text:
        path = _resolve(receipt_text)
        if not path.is_file():
            blockers.append(f"oracle_receipt_json_not_found:{path.name}")
        else:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                blockers.append(f"oracle_receipt_json_unparseable:{exc.msg}")
                payload = {}
            if isinstance(payload, dict):
                receipt = dict(payload)
            else:
                blockers.append("oracle_receipt_json_not_an_object")
    rows_text = str(rows_csv or "").strip()
    if rows_text:
        path = _resolve(rows_text)
        if not path.is_file():
            blockers.append(f"oracle_rows_csv_not_found:{path.name}")
        else:
            with path.open("r", encoding="utf-8", newline="") as handle:
                rows = [dict(row) for row in csv.DictReader(handle)]
    return receipt, rows, blockers


def _bundle_rows(record_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """One CSV row per reported pose per surface, plus a row for a blocked surface."""

    rows: list[dict[str, Any]] = []
    for surface, bundle in sorted((record_payload.get("results") or {}).items()):
        poses = ((bundle.get("pose_ensemble") or {}).get("poses")) or []
        denominator = bundle.get("failure_denominator") or {}
        budget = bundle.get("runtime_budget") or {}
        base = {
            "engine_surface": surface,
            "engine_version": bundle.get("engine_version", ""),
            "bundle_status": bundle.get("status", ""),
            "prepared_input_hash": (bundle.get("prepared_input_hashes") or {}).get(
                "prepared_input_hash", ""
            ),
            "candidate_budget": budget.get("candidate_budget", ""),
            "active_surface": surface == ACTIVE_SURFACE,
            "shadow_only": surface != ACTIVE_SURFACE,
            "attempted_case_count": denominator.get("attempted_case_count", ""),
            "scored_case_count": denominator.get("scored_case_count", ""),
            "failed_case_count": denominator.get("failed_case_count", ""),
            "bundle_blockers": ",".join(bundle.get("blockers") or []),
        }
        if not poses:
            rows.append({**base, "pose_id": "", "pose_rank": "", "total_score": ""})
            continue
        for pose in poses:
            rows.append(
                {
                    **base,
                    "pose_id": pose.get("pose_id", ""),
                    "pose_rank": pose.get("rank", ""),
                    "total_score": pose.get("total_score", ""),
                    "conformer_id": pose.get("conformer_id", ""),
                    "cluster_id": pose.get("cluster_id", ""),
                    "geometric_valid": pose.get("geometric_valid", ""),
                    "chemistry_valid": pose.get("chemistry_valid", ""),
                }
            )
    return rows


def _next_required_step(blockers: list[str], oracle_present: bool) -> str:
    """Name the single most useful next action for this case."""

    if blockers:
        if any(b.startswith("receptor_pdb") for b in blockers):
            return "Point --receptor-pdb at a readable receptor structure file."
        if any("prepared_input_not_ready" in b for b in blockers):
            return (
                "Preparation is blocked for this case; read the prepared-packet blockers. A macrocyclic "
                "ligand belongs in the unsupported lane rather than in this comparison."
            )
        return "Resolve the reported execution blockers: " + ",".join(blockers[:3])
    if not oracle_present:
        return (
            "Internal legacy-vs-V2 comparison is recorded. To close the P1-9 three-surface requirement, run "
            "the offline baseline on your licensed binaries and supply --oracle-receipt-json/--oracle-rows-csv."
        )
    return (
        "Three-surface shadow execution is recorded for this case. Scale it across the frozen benchmark suite "
        "before any accuracy statement."
    )


def run_docking_shadow_execution(
    *,
    receptor_pdb: str,
    ligand_smiles: str,
    target_id: str = "",
    ligand_id: str = "",
    case_id: str = "",
    max_conformers: int = 8,
    seed: int = 7,
    candidate_budget: int = 0,
    benchmark_profile: str = "internal_diagnostic_profile",
    claim_scope: str = "restricted_internal",
    oracle_receipt_json: str = "",
    oracle_rows_csv: str = "",
) -> dict[str, Any]:
    """Execute one case across every available engine surface."""

    input_blockers: list[str] = []
    receptor_payload, receptor_blockers = _read_receptor_payload(
        pdb_path=receptor_pdb, target_id=target_id
    )
    input_blockers.extend(receptor_blockers)
    smiles = str(ligand_smiles or "").strip()
    if not smiles:
        input_blockers.append("ligand_smiles_missing")
    oracle_receipt, oracle_rows, oracle_blockers = _read_oracle_inputs(
        receipt_json=oracle_receipt_json, rows_csv=oracle_rows_csv
    )
    input_blockers.extend(oracle_blockers)

    # Both internal surfaces must run at the same candidate budget, otherwise the
    # delta measures sampling depth instead of refinement.
    resolved_budget = int(candidate_budget or LEGACY_BUDGET.candidate_budget)
    legacy_budget = AdapterBudget(
        candidate_budget=resolved_budget,
        max_reported_poses=LEGACY_BUDGET.max_reported_poses,
    )
    v2_budget = AdapterBudget(
        candidate_budget=resolved_budget,
        max_reported_poses=ENGINE_V2_BUDGET.max_reported_poses,
        refinement=ENGINE_V2_BUDGET.refinement or RefinementParameters(),
    )

    summary: dict[str, Any] = {
        "packet_type": PACKET_TYPE,
        "schema_version": SCHEMA_VERSION,
        "case_id": str(case_id or ligand_id or "case_1"),
        "target_id": str(target_id),
        "ligand_id": str(ligand_id),
        "receptor_pdb": str(receptor_pdb),
        "candidate_budget": resolved_budget,
        "benchmark_profile": str(benchmark_profile),
        "claim_scope": str(claim_scope),
        "oracle_inputs_supplied": bool(oracle_receipt or oracle_rows),
        "active_engine_surface": ACTIVE_SURFACE,
        **READ_ONLY_FLAGS,
        "claim_boundary": CLAIM_BOUNDARY,
    }

    if input_blockers:
        # Fail before preparation: there is nothing to compare, and emitting a
        # partial record here would look like an executed case.
        unique = list(dict.fromkeys(input_blockers))
        summary.update(
            {
                "status": STATUS_BLOCKED,
                "ready": False,
                "prepared_input_hash": "",
                "executed_surface_count": 0,
                "blocker_count": len(unique),
                "blockers": unique,
                "next_required_step": _next_required_step(unique, bool(oracle_rows)),
            }
        )
        return {"summary": summary, "rows": [], "preparation_packet": {}, "shadow_execution": {}}

    packet = build_preparation_packet(
        receptor_payload=receptor_payload,
        ligand_smiles=smiles,
        target_id=target_id,
        ligand_id=ligand_id,
        root=ROOT,
        max_conformers=int(max_conformers),
        seed=int(seed),
    )

    bundles = [
        run_legacy_adapter(
            packet,
            budget=legacy_budget,
            benchmark_profile=benchmark_profile,
            claim_scope=claim_scope,
        ),
        run_engine_v2_adapter(
            packet,
            budget=v2_budget,
            benchmark_profile=benchmark_profile,
            claim_scope=claim_scope,
        ),
    ]
    if oracle_receipt or oracle_rows:
        bundles.append(
            record_external_oracle_bundle(
                packet,
                build_external_oracle_run(receipt=oracle_receipt, poses=oracle_rows),
                candidate_budget=resolved_budget,
                benchmark_profile=benchmark_profile,
                claim_scope=claim_scope,
            )
        )

    record = build_shadow_execution_record(packet=packet, bundles=bundles)
    record_payload = record.to_dict()
    packet_payload = packet.to_dict()

    blockers = list(
        dict.fromkeys(
            [
                *record_payload.get("violations", []),
                *[
                    f"{bundle.engine_surface}:{blocker}"
                    for bundle in bundles
                    for blocker in bundle.blockers
                ],
            ]
        )
    )
    ready = not blockers
    deltas = record_payload.get("pairwise_deltas") or []
    summary.update(
        {
            "status": STATUS_READY if ready else STATUS_BLOCKED,
            "ready": ready,
            "prepared_input_hash": packet.prepared_input_hash,
            "prepared_packet_ready": packet.ready,
            "prepared_packet_blockers": list(packet.blockers),
            "ligand_flexibility_lane": packet.ligand.flexibility_lane,
            "retained_conformer_count": len(packet.ligand.conformer_ids),
            "executed_surface_count": record_payload.get("executed_surface_count", 0),
            "engine_surfaces": sorted(record_payload.get("results") or {}),
            "shadow_result_surfaces": record_payload.get("shadow_result_surfaces", []),
            "comparison_comparable": bool(
                (record_payload.get("comparison") or {}).get("comparable")
            ),
            "pairwise_delta_count": len(deltas),
            "pairwise_deltas": deltas,
            "blocker_count": len(blockers),
            "blockers": blockers,
            "next_required_step": _next_required_step(blockers, bool(oracle_rows)),
        }
    )
    return {
        "summary": summary,
        "rows": _bundle_rows(record_payload),
        "preparation_packet": packet_payload,
        "shadow_execution": record_payload,
    }


def render_markdown(packet: dict[str, Any]) -> str:
    summary = packet.get("summary", {})
    lines = [
        "# Docking Shadow Execution (current)",
        "",
        "Generated packet. Re-run the builder to refresh; do not hand-edit.",
        "",
        f"- status: `{summary.get('status')}`",
        f"- case_id: `{summary.get('case_id')}`",
        f"- prepared_input_hash: `{summary.get('prepared_input_hash')}`",
        f"- active_engine_surface: `{summary.get('active_engine_surface')}`",
        f"- executed_surface_count: `{summary.get('executed_surface_count')}`",
        f"- candidate_budget: `{summary.get('candidate_budget')}`",
        f"- comparison_comparable: `{summary.get('comparison_comparable')}`",
        f"- pairwise_delta_count: `{summary.get('pairwise_delta_count')}`",
        f"- blocker_count: `{summary.get('blocker_count')}`",
        "",
        "## Pairwise Deltas",
        "",
    ]
    deltas = summary.get("pairwise_deltas") or []
    if deltas:
        lines.append("| left | right | left_top | right_top | delta |")
        lines.append("| --- | --- | --- | --- | --- |")
        for delta in deltas:
            lines.append(
                "| `{left}` | `{right}` | `{lt}` | `{rt}` | `{d}` |".format(
                    left=delta.get("left_engine_surface", ""),
                    right=delta.get("right_engine_surface", ""),
                    lt=delta.get("left_top_score", ""),
                    rt=delta.get("right_top_score", ""),
                    d=delta.get("top_score_delta", ""),
                )
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Blockers", ""])
    blockers = summary.get("blockers") or []
    if blockers:
        lines.extend(f"- `{blocker}`" for blocker in blockers)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Next Required Step",
            "",
            f"{summary.get('next_required_step', '')}",
            "",
            "## Claim Boundary",
            "",
            f"{summary.get('claim_boundary', '')}",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one docking case across the canonical packet and every engine surface."
    )
    parser.add_argument("--receptor-pdb", default="")
    parser.add_argument("--ligand-smiles", default="")
    parser.add_argument("--target-id", default="")
    parser.add_argument("--ligand-id", default="")
    parser.add_argument("--case-id", default="")
    parser.add_argument("--max-conformers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--candidate-budget", type=int, default=0)
    parser.add_argument("--benchmark-profile", default="internal_diagnostic_profile")
    parser.add_argument("--claim-scope", default="restricted_internal")
    parser.add_argument("--oracle-receipt-json", default="")
    parser.add_argument("--oracle-rows-csv", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    packet = run_docking_shadow_execution(
        receptor_pdb=args.receptor_pdb,
        ligand_smiles=args.ligand_smiles,
        target_id=args.target_id,
        ligand_id=args.ligand_id,
        case_id=args.case_id,
        max_conformers=args.max_conformers,
        seed=args.seed,
        candidate_budget=args.candidate_budget,
        benchmark_profile=args.benchmark_profile,
        claim_scope=args.claim_scope,
        oracle_receipt_json=args.oracle_receipt_json,
        oracle_rows_csv=args.oracle_rows_csv,
    )
    if args.out_json:
        out_json = _resolve(args.out_json)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(
            json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.out_csv:
        from tools.product.builder_table_utils import write_csv_rows

        write_csv_rows(_resolve(args.out_csv), packet["rows"])
    if args.out_md:
        out_md = _resolve(args.out_md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(packet), encoding="utf-8")
    if not args.quiet:
        print(json.dumps(packet["summary"], indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if packet["summary"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
