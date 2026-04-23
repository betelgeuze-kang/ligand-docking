#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import pandas as pd


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _parse_roles(spec: str) -> List[str]:
    return [tok.strip() for tok in str(spec or "").split(",") if tok.strip()]


def _key_set(df: pd.DataFrame, target_col: str, ligand_col: str) -> Set[Tuple[str, str]]:
    if df.empty:
        return set()
    t = df[target_col].astype(str)
    l = df[ligand_col].astype(str)
    return set(zip(t, l))


def _safe_ratio(num: Optional[int], den: Optional[int]) -> Optional[float]:
    if num is None or den is None:
        return None
    d = int(den)
    if d <= 0:
        return None
    return float(int(num) / float(d))


def run_validation(args: argparse.Namespace) -> Dict[str, Any]:
    split_csv = str(args.split_csv).strip()
    if (not split_csv) or (not os.path.exists(split_csv)):
        raise FileNotFoundError(f"split csv not found: {split_csv}")
    split_df = pd.read_csv(split_csv)

    split_target_col = str(args.split_target_col).strip()
    split_ligand_col = str(args.split_ligand_col).strip()
    split_role_col = str(args.split_role_col).strip()
    req = {split_target_col, split_ligand_col, split_role_col}
    miss = [c for c in req if c not in split_df.columns]
    if miss:
        raise ValueError(f"split csv missing columns: {miss}")

    fit_roles = _parse_roles(str(args.fit_roles))
    eval_roles = _parse_roles(str(args.eval_roles))
    if not fit_roles:
        raise ValueError("fit roles are empty")
    if not eval_roles:
        raise ValueError("eval roles are empty")

    fit_df = split_df[split_df[split_role_col].astype(str).isin(fit_roles)].copy()
    eval_df = split_df[split_df[split_role_col].astype(str).isin(eval_roles)].copy()

    fit_keys = _key_set(fit_df, split_target_col, split_ligand_col)
    eval_keys = _key_set(eval_df, split_target_col, split_ligand_col)
    expected_keys: Optional[Set[Tuple[str, str]]] = None
    expected_keys_csv = str(getattr(args, "expected_keys_csv", "") or "").strip()
    if expected_keys_csv:
        if not os.path.exists(expected_keys_csv):
            raise FileNotFoundError(f"expected keys csv not found: {expected_keys_csv}")
        ek_df = pd.read_csv(expected_keys_csv)
        ek_target_col = str(getattr(args, "expected_target_col", "target") or "target").strip()
        ek_ligand_col = str(getattr(args, "expected_ligand_col", "ligand_id") or "ligand_id").strip()
        ek_req = {ek_target_col, ek_ligand_col}
        ek_miss = [c for c in ek_req if c not in ek_df.columns]
        if ek_miss:
            raise ValueError(f"expected keys csv missing columns: {ek_miss}")
        expected_keys = _key_set(ek_df, ek_target_col, ek_ligand_col)
        fit_keys = fit_keys & expected_keys
        eval_keys = eval_keys & expected_keys

    overlap = fit_keys & eval_keys
    fit_eval_overlap_count = int(len(overlap))
    fit_eval_overlap_ratio = float(fit_eval_overlap_count / max(len(eval_keys), 1))

    observed_fit_count = None
    observed_eval_count = None
    observed_overlap_count = None
    observed_overlap_ratio = None
    observed_fit_coverage_ratio = None
    observed_eval_coverage_ratio = None
    observed_eval_positive_count = None
    observed_eval_positive_covered_count = None
    observed_eval_positive_coverage_ratio = None
    scores_csv = str(getattr(args, "scores_csv", "") or "").strip()
    score_target_col = str(getattr(args, "score_target_col", "target") or "target").strip()
    score_ligand_col = str(getattr(args, "score_ligand_col", "ligand_id") or "ligand_id").strip()
    if scores_csv:
        if not os.path.exists(scores_csv):
            raise FileNotFoundError(f"scores csv not found: {scores_csv}")
        sdf = pd.read_csv(scores_csv)
        sreq = {score_target_col, score_ligand_col}
        smiss = [c for c in sreq if c not in sdf.columns]
        if smiss:
            raise ValueError(f"scores csv missing columns: {smiss}")
        score_keys = _key_set(sdf, score_target_col, score_ligand_col)
        observed_fit = fit_keys & score_keys
        observed_eval = eval_keys & score_keys
        observed_overlap = observed_fit & observed_eval
        observed_fit_count = int(len(observed_fit))
        observed_eval_count = int(len(observed_eval))
        observed_overlap_count = int(len(observed_overlap))
        observed_overlap_ratio = float(observed_overlap_count / max(observed_eval_count, 1))
        observed_fit_coverage_ratio = _safe_ratio(observed_fit_count, len(fit_keys))
        observed_eval_coverage_ratio = _safe_ratio(observed_eval_count, len(eval_keys))

        labels_csv = str(getattr(args, "labels_csv", "") or "").strip()
        if labels_csv:
            if not os.path.exists(labels_csv):
                raise FileNotFoundError(f"labels csv not found: {labels_csv}")
            ldf = pd.read_csv(labels_csv)
            l_target_col = str(getattr(args, "labels_target_col", split_target_col) or split_target_col).strip()
            l_ligand_col = str(getattr(args, "labels_ligand_col", split_ligand_col) or split_ligand_col).strip()
            l_binder_col = str(getattr(args, "labels_binder_col", "is_binder") or "is_binder").strip()
            l_req = {l_target_col, l_ligand_col, l_binder_col}
            l_miss = [c for c in l_req if c not in ldf.columns]
            if l_miss:
                raise ValueError(f"labels csv missing columns: {l_miss}")
            l_part = ldf[[l_target_col, l_ligand_col, l_binder_col]].copy()
            l_part = l_part.rename(columns={l_target_col: split_target_col, l_ligand_col: split_ligand_col})
            l_part[l_binder_col] = pd.to_numeric(l_part[l_binder_col], errors="coerce").fillna(0).astype(int)
            roles_pos = _parse_roles(str(getattr(args, "eval_positive_roles", "") or ""))
            if not roles_pos:
                roles_pos = list(eval_roles)
            eval_split_pos = split_df[split_df[split_role_col].astype(str).isin(roles_pos)].copy()
            eval_pos = eval_split_pos.merge(
                l_part,
                on=[split_target_col, split_ligand_col],
                how="left",
            )
            eval_pos = eval_pos[pd.to_numeric(eval_pos[l_binder_col], errors="coerce").fillna(0).astype(int) == 1].copy()
            eval_pos_keys = _key_set(eval_pos, split_target_col, split_ligand_col)
            if expected_keys is not None:
                eval_pos_keys = eval_pos_keys & expected_keys
            observed_eval_positive = eval_pos_keys & score_keys
            observed_eval_positive_count = int(len(eval_pos_keys))
            observed_eval_positive_covered_count = int(len(observed_eval_positive))
            observed_eval_positive_coverage_ratio = _safe_ratio(
                observed_eval_positive_covered_count,
                observed_eval_positive_count,
            )

    failed_checks: List[Dict[str, Any]] = []
    passed = bool(fit_eval_overlap_count == 0)
    if observed_overlap_count is not None:
        passed = passed and bool(observed_overlap_count == 0)
    if fit_eval_overlap_count != 0:
        failed_checks.append({"metric": "fit_eval_overlap_count", "value": int(fit_eval_overlap_count), "threshold": 0})
    if (observed_overlap_count is not None) and (observed_overlap_count != 0):
        failed_checks.append({"metric": "observed_overlap_count", "value": int(observed_overlap_count), "threshold": 0})

    min_fit_cov = float(getattr(args, "min_observed_fit_coverage_ratio", 0.0) or 0.0)
    min_eval_cov = float(getattr(args, "min_observed_eval_coverage_ratio", 0.0) or 0.0)
    min_eval_pos_cov = float(getattr(args, "min_observed_eval_positive_coverage_ratio", 0.0) or 0.0)
    if min_fit_cov > 0:
        v = observed_fit_coverage_ratio
        if (v is None) or (float(v) < min_fit_cov):
            passed = False
            failed_checks.append({"metric": "observed_fit_coverage_ratio", "value": v, "threshold": min_fit_cov})
    if min_eval_cov > 0:
        v = observed_eval_coverage_ratio
        if (v is None) or (float(v) < min_eval_cov):
            passed = False
            failed_checks.append({"metric": "observed_eval_coverage_ratio", "value": v, "threshold": min_eval_cov})
    if min_eval_pos_cov > 0:
        v = observed_eval_positive_coverage_ratio
        if (v is None) or (float(v) < min_eval_pos_cov):
            passed = False
            failed_checks.append({"metric": "observed_eval_positive_coverage_ratio", "value": v, "threshold": min_eval_pos_cov})

    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "pass": bool(passed),
        "split_csv": split_csv,
        "expected_keys_csv": expected_keys_csv,
        "scores_csv": scores_csv,
        "fit_roles": fit_roles,
        "eval_roles": eval_roles,
        "fit_unique_keys": int(len(fit_keys)),
        "eval_unique_keys": int(len(eval_keys)),
        "expected_unique_keys": (int(len(expected_keys)) if expected_keys is not None else None),
        "fit_eval_overlap_count": int(fit_eval_overlap_count),
        "fit_eval_overlap_ratio": float(fit_eval_overlap_ratio),
        "overlap_examples": [
            {"target": str(t), "ligand_id": str(l)}
            for (t, l) in sorted(overlap)[: int(max(args.max_overlap_examples, 0))]
        ],
        "observed_fit_unique_keys": observed_fit_count,
        "observed_eval_unique_keys": observed_eval_count,
        "observed_overlap_count": observed_overlap_count,
        "observed_overlap_ratio": observed_overlap_ratio,
        "observed_fit_coverage_ratio": observed_fit_coverage_ratio,
        "observed_eval_coverage_ratio": observed_eval_coverage_ratio,
        "observed_eval_positive_count": observed_eval_positive_count,
        "observed_eval_positive_covered_count": observed_eval_positive_covered_count,
        "observed_eval_positive_coverage_ratio": observed_eval_positive_coverage_ratio,
        "coverage_thresholds": {
            "min_observed_fit_coverage_ratio": min_fit_cov,
            "min_observed_eval_coverage_ratio": min_eval_cov,
            "min_observed_eval_positive_coverage_ratio": min_eval_pos_cov,
        },
        "failed_checks": failed_checks,
        "artifacts": {},
    }

    out_json = str(args.out_json).strip()
    out_md = str(args.out_md).strip()
    out_csv = str(args.out_csv).strip()
    _ensure_parent(out_json)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    summary["artifacts"]["out_json"] = out_json

    _ensure_parent(out_csv)
    pd.DataFrame(
        [
            {
                "fit_unique_keys": summary["fit_unique_keys"],
                "eval_unique_keys": summary["eval_unique_keys"],
                "fit_eval_overlap_count": summary["fit_eval_overlap_count"],
                "fit_eval_overlap_ratio": summary["fit_eval_overlap_ratio"],
                "observed_fit_unique_keys": summary["observed_fit_unique_keys"],
                "observed_eval_unique_keys": summary["observed_eval_unique_keys"],
                "observed_overlap_count": summary["observed_overlap_count"],
                "observed_overlap_ratio": summary["observed_overlap_ratio"],
                "observed_fit_coverage_ratio": summary["observed_fit_coverage_ratio"],
                "observed_eval_coverage_ratio": summary["observed_eval_coverage_ratio"],
                "observed_eval_positive_count": summary["observed_eval_positive_count"],
                "observed_eval_positive_covered_count": summary["observed_eval_positive_covered_count"],
                "observed_eval_positive_coverage_ratio": summary["observed_eval_positive_coverage_ratio"],
                "pass": summary["pass"],
            }
        ]
    ).to_csv(out_csv, index=False)
    summary["artifacts"]["out_csv"] = out_csv

    lines = [
        "# Ligand Eval Integrity",
        "",
        f"- generated_at_local: {summary['generated_at_local']}",
        f"- pass: {summary['pass']}",
        f"- split_csv: `{split_csv}`",
        f"- scores_csv: `{scores_csv}`",
        f"- fit_roles: {fit_roles}",
        f"- eval_roles: {eval_roles}",
        f"- fit_unique_keys: {summary['fit_unique_keys']}",
        f"- eval_unique_keys: {summary['eval_unique_keys']}",
        f"- fit_eval_overlap_count: {summary['fit_eval_overlap_count']}",
        f"- fit_eval_overlap_ratio: {summary['fit_eval_overlap_ratio']}",
        f"- observed_overlap_count: {summary['observed_overlap_count']}",
        f"- observed_overlap_ratio: {summary['observed_overlap_ratio']}",
        f"- observed_fit_coverage_ratio: {summary['observed_fit_coverage_ratio']}",
        f"- observed_eval_coverage_ratio: {summary['observed_eval_coverage_ratio']}",
        f"- observed_eval_positive_count: {summary['observed_eval_positive_count']}",
        f"- observed_eval_positive_covered_count: {summary['observed_eval_positive_covered_count']}",
        f"- observed_eval_positive_coverage_ratio: {summary['observed_eval_positive_coverage_ratio']}",
        f"- coverage_thresholds: {summary['coverage_thresholds']}",
        f"- failed_checks: {summary['failed_checks']}",
    ]
    _ensure_parent(out_md)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    summary["artifacts"]["out_md"] = out_md
    return summary


def build_parser() -> argparse.ArgumentParser:
    stamp = dt.date.today().isoformat()
    p = argparse.ArgumentParser(description="Validate fit/eval split leakage for ligand ranking.")
    p.add_argument("--split-csv", type=str, required=True)
    p.add_argument("--scores-csv", type=str, default="")
    p.add_argument("--fit-roles", type=str, default="fit")
    p.add_argument("--eval-roles", type=str, default="eval,ood_eval")
    p.add_argument("--split-target-col", type=str, default="target")
    p.add_argument("--split-ligand-col", type=str, default="ligand_id")
    p.add_argument("--split-role-col", type=str, default="role")
    p.add_argument("--score-target-col", type=str, default="target")
    p.add_argument("--score-ligand-col", type=str, default="ligand_id")
    p.add_argument("--expected-keys-csv", type=str, default="")
    p.add_argument("--expected-target-col", type=str, default="target")
    p.add_argument("--expected-ligand-col", type=str, default="ligand_id")
    p.add_argument("--labels-csv", type=str, default="")
    p.add_argument("--labels-target-col", type=str, default="target")
    p.add_argument("--labels-ligand-col", type=str, default="ligand_id")
    p.add_argument("--labels-binder-col", type=str, default="is_binder")
    p.add_argument("--eval-positive-roles", type=str, default="")
    p.add_argument("--min-observed-fit-coverage-ratio", type=float, default=0.0)
    p.add_argument("--min-observed-eval-coverage-ratio", type=float, default=0.0)
    p.add_argument("--min-observed-eval-positive-coverage-ratio", type=float, default=0.0)
    p.add_argument("--max-overlap-examples", type=int, default=10)
    p.add_argument("--out-json", type=str, default=f"runs/ligand_eval_integrity_{stamp}.json")
    p.add_argument("--out-csv", type=str, default=f"runs/ligand_eval_integrity_{stamp}.csv")
    p.add_argument("--out-md", type=str, default=f"runs/ligand_eval_integrity_{stamp}.md")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = run_validation(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not bool(payload.get("pass", False)):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
