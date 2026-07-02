#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fmt_float(v: Any, digits: int = 4) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return ""
        return f"{float(v):.{digits}f}"
    try:
        fv = float(v)
    except Exception:
        return ""
    if math.isnan(fv) or math.isinf(fv):
        return ""
    return f"{fv:.{digits}f}"


def _slug(text: str) -> str:
    out = []
    for ch in str(text):
        if ch.isalnum() or ch in {"-", "_"}:
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("_") or "x"


def _load_spec(path: Path) -> Dict[str, Any]:
    spec = _read_json(path)
    if not isinstance(spec.get("candidate_score_columns"), list) or not spec["candidate_score_columns"]:
        raise ValueError(f"Spec missing candidate_score_columns: {path}")
    return spec


def _load_run_root(args: argparse.Namespace) -> Path:
    if str(args.run_root).strip():
        p = Path(str(args.run_root))
        return (ROOT / p).resolve() if not p.is_absolute() else p.resolve()
    meta_path = Path(str(args.current_meta_json))
    meta_path = (ROOT / meta_path).resolve() if not meta_path.is_absolute() else meta_path.resolve()
    meta = _read_json(meta_path)
    run_root = Path(str(meta.get("run_root", ""))).resolve()
    if not run_root.exists():
        raise FileNotFoundError(f"run_root not found from {meta_path}: {run_root}")
    return run_root


def _find_set_manifests(run_root: Path) -> List[Path]:
    manifests = sorted(run_root.glob("*/manifest.json"))
    return [p for p in manifests if p.is_file()]


def _get_flag(cmd: List[str], flag: str) -> Optional[str]:
    for i, tok in enumerate(cmd):
        if tok == flag and (i + 1) < len(cmd):
            return str(cmd[i + 1])
    return None


def _set_flag(cmd: List[str], flag: str, value: str) -> None:
    for i, tok in enumerate(cmd):
        if tok == flag:
            if (i + 1) < len(cmd):
                cmd[i + 1] = value
                return
    cmd.extend([flag, value])


def _read_stage3_columns(scores_csv: Path) -> List[str]:
    with scores_csv.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            return next(reader)
        except StopIteration:
            return []


def _ranking_summary_from_cmd(cmd: List[str]) -> Path:
    out_json = _get_flag(cmd, "--out-json")
    if not out_json:
        raise ValueError("stage5 command missing --out-json")
    return Path(out_json).resolve()


def _extract_topk(summary: Dict[str, Any], k: int) -> Dict[str, Any]:
    for row in summary.get("topk_unique", []) or []:
        try:
            if int(row.get("k", -1)) == int(k):
                return dict(row)
        except Exception:
            continue
    return {}


def _extract_metrics(summary: Dict[str, Any]) -> Dict[str, Any]:
    metrics = summary.get("metrics_unique", {}) if isinstance(summary.get("metrics_unique"), dict) else {}
    ci = summary.get("metrics_ci_unique", {}) if isinstance(summary.get("metrics_ci_unique"), dict) else {}
    top10 = _extract_topk(summary, 10)
    top20 = _extract_topk(summary, 20)
    top50 = _extract_topk(summary, 50)

    def _ci_low(name: str) -> Optional[float]:
        payload = ci.get(name)
        if isinstance(payload, dict):
            v = payload.get("low")
            return float(v) if isinstance(v, (int, float)) else None
        return None

    return {
        "score_col": summary.get("score_col"),
        "probability_score_col": summary.get("probability_score_col"),
        "roc_auc": metrics.get("roc_auc"),
        "pr_auc": metrics.get("pr_auc"),
        "ef1": metrics.get("ef1"),
        "bedroc": metrics.get("bedroc_alpha20"),
        "brier": metrics.get("brier"),
        "ece": metrics.get("ece_10bin"),
        "roc_auc_ci_low": _ci_low("roc_auc"),
        "pr_auc_ci_low": _ci_low("pr_auc"),
        "ef1_ci_low": _ci_low("ef1"),
        "top10_hit_rate": top10.get("hit_rate"),
        "top10_hits": top10.get("hits"),
        "top20_hit_rate": top20.get("hit_rate"),
        "top20_hits": top20.get("hits"),
        "top50_hit_rate": top50.get("hit_rate"),
        "top50_hits": top50.get("hits"),
        "rows_eval": summary.get("rows_eval"),
        "eval_unique_keys": summary.get("eval_unique_keys"),
        "observed_expected_score_coverage_ratio": summary.get("observed_expected_score_coverage_ratio"),
        "mean_min_distance_A_unique": summary.get("mean_min_distance_A_unique"),
        "mean_min_distance_A_topk_unique": summary.get("mean_min_distance_A_topk_unique"),
        "distance_topk_k": summary.get("distance_topk_k"),
        "lower_better": summary.get("lower_better"),
    }


def _winner_key(row: Dict[str, Any], primary: str, tie_breaks: List[str]) -> tuple:
    def _norm(v: Any) -> float:
        if isinstance(v, (int, float)):
            fv = float(v)
            if math.isnan(fv) or math.isinf(fv):
                return float("-inf")
            return fv
        return float("-inf")

    vals = [_norm(row.get(primary))]
    vals.extend(_norm(row.get(k)) for k in tie_breaks)
    return tuple(vals)


def _run_eval(cmd: List[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "baseline evaluator failed\n"
            f"cmd: {' '.join(cmd)}\n"
            f"returncode: {proc.returncode}\n"
            f"stdout:\n{proc.stdout[-4000:]}\n"
            f"stderr:\n{proc.stderr[-4000:]}"
        )


def _collect_tasks(run_root: Path, task_kind: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for manifest_path in _find_set_manifests(run_root):
        manifest = _read_json(manifest_path)
        set_id = str(manifest.get("set_id") or manifest_path.parent.name)
        for task in manifest.get("tasks", []) or []:
            if str(task.get("kind", "")) != task_kind:
                continue
            if not str(task.get("pipeline_summary_json") or "").strip():
                continue
            row = dict(task)
            row["set_id"] = set_id
            rows.append(row)
    return rows


def _score_rows_for_task(
    task: Dict[str, Any],
    spec: Dict[str, Any],
    bundle_root: Path,
    rerun_current: bool,
) -> Dict[str, Any]:
    task_id = str(task.get("task_id"))
    set_id = str(task.get("set_id"))
    pipe_path = Path(str(task.get("pipeline_summary_json"))).resolve()
    pipe = _read_json(pipe_path)
    stage5 = ((pipe.get("stages") or {}).get("stage5_ranking_eval") or {})
    stage5_cmd = list(stage5.get("cmd") or [])
    if not stage5_cmd:
        raise ValueError(f"stage5 command missing for {task_id}: {pipe_path}")
    scores_csv = Path(str(_get_flag(stage5_cmd, "--scores-csv") or "")).resolve()
    if not scores_csv.exists():
        raise FileNotFoundError(f"scores csv missing for {task_id}: {scores_csv}")
    current_score = str(_get_flag(stage5_cmd, "--score-col") or "")
    current_prob_score = str(_get_flag(stage5_cmd, "--probability-score-col") or current_score)
    current_summary_json = _ranking_summary_from_cmd(stage5_cmd)
    available_cols = _read_stage3_columns(scores_csv)
    candidates = [c for c in spec.get("candidate_score_columns", []) if c in available_cols]
    if current_score and current_score not in candidates:
        candidates = [current_score] + candidates
    aliases = spec.get("score_aliases", {}) if isinstance(spec.get("score_aliases"), dict) else {}

    score_rows: List[Dict[str, Any]] = []
    task_dir = bundle_root / "tasks" / f"{_slug(set_id)}__{_slug(task_id)}"
    task_dir.mkdir(parents=True, exist_ok=True)

    for score_col in candidates:
        alias = str(aliases.get(score_col, score_col))
        is_current = score_col == current_score
        out_json: Path
        if is_current and (not rerun_current) and current_summary_json.exists():
            out_json = current_summary_json
        else:
            prefix = task_dir / alias
            cmd = list(stage5_cmd)
            _set_flag(cmd, "--score-col", score_col)
            _set_flag(cmd, "--probability-score-col", score_col)
            _set_flag(cmd, "--out-detail-csv", str((prefix.with_name(prefix.name + "_rows.csv")).resolve()))
            _set_flag(cmd, "--out-topk-csv", str((prefix.with_name(prefix.name + "_topk.csv")).resolve()))
            _set_flag(cmd, "--out-unique-csv", str((prefix.with_name(prefix.name + "_unique.csv")).resolve()))
            out_json = prefix.with_name(prefix.name + "_summary.json").resolve()
            _set_flag(cmd, "--out-json", str(out_json))
            _set_flag(cmd, "--out-md", str((prefix.with_name(prefix.name + "_summary.md")).resolve()))
            _run_eval(cmd, ROOT)
        summary = _read_json(out_json)
        metrics = _extract_metrics(summary)
        row = {
            "set_id": set_id,
            "task_id": task_id,
            "domain": task.get("domain"),
            "kind": task.get("kind"),
            "profile_json": task.get("profile_json"),
            "score_col": score_col,
            "score_alias": alias,
            "is_current_score": is_current,
            "current_task_pass": task.get("pass") if is_current else None,
            "current_operational_gate_pass": (task.get("metrics") or {}).get("operational_gate_pass") if is_current else None,
            "current_strict_gate_pass": (task.get("metrics") or {}).get("strict_gate_pass") if is_current else None,
            "ranking_summary_json": str(out_json),
        }
        row.update(metrics)
        score_rows.append(row)

    primary = str(spec.get("primary_metric") or "pr_auc")
    tie_breaks = list(spec.get("tie_break_metrics") or ["top20_hit_rate", "ef1", "roc_auc"])
    winner = max(score_rows, key=lambda r: _winner_key(r, primary, tie_breaks))
    current_row = next((r for r in score_rows if r.get("is_current_score")), None)
    current_is_winner = bool(current_row and current_row.get("score_col") == winner.get("score_col"))

    return {
        "task": task,
        "pipeline_summary_json": str(pipe_path),
        "current_score_col": current_score,
        "current_probability_score_col": current_prob_score,
        "available_score_columns": available_cols,
        "tested_score_columns": candidates,
        "current_is_primary_winner": current_is_winner,
        "primary_winner": {
            "score_col": winner.get("score_col"),
            "score_alias": winner.get("score_alias"),
            "pr_auc": winner.get("pr_auc"),
            "top20_hit_rate": winner.get("top20_hit_rate"),
            "ef1": winner.get("ef1"),
            "roc_auc": winner.get("roc_auc"),
            "ranking_summary_json": winner.get("ranking_summary_json"),
        },
        "score_rows": score_rows,
    }


def _build_markdown(summary: Dict[str, Any], task_df: pd.DataFrame, score_df: pd.DataFrame) -> str:
    lines: List[str] = []
    lines.append("# External Validation Baseline Gauntlet")
    lines.append("")
    lines.append(f"- protocol_id: `{summary['protocol_id']}`")
    lines.append(f"- run_root: `{summary['run_root']}`")
    lines.append(f"- task_count: `{summary['task_count']}`")
    lines.append(f"- score_candidates: `{', '.join(summary['score_candidates'])}`")
    lines.append("")
    lines.append(summary.get("note", ""))
    lines.append("")
    lines.append("## Score Leaderboard")
    lines.append("")
    if score_df.empty:
        lines.append("No ligand tasks found.")
    else:
        lines.append("| score | tasks | wins_pr_auc | mean_pr_auc | mean_top20 | mean_ef1 |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for _, row in score_df.sort_values(["wins_pr_auc", "mean_pr_auc"], ascending=[False, False]).iterrows():
            lines.append(
                "| {score_alias} | {task_count} | {wins_pr_auc} | {mean_pr_auc} | {mean_top20_hit_rate} | {mean_ef1} |".format(
                    score_alias=row["score_alias"],
                    task_count=int(row["task_count"]),
                    wins_pr_auc=int(row["wins_pr_auc"]),
                    mean_pr_auc=_fmt_float(row["mean_pr_auc"]),
                    mean_top20_hit_rate=_fmt_float(row["mean_top20_hit_rate"]),
                    mean_ef1=_fmt_float(row["mean_ef1"]),
                )
            )
    lines.append("")
    lines.append("## Task Winners")
    lines.append("")
    lines.append("| set | task | domain | current | winner | current_pr | winner_pr | current_top20 | winner_top20 |")
    lines.append("| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |")
    if task_df.empty:
        lines.append("| - | - | - | - | - | - | - | - | - |")
    else:
        for _, row in task_df.sort_values(["set_id", "task_id"]).iterrows():
            lines.append(
                "| {set_id} | {task_id} | {domain} | {current_score_col} | {winner_score_col} | {current_pr_auc} | {winner_pr_auc} | {current_top20_hit_rate} | {winner_top20_hit_rate} |".format(
                    set_id=row["set_id"],
                    task_id=row["task_id"],
                    domain=row["domain"],
                    current_score_col=row["current_score_col"],
                    winner_score_col=row["winner_score_col"],
                    current_pr_auc=_fmt_float(row["current_pr_auc"]),
                    winner_pr_auc=_fmt_float(row["winner_pr_auc"]),
                    current_top20_hit_rate=_fmt_float(row["current_top20_hit_rate"]),
                    winner_top20_hit_rate=_fmt_float(row["winner_top20_hit_rate"]),
                )
            )
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Run a baseline gauntlet over accepted external validation ligand tasks.")
    ap.add_argument("--current-meta-json", default="runs/biorxiv_external_validation_package_current.json")
    ap.add_argument("--run-root", default="")
    ap.add_argument("--spec-json", default="config/external_validation_baselines_v1.json")
    ap.add_argument("--out-root", default="runs")
    ap.add_argument("--label", default="current")
    ap.add_argument(
        "--require-tasks",
        action="store_true",
        help="Return nonzero when no matching ligand task manifests are materialized.",
    )
    ap.add_argument("--rerun-current", action=argparse.BooleanOptionalAction, default=False)
    args = ap.parse_args(argv)

    run_root = _load_run_root(args)
    manifest_count = len(_find_set_manifests(run_root))
    spec_path = Path(str(args.spec_json))
    spec_path = (ROOT / spec_path).resolve() if not spec_path.is_absolute() else spec_path.resolve()
    spec = _load_spec(spec_path)
    out_root = Path(str(args.out_root))
    out_root = (ROOT / out_root).resolve() if not out_root.is_absolute() else out_root.resolve()
    bundle_root = out_root / f"biorxiv_baseline_comparison_{args.label}"
    bundle_root.mkdir(parents=True, exist_ok=True)

    tasks = _collect_tasks(run_root, str(spec.get("task_kind", "ligand_stress")))
    blockers: List[str] = []
    if args.require_tasks:
        if not run_root.exists():
            blockers.append("run_root_missing")
        if manifest_count <= 0:
            blockers.append("set_manifest_missing")
        if not tasks:
            blockers.append("ligand_stress_tasks_missing")
    per_task_payloads: List[Dict[str, Any]] = []
    flat_rows: List[Dict[str, Any]] = []
    winner_rows: List[Dict[str, Any]] = []
    for task in tasks:
        payload = _score_rows_for_task(task, spec, bundle_root, bool(args.rerun_current))
        per_task_payloads.append(payload)
        flat_rows.extend(payload["score_rows"])
        current_row = next((r for r in payload["score_rows"] if r.get("is_current_score")), None)
        winner = payload["primary_winner"]
        winner_rows.append(
            {
                "set_id": task.get("set_id"),
                "task_id": task.get("task_id"),
                "domain": task.get("domain"),
                "current_score_col": payload.get("current_score_col"),
                "winner_score_col": winner.get("score_col"),
                "winner_score_alias": winner.get("score_alias"),
                "current_is_primary_winner": payload.get("current_is_primary_winner"),
                "current_pr_auc": (current_row or {}).get("pr_auc"),
                "winner_pr_auc": winner.get("pr_auc"),
                "current_top20_hit_rate": (current_row or {}).get("top20_hit_rate"),
                "winner_top20_hit_rate": winner.get("top20_hit_rate"),
                "current_ef1": (current_row or {}).get("ef1"),
                "winner_ef1": winner.get("ef1"),
            }
        )

    task_df = pd.DataFrame(flat_rows)
    winner_df = pd.DataFrame(winner_rows)
    score_df = pd.DataFrame()
    if not task_df.empty:
        agg = task_df.groupby(["score_alias", "score_col"], dropna=False).agg(
            task_count=("task_id", "nunique"),
            mean_pr_auc=("pr_auc", "mean"),
            mean_roc_auc=("roc_auc", "mean"),
            mean_ef1=("ef1", "mean"),
            mean_top20_hit_rate=("top20_hit_rate", "mean"),
            mean_top20_hits=("top20_hits", "mean"),
        ).reset_index()
        wins = winner_df.groupby("winner_score_alias").size().rename("wins_pr_auc").reset_index()
        wins = wins.rename(columns={"winner_score_alias": "score_alias"})
        score_df = agg.merge(wins, on="score_alias", how="left").fillna({"wins_pr_auc": 0})
        score_df["wins_pr_auc"] = score_df["wins_pr_auc"].astype(int)

    summary = {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "protocol_id": spec.get("protocol_id"),
        "spec_json": str(spec_path),
        "run_root": str(run_root),
        "run_root_exists": run_root.exists(),
        "set_manifest_count": manifest_count,
        "bundle_root": str(bundle_root),
        "ok": not blockers,
        "blockers": blockers,
        "task_count": int(len(per_task_payloads)),
        "score_candidates": list(spec.get("candidate_score_columns", [])),
        "note": str(spec.get("note", "")),
        "task_winner_count_current": int(sum(1 for row in winner_rows if row.get("current_is_primary_winner") is True)),
        "task_winner_count_noncurrent": int(sum(1 for row in winner_rows if row.get("current_is_primary_winner") is False)),
        "tasks": [],
        "score_leaderboard": score_df.to_dict(orient="records") if not score_df.empty else [],
        "winner_table": winner_df.to_dict(orient="records") if not winner_df.empty else [],
    }
    for payload in per_task_payloads:
        task = payload["task"]
        summary["tasks"].append(
            {
                "set_id": task.get("set_id"),
                "task_id": task.get("task_id"),
                "domain": task.get("domain"),
                "kind": task.get("kind"),
                "profile_json": task.get("profile_json"),
                "pipeline_summary_json": payload.get("pipeline_summary_json"),
                "current_score_col": payload.get("current_score_col"),
                "current_probability_score_col": payload.get("current_probability_score_col"),
                "available_score_columns": payload.get("available_score_columns"),
                "tested_score_columns": payload.get("tested_score_columns"),
                "current_is_primary_winner": payload.get("current_is_primary_winner"),
                "primary_winner": payload.get("primary_winner"),
                "score_rows": payload.get("score_rows"),
            }
        )

    summary_json = bundle_root / "summary.json"
    summary_md = bundle_root / "summary.md"
    task_table_csv = bundle_root / "task_scores.csv"
    winner_table_csv = bundle_root / "task_winners.csv"
    score_table_csv = bundle_root / "score_leaderboard.csv"

    _write_json(summary_json, summary)
    if not task_df.empty:
        task_df.to_csv(task_table_csv, index=False)
    if not winner_df.empty:
        winner_df.to_csv(winner_table_csv, index=False)
    if not score_df.empty:
        score_df.to_csv(score_table_csv, index=False)
    _write_text(summary_md, _build_markdown(summary, winner_df, score_df))

    convenience = {
        "summary_json": str(summary_json.resolve()),
        "summary_md": str(summary_md.resolve()),
        "task_scores_csv": str(task_table_csv.resolve()) if task_table_csv.exists() else "",
        "task_winners_csv": str(winner_table_csv.resolve()) if winner_table_csv.exists() else "",
        "score_leaderboard_csv": str(score_table_csv.resolve()) if score_table_csv.exists() else "",
    }
    meta_json = out_root / f"biorxiv_baseline_comparison_{args.label}.json"
    meta_md = out_root / f"biorxiv_baseline_comparison_{args.label}.md"
    _write_json(meta_json, {
        "generated_at_local": summary["generated_at_local"],
        "protocol_id": spec.get("protocol_id"),
        "run_root": str(run_root),
        "bundle_root": str(bundle_root),
        "ok": not blockers,
        "blockers": blockers,
        "convenience_artifacts": convenience,
    })
    _write_text(
        meta_md,
        "# bioRxiv Baseline Comparison\n\n"
        f"- protocol_id: `{spec.get('protocol_id')}`\n"
        f"- run_root: `{run_root}`\n"
        f"- bundle_root: `{bundle_root}`\n"
        f"- summary_json: `{summary_json}`\n"
        f"- summary_md: `{summary_md}`\n",
    )
    print(json.dumps({
        "ok": not blockers,
        "summary_json": str(summary_json.resolve()),
        "summary_md": str(summary_md.resolve()),
        "task_count": len(per_task_payloads),
        "blockers": blockers,
        "winner_current": summary["task_winner_count_current"],
        "winner_noncurrent": summary["task_winner_count_noncurrent"],
    }, indent=2, ensure_ascii=False))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
