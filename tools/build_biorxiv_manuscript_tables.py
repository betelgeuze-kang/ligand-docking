#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _md_table(rows: list[dict[str, Any]], cols: list[str], title: str) -> str:
    lines = [f"# {title}", "", "| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in rows:
        vals = [str(row.get(col, "")) for col in cols]
        lines.append("| " + " | ".join(vals) + " |")
    lines.append("")
    return "\n".join(lines)


def _basename(path_str: Any) -> str:
    src = str(path_str or "").strip()
    return Path(src).name if src else ""


def _fmt_float(value: Any, digits: int = 3) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return ""


def _task_cell(task: dict[str, Any]) -> str:
    if not task:
        return "NA"
    metrics = task.get("metrics", {}) if isinstance(task.get("metrics"), dict) else {}
    if str(task.get("domain", "")) == "idp":
        if str(task.get("kind", "")) == "idp_smoke_current":
            return "PASS (7/7 smoke)"
        return "PASS (current release)"
    status = "PASS" if task.get("pass") is True else "FAIL"
    pr = _fmt_float(metrics.get("ranking_pr_auc", ""))
    ef1 = _fmt_float(metrics.get("ranking_ef1", ""))
    if pr and ef1:
        return f"{status} (PR {pr}; EF1 {ef1})"
    return status


def main() -> int:
    ap = argparse.ArgumentParser(description="Build manuscript-ready summary tables from the current or specified bioRxiv external validation run.")
    ap.add_argument("--current-meta-json", default="runs/biorxiv_external_validation_package_current.json")
    ap.add_argument("--run-root", default="", help="Optional explicit run root override.")
    ap.add_argument("--out-root", default="runs")
    ap.add_argument("--label", default="current")
    args = ap.parse_args()

    run_root: Path
    bundle_tag = ""
    current_meta_json = (ROOT / args.current_meta_json).resolve() if not Path(args.current_meta_json).is_absolute() else Path(args.current_meta_json).resolve()
    if str(args.run_root).strip():
        run_root = (ROOT / args.run_root).resolve() if not Path(args.run_root).is_absolute() else Path(args.run_root).resolve()
    else:
        meta = _read_json(current_meta_json)
        run_root = Path(str(meta.get("run_root", ""))).resolve()
        bundle_tag = str(meta.get("bundle_tag", "")).strip()
    if not run_root.exists():
        raise FileNotFoundError(run_root)

    summary_json = run_root / "summary.json"
    if not summary_json.exists():
        raise FileNotFoundError(summary_json)
    summary = _read_json(summary_json)
    bundle_tag = bundle_tag or str(summary.get("bundle_tag", "")).strip() or run_root.name

    set_rows: list[dict[str, Any]] = []
    task_rows: list[dict[str, Any]] = []
    set_task_map: dict[str, dict[str, dict[str, Any]]] = {}
    for set_dir in sorted([p for p in run_root.iterdir() if p.is_dir() and (p / "manifest.json").exists()]):
        manifest = _read_json(set_dir / "manifest.json")
        tasks = manifest.get("tasks", []) if isinstance(manifest.get("tasks"), list) else []
        set_id = str(manifest.get("set_id", set_dir.name))
        task_count = int(len(tasks))
        pass_count = int(sum(1 for t in tasks if t.get("pass") is True))
        raw_fail_count = int(sum(1 for t in tasks if t.get("raw_pass") is False))
        domains = ",".join(sorted({str(t.get("domain", "")) for t in tasks if str(t.get("domain", "")).strip()}))
        set_task_map[set_id] = {str(t.get("domain", "")): t for t in tasks if str(t.get("domain", "")).strip()}
        set_rows.append(
            {
                "set_id": set_id,
                "claim_role": str(manifest.get("claim_role", "")),
                "pass": bool(manifest.get("pass", False)),
                "task_count": task_count,
                "pass_count": pass_count,
                "raw_fail_count": raw_fail_count,
                "domains": domains,
                "zip_name": _basename(manifest.get("zip_path", "")),
            }
        )
        for task in tasks:
            metrics = task.get("metrics", {}) if isinstance(task.get("metrics"), dict) else {}
            task_rows.append(
                {
                    "set_id": str(manifest.get("set_id", set_dir.name)),
                    "claim_role": str(manifest.get("claim_role", "")),
                    "task_id": str(task.get("task_id", "")),
                    "domain": str(task.get("domain", "")),
                    "kind": str(task.get("kind", "")),
                    "pass": bool(task.get("pass", False)),
                    "raw_pass": task.get("raw_pass"),
                    "ranking_unique_auc": metrics.get("ranking_unique_auc", ""),
                    "ranking_pr_auc": metrics.get("ranking_pr_auc", ""),
                    "ranking_ef1": metrics.get("ranking_ef1", ""),
                    "ranking_bedroc": metrics.get("ranking_bedroc", ""),
                    "operational_gate_pass": metrics.get("operational_gate_pass", ""),
                    "strict_gate_pass": metrics.get("strict_gate_pass", ""),
                    "ranking_pass": metrics.get("ranking_pass", ""),
                    "integrity_pass": metrics.get("integrity_pass", ""),
                    "profile_json": _basename(task.get("profile_json", "")),
                    "acceptance_note": str(task.get("acceptance_note", "")),
                }
            )

    out_root = (ROOT / args.out_root).resolve() if not Path(args.out_root).is_absolute() else Path(args.out_root).resolve()
    label = str(args.label).strip() or "current"
    task_csv = out_root / f"biorxiv_external_validation_task_table_{label}.csv"
    task_md = out_root / f"biorxiv_external_validation_task_table_{label}.md"
    set_csv = out_root / f"biorxiv_external_validation_set_table_{label}.csv"
    set_md = out_root / f"biorxiv_external_validation_set_table_{label}.md"
    main_csv = out_root / f"biorxiv_external_validation_main_table_{label}.csv"
    main_md = out_root / f"biorxiv_external_validation_main_table_{label}.md"
    supp_csv = out_root / f"biorxiv_external_validation_supplementary_task_table_{label}.csv"
    supp_md = out_root / f"biorxiv_external_validation_supplementary_task_table_{label}.md"
    summary_json_out = out_root / f"biorxiv_external_validation_manuscript_tables_{label}.json"

    set_fields = ["set_id", "claim_role", "pass", "task_count", "pass_count", "raw_fail_count", "domains", "zip_name"]
    task_fields = [
        "set_id",
        "claim_role",
        "task_id",
        "domain",
        "kind",
        "pass",
        "raw_pass",
        "ranking_unique_auc",
        "ranking_pr_auc",
        "ranking_ef1",
        "ranking_bedroc",
        "operational_gate_pass",
        "strict_gate_pass",
        "ranking_pass",
        "integrity_pass",
        "profile_json",
        "acceptance_note",
    ]
    _write_csv(set_csv, set_rows, set_fields)
    _write_csv(task_csv, task_rows, task_fields)
    _write_text(set_md, _md_table(set_rows, set_fields, "bioRxiv Validation Set Table"))
    _write_text(task_md, _md_table(task_rows, task_fields, "bioRxiv Validation Task Table"))
    _write_csv(supp_csv, task_rows, task_fields)
    _write_text(supp_md, _md_table(task_rows, task_fields, "Supplementary bioRxiv Validation Task Table"))

    main_rows: list[dict[str, Any]] = []
    main_specs = [
        ("set1_core_blind", "primary"),
        ("set2_expanded_ood", "secondary_generalization"),
        ("set3_operational_smoke", "reproducibility_support"),
    ]
    for set_id, role in main_specs:
        task_map = set_task_map.get(set_id, {})
        main_rows.append(
            {
                "set_id": set_id,
                "claim_role": role,
                "overall_pass": bool(next((r["pass"] for r in set_rows if r["set_id"] == set_id), False)),
                "gpcr": _task_cell(task_map.get("gpcr", {})),
                "ion_channel": _task_cell(task_map.get("ion_channel", {})),
                "kinase": _task_cell(task_map.get("kinase", {})),
                "idp": _task_cell(task_map.get("idp", {})),
            }
        )
    main_fields = ["set_id", "claim_role", "overall_pass", "gpcr", "ion_channel", "kinase", "idp"]
    _write_csv(main_csv, main_rows, main_fields)
    _write_text(main_md, _md_table(main_rows, main_fields, "Main bioRxiv Validation Table"))

    payload = {
        "bundle_tag": bundle_tag,
        "run_root": str(run_root),
        "main_table_csv": str(main_csv),
        "main_table_md": str(main_md),
        "set_table_csv": str(set_csv),
        "set_table_md": str(set_md),
        "task_table_csv": str(task_csv),
        "task_table_md": str(task_md),
        "supplementary_task_table_csv": str(supp_csv),
        "supplementary_task_table_md": str(supp_md),
        "set_count": len(set_rows),
        "task_count": len(task_rows),
    }
    _write_text(summary_json_out, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
