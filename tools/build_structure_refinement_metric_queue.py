#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_STRUCTURE_SCORECARD_JSON = "runs/structure_refinement_scorecard_current.json"
DEFAULT_NATIVE_MANIFEST_CSV = "runs/selected_allatom_native_structure_manifest_current.csv"
DEFAULT_TCRUZI_REVIEW_JSON = "runs/wetlab_tcruzi_pde_allatom_review_packet_current.json"
DEFAULT_SARSCOV2_RUNNER_JSON = "runs/wetlab_sarscov2_mpro_allatom_refinement_runner_current.json"
DEFAULT_CATHEPSIN_RUNNER_JSON = "runs/wetlab_cathepsin_k_allatom_refinement_runner_current.json"
DEFAULT_OUT_JSON = "runs/structure_refinement_metric_queue_current.json"
DEFAULT_OUT_CSV = "runs/structure_refinement_metric_queue_current.csv"
DEFAULT_OUT_MD = "runs/structure_refinement_metric_queue_current.md"

METRIC_FAMILIES = (
    "rmsd",
    "tm_score",
    "gdt",
    "lddt_or_molprobity",
    "dockq_or_interface",
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _artifact(path_like: str | Path) -> str:
    path = _resolve(path_like)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary", {})
    return summary if isinstance(summary, dict) else {}


def _combined_summary(payload: dict[str, Any]) -> dict[str, Any]:
    structured = payload.get("structured", {})
    summary = payload.get("summary", {})
    combined: dict[str, Any] = {}
    if isinstance(structured, dict):
        combined.update(structured)
    if isinstance(summary, dict):
        combined.update(summary)
    return combined


def _scorecard_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows", [])
    return rows if isinstance(rows, list) else []


def _native_by_target(native_manifest_csv: str | Path) -> dict[str, dict[str, str]]:
    return {_text(row.get("target")): row for row in _read_csv(native_manifest_csv)}


def _source_summary_by_target(
    *,
    tcruzi_review_json: str | Path,
    sarscov2_runner_json: str | Path,
    cathepsin_runner_json: str | Path,
) -> dict[str, dict[str, Any]]:
    specs = {
        "T. cruzi PDE": tcruzi_review_json,
        "SARS-CoV-2 Mpro": sarscov2_runner_json,
        "Cathepsin K": cathepsin_runner_json,
    }
    return {
        target: {"artifact": _artifact(path), "summary": _combined_summary(_read_json(path))}
        for target, path in specs.items()
    }


def _path_exists(path_like: Any) -> bool:
    text = _text(path_like)
    return bool(text and _resolve(text).exists())


def _count_backmapped_pdbs(scores_csv: Any) -> int:
    text = _text(scores_csv)
    if not text:
        return 0
    rows = _read_csv(text)
    count = 0
    for row in rows:
        if _path_exists(row.get("backmapped_pdb")):
            count += 1
    return count


def _missing_metric_families(scorecard_row: dict[str, Any]) -> list[str]:
    checks = {
        "rmsd": bool(scorecard_row.get("rmsd_available")),
        "tm_score": bool(scorecard_row.get("tm_score_available")),
        "gdt": bool(scorecard_row.get("gdt_available")),
        "lddt_or_molprobity": bool(scorecard_row.get("lddt_or_molprobity_available")),
        "dockq_or_interface": bool(
            scorecard_row.get("dockq_or_interface_metric_available")
            or scorecard_row.get("dockq_or_interface_not_applicable")
            or scorecard_row.get("dockq_or_interface_resolved")
        ),
    }
    return [family for family in METRIC_FAMILIES if not checks[family]]


def _metric_queue_rows(
    *,
    scorecard_rows: list[dict[str, Any]],
    native_rows: dict[str, dict[str, str]],
    source_rows: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    priority = 1
    for scorecard_row in scorecard_rows:
        target = _text(scorecard_row.get("target_id"))
        source = source_rows.get(target, {})
        source_summary = source.get("summary", {}) if isinstance(source.get("summary"), dict) else {}
        native_row = native_rows.get(target, {})
        native_path = _text(scorecard_row.get("native_pdb_path")) or _text(native_row.get("path"))
        scores_csv = _text(source_summary.get("allatom_scores_csv"))
        backmapped_count = _count_backmapped_pdbs(scores_csv)
        source_artifacts = [
            _text(scorecard_row.get("source_artifact")),
            _text(source.get("artifact")),
            _artifact(DEFAULT_STRUCTURE_SCORECARD_JSON),
            _artifact(DEFAULT_NATIVE_MANIFEST_CSV),
        ]
        source_artifacts = sorted({item for item in source_artifacts if item})
        missing = _missing_metric_families(scorecard_row)
        shared = {
            "target": target,
            "native_pdb_id": _text(scorecard_row.get("native_pdb_id")) or _text(native_row.get("pdb_id")),
            "native_pdb_path": native_path,
            "native_reference_available": bool(scorecard_row.get("native_reference_available")) and _path_exists(native_path),
            "pseudo_allatom_lane_ready": bool(scorecard_row.get("pseudo_allatom_lane_ready")),
            "allatom_scores_csv": scores_csv,
            "allatom_scores_available": _path_exists(scores_csv),
            "candidate_backmapped_pdb_count": backmapped_count,
            "source_artifacts": ",".join(source_artifacts),
            "claim_promotion_allowed": False,
        }
        protein_missing = [item for item in missing if item != "dockq_or_interface"]
        if protein_missing:
            rows.append(
                {
                    "priority": priority,
                    "queue_id": f"{target}::protein_alignment_metrics",
                    "metric_task": "protein_alignment_metrics",
                    "missing_metric_families": ",".join(protein_missing),
                    "status": "open",
                    "next_action": (
                        "Compute frozen structure-native RMSD/TM/GDT/lDDT-or-MolProbity metrics from the "
                        "native PDB and selected backmapped/refined PDB candidates; write metrics back to a "
                        "target summary artifact before claiming GALAXY-style refinement parity."
                    ),
                    **shared,
                }
            )
            priority += 1
        interface_not_applicable = bool(scorecard_row.get("dockq_or_interface_not_applicable"))
        if "dockq_or_interface" in missing or interface_not_applicable:
            interface_status = "not_applicable_provenance" if interface_not_applicable and "dockq_or_interface" not in missing else "open"
            rows.append(
                {
                    "priority": priority,
                    "queue_id": f"{target}::interface_metrics",
                    "metric_task": "interface_metrics",
                    "missing_metric_families": "dockq_or_interface",
                    "status": interface_status,
                    "next_action": (
                        "Compute DockQ or interface RMSD only if a biologically meaningful complex/interface "
                        "claim is in scope; otherwise record an explicit non-applicable interface provenance row."
                    ),
                    **shared,
                }
            )
            priority += 1
    return rows


def build_queue(
    *,
    structure_scorecard_json: str | Path = DEFAULT_STRUCTURE_SCORECARD_JSON,
    native_manifest_csv: str | Path = DEFAULT_NATIVE_MANIFEST_CSV,
    tcruzi_review_json: str | Path = DEFAULT_TCRUZI_REVIEW_JSON,
    sarscov2_runner_json: str | Path = DEFAULT_SARSCOV2_RUNNER_JSON,
    cathepsin_runner_json: str | Path = DEFAULT_CATHEPSIN_RUNNER_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    scorecard = _read_json(structure_scorecard_json)
    scorecard_summary = _summary(scorecard)
    rows = _metric_queue_rows(
        scorecard_rows=_scorecard_rows(scorecard),
        native_rows=_native_by_target(native_manifest_csv),
        source_rows=_source_summary_by_target(
            tcruzi_review_json=tcruzi_review_json,
            sarscov2_runner_json=sarscov2_runner_json,
            cathepsin_runner_json=cathepsin_runner_json,
        ),
    )
    target_count = int(scorecard_summary.get("target_count") or 0)
    open_target_count = len({row["target"] for row in rows})
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "open_structure_refinement_metric_queue" if rows else "structure_refinement_metric_queue_empty",
        "queue_row_count": len(rows),
        "target_count": target_count,
        "open_target_count": open_target_count,
        "scorecard_status": scorecard_summary.get("status"),
        "native_reference_target_count": scorecard_summary.get("native_reference_target_count"),
        "pseudo_allatom_lane_ready_count": scorecard_summary.get("pseudo_allatom_lane_ready_count"),
        "rmsd_available_count": scorecard_summary.get("rmsd_available_count"),
        "tm_score_available_count": scorecard_summary.get("tm_score_available_count"),
        "gdt_available_count": scorecard_summary.get("gdt_available_count"),
        "lddt_or_molprobity_available_count": scorecard_summary.get("lddt_or_molprobity_available_count"),
        "dockq_or_interface_metric_available_count": scorecard_summary.get(
            "dockq_or_interface_metric_available_count"
        ),
        "claim_promotion_allowed": False,
        "galaxy_class_claim_allowed": False,
        "top_priority_queue_id": rows[0]["queue_id"] if rows else None,
        "next_required_step": (
            rows[0]["next_action"]
            if rows
            else "No open structure/refinement metric queue rows were generated from the current scorecard."
        ),
    }
    return {
        "packet_type": "structure_refinement_metric_queue",
        "summary": summary,
        "rows": rows,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "galaxy_class_claim_allowed": False,
            "metric_availability_alone_is_not_galaxy_parity": True,
            "threshold_relaxation_allowed": False,
            "fake_pass_allowed": False,
        },
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Structure Refinement Metric Queue",
        "",
        "## Summary",
        "",
        f"- status: `{summary['status']}`",
        f"- queue_row_count: `{summary['queue_row_count']}`",
        f"- open_target_count: `{summary['open_target_count']}`",
        f"- scorecard_status: `{summary['scorecard_status']}`",
        f"- claim_promotion_allowed: `{str(summary['claim_promotion_allowed']).lower()}`",
        f"- top_priority_queue_id: `{summary['top_priority_queue_id']}`",
        "",
        "## Queue",
        "",
        "| Priority | Queue ID | Task | Missing metric families | Native | Candidates | Status |",
        "|---:|---|---|---|---:|---:|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| {row['priority']} | `{row['queue_id']}` | `{row['metric_task']}` | "
            f"`{row['missing_metric_families']}` | `{str(row['native_reference_available']).lower()}` | "
            f"`{row['candidate_backmapped_pdb_count']}` | `{row['status']}` |"
        )
    lines.extend(["", "## Next Required Step", "", f"- {summary['next_required_step']}", ""])
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an A3 structure/refinement metric materialization queue.")
    parser.add_argument("--structure-scorecard-json", default=DEFAULT_STRUCTURE_SCORECARD_JSON)
    parser.add_argument("--native-manifest-csv", default=DEFAULT_NATIVE_MANIFEST_CSV)
    parser.add_argument("--tcruzi-review-json", default=DEFAULT_TCRUZI_REVIEW_JSON)
    parser.add_argument("--sarscov2-runner-json", default=DEFAULT_SARSCOV2_RUNNER_JSON)
    parser.add_argument("--cathepsin-runner-json", default=DEFAULT_CATHEPSIN_RUNNER_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_queue(
        structure_scorecard_json=args.structure_scorecard_json,
        native_manifest_csv=args.native_manifest_csv,
        tcruzi_review_json=args.tcruzi_review_json,
        sarscov2_runner_json=args.sarscov2_runner_json,
        cathepsin_runner_json=args.cathepsin_runner_json,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    out_md = _resolve(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_md(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
