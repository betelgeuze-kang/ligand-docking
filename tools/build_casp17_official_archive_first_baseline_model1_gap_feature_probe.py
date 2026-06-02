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


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_VIEWER_PACKET_JSON = "casp17/casp17_official_archive_first_baseline_model1_gap_viewer_packet_current.json"
DEFAULT_OUT_DIR = "casp17/official_archive_first_baseline_model1_gap_feature_probe"
DEFAULT_OUT_JSON = "casp17/casp17_official_archive_first_baseline_model1_gap_feature_probe_current.json"
DEFAULT_OUT_CSV = "casp17/casp17_official_archive_first_baseline_model1_gap_feature_probe_current.csv"
DEFAULT_OUT_MD = "casp17/CASP17_OFFICIAL_ARCHIVE_FIRST_BASELINE_MODEL1_GAP_FEATURE_PROBE.md"

CLAIM_BOUNDARY = (
    "Local CASP17 official-archive first baseline model1 gap feature probe only. It uses native-free "
    "geometry features from copied baseline-only official archive model1/best-of-5 PDB files to study "
    "model-selection failure modes. It is not an official CASP assessment, not strict-blind competitive "
    "proof, does not import official archive models as internal predictions, does not push remotes, and "
    "does not submit to CASP."
)
RULE_ID = "official_archive_first_baseline_model1_gap_feature_probe_v1"

ROW_COLUMNS = [
    "feature_rank",
    "target_id",
    "group_id",
    "triage_band",
    "best_minus_model1_gdt_ts_proxy",
    "model1_model_id",
    "best_top5_model_id",
    "model1_geometry_risk_score",
    "best_top5_geometry_risk_score",
    "geometry_risk_delta_model1_minus_best",
    "geometry_signal",
    "selector_label",
    "model1_ca_count",
    "best_top5_ca_count",
    "model1_radius_gyration",
    "best_top5_radius_gyration",
    "model1_chain_break_count",
    "best_top5_chain_break_count",
    "model1_ca_clash_count",
    "best_top5_ca_clash_count",
    "model1_long_step_fraction",
    "best_top5_long_step_fraction",
    "model1_short_step_fraction",
    "best_top5_short_step_fraction",
    "model1_pdb",
    "best_top5_pdb",
    "review_md",
    "feature_status",
    "blockers",
    "claim_boundary",
    "rule_id",
]

MATRIX_COLUMNS = [
    "feature_rank",
    "target_id",
    "group_id",
    "model_role",
    "model_id",
    "geometry_risk_score",
    "ca_count",
    "residue_count",
    "chain_count",
    "radius_gyration",
    "max_span",
    "mean_ca_step",
    "median_ca_step",
    "long_step_fraction",
    "short_step_fraction",
    "chain_break_count",
    "ca_clash_count",
    "expected_radius_gyration",
    "radius_expected_deviation_fraction",
    "missing_ca_fraction_vs_pair",
    "pdb_path",
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


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.sqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 + (a["z"] - b["z"]) ** 2)


def _parse_ca_atoms(path: Path) -> list[dict[str, Any]]:
    atoms: list[dict[str, Any]] = []
    if not path.is_file():
        return atoms
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if not line.startswith("ATOM  "):
                continue
            if line[12:16].strip() != "CA":
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                continue
            chain = line[21].strip() or "_"
            residue_number = line[22:26].strip()
            insertion = line[26].strip()
            resname = line[17:20].strip()
            atoms.append(
                {
                    "x": x,
                    "y": y,
                    "z": z,
                    "chain": chain,
                    "residue_number": residue_number,
                    "insertion": insertion,
                    "resname": resname,
                    "ordinal": len(atoms),
                    "residue_key": f"{chain}:{residue_number}{insertion}",
                }
            )
    return atoms


def _expected_rg(ca_count: int) -> float:
    if ca_count <= 0:
        return 0.0
    return 2.2 * (float(ca_count) ** 0.38)


def _geometry_features(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    atoms = _parse_ca_atoms(path)
    ca_count = len(atoms)
    if not atoms:
        return {
            "pdb_path": _artifact(path_like),
            "ca_count": 0,
            "residue_count": 0,
            "chain_count": 0,
            "radius_gyration": 0.0,
            "max_span": 0.0,
            "mean_ca_step": 0.0,
            "median_ca_step": 0.0,
            "long_step_fraction": 0.0,
            "short_step_fraction": 0.0,
            "chain_break_count": 0,
            "ca_clash_count": 0,
            "expected_radius_gyration": 0.0,
            "radius_expected_deviation_fraction": 0.0,
            "file_present": path.is_file(),
        }

    xs = [atom["x"] for atom in atoms]
    ys = [atom["y"] for atom in atoms]
    zs = [atom["z"] for atom in atoms]
    center = (statistics.fmean(xs), statistics.fmean(ys), statistics.fmean(zs))
    radius_gyration = math.sqrt(
        statistics.fmean(
            (atom["x"] - center[0]) ** 2 + (atom["y"] - center[1]) ** 2 + (atom["z"] - center[2]) ** 2
            for atom in atoms
        )
    )
    max_span = math.sqrt((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2 + (max(zs) - min(zs)) ** 2)

    steps = [
        _distance(left, right)
        for left, right in zip(atoms, atoms[1:])
        if left["chain"] == right["chain"]
    ]
    long_steps = [step for step in steps if step > 5.0]
    short_steps = [step for step in steps if step < 2.0]
    chain_break_count = sum(1 for step in steps if step > 6.0)

    ca_clash_count = 0
    for left_index, left in enumerate(atoms):
        for right in atoms[left_index + 1 :]:
            if left["chain"] == right["chain"] and abs(left["ordinal"] - right["ordinal"]) <= 2:
                continue
            if _distance(left, right) < 2.5:
                ca_clash_count += 1

    expected_rg = _expected_rg(ca_count)
    radius_deviation = abs(radius_gyration - expected_rg) / expected_rg if expected_rg else 0.0
    residue_keys = {atom["residue_key"] for atom in atoms}
    chains = {atom["chain"] for atom in atoms}
    step_count = len(steps)
    return {
        "pdb_path": _artifact(path_like),
        "ca_count": ca_count,
        "residue_count": len(residue_keys),
        "chain_count": len(chains),
        "radius_gyration": radius_gyration,
        "max_span": max_span,
        "mean_ca_step": statistics.fmean(steps) if steps else 0.0,
        "median_ca_step": statistics.median(steps) if steps else 0.0,
        "long_step_fraction": len(long_steps) / step_count if step_count else 0.0,
        "short_step_fraction": len(short_steps) / step_count if step_count else 0.0,
        "chain_break_count": chain_break_count,
        "ca_clash_count": ca_clash_count,
        "expected_radius_gyration": expected_rg,
        "radius_expected_deviation_fraction": radius_deviation,
        "file_present": path.is_file(),
    }


def _geometry_risk(features: dict[str, Any], *, pair_max_ca: int) -> float:
    ca_count = int(features.get("ca_count") or 0)
    missing_ca_fraction = (pair_max_ca - ca_count) / pair_max_ca if pair_max_ca > 0 else 0.0
    return (
        float(features.get("long_step_fraction") or 0.0) * 100.0
        + float(features.get("short_step_fraction") or 0.0) * 80.0
        + float(features.get("chain_break_count") or 0) * 2.0
        + float(features.get("ca_clash_count") or 0) * 0.20
        + float(features.get("radius_expected_deviation_fraction") or 0.0) * 15.0
        + missing_ca_fraction * 60.0
        + (50.0 if ca_count == 0 else 0.0)
    )


def _signal(model1_risk: float, best_risk: float, *, threshold: float) -> str:
    delta = model1_risk - best_risk
    if delta >= threshold:
        return "supports_best_top5"
    if delta <= -threshold:
        return "supports_model1"
    return "ambiguous"


def _matrix_row(
    *,
    rank: int,
    source: dict[str, Any],
    role: str,
    model_id: str,
    features: dict[str, Any],
    risk: float,
    pair_max_ca: int,
) -> dict[str, Any]:
    ca_count = int(features.get("ca_count") or 0)
    missing_ca_fraction = (pair_max_ca - ca_count) / pair_max_ca if pair_max_ca > 0 else 0.0
    return {
        "feature_rank": rank,
        "target_id": _text(source.get("target_id")),
        "group_id": _text(source.get("group_id")),
        "model_role": role,
        "model_id": model_id,
        "geometry_risk_score": _fmt(risk),
        "ca_count": ca_count,
        "residue_count": int(features.get("residue_count") or 0),
        "chain_count": int(features.get("chain_count") or 0),
        "radius_gyration": _fmt(float(features.get("radius_gyration") or 0.0)),
        "max_span": _fmt(float(features.get("max_span") or 0.0)),
        "mean_ca_step": _fmt(float(features.get("mean_ca_step") or 0.0)),
        "median_ca_step": _fmt(float(features.get("median_ca_step") or 0.0)),
        "long_step_fraction": _fmt(float(features.get("long_step_fraction") or 0.0), digits=4),
        "short_step_fraction": _fmt(float(features.get("short_step_fraction") or 0.0), digits=4),
        "chain_break_count": int(features.get("chain_break_count") or 0),
        "ca_clash_count": int(features.get("ca_clash_count") or 0),
        "expected_radius_gyration": _fmt(float(features.get("expected_radius_gyration") or 0.0)),
        "radius_expected_deviation_fraction": _fmt(
            float(features.get("radius_expected_deviation_fraction") or 0.0), digits=4
        ),
        "missing_ca_fraction_vs_pair": _fmt(missing_ca_fraction, digits=4),
        "pdb_path": _text(features.get("pdb_path")),
        "rule_id": RULE_ID,
    }


def _write_case_review(path: Path, row: dict[str, Any]) -> None:
    lines = [
        f"# {row['target_id']} group {row['group_id']} native-free feature probe",
        "",
        f"- triage band: `{row['triage_band']}`",
        f"- native-proxy label: `{row['selector_label']}`",
        f"- geometry signal: `{row['geometry_signal']}`",
        f"- model1 risk: `{row['model1_geometry_risk_score']}`",
        f"- best top5 risk: `{row['best_top5_geometry_risk_score']}`",
        f"- risk delta model1-best: `{row['geometry_risk_delta_model1_minus_best']}`",
        f"- model1 CA/chain breaks/clashes: `{row['model1_ca_count']}` `{row['model1_chain_break_count']}` `{row['model1_ca_clash_count']}`",
        f"- best CA/chain breaks/clashes: `{row['best_top5_ca_count']}` `{row['best_top5_chain_break_count']}` `{row['best_top5_ca_clash_count']}`",
        "",
        "## Claim Boundary",
        "",
        CLAIM_BOUNDARY,
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    viewer_payload = _read_json(args.viewer_packet_json)
    viewer_summary = _summary(viewer_payload)
    viewer_rows = _rows(viewer_payload)
    rows: list[dict[str, Any]] = []
    matrix_rows: list[dict[str, Any]] = []
    out_dir = _resolve(args.out_dir)

    for rank, source in enumerate(viewer_rows, start=1):
        model1_features = _geometry_features(source.get("model1_pdb", ""))
        best_features = _geometry_features(source.get("best_top5_pdb", ""))
        pair_max_ca = max(int(model1_features.get("ca_count") or 0), int(best_features.get("ca_count") or 0))
        model1_risk = _geometry_risk(model1_features, pair_max_ca=pair_max_ca)
        best_risk = _geometry_risk(best_features, pair_max_ca=pair_max_ca)
        risk_delta = model1_risk - best_risk
        blockers = []
        if not model1_features.get("file_present"):
            blockers.append("model1_pdb_missing")
        if not best_features.get("file_present"):
            blockers.append("best_top5_pdb_missing")
        if int(model1_features.get("ca_count") or 0) == 0:
            blockers.append("model1_ca_atoms_missing")
        if int(best_features.get("ca_count") or 0) == 0:
            blockers.append("best_top5_ca_atoms_missing")

        signal = _signal(model1_risk, best_risk, threshold=args.signal_threshold)
        selector_label = (
            "best_top5_wins_from_native_proxy"
            if _float(source.get("best_minus_model1_gdt_ts_proxy")) > 0.0
            else "model1_tied_or_wins_from_native_proxy"
        )
        review = out_dir / f"{rank:02d}_{_text(source.get('target_id')).lower()}_group_{_text(source.get('group_id'))}" / "FEATURE_PROBE.md"
        row = {
            "feature_rank": rank,
            "target_id": _text(source.get("target_id")),
            "group_id": _text(source.get("group_id")),
            "triage_band": _text(source.get("triage_band")),
            "best_minus_model1_gdt_ts_proxy": _text(source.get("best_minus_model1_gdt_ts_proxy")),
            "model1_model_id": _text(source.get("model1_model_id")),
            "best_top5_model_id": _text(source.get("best_top5_model_id")),
            "model1_geometry_risk_score": _fmt(model1_risk),
            "best_top5_geometry_risk_score": _fmt(best_risk),
            "geometry_risk_delta_model1_minus_best": _fmt(risk_delta),
            "geometry_signal": signal,
            "selector_label": selector_label,
            "model1_ca_count": int(model1_features.get("ca_count") or 0),
            "best_top5_ca_count": int(best_features.get("ca_count") or 0),
            "model1_radius_gyration": _fmt(float(model1_features.get("radius_gyration") or 0.0)),
            "best_top5_radius_gyration": _fmt(float(best_features.get("radius_gyration") or 0.0)),
            "model1_chain_break_count": int(model1_features.get("chain_break_count") or 0),
            "best_top5_chain_break_count": int(best_features.get("chain_break_count") or 0),
            "model1_ca_clash_count": int(model1_features.get("ca_clash_count") or 0),
            "best_top5_ca_clash_count": int(best_features.get("ca_clash_count") or 0),
            "model1_long_step_fraction": _fmt(float(model1_features.get("long_step_fraction") or 0.0), digits=4),
            "best_top5_long_step_fraction": _fmt(float(best_features.get("long_step_fraction") or 0.0), digits=4),
            "model1_short_step_fraction": _fmt(float(model1_features.get("short_step_fraction") or 0.0), digits=4),
            "best_top5_short_step_fraction": _fmt(float(best_features.get("short_step_fraction") or 0.0), digits=4),
            "model1_pdb": _artifact(source.get("model1_pdb", "")),
            "best_top5_pdb": _artifact(source.get("best_top5_pdb", "")),
            "review_md": _artifact(review),
            "feature_status": "feature_ready" if not blockers else "feature_blocked",
            "blockers": ",".join(blockers),
            "claim_boundary": CLAIM_BOUNDARY,
            "rule_id": RULE_ID,
        }
        _write_case_review(review, row)
        rows.append(row)
        matrix_rows.append(
            _matrix_row(
                rank=rank,
                source=source,
                role="model1",
                model_id=row["model1_model_id"],
                features=model1_features,
                risk=model1_risk,
                pair_max_ca=pair_max_ca,
            )
        )
        matrix_rows.append(
            _matrix_row(
                rank=rank,
                source=source,
                role="best_top5",
                model_id=row["best_top5_model_id"],
                features=best_features,
                risk=best_risk,
                pair_max_ca=pair_max_ca,
            )
        )

    ready_rows = [row for row in rows if row["feature_status"] == "feature_ready"]
    supports_best = [row for row in ready_rows if row["geometry_signal"] == "supports_best_top5"]
    supports_model1 = [row for row in ready_rows if row["geometry_signal"] == "supports_model1"]
    ambiguous = [row for row in ready_rows if row["geometry_signal"] == "ambiguous"]
    first = ready_rows[0] if ready_rows else (rows[0] if rows else {})
    status = (
        "official_archive_first_baseline_model1_gap_feature_probe_ready_baseline_only"
        if rows and len(ready_rows) == len(rows)
        else "official_archive_first_baseline_model1_gap_feature_probe_blocked"
    )
    feature_probe_csv = out_dir / "feature_probe.csv"
    pair_feature_matrix_csv = out_dir / "pair_feature_matrix.csv"
    summary = {
        "packet_type": "casp17_official_archive_first_baseline_model1_gap_feature_probe",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_archive_first_baseline_model1_gap_feature_probe_status": status,
        "viewer_packet_json": _artifact(args.viewer_packet_json),
        "viewer_packet_status": _text(
            viewer_summary.get("official_archive_first_baseline_model1_gap_viewer_packet_status")
        ),
        "first_baseline_candidate_id": _text(viewer_summary.get("first_baseline_candidate_id")),
        "first_competition": _text(viewer_summary.get("first_competition")),
        "first_target_id": _text(viewer_summary.get("first_target_id")),
        "first_native_pdb_code": _text(viewer_summary.get("first_native_pdb_code")),
        "selected_case_count": len(rows),
        "feature_ready_count": len(ready_rows),
        "feature_blocked_count": len(rows) - len(ready_rows),
        "matrix_row_count": len(matrix_rows),
        "supports_best_top5_count": len(supports_best),
        "supports_model1_count": len(supports_model1),
        "ambiguous_count": len(ambiguous),
        "supports_best_top5_rate": _fmt(len(supports_best) / len(ready_rows), digits=3) if ready_rows else "0.000",
        "catastrophic_case_count": sum(1 for row in rows if row["triage_band"] == "catastrophic_model1_selection_gap"),
        "large_case_count": sum(1 for row in rows if row["triage_band"] == "large_selection_gap"),
        "first_signal_group_id": _text(first.get("group_id")),
        "first_signal": _text(first.get("geometry_signal")),
        "first_model1_geometry_risk_score": _text(first.get("model1_geometry_risk_score")),
        "first_best_top5_geometry_risk_score": _text(first.get("best_top5_geometry_risk_score")),
        "first_risk_delta_model1_minus_best": _text(first.get("geometry_risk_delta_model1_minus_best")),
        "feature_probe_csv": _artifact(feature_probe_csv),
        "pair_feature_matrix_csv": _artifact(pair_feature_matrix_csv),
        "competitive_proof_eligible": False,
        "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
        "next_action": (
            "use native-free feature signals to tune model1 selection calibration, then repeat on strict-blind "
            "eligible internal predictions only"
            if status == "official_archive_first_baseline_model1_gap_feature_probe_ready_baseline_only"
            else "repair missing copied model PDB files before geometry feature calibration"
        ),
        "claim_boundary": CLAIM_BOUNDARY,
        "rule_id": RULE_ID,
    }
    return {"summary": summary, "rows": rows, "pair_feature_matrix": matrix_rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Official Archive First Baseline Model1 Gap Feature Probe",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- status: `{summary['official_archive_first_baseline_model1_gap_feature_probe_status']}`",
        f"- first baseline: `{summary['first_baseline_candidate_id']}` `{summary['first_competition']}` `{summary['first_target_id']}` native `{summary['first_native_pdb_code']}`",
        f"- features ready/blocked/selected: `{summary['feature_ready_count']}/{summary['feature_blocked_count']}/{summary['selected_case_count']}`",
        f"- signals supports-best/model1/ambiguous: `{summary['supports_best_top5_count']}/{summary['supports_model1_count']}/{summary['ambiguous_count']}` rate `{summary['supports_best_top5_rate']}`",
        f"- catastrophic/large cases: `{summary['catastrophic_case_count']}/{summary['large_case_count']}`",
        f"- first signal: group `{summary['first_signal_group_id'] or '-'}` `{summary['first_signal'] or '-'}` model1/best risk `{summary['first_model1_geometry_risk_score'] or '-'}` `{summary['first_best_top5_geometry_risk_score'] or '-'}` delta `{summary['first_risk_delta_model1_minus_best'] or '-'}`",
        f"- feature csv: `{summary['feature_probe_csv']}`",
        f"- pair matrix csv: `{summary['pair_feature_matrix_csv']}`",
        f"- proof eligible: `{summary['competitive_proof_eligible']}` policy `{summary['strict_blind_intake_policy']}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Feature Worklist",
        "",
        "| rank | group | band | delta | signal | model1 risk | best risk | review |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['feature_rank']}` | `{row['group_id']}` | `{row['triage_band']}` | "
            f"`{row['best_minus_model1_gdt_ts_proxy']}` | `{row['geometry_signal']}` | "
            f"`{row['model1_geometry_risk_score']}` | `{row['best_top5_geometry_risk_score']}` | "
            f"`{row['review_md']}` |"
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
    _write_json(out_dir / "feature_probe.json", payload)
    _write_csv(out_dir / "feature_probe.csv", payload["rows"], ROW_COLUMNS)
    _write_csv(out_dir / "pair_feature_matrix.csv", payload["pair_feature_matrix"], MATRIX_COLUMNS)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build native-free geometry feature probes for first official archive baseline model1 gap cases."
    )
    parser.add_argument("--viewer-packet-json", default=DEFAULT_VIEWER_PACKET_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--signal-threshold", type=float, default=5.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    write_outputs(args, payload)
    print(
        json.dumps(
            {
                "status": payload["summary"]["official_archive_first_baseline_model1_gap_feature_probe_status"],
                "target": payload["summary"]["first_target_id"],
                "features": payload["summary"]["feature_ready_count"],
                "selected": payload["summary"]["selected_case_count"],
                "supports_best": payload["summary"]["supports_best_top5_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
