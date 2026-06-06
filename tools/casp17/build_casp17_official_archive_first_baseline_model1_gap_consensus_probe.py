#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_TRIAGE_JSON = "casp17/casp17_official_archive_first_baseline_model1_gap_triage_current.json"
DEFAULT_SCORE_LEDGER_JSON = "casp17/casp17_official_archive_first_baseline_score_ledger_current.json"
DEFAULT_OUT_DIR = "casp17/official_archive_first_baseline_model1_gap_consensus_probe"
DEFAULT_OUT_JSON = "casp17/casp17_official_archive_first_baseline_model1_gap_consensus_probe_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_official_archive_first_baseline_model1_gap_consensus_probe_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_OFFICIAL_ARCHIVE_FIRST_BASELINE_MODEL1_GAP_CONSENSUS_PROBE.md"

CLAIM_BOUNDARY = (
    "Local CASP17 official-archive first baseline model1 gap consensus probe only. It uses native-free "
    "top5 pairwise CA RMSD clustering on baseline-only official archive models to study model-selection "
    "failure modes. It is not an official CASP assessment, not strict-blind competitive proof, does not "
    "import official archive models as internal predictions, does not push remotes, and does not submit to CASP."
)
RULE_ID = "official_archive_first_baseline_model1_gap_consensus_probe_v1"

ROW_COLUMNS = [
    "consensus_rank",
    "target_id",
    "group_id",
    "triage_band",
    "best_minus_model1_gdt_ts_proxy",
    "model1_model_id",
    "best_top5_model_id",
    "top5_ready_count",
    "model1_consensus_rank",
    "best_top5_consensus_rank",
    "consensus_top_model_id",
    "consensus_top_native_proxy_rank",
    "model1_mean_pairwise_rmsd",
    "best_top5_mean_pairwise_rmsd",
    "consensus_margin_model1_minus_best",
    "consensus_signal",
    "selector_label",
    "pairwise_matrix_csv",
    "review_md",
    "consensus_status",
    "blockers",
    "claim_boundary",
    "rule_id",
]

MATRIX_COLUMNS = [
    "case_rank",
    "target_id",
    "group_id",
    "model_a_id",
    "model_b_id",
    "ordered_ca_match_count",
    "pairwise_ca_rmsd",
    "rule_id",
]


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _artifact(path_like: str | Path) -> str:
    if not str(path_like).strip():
        return ""
    path = _resolve(path_like).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _fmt(value: float, digits: int = 3) -> str:
    if not math.isfinite(value):
        return "0.000"
    return f"{value:.{digits}f}"


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


def _rows(payload: dict[str, Any], key: str = "rows") -> list[dict[str, Any]]:
    rows = payload.get(key)
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


def _ca_coords(path_like: str | Path) -> np.ndarray:
    path = _resolve(path_like)
    coords: list[tuple[float, float, float]] = []
    if not path.is_file():
        return np.empty((0, 3), dtype=float)
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.startswith("ATOM  "):
                continue
            if line[12:16].strip() != "CA":
                continue
            try:
                coords.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
            except ValueError:
                continue
    return np.asarray(coords, dtype=float)


def _kabsch_rmsd(left: np.ndarray, right: np.ndarray) -> tuple[float, int]:
    count = min(len(left), len(right))
    if count < 3:
        return 0.0, count
    left_match = left[:count] - left[:count].mean(axis=0)
    right_match = right[:count] - right[:count].mean(axis=0)
    covariance = left_match.T @ right_match
    u_matrix, _, vt_matrix = np.linalg.svd(covariance)
    rotation = vt_matrix.T @ u_matrix.T
    if np.linalg.det(rotation) < 0:
        vt_matrix[-1, :] *= -1
        rotation = vt_matrix.T @ u_matrix.T
    aligned = left_match @ rotation
    diff = aligned - right_match
    return float(np.sqrt((diff * diff).sum() / count)), count


def _model_rows_by_group(score_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in score_rows:
        if _text(row.get("metric_status")) != "metric_ready":
            continue
        group_id = _text(row.get("group_id"))
        grouped.setdefault(group_id, []).append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: int(row.get("model_number") or 0))
    return grouped


def _consensus_signal(model1_rank: int, best_rank: int, margin: float, threshold: float) -> str:
    if best_rank < model1_rank and margin >= threshold:
        return "supports_best_top5"
    if model1_rank < best_rank and margin <= -threshold:
        return "supports_model1"
    return "ambiguous"


def _write_review(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} group {row['group_id']} consensus probe",
        "",
        f"- triage band: `{row['triage_band']}`",
        f"- native-proxy label: `{row['selector_label']}`",
        f"- consensus signal: `{row['consensus_signal']}`",
        f"- model1 consensus rank/mean RMSD: `{row['model1_consensus_rank']}` `{row['model1_mean_pairwise_rmsd']}`",
        f"- best top5 consensus rank/mean RMSD: `{row['best_top5_consensus_rank']}` `{row['best_top5_mean_pairwise_rmsd']}`",
        f"- consensus top: `{row['consensus_top_model_id']}` native-proxy rank `{row['consensus_top_native_proxy_rank']}`",
        f"- pairwise matrix: `{row['pairwise_matrix_csv']}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _case_payload(
    *,
    rank: int,
    triage: dict[str, Any],
    top5: list[dict[str, Any]],
    out_dir: Path,
    signal_threshold: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    blockers: list[str] = []
    if len(top5) < 2:
        blockers.append("top5_model_rows_missing")
    coords_by_id = {_text(row.get("model_id")): _ca_coords(row.get("path", "")) for row in top5}
    for model_id, coords in coords_by_id.items():
        if len(coords) < 3:
            blockers.append(f"ca_missing:{model_id}")

    pairwise_rows: list[dict[str, Any]] = []
    rmsd_by_model: dict[str, list[float]] = {_text(row.get("model_id")): [] for row in top5}
    for index, left in enumerate(top5):
        left_id = _text(left.get("model_id"))
        for right in top5[index + 1 :]:
            right_id = _text(right.get("model_id"))
            rmsd, match_count = _kabsch_rmsd(coords_by_id.get(left_id, np.empty((0, 3))), coords_by_id.get(right_id, np.empty((0, 3))))
            if match_count < 3:
                blockers.append(f"pair_ca_match_too_small:{left_id}:{right_id}")
            rmsd_by_model[left_id].append(rmsd)
            rmsd_by_model[right_id].append(rmsd)
            pairwise_rows.append(
                {
                    "case_rank": rank,
                    "target_id": _text(triage.get("target_id")),
                    "group_id": _text(triage.get("group_id")),
                    "model_a_id": left_id,
                    "model_b_id": right_id,
                    "ordered_ca_match_count": match_count,
                    "pairwise_ca_rmsd": _fmt(rmsd),
                    "rule_id": RULE_ID,
                }
            )

    mean_rmsd_by_model = {
        model_id: (statistics.fmean(values) if values else float("inf"))
        for model_id, values in rmsd_by_model.items()
    }
    consensus_order = sorted(mean_rmsd_by_model, key=lambda model_id: (mean_rmsd_by_model[model_id], model_id))
    consensus_rank_by_model = {model_id: index for index, model_id in enumerate(consensus_order, start=1)}
    native_proxy_order = sorted(top5, key=lambda row: (-_float(row.get("gdt_ts_proxy")), int(row.get("model_number") or 0)))
    native_proxy_rank_by_model = {
        _text(row.get("model_id")): index for index, row in enumerate(native_proxy_order, start=1)
    }

    model1_id = _text(triage.get("model1_model_id"))
    best_id = _text(triage.get("best_top5_model_id"))
    model1_rank = consensus_rank_by_model.get(model1_id, 0)
    best_rank = consensus_rank_by_model.get(best_id, 0)
    model1_mean = mean_rmsd_by_model.get(model1_id, float("inf"))
    best_mean = mean_rmsd_by_model.get(best_id, float("inf"))
    margin = model1_mean - best_mean if math.isfinite(model1_mean) and math.isfinite(best_mean) else 0.0
    signal = _consensus_signal(model1_rank, best_rank, margin, signal_threshold)
    case_dir = out_dir / f"{rank:02d}_{_text(triage.get('target_id')).lower()}_group_{_text(triage.get('group_id'))}"
    pairwise_csv = case_dir / "pairwise_consensus_matrix.csv"
    review_md = case_dir / "CONSENSUS_PROBE.md"
    row = {
        "consensus_rank": rank,
        "target_id": _text(triage.get("target_id")),
        "group_id": _text(triage.get("group_id")),
        "triage_band": _text(triage.get("triage_band")),
        "best_minus_model1_gdt_ts_proxy": _text(triage.get("best_minus_model1_gdt_ts_proxy")),
        "model1_model_id": model1_id,
        "best_top5_model_id": best_id,
        "top5_ready_count": len(top5),
        "model1_consensus_rank": model1_rank,
        "best_top5_consensus_rank": best_rank,
        "consensus_top_model_id": consensus_order[0] if consensus_order else "",
        "consensus_top_native_proxy_rank": native_proxy_rank_by_model.get(consensus_order[0], 0) if consensus_order else 0,
        "model1_mean_pairwise_rmsd": _fmt(model1_mean if math.isfinite(model1_mean) else 0.0),
        "best_top5_mean_pairwise_rmsd": _fmt(best_mean if math.isfinite(best_mean) else 0.0),
        "consensus_margin_model1_minus_best": _fmt(margin),
        "consensus_signal": signal,
        "selector_label": (
            "best_top5_wins_from_native_proxy"
            if _float(triage.get("best_minus_model1_gdt_ts_proxy")) > 0.0
            else "model1_tied_or_wins_from_native_proxy"
        ),
        "pairwise_matrix_csv": _artifact(pairwise_csv),
        "review_md": _artifact(review_md),
        "consensus_status": "consensus_ready" if not blockers else "consensus_blocked",
        "blockers": ",".join(dict.fromkeys(blockers)),
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    _write_csv(pairwise_csv, pairwise_rows, MATRIX_COLUMNS)
    _write_review(review_md, row)
    return row, pairwise_rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    triage_payload = _read_json(args.triage_json)
    score_payload = _read_json(args.score_ledger_json)
    triage_summary = _summary(triage_payload)
    score_summary = _summary(score_payload)
    triage_rows = [
        row
        for row in _rows(triage_payload)
        if _text(row.get("triage_band")) in {"large_selection_gap", "catastrophic_model1_selection_gap"}
    ][: args.max_cases]
    grouped = _model_rows_by_group(_rows(score_payload, key="model_score_rows"))
    out_dir = _resolve(args.out_dir)
    rows: list[dict[str, Any]] = []
    matrix_rows: list[dict[str, Any]] = []
    for rank, triage in enumerate(triage_rows, start=1):
        row, pairs = _case_payload(
            rank=rank,
            triage=triage,
            top5=grouped.get(_text(triage.get("group_id")), []),
            out_dir=out_dir,
            signal_threshold=args.signal_threshold,
        )
        rows.append(row)
        matrix_rows.extend(pairs)

    ready_rows = [row for row in rows if row["consensus_status"] == "consensus_ready"]
    supports_best = [row for row in ready_rows if row["consensus_signal"] == "supports_best_top5"]
    supports_model1 = [row for row in ready_rows if row["consensus_signal"] == "supports_model1"]
    ambiguous = [row for row in ready_rows if row["consensus_signal"] == "ambiguous"]
    top_matches_best = [row for row in ready_rows if row["consensus_top_model_id"] == row["best_top5_model_id"]]
    top_matches_model1 = [row for row in ready_rows if row["consensus_top_model_id"] == row["model1_model_id"]]
    first = ready_rows[0] if ready_rows else (rows[0] if rows else {})
    status = (
        "official_archive_first_baseline_model1_gap_consensus_probe_ready_baseline_only"
        if rows and len(ready_rows) == len(rows)
        else "official_archive_first_baseline_model1_gap_consensus_probe_blocked"
    )
    consensus_csv = out_dir / "consensus_probe.csv"
    matrix_csv = out_dir / "pairwise_consensus_matrix.csv"
    summary = {
        "packet_type": "casp17_official_archive_first_baseline_model1_gap_consensus_probe",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_archive_first_baseline_model1_gap_consensus_probe_status": status,
        "triage_json": _artifact(args.triage_json),
        "triage_status": _text(triage_summary.get("official_archive_first_baseline_model1_gap_triage_status")),
        "score_ledger_json": _artifact(args.score_ledger_json),
        "score_ledger_status": _text(score_summary.get("official_archive_first_baseline_score_ledger_status")),
        "first_baseline_candidate_id": _text(score_summary.get("first_baseline_candidate_id")),
        "first_competition": _text(score_summary.get("first_competition")),
        "first_target_id": _text(score_summary.get("first_target_id")),
        "first_native_pdb_code": _text(score_summary.get("first_native_pdb_code")),
        "selected_case_count": len(rows),
        "consensus_ready_count": len(ready_rows),
        "consensus_blocked_count": len(rows) - len(ready_rows),
        "pairwise_row_count": len(matrix_rows),
        "supports_best_top5_count": len(supports_best),
        "supports_model1_count": len(supports_model1),
        "ambiguous_count": len(ambiguous),
        "supports_best_top5_rate": _fmt(len(supports_best) / len(ready_rows), digits=3) if ready_rows else "0.000",
        "consensus_top_matches_best_count": len(top_matches_best),
        "consensus_top_matches_model1_count": len(top_matches_model1),
        "catastrophic_case_count": sum(1 for row in rows if row["triage_band"] == "catastrophic_model1_selection_gap"),
        "large_case_count": sum(1 for row in rows if row["triage_band"] == "large_selection_gap"),
        "first_signal_group_id": _text(first.get("group_id")),
        "first_signal": _text(first.get("consensus_signal")),
        "first_model1_consensus_rank": _text(first.get("model1_consensus_rank")),
        "first_best_top5_consensus_rank": _text(first.get("best_top5_consensus_rank")),
        "first_consensus_top_model_id": _text(first.get("consensus_top_model_id")),
        "first_consensus_margin_model1_minus_best": _text(first.get("consensus_margin_model1_minus_best")),
        "consensus_probe_csv": _artifact(consensus_csv),
        "pairwise_consensus_matrix_csv": _artifact(matrix_csv),
        "competitive_proof_eligible": False,
        "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
        "next_action": (
            "combine consensus-rank, diversity, and confidence features into a no-native model1 selector; "
            "repeat only on strict-blind eligible internal predictions before competitive claims"
            if status == "official_archive_first_baseline_model1_gap_consensus_probe_ready_baseline_only"
            else "repair missing top5 model paths before consensus model1 selection calibration"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": rows, "pairwise_consensus_matrix": matrix_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Official Archive First Baseline Model1 Gap Consensus Probe",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['official_archive_first_baseline_model1_gap_consensus_probe_status']}`",
        f"- first baseline: `{summary['first_baseline_candidate_id']}` `{summary['first_competition']}` `{summary['first_target_id']}` native `{summary['first_native_pdb_code']}`",
        f"- consensus ready/blocked/selected: `{summary['consensus_ready_count']}/{summary['consensus_blocked_count']}/{summary['selected_case_count']}`",
        f"- signals supports-best/model1/ambiguous: `{summary['supports_best_top5_count']}/{summary['supports_model1_count']}/{summary['ambiguous_count']}` rate `{summary['supports_best_top5_rate']}`",
        f"- consensus top matches best/model1: `{summary['consensus_top_matches_best_count']}/{summary['consensus_top_matches_model1_count']}`",
        f"- catastrophic/large cases: `{summary['catastrophic_case_count']}/{summary['large_case_count']}`",
        f"- first signal: group `{summary['first_signal_group_id'] or '-'}` `{summary['first_signal'] or '-'}` ranks model1/best `{summary['first_model1_consensus_rank'] or '-'}` `{summary['first_best_top5_consensus_rank'] or '-'}` top `{summary['first_consensus_top_model_id'] or '-'}` margin `{summary['first_consensus_margin_model1_minus_best'] or '-'}`",
        f"- consensus csv: `{summary['consensus_probe_csv']}`",
        f"- pairwise matrix csv: `{summary['pairwise_consensus_matrix_csv']}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['strict_blind_intake_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Consensus Worklist",
        "",
        "| rank | group | band | delta | signal | model1 rank | best rank | top | review |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['consensus_rank']}` | `{row['group_id']}` | `{row['triage_band']}` | "
            f"`{row['best_minus_model1_gdt_ts_proxy']}` | `{row['consensus_signal']}` | "
            f"`{row['model1_consensus_rank']}` | `{row['best_top5_consensus_rank']}` | "
            f"`{row['consensus_top_model_id']}` | `{row['review_md']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", CLAIM_BOUNDARY])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"], ROW_COLUMNS)
    _write_md(args.out_md, payload)
    _write_json(out_dir / "consensus_probe.json", payload)
    _write_csv(out_dir / "consensus_probe.csv", payload["rows"], ROW_COLUMNS)
    _write_csv(out_dir / "pairwise_consensus_matrix.csv", payload["pairwise_consensus_matrix"], MATRIX_COLUMNS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build native-free top5 consensus probes for first official archive baseline model1 gap cases."
    )
    parser.add_argument("--triage-json", default=DEFAULT_TRIAGE_JSON)
    parser.add_argument("--score-ledger-json", default=DEFAULT_SCORE_LEDGER_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--max-cases", type=int, default=14)
    parser.add_argument("--signal-threshold", type=float, default=1.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["official_archive_first_baseline_model1_gap_consensus_probe_status"],
                "target": payload["summary"]["first_target_id"],
                "consensus": payload["summary"]["consensus_ready_count"],
                "selected": payload["summary"]["selected_case_count"],
                "supports_best": payload["summary"]["supports_best_top5_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
