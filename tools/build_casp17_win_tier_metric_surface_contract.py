#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_GOAL_SCORECARD_JSON = "runs/casp17_win_tier_goal_scorecard_current.json"
DEFAULT_STRICT_BLIND_QUEUE_JSON = "casp17/casp17_historical_seed_strict_blind_replacement_queue_current.json"
DEFAULT_INPUT_SCAFFOLD_JSON = "runs/casp17_win_tier_benchmark_input_scaffold_current.json"
DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON = "runs/casp17_sidechain_native_benchmark_packet_current.json"
DEFAULT_OFFICIAL_ARCHIVE_BASELINE_LANE_JSON = (
    "casp17/casp17_historical_seed_official_archive_baseline_lane_current.json"
)
DEFAULT_OUT_DIR = "casp17/win_tier_metric_surface_contract"
DEFAULT_OUT_JSON = "casp17/casp17_win_tier_metric_surface_contract_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_win_tier_metric_surface_contract_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_WIN_TIER_METRIC_SURFACE_CONTRACT.md"

DEFAULT_REQUIRED_METRICS = [
    "GDT_TS",
    "lDDT",
    "TM-score",
    "RMSD",
    "GDT_HA",
    "MolProbity",
    "DockQ",
    "ICS",
    "IPS",
    "LDDT-PLI",
    "BiSyRMSD",
]

METRIC_SPECS = {
    "GDT_TS": ("monomer_domain", "metrics/monomer/gdt_ts.json", "prediction/native chain mapping"),
    "lDDT": ("monomer_domain", "metrics/monomer/lddt.json", "prediction/native residue mapping"),
    "TM-score": ("monomer_domain", "metrics/monomer/tm_score.json", "prediction/native chain mapping"),
    "RMSD": ("geometry", "metrics/geometry/rmsd.json", "prediction/native atom mapping"),
    "GDT_HA": ("monomer_domain", "metrics/monomer/gdt_ha.json", "prediction/native chain mapping"),
    "MolProbity": ("model_quality", "metrics/model_quality/molprobity.json", "prediction structure"),
    "DockQ": ("complex_interface", "metrics/complex/dockq.json", "complex chain mapping"),
    "ICS": ("complex_interface", "metrics/complex/ics.json", "interface contact map"),
    "IPS": ("complex_interface", "metrics/complex/ips.json", "interface patch map"),
    "LDDT-PLI": ("ligand_pose", "metrics/ligand/lddt_pli.json", "receptor ligand interaction map"),
    "BiSyRMSD": ("ligand_pose", "metrics/ligand/bisyrmsd.json", "binding-site ligand mapping"),
}

CORE_METRICS_BY_SCOPE = {
    "monomer": {"GDT_TS", "lDDT", "TM-score", "RMSD", "GDT_HA", "MolProbity"},
    "domain": {"GDT_TS", "lDDT", "TM-score", "RMSD", "GDT_HA", "MolProbity"},
    "complex": {
        "GDT_TS",
        "lDDT",
        "TM-score",
        "RMSD",
        "GDT_HA",
        "MolProbity",
        "DockQ",
        "ICS",
        "IPS",
    },
    "immune_complex": {
        "GDT_TS",
        "lDDT",
        "TM-score",
        "RMSD",
        "GDT_HA",
        "MolProbity",
        "DockQ",
        "ICS",
        "IPS",
    },
    "ligand": {"RMSD", "MolProbity", "LDDT-PLI", "BiSyRMSD"},
    "protein_ligand": {
        "GDT_TS",
        "lDDT",
        "TM-score",
        "RMSD",
        "GDT_HA",
        "MolProbity",
        "LDDT-PLI",
        "BiSyRMSD",
    },
}

CLAIM_BOUNDARY = (
    "Local CASP17 win-tier metric-surface contract only. It creates per-slot metric input and output "
    "requirements for strict-blind historical replay. It does not compute official CASP scores, download "
    "large external model pools, import official archive submissions as internal predictions, or claim current "
    "CASP17 target accuracy."
)

OFFICIAL_ARCHIVE_BASELINE_POLICY = "excluded_from_competitive_proof"

ROW_COLUMNS = [
    "metric_surface_row_id",
    "slot_rank",
    "benchmark_id",
    "target_id",
    "scope",
    "metric_name",
    "metric_family",
    "profile_fit",
    "metric_input_contract",
    "prediction_pdb",
    "native_pdb",
    "expected_output_json",
    "metric_status",
    "blockers",
    "next_action",
    "metric_folder",
    "slot_manifest",
    "requirements_csv",
    "official_archive_baseline_policy",
    "competitive_proof_eligible",
]

SLOT_COLUMNS = [
    "slot_rank",
    "benchmark_id",
    "target_id",
    "scope",
    "metric_contract_status",
    "required_metric_count",
    "core_metric_count",
    "extension_metric_count",
    "prediction_pdb",
    "native_pdb",
    "slot_folder",
    "slot_manifest",
    "requirements_csv",
    "blockers",
    "next_action",
]


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


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_").lower()
    return slug[:96] or "slot"


def _required_metrics(goal_payload: dict[str, Any]) -> list[str]:
    metrics = _summary(goal_payload).get("required_metric_surface")
    if isinstance(metrics, list):
        cleaned = [_text(metric) for metric in metrics if _text(metric)]
        if cleaned:
            return cleaned
    return DEFAULT_REQUIRED_METRICS[:]


def _row_map(rows: list[dict[str, Any]], key_name: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _text(row.get(key_name))
        if key and key not in out:
            out[key] = row
    return out


def _queue_rows(queue_payload: dict[str, Any], scaffold_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _rows(queue_payload)
    return rows if rows else _rows(scaffold_payload)


def _slot_folder(out_dir: str | Path, slot_rank: int, benchmark_id: str) -> Path:
    return _resolve(out_dir) / f"{slot_rank:02d}_{_safe_slug(benchmark_id)}"


def _core_metrics(scope: str) -> set[str]:
    return CORE_METRICS_BY_SCOPE.get(scope, CORE_METRICS_BY_SCOPE.get(scope.lower(), set()))


def _profile_fit(scope: str, metric_name: str) -> str:
    if metric_name in _core_metrics(scope):
        return "scope_core_metric"
    if metric_name in {"LDDT-PLI", "BiSyRMSD"}:
        return "organic_ligand_category_slot_required"
    if metric_name in {"DockQ", "ICS", "IPS"}:
        return "complex_or_interface_category_slot_required"
    return "win_tier_surface_extension"


def _metric_status(slot_status: str, profile_fit: str) -> str:
    if slot_status != "metric_inputs_ready":
        return slot_status
    if profile_fit != "scope_core_metric":
        return "category_scope_extension_required"
    return "metric_inputs_ready"


def _slot_status(slot_row: dict[str, Any], sidechain_row: dict[str, Any]) -> str:
    if _text(slot_row.get("replacement_queue_status")).startswith("awaiting"):
        return "awaiting_strict_blind_evidence_files"
    if _text(slot_row.get("operator_row_status")) == "blocked":
        return "awaiting_strict_blind_evidence_files"
    if _text(sidechain_row.get("sidechain_native_status")) == "blocked":
        return "awaiting_strict_blind_evidence_files"
    if _text(slot_row.get("blockers")) or _text(sidechain_row.get("blockers")):
        return "awaiting_strict_blind_evidence_files"
    return "metric_inputs_ready"


def _slot_blockers(slot_row: dict[str, Any], scaffold_row: dict[str, Any], sidechain_row: dict[str, Any]) -> str:
    blockers = [
        _text(slot_row.get("blockers")),
        _text(scaffold_row.get("blockers")),
        _text(sidechain_row.get("blockers")),
    ]
    merged: list[str] = []
    for chunk in blockers:
        for item in chunk.split(","):
            item = item.strip()
            if item and item not in merged:
                merged.append(item)
    if not merged:
        return ""
    return ",".join(merged)


def _build_slot_and_metric_rows(
    *,
    args: argparse.Namespace,
    queue_payload: dict[str, Any],
    scaffold_payload: dict[str, Any],
    sidechain_payload: dict[str, Any],
    required_metrics: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scaffold_by_id = _row_map(_rows(scaffold_payload), "benchmark_id")
    sidechain_by_id = _row_map(_rows(sidechain_payload), "benchmark_id")
    slot_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []

    for fallback_rank, row in enumerate(_queue_rows(queue_payload, scaffold_payload), start=1):
        benchmark_id = _text(row.get("required_benchmark_id") or row.get("benchmark_id"))
        if not benchmark_id:
            continue
        scaffold_row = scaffold_by_id.get(benchmark_id, {})
        sidechain_row = sidechain_by_id.get(benchmark_id, {})
        slot_rank = _int(row.get("queue_rank") or row.get("row_rank") or row.get("scaffold_row_rank"), fallback_rank)
        target_id = _text(row.get("required_target_id") or row.get("target_id") or scaffold_row.get("target_id"))
        scope = _text(row.get("scope") or scaffold_row.get("scope") or sidechain_row.get("scope") or "unknown")
        prediction_pdb = _text(scaffold_row.get("prediction_pdb") or sidechain_row.get("prediction_pdb"))
        native_pdb = _text(scaffold_row.get("native_pdb") or sidechain_row.get("native_pdb"))
        folder = _slot_folder(args.out_dir, slot_rank, benchmark_id)
        manifest = folder / "METRIC_SURFACE.md"
        requirements_csv = folder / "metric_surface_requirements.csv"
        status = _slot_status({**scaffold_row, **row}, sidechain_row)
        blockers = _slot_blockers(row, scaffold_row, sidechain_row)
        core_count = sum(1 for metric in required_metrics if _profile_fit(scope, metric) == "scope_core_metric")
        slot_rows.append(
            {
                "slot_rank": slot_rank,
                "benchmark_id": benchmark_id,
                "target_id": target_id,
                "scope": scope,
                "metric_contract_status": status,
                "required_metric_count": len(required_metrics),
                "core_metric_count": core_count,
                "extension_metric_count": len(required_metrics) - core_count,
                "prediction_pdb": prediction_pdb,
                "native_pdb": native_pdb,
                "slot_folder": _artifact(folder),
                "slot_manifest": _artifact(manifest),
                "requirements_csv": _artifact(requirements_csv),
                "blockers": blockers,
                "next_action": (
                    "place strict-blind prediction/native PDBs, no-leak provenance, chain/ligand maps, "
                    "then run official-like metric calculators for model1 and best-of-5"
                ),
            }
        )
        for metric_index, metric_name in enumerate(required_metrics, start=1):
            metric_family, output_json, input_contract = METRIC_SPECS.get(
                metric_name, ("custom", f"metrics/custom/{_safe_slug(metric_name)}.json", "metric-specific inputs")
            )
            profile_fit = _profile_fit(scope, metric_name)
            metric_status = _metric_status(status, profile_fit)
            metric_rows.append(
                {
                    "metric_surface_row_id": f"{slot_rank:02d}_{metric_index:02d}_{_safe_slug(metric_name)}",
                    "slot_rank": slot_rank,
                    "benchmark_id": benchmark_id,
                    "target_id": target_id,
                    "scope": scope,
                    "metric_name": metric_name,
                    "metric_family": metric_family,
                    "profile_fit": profile_fit,
                    "metric_input_contract": input_contract,
                    "prediction_pdb": prediction_pdb,
                    "native_pdb": native_pdb,
                    "expected_output_json": _artifact(folder / output_json),
                    "metric_status": metric_status,
                    "blockers": blockers or profile_fit,
                    "next_action": (
                        "fill strict-blind core evidence before metric calculation"
                        if metric_status == "awaiting_strict_blind_evidence_files"
                        else "add the matching CASP17 category slot and ligand/interface metadata"
                    ),
                    "metric_folder": _artifact(folder),
                    "slot_manifest": _artifact(manifest),
                    "requirements_csv": _artifact(requirements_csv),
                    "official_archive_baseline_policy": OFFICIAL_ARCHIVE_BASELINE_POLICY,
                    "competitive_proof_eligible": "False" if metric_status != "metric_inputs_ready" else "True",
                }
            )
    return slot_rows, metric_rows


def _contract_status(input_exists: bool, required_metrics: list[str], slot_rows: list[dict[str, Any]]) -> str:
    if not input_exists:
        return "blocked_goal_scorecard_missing"
    if not required_metrics:
        return "blocked_required_metric_surface_missing"
    if not slot_rows:
        return "blocked_strict_blind_slots_missing"
    if any(row["scope"] in {"ligand", "protein_ligand", "organic_ligand"} for row in slot_rows):
        ligand_suffix = ""
    else:
        ligand_suffix = "_and_ligand_category_slots"
    if any(row["metric_contract_status"] != "metric_inputs_ready" for row in slot_rows):
        return "awaiting_strict_blind_evidence_files" + ligand_suffix
    if ligand_suffix:
        return "awaiting_ligand_category_slots"
    return "metric_surface_contract_ready_for_calculation"


def _build_summary(
    *,
    args: argparse.Namespace,
    goal_input_exists: bool,
    required_metrics: list[str],
    slot_rows: list[dict[str, Any]],
    metric_rows: list[dict[str, Any]],
    official_payload: dict[str, Any],
) -> dict[str, Any]:
    official_summary = _summary(official_payload)
    metric_names = {row["metric_name"] for row in metric_rows}
    core_metric_names = {row["metric_name"] for row in metric_rows if row["profile_fit"] == "scope_core_metric"}
    ligand_metric_names = {"LDDT-PLI", "BiSyRMSD"} & metric_names
    blocked_rows = [row for row in metric_rows if row["metric_status"] != "metric_inputs_ready"]
    first_blocked = blocked_rows[0] if blocked_rows else {}
    blocked_slots = [row for row in slot_rows if row["metric_contract_status"] != "metric_inputs_ready"]
    status = _contract_status(goal_input_exists, required_metrics, slot_rows)
    return {
        "packet_type": "casp17_win_tier_metric_surface_contract",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "metric_surface_contract_status": status,
        "goal_scorecard_json": _artifact(args.goal_scorecard_json),
        "strict_blind_queue_json": _artifact(args.strict_blind_queue_json),
        "input_scaffold_json": _artifact(args.input_scaffold_json),
        "sidechain_native_benchmark_json": _artifact(args.sidechain_native_benchmark_json),
        "required_metric_count": len(required_metrics),
        "covered_required_metric_count": sum(1 for metric in required_metrics if metric in metric_names),
        "core_metric_name_count": len(core_metric_names),
        "ligand_metric_name_count": len(ligand_metric_names),
        "strict_blind_slot_count": len(slot_rows),
        "ready_slot_count": len(slot_rows) - len(blocked_slots),
        "blocked_slot_count": len(blocked_slots),
        "monomer_slot_count": sum(1 for row in slot_rows if row["scope"] == "monomer"),
        "complex_slot_count": sum(1 for row in slot_rows if row["scope"] == "complex"),
        "organic_ligand_slot_count": sum(
            1 for row in slot_rows if row["scope"] in {"ligand", "protein_ligand", "organic_ligand"}
        ),
        "metric_surface_row_count": len(metric_rows),
        "core_metric_row_count": sum(1 for row in metric_rows if row["profile_fit"] == "scope_core_metric"),
        "extension_metric_row_count": sum(1 for row in metric_rows if row["profile_fit"] != "scope_core_metric"),
        "ready_metric_row_count": len(metric_rows) - len(blocked_rows),
        "blocked_metric_row_count": len(blocked_rows),
        "official_archive_baseline_policy": OFFICIAL_ARCHIVE_BASELINE_POLICY,
        "official_archive_baseline_candidate_count": _int(official_summary.get("baseline_candidate_count")),
        "official_archive_competitive_proof_eligible_count": _int(
            official_summary.get("competitive_proof_eligible_count")
        ),
        "first_blocked_benchmark_id": _text(first_blocked.get("benchmark_id")),
        "first_blocked_metric": _text(first_blocked.get("metric_name")),
        "first_blocked_blockers": _text(first_blocked.get("blockers")),
        "out_dir": _artifact(args.out_dir),
        "next_action": (
            "fill strict-blind prediction/native/no-leak evidence for 40 historical slots and add organic "
            "ligand-protein historical slots before claiming full CASP17 win-tier metric surface"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    goal_path = _resolve(args.goal_scorecard_json)
    goal_payload = _read_json(goal_path)
    queue_payload = _read_json(args.strict_blind_queue_json)
    scaffold_payload = _read_json(args.input_scaffold_json)
    sidechain_payload = _read_json(args.sidechain_native_benchmark_json)
    official_payload = _read_json(args.official_archive_baseline_lane_json)
    required_metrics = _required_metrics(goal_payload)
    slot_rows, metric_rows = _build_slot_and_metric_rows(
        args=args,
        queue_payload=queue_payload,
        scaffold_payload=scaffold_payload,
        sidechain_payload=sidechain_payload,
        required_metrics=required_metrics,
    )
    summary = _build_summary(
        args=args,
        goal_input_exists=goal_path.exists(),
        required_metrics=required_metrics,
        slot_rows=slot_rows,
        metric_rows=metric_rows,
        official_payload=official_payload,
    )
    return {"summary": summary, "slot_rows": slot_rows, "rows": metric_rows}


def _write_slot_manifest(slot_row: dict[str, Any], metric_rows: list[dict[str, Any]]) -> None:
    lines = [
        f"# {slot_row['benchmark_id']} Win-Tier Metric Surface",
        "",
        f"- status: `{slot_row['metric_contract_status']}`",
        f"- target_id: `{slot_row['target_id']}`",
        f"- scope: `{slot_row['scope']}`",
        f"- prediction_pdb: `{slot_row['prediction_pdb'] or '-'}`",
        f"- native_pdb: `{slot_row['native_pdb'] or '-'}`",
        f"- required/core/extension metrics: `{slot_row['required_metric_count']}/{slot_row['core_metric_count']}/{slot_row['extension_metric_count']}`",
        f"- official_archive_baseline_policy: `{OFFICIAL_ARCHIVE_BASELINE_POLICY}`",
        f"- blockers: `{slot_row['blockers'] or '-'}`",
        "",
        "## Metric Requirements",
        "",
        "| metric | family | fit | output | status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in metric_rows:
        lines.append(
            f"| `{row['metric_name']}` | `{row['metric_family']}` | `{row['profile_fit']}` | "
            f"`{row['expected_output_json']}` | `{row['metric_status']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY, ""])
    path = _resolve(slot_row["slot_manifest"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    _write_csv(slot_row["requirements_csv"], metric_rows, ROW_COLUMNS)


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Win-Tier Metric Surface Contract",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['metric_surface_contract_status']}`",
        f"- required metrics covered: `{summary['covered_required_metric_count']}/{summary['required_metric_count']}`",
        f"- slots ready/blocked/total: `{summary['ready_slot_count']}/{summary['blocked_slot_count']}/{summary['strict_blind_slot_count']}`",
        f"- metric rows ready/blocked/total: `{summary['ready_metric_row_count']}/{summary['blocked_metric_row_count']}/{summary['metric_surface_row_count']}`",
        f"- monomer/complex/organic-ligand slots: `{summary['monomer_slot_count']}/{summary['complex_slot_count']}/{summary['organic_ligand_slot_count']}`",
        f"- official archive baseline policy: `{summary['official_archive_baseline_policy']}` candidates `{summary['official_archive_baseline_candidate_count']}` proof eligible `{summary['official_archive_competitive_proof_eligible_count']}`",
        f"- first blocked: `{summary['first_blocked_benchmark_id'] or '-'}` `{summary['first_blocked_metric'] or '-'}` `{summary['first_blocked_blockers'] or '-'}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Slots",
        "",
        "| slot | benchmark | scope | core/ext | status | manifest |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["slot_rows"]:
        lines.append(
            f"| `{row['slot_rank']}` | `{row['benchmark_id']}` | `{row['scope']}` | "
            f"`{row['core_metric_count']}/{row['extension_metric_count']}` | "
            f"`{row['metric_contract_status']}` | `{row['slot_manifest']}` |"
        )
    if not payload["slot_rows"]:
        lines.append("| - | - | - | - | `blocked` | - |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    by_benchmark: dict[str, list[dict[str, Any]]] = {}
    for row in payload["rows"]:
        by_benchmark.setdefault(row["benchmark_id"], []).append(row)
    for slot_row in payload["slot_rows"]:
        _write_slot_manifest(slot_row, by_benchmark.get(slot_row["benchmark_id"], []))
    _write_csv(_resolve(args.out_dir) / "slot_contracts.csv", payload["slot_rows"], SLOT_COLUMNS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a CASP17 win-tier metric-surface contract.")
    parser.add_argument("--goal-scorecard-json", default=DEFAULT_GOAL_SCORECARD_JSON)
    parser.add_argument("--strict-blind-queue-json", default=DEFAULT_STRICT_BLIND_QUEUE_JSON)
    parser.add_argument("--input-scaffold-json", default=DEFAULT_INPUT_SCAFFOLD_JSON)
    parser.add_argument("--sidechain-native-benchmark-json", default=DEFAULT_SIDECHAIN_NATIVE_BENCHMARK_JSON)
    parser.add_argument(
        "--official-archive-baseline-lane-json",
        default=DEFAULT_OFFICIAL_ARCHIVE_BASELINE_LANE_JSON,
    )
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)


if __name__ == "__main__":
    main()
