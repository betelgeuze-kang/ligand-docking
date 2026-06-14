#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.accounting.apply_ligand_heavy_run_cleanup_manifest import APPROVAL_TOKEN
from tools.accounting.build_storage_retention_manifest import _display, _human_size, _resolve
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "config/ligand_tcruzi_pde_heavy_trajectory_retention_current.json"
DEFAULT_OUT_MD = "docs/ligand_tcruzi_pde_heavy_trajectory_retention_current.md"
DEFAULT_MANIFEST_JSON = "runs/ligand_tcruzi_pde_heavy_trajectory_cleanup_manifest_current.json"
DEFAULT_MANIFEST_CSV = "runs/ligand_tcruzi_pde_heavy_trajectory_cleanup_manifest_current.csv"
DEFAULT_RUN_ROOTS = (
    "runs/wetlab_tcruzi_pde_external_pdeb1_seed_screen",
    "runs/wetlab_tcruzi_pde_external_geomstab_stage2_adress_rescue_current",
    "runs/wetlab_tcruzi_pde_external_geomstab_contact_rescue_current",
    "runs/wetlab_tcruzi_pde_bindingdb_similarity_seed_screen",
)
DEFAULT_EVIDENCE_ROOTS = {
    "runs/wetlab_tcruzi_pde_external_pdeb1_seed_screen": (
        "runs/wetlab_tcruzi_pde_external_pdeb1_seed_screen",
    ),
    "runs/wetlab_tcruzi_pde_external_geomstab_stage2_adress_rescue_current": (
        "runs/wetlab_tcruzi_pde_external_geomstab_stage2_adress_rescue_current",
        "runs/wetlab_tcruzi_pde_external_geomstab_adress_rescue_scores_current",
    ),
    "runs/wetlab_tcruzi_pde_external_geomstab_contact_rescue_current": (
        "runs/wetlab_tcruzi_pde_external_geomstab_contact_rescue_current",
        "runs/wetlab_tcruzi_pde_external_geomstab_contact_rescue_scores_current",
    ),
    "runs/wetlab_tcruzi_pde_bindingdb_similarity_seed_screen": (
        "runs/wetlab_tcruzi_pde_bindingdb_similarity_seed_screen",
    ),
}
RETENTION_COLUMNS = (
    "source_summary_json",
    "export_rank",
    "queue_id",
    "target",
    "ligand_id",
    "ligand_smiles",
    "active_score_col",
    "active_score",
    "binding_energy_mmpbsa_kcal_mol_proxy",
    "stability_score",
    "contact_fraction",
    "mean_min_distance_A",
    "trajectory_frames",
    "trajectory_npz",
    "protein_structure_source_explicit_native_path",
)
CLAIM_BOUNDARY = (
    "Ligand trajectory-heavy compaction only records compact top-ranking and score evidence for local T. cruzi PDE "
    "ligand trajectory payloads, then prepares an approval-gated manifest for deleting raw stage2 trajectory NPZ files. "
    "It does not change scientific claims, delete retained score/summary files, touch git history, upload, push, or run docking."
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _stage2_npz_files(run_root: Path) -> list[Path]:
    if not run_root.exists():
        return []
    rows: list[Path] = []
    for path in sorted(run_root.rglob("*.npz")):
        parts = [part.lower() for part in path.parts]
        if any("stage2_traj_frames" in part or "stage2_trajectory_frames" in part for part in parts):
            rows.append(path)
    return rows


def _evidence_roots_for(run_root_rel: str, *, root: Path) -> list[Path]:
    mapped = DEFAULT_EVIDENCE_ROOTS.get(run_root_rel, (run_root_rel,))
    return [_resolve(item, root=root) for item in mapped]


def _evidence_files(evidence_roots: list[Path], *, root: Path) -> list[str]:
    suffixes = {".json", ".csv", ".md"}
    files: list[str] = []
    for evidence_root in evidence_roots:
        if not evidence_root.exists():
            continue
        for path in sorted(evidence_root.iterdir()):
            if path.is_file() and path.suffix.lower() in suffixes:
                files.append(_display(path, root=root))
    return files


def _summary_jsons(evidence_roots: list[Path]) -> list[Path]:
    rows: list[Path] = []
    for evidence_root in evidence_roots:
        if not evidence_root.exists():
            continue
        for path in sorted(evidence_root.glob("*.json")):
            if "summary" in path.name.lower():
                rows.append(path)
    return rows


def _compact_topk_row(row: dict[str, Any], *, source_summary_json: str, active_score_col: str) -> dict[str, Any]:
    active_score = row.get(active_score_col) if active_score_col else None
    if active_score is None:
        active_score = row.get("binding_score_composite_v7")
    compact = {column: "" for column in RETENTION_COLUMNS}
    compact.update(
        {
            "source_summary_json": source_summary_json,
            "export_rank": row.get("export_rank", ""),
            "queue_id": row.get("queue_id", ""),
            "target": row.get("target", ""),
            "ligand_id": row.get("ligand_id", ""),
            "ligand_smiles": row.get("ligand_smiles", ""),
            "active_score_col": active_score_col or "binding_score_composite_v7",
            "active_score": active_score,
            "binding_energy_mmpbsa_kcal_mol_proxy": row.get("binding_energy_mmpbsa_kcal_mol_proxy", ""),
            "stability_score": row.get("stability_score", ""),
            "contact_fraction": row.get("contact_fraction", ""),
            "mean_min_distance_A": row.get("mean_min_distance_A", ""),
            "trajectory_frames": row.get("trajectory_frames", ""),
            "trajectory_npz": row.get("trajectory_npz", ""),
            "protein_structure_source_explicit_native_path": row.get(
                "protein_structure_source_explicit_native_path", ""
            ),
        }
    )
    return compact


def _collect_topk(evidence_roots: list[Path], *, root: Path, topk_limit_per_summary: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for summary_json in _summary_jsons(evidence_roots):
        payload = _read_json(summary_json)
        topk = payload.get("topk")
        if not isinstance(topk, list):
            continue
        source = _display(summary_json, root=root)
        active_score_col = str(payload.get("active_score_col") or payload.get("ranking_score_col_used") or "")
        for item in topk[:topk_limit_per_summary]:
            if not isinstance(item, dict):
                continue
            compact = _compact_topk_row(item, source_summary_json=source, active_score_col=active_score_col)
            key = (str(compact["source_summary_json"]), str(compact["export_rank"]), str(compact["ligand_id"]))
            if key in seen:
                continue
            seen.add(key)
            rows.append(compact)
    return rows


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Ligand T.cruzi PDE Heavy Trajectory Retention",
        "",
        f"- status: `{s['status']}`",
        f"- run_root_count: `{s['run_root_count']}`",
        f"- heavy_npz_count: `{s['heavy_npz_count']}`",
        f"- heavy_npz_size_human: `{s['heavy_npz_size_human']}`",
        f"- topk_record_count: `{s['topk_record_count']}`",
        f"- evidence_file_count: `{s['evidence_file_count']}`",
        f"- delete_manifest_json: `{s['delete_manifest_json']}`",
        f"- approval_token_required: `{s['approval_token_required']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        "",
        "## Top Retained Records",
        "",
        "| source | rank | ligand_id | active_score | dG_proxy | trajectory_npz |",
        "| --- | ---: | --- | ---: | ---: | --- |",
    ]
    for row in payload["retained_topk"][:20]:
        lines.append(
            f"| `{row['source_summary_json']}` | `{row['export_rank']}` | `{row['ligand_id']}` | "
            f"`{row['active_score']}` | `{row['binding_energy_mmpbsa_kcal_mol_proxy']}` | "
            f"`{row['trajectory_npz']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_ligand_trajectory_heavy_compaction_manifest(
    *,
    root: str | Path = ROOT,
    run_roots: tuple[str, ...] = DEFAULT_RUN_ROOTS,
    topk_limit_per_summary: int = 10,
    delete_manifest_json: str = DEFAULT_MANIFEST_JSON,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root_path = Path(root).resolve()
    retained_topk: list[dict[str, Any]] = []
    evidence_files: set[str] = set()
    manifest_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []

    for run_root_rel in run_roots:
        run_root = _resolve(run_root_rel, root=root_path)
        heavy_files = _stage2_npz_files(run_root)
        evidence_roots = _evidence_roots_for(run_root_rel, root=root_path)
        run_evidence_files = _evidence_files(evidence_roots, root=root_path)
        run_topk = _collect_topk(evidence_roots, root=root_path, topk_limit_per_summary=topk_limit_per_summary)
        evidence_files.update(run_evidence_files)
        retained_topk.extend(run_topk)
        delete_allowed = bool(run_topk and run_evidence_files)
        run_size = sum(path.stat().st_size for path in heavy_files if path.exists())
        run_rows.append(
            {
                "run_root": _display(run_root, root=root_path),
                "run_root_present": run_root.exists(),
                "evidence_root_count": len(evidence_roots),
                "evidence_file_count": len(run_evidence_files),
                "topk_record_count": len(run_topk),
                "heavy_npz_count": len(heavy_files),
                "heavy_npz_size_bytes": run_size,
                "heavy_npz_size_human": _human_size(run_size),
                "delete_recommended": delete_allowed,
            }
        )
        for heavy_path in heavy_files:
            size = heavy_path.stat().st_size if heavy_path.exists() else 0
            manifest_rows.append(
                {
                    "path": _display(heavy_path, root=root_path),
                    "path_type": "file",
                    "size_bytes": size,
                    "size_human": _human_size(size),
                    "cleanup_class": "raw_stage2_trajectory_npz",
                    "disposition": (
                        "delete_after_compact_retention_record" if delete_allowed else "review_missing_top_rank_evidence"
                    ),
                    "delete_recommended": delete_allowed,
                    "preserved_evidence_count": len(run_evidence_files),
                    "preserved_evidence": ";".join(run_evidence_files[:20]),
                    "delete_executed": False,
                    "external_state_mutated": False,
                    "reason": (
                        "Compact top-ranking and score evidence is retained in config/docs."
                        if delete_allowed
                        else "No compact top-ranking evidence found for this run root."
                    ),
                }
            )

    heavy_npz_count = len(manifest_rows)
    heavy_npz_size = sum(int(row["size_bytes"]) for row in manifest_rows)
    delete_rows = [row for row in manifest_rows if row["delete_recommended"] is True]
    blocked_rows = [row for row in manifest_rows if row["delete_recommended"] is not True]
    status = "ligand_trajectory_heavy_compaction_ready" if delete_rows and not blocked_rows else "blocked_ligand_trajectory_heavy_compaction"
    if not manifest_rows:
        status = "ligand_trajectory_heavy_compaction_noop"
    summary = {
        "packet_type": "ligand_trajectory_heavy_compaction_retention",
        "status": status,
        "generated_at_local": datetime.now().replace(microsecond=0).isoformat(),
        "run_root_count": len(run_roots),
        "heavy_npz_count": heavy_npz_count,
        "heavy_npz_size_bytes": heavy_npz_size,
        "heavy_npz_size_human": _human_size(heavy_npz_size),
        "delete_recommended_count": len(delete_rows),
        "delete_recommended_size_bytes": sum(int(row["size_bytes"]) for row in delete_rows),
        "delete_recommended_size_human": _human_size(sum(int(row["size_bytes"]) for row in delete_rows)),
        "blocked_count": len(blocked_rows),
        "topk_record_count": len(retained_topk),
        "evidence_file_count": len(evidence_files),
        "delete_manifest_json": delete_manifest_json,
        "approval_token_required": APPROVAL_TOKEN,
        "delete_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run the approval-gated ligand heavy cleanup executor on the generated manifest."
            if status == "ligand_trajectory_heavy_compaction_ready"
            else "Review missing evidence or no-op status before deleting trajectory NPZ files."
        ),
    }
    retention_payload = {
        "summary": summary,
        "run_roots": run_rows,
        "evidence_files": sorted(evidence_files),
        "retained_topk": retained_topk,
    }
    manifest_payload = {
        "summary": {
            "packet_type": "ligand_trajectory_heavy_compaction_delete_manifest",
            "status": "ligand_heavy_run_cleanup_manifest_ready",
            "source_retention_json": DEFAULT_OUT_JSON,
            "delete_recommended_count": len(delete_rows),
            "delete_recommended_size_bytes": summary["delete_recommended_size_bytes"],
            "delete_recommended_size_human": summary["delete_recommended_size_human"],
            "delete_executed": False,
            "external_state_mutated": False,
            "claim_boundary": CLAIM_BOUNDARY,
        },
        "rows": manifest_rows,
    }
    return retention_payload, manifest_payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compact T. cruzi PDE ligand trajectory-heavy payload evidence.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--run-root", action="append", default=[])
    parser.add_argument("--topk-limit-per-summary", type=int, default=10)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--manifest-json", default=DEFAULT_MANIFEST_JSON)
    parser.add_argument("--manifest-csv", default=DEFAULT_MANIFEST_CSV)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    run_roots = tuple(args.run_root) if args.run_root else DEFAULT_RUN_ROOTS
    retention_payload, manifest_payload = build_ligand_trajectory_heavy_compaction_manifest(
        root=root,
        run_roots=run_roots,
        topk_limit_per_summary=args.topk_limit_per_summary,
        delete_manifest_json=args.manifest_json,
    )
    _write_json(args.out_json, retention_payload, root=root)
    _write_markdown(args.out_md, retention_payload, root=root)
    _write_json(args.manifest_json, manifest_payload, root=root)
    write_csv_rows(_resolve(args.manifest_csv, root=root), manifest_payload["rows"])


if __name__ == "__main__":
    main()
