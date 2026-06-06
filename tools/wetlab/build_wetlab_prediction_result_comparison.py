#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_OUT_JSON = "runs/wetlab_prediction_result_comparison_current.json"
DEFAULT_OUT_CSV = "runs/wetlab_prediction_result_comparison_current.csv"
DEFAULT_OUT_MD = "runs/wetlab_prediction_result_comparison_current.md"
JOIN_KEY_PRIORITY = (
    "inchi_key",
    "chembl_id",
    "compound_id",
    "ligand_id",
    "normalized_name",
    "compound_name",
    "name",
)
TARGET_COL_CANDIDATES = (
    "target_id",
    "target",
    "target_name",
)
SCORE_COL_PRIORITY = (
    "commercial_overall_score_v2",
    "commercial_overall_score_v1",
    "binding_score_composite_v7_residual_active",
    "binding_score_composite_v7",
    "binding_score_composite_v6d",
    "binding_score_composite_v6b",
    "binding_score_composite_v5",
    "binding_score_composite_v4",
    "selection_score_value",
    "bulk_score",
    "binding_energy_proxy",
    "binding_energy_mmpbsa_kcal_mol_proxy",
)
IC50_NM_COLS = (
    "ic50_nM",
    "ic50_nm",
    "IC50_nM",
    "IC50_nm",
)
IC50_UM_COLS = (
    "ic50_uM",
    "ic50_um",
    "IC50_uM",
    "IC50_um",
)
PERCENT_INHIBITION_COLS = (
    "percent_inhibition",
    "percent_inhibition_mean",
    "pct_inhibition",
    "inhibition_percent",
    "% inhibition",
)
ACTIVITY_SCORE_COLS = (
    "observed_activity_score",
    "activity_score",
    "normalized_signal",
    "signal",
)
REPLICATE_COUNT_COLS = ("replicate_count", "replicates", "n_replicates")
NOTES_COLS = ("notes", "comment", "annotation")


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _infer_target_col(frame: pd.DataFrame) -> str:
    for col in TARGET_COL_CANDIDATES:
        if col in frame.columns:
            return col
    return ""


def _infer_score_col(frame: pd.DataFrame) -> str:
    for candidate in SCORE_COL_PRIORITY:
        if candidate not in frame.columns:
            continue
        series = pd.to_numeric(frame[candidate], errors="coerce")
        if series.notna().any():
            return candidate
    return ""


def _infer_actual_metric(frame: pd.DataFrame) -> tuple[str, str]:
    for col in IC50_NM_COLS:
        if col in frame.columns and pd.to_numeric(frame[col], errors="coerce").notna().any():
            return col, "ic50_nM"
    for col in IC50_UM_COLS:
        if col in frame.columns and pd.to_numeric(frame[col], errors="coerce").notna().any():
            return col, "ic50_uM"
    for col in PERCENT_INHIBITION_COLS:
        if col in frame.columns and pd.to_numeric(frame[col], errors="coerce").notna().any():
            return col, "percent_inhibition"
    for col in ACTIVITY_SCORE_COLS:
        if col in frame.columns and pd.to_numeric(frame[col], errors="coerce").notna().any():
            return col, "activity_score"
    return "", ""


def _infer_optional_col(frame: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    return ""


def _prepare_join_key(frame: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    prepared = frame.copy()
    join_key_col = ""
    for col in JOIN_KEY_PRIORITY:
        if col not in prepared.columns:
            continue
        normalized = prepared[col].map(_normalize_text)
        if normalized.ne("").any():
            prepared["join_key"] = normalized
            join_key_col = col
            break
    if "join_key" not in prepared.columns:
        prepared["join_key"] = ""
    return prepared, join_key_col


def _activity_score_from_row(row: pd.Series, actual_col: str, actual_kind: str) -> float | None:
    value = _safe_float(row.get(actual_col), None)
    if value is None:
        return None
    if actual_kind == "ic50_nM":
        if value <= 0:
            return None
        return round(9.0 - math.log10(value), 6)
    if actual_kind == "ic50_uM":
        if value <= 0:
            return None
        return round(6.0 - math.log10(value), 6)
    return value


def _binary_hit_from_row(row: pd.Series, actual_col: str, actual_kind: str) -> int | None:
    value = _safe_float(row.get(actual_col), None)
    if value is None:
        return None
    if actual_kind in {"ic50_nM", "ic50_uM"}:
        activity_score = _activity_score_from_row(row, actual_col, actual_kind)
        if activity_score is None:
            return None
        return int(activity_score >= 6.0)
    if actual_kind == "percent_inhibition":
        return int(value >= 50.0)
    return None


def _load_frame(path_like: str) -> pd.DataFrame:
    path = _resolve(path_like)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "rows" in payload:
            return pd.DataFrame(payload.get("rows", []) or [])
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        raise ValueError(f"Unsupported JSON payload shape for {path}")
    return pd.read_csv(path)


def _corr(series_a: pd.Series, series_b: pd.Series, method: str) -> float | None:
    if len(series_a) < 2 or len(series_b) < 2:
        return None
    if series_a.nunique(dropna=True) < 2 or series_b.nunique(dropna=True) < 2:
        return None
    value = series_a.corr(series_b, method=method)
    if pd.isna(value):
        return None
    return round(float(value), 6)


def build_payload(
    prediction_frame: pd.DataFrame,
    actual_frame: pd.DataFrame,
    *,
    score_col: str = "",
    actual_col: str = "",
) -> dict[str, Any]:
    pred = prediction_frame.copy()
    act = actual_frame.copy()

    pred, pred_join_key_col = _prepare_join_key(pred)
    act, act_join_key_col = _prepare_join_key(act)

    pred_target_col = _infer_target_col(pred)
    act_target_col = _infer_target_col(act)
    score_col = score_col or _infer_score_col(pred)
    actual_col = actual_col or _infer_actual_metric(act)[0]
    actual_kind = _infer_actual_metric(act)[1]

    if not score_col:
        raise ValueError("Could not infer prediction score column.")
    if not actual_col or not actual_kind:
        raise ValueError("Could not infer wet-lab activity column.")
    if not pred["join_key"].ne("").any():
        raise ValueError("Prediction table has no usable join key.")
    if not act["join_key"].ne("").any():
        raise ValueError("Actual-result table has no usable join key.")

    pred["target_id"] = pred[pred_target_col].map(str) if pred_target_col else ""
    act["target_id"] = act[act_target_col].map(str) if act_target_col else ""

    pred["prediction_score"] = pd.to_numeric(pred[score_col], errors="coerce")
    act["observed_activity_score"] = act.apply(
        lambda row: _activity_score_from_row(row, actual_col, actual_kind),
        axis=1,
    )
    act["binary_hit"] = act.apply(
        lambda row: _binary_hit_from_row(row, actual_col, actual_kind),
        axis=1,
    )

    pred = pred[pred["prediction_score"].notna() & pred["join_key"].ne("")].copy()
    act = act[act["observed_activity_score"].notna() & act["join_key"].ne("")].copy()

    if pred_target_col and act_target_col:
        merge_keys = ["target_id", "join_key"]
    else:
        merge_keys = ["join_key"]

    pred_sorted = pred.sort_values(["target_id", "prediction_score"], ascending=[True, False]).copy()
    pred_sorted["predicted_rank"] = pred_sorted.groupby("target_id").cumcount() + 1
    act_sorted = act.sort_values(["target_id", "observed_activity_score"], ascending=[True, False]).copy()
    act_sorted["observed_rank"] = act_sorted.groupby("target_id").cumcount() + 1

    replicate_col = _infer_optional_col(act_sorted, REPLICATE_COUNT_COLS)
    notes_col = _infer_optional_col(act_sorted, NOTES_COLS)
    pred_name_col = _infer_optional_col(pred_sorted, ("compound_name", "normalized_name", "ligand_id", "chembl_id"))
    act_name_col = _infer_optional_col(act_sorted, ("compound_name", "normalized_name", "ligand_id", "chembl_id"))

    merged = pred_sorted.merge(
        act_sorted,
        on=merge_keys,
        how="inner",
        suffixes=("_pred", "_actual"),
    )
    if merged.empty:
        raise ValueError("No overlapping compounds between prediction and wet-lab results.")

    merged_target_col = "target_id" if "target_id" in merge_keys else "target_id_pred"
    merged["target_id"] = merged[merged_target_col].map(str)
    merged["compound_label"] = (
        merged.get(f"{pred_name_col}_pred", pd.Series([""] * len(merged))).astype(str).where(
            merged.get(f"{pred_name_col}_pred", pd.Series([""] * len(merged))).astype(str).str.strip().ne(""),
            merged.get(f"{act_name_col}_actual", pd.Series([""] * len(merged))).astype(str),
        )
    )
    merged["rank_delta"] = merged["predicted_rank"] - merged["observed_rank"]

    rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    for target_id, group in merged.groupby("target_id", dropna=False):
        target_label = str(target_id or "global")
        group = group.sort_values("predicted_rank").copy()
        predicted_top3 = set(group.nsmallest(3, "predicted_rank")["join_key"])
        observed_top3 = set(group.nsmallest(3, "observed_rank")["join_key"])
        top3_overlap_count = len(predicted_top3 & observed_top3)
        binary_series = pd.to_numeric(group["binary_hit"], errors="coerce")
        top3_hit_count = int(binary_series.loc[group["predicted_rank"] <= 3].fillna(0).sum()) if binary_series.notna().any() else 0
        target_row = {
            "target_id": target_label,
            "merged_row_count": int(len(group)),
            "prediction_score_col": score_col,
            "actual_value_col": actual_col,
            "actual_value_kind": actual_kind,
            "prediction_join_key_col": pred_join_key_col,
            "actual_join_key_col": act_join_key_col,
            "spearman_prediction_vs_activity": _corr(group["prediction_score"], group["observed_activity_score"], "spearman"),
            "pearson_prediction_vs_activity": _corr(group["prediction_score"], group["observed_activity_score"], "pearson"),
            "kendall_prediction_vs_activity": _corr(group["prediction_score"], group["observed_activity_score"], "kendall"),
            "top1_rank_match": bool(
                int(group.nsmallest(1, "predicted_rank")["join_key"].iloc[0] == group.nsmallest(1, "observed_rank")["join_key"].iloc[0])
            ),
            "top3_overlap_count": int(top3_overlap_count),
            "top3_hit_count": int(top3_hit_count),
            "binary_hit_rows": int(binary_series.notna().sum()),
            "replicate_count_col": replicate_col,
            "notes_col": notes_col,
        }
        target_rows.append(target_row)

        for _, row in group.iterrows():
            rows.append(
                {
                    "target_id": target_label,
                    "join_key": row["join_key"],
                    "compound_label": str(row.get("compound_label", "")).strip(),
                    "prediction_score": round(float(row["prediction_score"]), 6),
                    "observed_activity_score": round(float(row["observed_activity_score"]), 6),
                    "actual_raw_value": row.get(actual_col),
                    "actual_value_kind": actual_kind,
                    "binary_hit": int(row["binary_hit"]) if pd.notna(row["binary_hit"]) else "",
                    "predicted_rank": int(row["predicted_rank"]),
                    "observed_rank": int(row["observed_rank"]),
                    "rank_delta": int(row["rank_delta"]),
                    "replicate_count": row.get(replicate_col, "") if replicate_col else "",
                    "notes": row.get(notes_col, "") if notes_col else "",
                }
            )

    target_rows_sorted = sorted(target_rows, key=lambda row: (row["target_id"].lower(), -row["merged_row_count"]))
    global_group = merged.copy()
    summary = {
        "status": "wetlab_prediction_result_comparison_ready",
        "target_count": len(target_rows_sorted),
        "merged_row_count": int(len(merged)),
        "prediction_score_col": score_col,
        "actual_value_col": actual_col,
        "actual_value_kind": actual_kind,
        "prediction_join_key_col": pred_join_key_col,
        "actual_join_key_col": act_join_key_col,
        "global_spearman_prediction_vs_activity": _corr(global_group["prediction_score"], global_group["observed_activity_score"], "spearman"),
        "global_pearson_prediction_vs_activity": _corr(global_group["prediction_score"], global_group["observed_activity_score"], "pearson"),
        "global_kendall_prediction_vs_activity": _corr(global_group["prediction_score"], global_group["observed_activity_score"], "kendall"),
        "next_required_step": "Load the filled wet-lab return CSV here after the first assay wave so ranking correlation and top-k recovery can be reviewed automatically.",
    }
    structured = {
        "interpretation_note": "Higher observed_activity_score is always better. IC50 inputs are converted to pIC50-style activity scores before comparison.",
        "binary_hit_rule": (
            "percent_inhibition >= 50" if actual_kind == "percent_inhibition" else "pIC50 >= 6.0" if actual_kind in {"ic50_nM", "ic50_uM"} else "not_derived"
        ),
        "per_target_columns": "target_id ; merged_row_count ; spearman_prediction_vs_activity ; top3_overlap_count ; top3_hit_count",
    }
    return {"summary": summary, "structured": structured, "rows": rows, "targets": target_rows_sorted}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    targets = payload["targets"]
    lines = [
        "# Wet-Lab Prediction Result Comparison",
        "",
        f"- status: `{summary['status']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- merged_row_count: `{summary['merged_row_count']}`",
        f"- prediction_score_col: `{summary['prediction_score_col']}`",
        f"- actual_value_col: `{summary['actual_value_col']}`",
        f"- actual_value_kind: `{summary['actual_value_kind']}`",
        f"- global_spearman_prediction_vs_activity: `{summary['global_spearman_prediction_vs_activity']}`",
        f"- global_pearson_prediction_vs_activity: `{summary['global_pearson_prediction_vs_activity']}`",
        f"- global_kendall_prediction_vs_activity: `{summary['global_kendall_prediction_vs_activity']}`",
        "",
        "## Per-Target Summary",
        "",
        "| target_id | merged_row_count | spearman | pearson | kendall | top1_rank_match | top3_overlap_count | top3_hit_count |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in targets:
        lines.append(
            f"| `{row['target_id']}` | `{row['merged_row_count']}` | `{row['spearman_prediction_vs_activity']}` | `{row['pearson_prediction_vs_activity']}` | `{row['kendall_prediction_vs_activity']}` | `{row['top1_rank_match']}` | `{row['top3_overlap_count']}` | `{row['top3_hit_count']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare wet-lab results against model ranking scores.")
    parser.add_argument("--prediction-table", required=True, help="CSV or JSON table with predicted ranking scores.")
    parser.add_argument("--actual-table", required=True, help="CSV or JSON table with wet-lab results.")
    parser.add_argument("--score-col", default="", help="Optional explicit prediction score column.")
    parser.add_argument("--actual-col", default="", help="Optional explicit wet-lab activity column.")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_frame(args.prediction_table),
        _load_frame(args.actual_table),
        score_col=args.score_col,
        actual_col=args.actual_col,
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
