#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fmt_float(v: Any, digits: int = 4) -> str:
    if not isinstance(v, (int, float)):
        try:
            v = float(v)
        except Exception:
            return ""
    fv = float(v)
    if math.isnan(fv) or math.isinf(fv):
        return ""
    return f"{fv:.{digits}f}"


def _bool_text(v: Any) -> str:
    if v is True:
        return "PASS"
    if v is False:
        return "FAIL"
    return "NA"


def _resolve_run_root(path_str: str) -> Path:
    p = Path(path_str)
    return (ROOT / p).resolve() if not p.is_absolute() else p.resolve()


def _load_task_index(run_root: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    top = _read_json(run_root / "summary.json")
    out: Dict[str, Dict[str, Any]] = {}
    set_rows: Dict[str, Any] = {}
    for set_dir in sorted(run_root.glob("*/manifest.json")):
        man = _read_json(set_dir)
        set_id = str(man.get("set_id") or set_dir.parent.name)
        set_rows[set_id] = {"pass": man.get("pass"), "title": man.get("title", set_id)}
        for task in man.get("tasks", []) or []:
            key = f"{set_id}::{task.get('task_id')}"
            out[key] = dict(task)
    return out, top


def _select_task_keys(
    baseline_keys: set[str],
    candidate_keys: set[str],
    *,
    task_scope: str,
) -> List[str]:
    scope = str(task_scope or "union").strip().lower()
    if scope == "baseline":
        keys = baseline_keys
    elif scope == "candidate":
        keys = candidate_keys
    elif scope == "common":
        keys = baseline_keys & candidate_keys
    else:
        keys = baseline_keys | candidate_keys
    return sorted(keys)


def _read_manifest_if_exists(run_root: Path, set_id: str) -> Dict[str, Any]:
    path = run_root / set_id / "manifest.json"
    if not path.exists():
        return {}
    return _read_json(path)


def _enrich_task(task: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(task)
    metrics = row.get("metrics", {}) if isinstance(row.get("metrics"), dict) else {}
    row.setdefault("ranking_unique_auc", metrics.get("ranking_unique_auc"))
    row.setdefault("ranking_pr_auc", metrics.get("ranking_pr_auc"))
    row.setdefault("ranking_ef1", metrics.get("ranking_ef1"))
    row.setdefault("ranking_bedroc", metrics.get("ranking_bedroc"))
    row.setdefault("operational_gate_pass", metrics.get("operational_gate_pass"))
    row.setdefault("strict_gate_pass", metrics.get("strict_gate_pass"))
    row.setdefault("ranking_pass", metrics.get("ranking_pass"))
    row.setdefault("integrity_pass", metrics.get("integrity_pass"))
    pipe = None
    pipe_path = str(row.get("pipeline_summary_json") or "").strip()
    if pipe_path:
        p = Path(pipe_path).resolve()
        if p.exists():
            pipe = _read_json(p)
    if pipe:
        stages = pipe.get("stages", {}) if isinstance(pipe.get("stages"), dict) else {}
        stage6 = stages.get("stage6_operational_gate", {}) if isinstance(stages.get("stage6_operational_gate"), dict) else {}
        row["ranking_topk_hit_rate"] = stage6.get("ranking_topk_hit_rate")
        row["ranking_pr_auc_ci_low"] = stage6.get("ranking_pr_auc_ci_low")
        row["ranking_ef1_ci_low"] = stage6.get("ranking_ef1_ci_low")
        row["mean_min_distance_A"] = stage6.get("mean_min_distance_A")
        row["ranking_score_col_used"] = stage6.get("ranking_score_col_used")
        row["ranking_probability_score_col_used"] = stage6.get("ranking_probability_score_col_used")
    return row


def _compare_metric(a: Any, b: Any) -> Dict[str, Any]:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return {"baseline": float(a), "candidate": float(b), "delta": float(b) - float(a)}
    return {"baseline": a, "candidate": b, "delta": None}


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compare two bioRxiv external-validation run roots side by side.")
    ap.add_argument("--baseline-run-root", required=True)
    ap.add_argument("--candidate-run-root", required=True)
    ap.add_argument("--out-root", default="runs")
    ap.add_argument("--label", default="current_vs_candidate")
    ap.add_argument(
        "--task-scope",
        choices=["union", "common", "candidate", "baseline"],
        default="union",
        help="Which task keys to include. Use candidate for slice comparisons against a larger baseline package.",
    )
    args = ap.parse_args(argv)

    baseline_root = _resolve_run_root(args.baseline_run_root)
    candidate_root = _resolve_run_root(args.candidate_run_root)
    out_root = _resolve_run_root(args.out_root)
    bundle_root = out_root / f"biorxiv_run_comparison_{args.label}"
    bundle_root.mkdir(parents=True, exist_ok=True)

    baseline_idx, baseline_top = _load_task_index(baseline_root)
    candidate_idx, candidate_top = _load_task_index(candidate_root)

    baseline_keys = set(baseline_idx.keys())
    candidate_keys = set(candidate_idx.keys())
    all_keys = _select_task_keys(baseline_keys, candidate_keys, task_scope=str(args.task_scope))
    rows: List[Dict[str, Any]] = []
    set_summary: Dict[str, Dict[str, Any]] = {}
    improved = 0
    regressed = 0
    changed_profiles = 0

    for key in all_keys:
        b = _enrich_task(baseline_idx.get(key, {})) if key in baseline_idx else {}
        c = _enrich_task(candidate_idx.get(key, {})) if key in candidate_idx else {}
        set_id, task_id = key.split("::", 1)
        domain = c.get("domain") or b.get("domain")
        kind = c.get("kind") or b.get("kind")
        b_pr = b.get("ranking_pr_auc")
        c_pr = c.get("ranking_pr_auc")
        b_ef1 = b.get("ranking_ef1")
        c_ef1 = c.get("ranking_ef1")
        b_top20 = b.get("ranking_topk_hit_rate")
        c_top20 = c.get("ranking_topk_hit_rate")
        profile_changed = str(b.get("profile_json", "")) != str(c.get("profile_json", ""))
        if profile_changed:
            changed_profiles += 1
        delta_pr = (float(c_pr) - float(b_pr)) if isinstance(b_pr, (int, float)) and isinstance(c_pr, (int, float)) else None
        if delta_pr is not None:
            if delta_pr > 1e-12:
                improved += 1
            elif delta_pr < -1e-12:
                regressed += 1
        row = {
            "set_id": set_id,
            "task_id": task_id,
            "domain": domain,
            "kind": kind,
            "baseline_pass": b.get("pass"),
            "candidate_pass": c.get("pass"),
            "baseline_profile_json": b.get("profile_json", ""),
            "candidate_profile_json": c.get("profile_json", ""),
            "profile_changed": profile_changed,
            "baseline_score_col": b.get("ranking_score_col_used", ""),
            "candidate_score_col": c.get("ranking_score_col_used", ""),
            "score_changed": str(b.get("ranking_score_col_used", "")) != str(c.get("ranking_score_col_used", "")),
            "baseline_pr_auc": b_pr,
            "candidate_pr_auc": c_pr,
            "delta_pr_auc": delta_pr,
            "baseline_ef1": b_ef1,
            "candidate_ef1": c_ef1,
            "delta_ef1": (float(c_ef1) - float(b_ef1)) if isinstance(b_ef1, (int, float)) and isinstance(c_ef1, (int, float)) else None,
            "baseline_top20_hit_rate": b_top20,
            "candidate_top20_hit_rate": c_top20,
            "delta_top20_hit_rate": (float(c_top20) - float(b_top20)) if isinstance(b_top20, (int, float)) and isinstance(c_top20, (int, float)) else None,
            "baseline_operational_gate_pass": b.get("operational_gate_pass"),
            "candidate_operational_gate_pass": c.get("operational_gate_pass"),
            "baseline_mean_min_distance_A": b.get("mean_min_distance_A"),
            "candidate_mean_min_distance_A": c.get("mean_min_distance_A"),
        }
        rows.append(row)
        ss = set_summary.setdefault(set_id, {"tasks": 0, "improved": 0, "regressed": 0, "baseline_pass": None, "candidate_pass": None})
        ss["tasks"] += 1
        if delta_pr is not None and delta_pr > 1e-12:
            ss["improved"] += 1
        elif delta_pr is not None and delta_pr < -1e-12:
            ss["regressed"] += 1

    for set_id in set_summary:
        b_man = _read_manifest_if_exists(baseline_root, set_id)
        c_man = _read_manifest_if_exists(candidate_root, set_id)
        set_summary[set_id]["baseline_pass"] = b_man.get("pass")
        set_summary[set_id]["candidate_pass"] = c_man.get("pass")

    summary = {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "baseline_run_root": str(baseline_root),
        "candidate_run_root": str(candidate_root),
        "baseline_status": baseline_top.get("status"),
        "candidate_status": candidate_top.get("status"),
        "task_scope": str(args.task_scope),
        "baseline_task_count_total": int(len(baseline_keys)),
        "candidate_task_count_total": int(len(candidate_keys)),
        "task_count": len(rows),
        "tasks_with_pr_improvement": improved,
        "tasks_with_pr_regression": regressed,
        "profile_changed_task_count": changed_profiles,
        "set_summary": set_summary,
        "task_rows": rows,
    }

    summary_json = bundle_root / "summary.json"
    summary_md = bundle_root / "summary.md"
    task_csv = bundle_root / "task_comparison.csv"
    set_csv = bundle_root / "set_comparison.csv"
    _write_json(summary_json, summary)

    with task_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["set_id", "task_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    with set_csv.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["set_id", "tasks", "improved", "regressed", "baseline_pass", "candidate_pass"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for set_id, row in sorted(set_summary.items()):
            writer.writerow({"set_id": set_id, **row})

    md_lines = [
        "# bioRxiv Run Comparison",
        "",
        f"- baseline_run_root: `{baseline_root}`",
        f"- candidate_run_root: `{candidate_root}`",
        f"- task_scope: `{args.task_scope}`",
        f"- task_count: `{len(rows)}`",
        f"- tasks_with_pr_improvement: `{improved}`",
        f"- tasks_with_pr_regression: `{regressed}`",
        f"- profile_changed_task_count: `{changed_profiles}`",
        "",
        "## Set Summary",
        "",
        "| set | baseline | candidate | improved_tasks | regressed_tasks |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for set_id, row in sorted(set_summary.items()):
        md_lines.append(
            f"| {set_id} | {_bool_text(row['baseline_pass'])} | {_bool_text(row['candidate_pass'])} | {row['improved']} | {row['regressed']} |"
        )
    md_lines.extend([
        "",
        "## Task Deltas",
        "",
        "| set | task | domain | baseline_score | candidate_score | delta_pr | delta_ef1 | delta_top20 |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: |",
    ])
    for row in sorted(rows, key=lambda r: (r['set_id'], r['task_id'])):
        md_lines.append(
            f"| {row['set_id']} | {row['task_id']} | {row['domain']} | {row['baseline_score_col']} | {row['candidate_score_col']} | {_fmt_float(row['delta_pr_auc'])} | {_fmt_float(row['delta_ef1'])} | {_fmt_float(row['delta_top20_hit_rate'])} |"
        )
    _write_text(summary_md, "\n".join(md_lines) + "\n")

    print(json.dumps({
        "ok": True,
        "summary_json": str(summary_json.resolve()),
        "summary_md": str(summary_md.resolve()),
        "task_count": len(rows),
        "tasks_with_pr_improvement": improved,
        "tasks_with_pr_regression": regressed,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
