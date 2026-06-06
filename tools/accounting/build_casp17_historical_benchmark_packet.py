#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MANIFEST_CSV = "runs/casp17_historical_benchmark_manifest_current.csv"
DEFAULT_OUT_JSON = "runs/casp17_historical_benchmark_packet_current.json"
DEFAULT_OUT_CSV = "runs/casp17_historical_benchmark_packet_current.csv"
DEFAULT_OUT_MD = "runs/casp17_historical_benchmark_packet_current.md"

LEAKAGE_CLEAR_VALUES = {"no_leak", "cleared", "true", "yes", "internal_no_leak"}


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


def _record(line: str) -> str:
    return line[:6].strip().upper()


def _float_or_none(value: str) -> float | None:
    try:
        parsed = float(value.strip())
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _pdb_float(line: str, start: int, end: int, fallback_index: int) -> float | None:
    if len(line) >= end:
        parsed = _float_or_none(line[start:end])
        if parsed is not None:
            return parsed
    fields = line.split()
    if len(fields) > fallback_index:
        return _float_or_none(fields[fallback_index])
    return None


def _read_manifest(path_like: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    path = _resolve(path_like)
    if not path.exists():
        return [], ["manifest_missing"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return [], ["manifest_empty"]
    return rows, []


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["benchmark_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _parse_ca_entries(path_like: str | Path) -> dict[tuple[str, int, str], dict[str, Any]]:
    path = _resolve(path_like)
    atoms: dict[tuple[str, int, str], dict[str, Any]] = {}
    seen_model = False
    in_first_model = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        rec = _record(line)
        if rec == "MODEL":
            if seen_model:
                break
            seen_model = True
            in_first_model = True
            continue
        if rec == "END" and in_first_model:
            break
        if rec != "ATOM" or (seen_model and not in_first_model):
            continue
        atom_name = line[12:16].strip() if len(line) >= 16 else ""
        if atom_name != "CA":
            continue
        resname = line[17:20].strip().upper() if len(line) >= 20 else ""
        chain = line[21].strip() or "_" if len(line) > 21 else "_"
        try:
            resseq = int(line[22:26])
        except ValueError:
            fields = line.split()
            resseq = int(fields[5]) if len(fields) > 5 and fields[5].lstrip("-").isdigit() else 0
        insertion = line[26].strip() or "_" if len(line) > 26 else "_"
        coord = (
            _pdb_float(line, 30, 38, 6),
            _pdb_float(line, 38, 46, 7),
            _pdb_float(line, 46, 54, 8),
        )
        if any(value is None for value in coord):
            continue
        atoms[(chain, resseq, insertion)] = {
            "coord": (float(coord[0]), float(coord[1]), float(coord[2])),
            "resname": resname or "UNK",
        }
    return atoms


def _coords(entries: dict[tuple[str, int, str], dict[str, Any]]) -> dict[tuple[str, int, str], tuple[float, float, float]]:
    return {key: value["coord"] for key, value in entries.items()}


def _matched_points(
    prediction_ca: dict[tuple[str, int, str], tuple[float, float, float]],
    native_ca: dict[tuple[str, int, str], tuple[float, float, float]],
) -> tuple[list[tuple[str, int, str]], np.ndarray, np.ndarray]:
    keys = sorted(set(prediction_ca) & set(native_ca), key=lambda item: (item[0], item[1], item[2]))
    if not keys:
        pred_values = list(prediction_ca.values())
        native_values = list(native_ca.values())
        count = min(len(pred_values), len(native_values))
        keys = [("_", index + 1, "_") for index in range(count)]
        pred = np.asarray(pred_values[:count], dtype=float)
        native = np.asarray(native_values[:count], dtype=float)
        return keys, pred, native
    pred = np.asarray([prediction_ca[key] for key in keys], dtype=float)
    native = np.asarray([native_ca[key] for key in keys], dtype=float)
    return keys, pred, native


def _chain_ids(entries: dict[tuple[str, int, str], dict[str, Any]]) -> list[str]:
    return sorted({key[0] for key in entries})


def _identity_match_fraction(
    keys: list[tuple[str, int, str]],
    prediction_entries: dict[tuple[str, int, str], dict[str, Any]],
    native_entries: dict[tuple[str, int, str], dict[str, Any]],
) -> float:
    comparable = [key for key in keys if key in prediction_entries and key in native_entries]
    if not comparable:
        return 0.0
    matched = sum(
        1
        for key in comparable
        if _text(prediction_entries[key].get("resname")).upper() == _text(native_entries[key].get("resname")).upper()
    )
    return float(matched / len(comparable))


def _matched_chain_count(keys: list[tuple[str, int, str]]) -> int:
    return len({key[0] for key in keys})


def _superpose(prediction: np.ndarray, native: np.ndarray) -> np.ndarray:
    pred_center = prediction.mean(axis=0)
    native_center = native.mean(axis=0)
    pred_centered = prediction - pred_center
    native_centered = native - native_center
    covariance = pred_centered.T @ native_centered
    u, _s, vt = np.linalg.svd(covariance)
    determinant = np.linalg.det(vt.T @ u.T)
    correction = np.diag([1.0, 1.0, -1.0 if determinant < 0 else 1.0])
    rotation = vt.T @ correction @ u.T
    return pred_centered @ rotation + native_center


def _fraction_within(distances: np.ndarray, threshold: float) -> float:
    if len(distances) == 0:
        return 0.0
    return float(np.mean(distances <= threshold))


def _tm_proxy(distances: np.ndarray) -> float:
    length = len(distances)
    if length == 0:
        return 0.0
    d0 = 1.24 * max(length - 15, 1) ** (1.0 / 3.0) - 1.8
    d0 = max(0.5, float(d0))
    return float(np.mean(1.0 / (1.0 + (distances / d0) ** 2)))


def _ca_lddt_proxy(native: np.ndarray, aligned_prediction: np.ndarray, *, cutoff: float = 15.0) -> float:
    length = len(native)
    if length < 2:
        return 0.0
    native_diffs = native[:, None, :] - native[None, :, :]
    pred_diffs = aligned_prediction[:, None, :] - aligned_prediction[None, :, :]
    native_dist = np.linalg.norm(native_diffs, axis=2)
    pred_dist = np.linalg.norm(pred_diffs, axis=2)
    mask = (native_dist > 0.0) & (native_dist <= cutoff)
    if not np.any(mask):
        return 0.0
    delta = np.abs(native_dist[mask] - pred_dist[mask])
    scores = [
        np.mean(delta <= 0.5),
        np.mean(delta <= 1.0),
        np.mean(delta <= 2.0),
        np.mean(delta <= 4.0),
    ]
    return float(np.mean(scores))


def _interface_contact_f1(
    keys: list[tuple[str, int, str]],
    native: np.ndarray,
    aligned_prediction: np.ndarray,
    *,
    threshold: float = 10.0,
) -> float:
    native_contacts: set[tuple[int, int]] = set()
    pred_contacts: set[tuple[int, int]] = set()
    for left in range(len(keys)):
        for right in range(left + 1, len(keys)):
            if keys[left][0] == keys[right][0]:
                continue
            native_distance = float(np.linalg.norm(native[left] - native[right]))
            pred_distance = float(np.linalg.norm(aligned_prediction[left] - aligned_prediction[right]))
            if native_distance <= threshold:
                native_contacts.add((left, right))
            if pred_distance <= threshold:
                pred_contacts.add((left, right))
    if not native_contacts and not pred_contacts:
        return 1.0
    if not native_contacts or not pred_contacts:
        return 0.0
    true_positive = len(native_contacts & pred_contacts)
    precision = true_positive / len(pred_contacts) if pred_contacts else 0.0
    recall = true_positive / len(native_contacts) if native_contacts else 0.0
    if precision + recall == 0.0:
        return 0.0
    return float(2.0 * precision * recall / (precision + recall))


def _interface_proxy_metrics(
    keys: list[tuple[str, int, str]],
    native: np.ndarray,
    aligned_prediction: np.ndarray,
    *,
    threshold: float = 10.0,
) -> dict[str, float | int]:
    native_contacts: set[tuple[int, int]] = set()
    pred_contacts: set[tuple[int, int]] = set()
    native_patch: set[int] = set()
    pred_patch: set[int] = set()
    for left in range(len(keys)):
        for right in range(left + 1, len(keys)):
            if keys[left][0] == keys[right][0]:
                continue
            native_distance = float(np.linalg.norm(native[left] - native[right]))
            pred_distance = float(np.linalg.norm(aligned_prediction[left] - aligned_prediction[right]))
            if native_distance <= threshold:
                native_contacts.add((left, right))
                native_patch.update((left, right))
            if pred_distance <= threshold:
                pred_contacts.add((left, right))
                pred_patch.update((left, right))
    shared_contacts = native_contacts & pred_contacts
    precision = len(shared_contacts) / len(pred_contacts) if pred_contacts else 0.0
    recall = len(shared_contacts) / len(native_contacts) if native_contacts else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if precision + recall else 0.0
    contact_union = native_contacts | pred_contacts
    contact_jaccard = len(shared_contacts) / len(contact_union) if contact_union else 0.0
    patch_union = native_patch | pred_patch
    patch_jaccard = len(native_patch & pred_patch) / len(patch_union) if patch_union else 0.0
    interface_residue_indices = sorted(native_patch | pred_patch)
    if interface_residue_indices:
        deltas = aligned_prediction[interface_residue_indices] - native[interface_residue_indices]
        irmsd = float(math.sqrt(np.mean(np.sum(deltas**2, axis=1))))
    else:
        irmsd = 0.0
    irms_component = 1.0 / (1.0 + (irmsd / 1.5) ** 2) if interface_residue_indices else 0.0
    dockq_proxy = float((f1 + patch_jaccard + irms_component) / 3.0)
    return {
        "native_interface_contact_count": int(len(native_contacts)),
        "prediction_interface_contact_count": int(len(pred_contacts)),
        "shared_interface_contact_count": int(len(shared_contacts)),
        "interface_contact_precision_proxy": round(float(precision), 6),
        "interface_contact_recall_proxy": round(float(recall), 6),
        "interface_contact_f1_proxy": round(float(f1), 6),
        "interface_patch_jaccard_proxy": round(float(patch_jaccard), 6),
        "interface_qsbest_proxy": round(float(contact_jaccard), 6),
        "interface_irmsd_A": round(float(irmsd), 4),
        "dockq_proxy": round(dockq_proxy, 6),
    }


def _score_one(row: dict[str, str], args: argparse.Namespace) -> dict[str, Any]:
    benchmark_id = _text(row.get("benchmark_id")) or _text(row.get("target_id")) or "unknown"
    target_id = _text(row.get("target_id")) or benchmark_id
    scope = (_text(row.get("scope")) or "monomer").lower()
    prediction_path = _resolve(_text(row.get("prediction_pdb")) or _text(row.get("prediction_file")))
    native_path = _resolve(_text(row.get("native_pdb")) or _text(row.get("native_file")))
    leakage = _text(row.get("leakage_clearance") or row.get("no_leak_status")).lower()
    blockers: list[str] = []
    if leakage not in LEAKAGE_CLEAR_VALUES:
        blockers.append("leakage_clearance_missing_or_not_clear")
    if not prediction_path.exists():
        blockers.append("prediction_pdb_missing")
    if not native_path.exists():
        blockers.append("native_pdb_missing")
    metrics: dict[str, Any] = {
        "matched_ca_count": 0,
        "prediction_ca_count": 0,
        "native_ca_count": 0,
        "prediction_chain_count": 0,
        "native_chain_count": 0,
        "matched_chain_count": 0,
        "prediction_ca_coverage": 0.0,
        "native_ca_coverage": 0.0,
        "sequence_identity_match_fraction": 0.0,
        "sequence_exact_match": False,
        "chain_exact_match": False,
        "coordinate_pairing_mode": "unscored",
        "ca_rmsd_A": 0.0,
        "tm_score_proxy": 0.0,
        "gdt_ts_proxy": 0.0,
        "gdt_ha_proxy": 0.0,
        "ca_lddt_proxy": 0.0,
        "interface_contact_f1_proxy": 0.0,
        "native_interface_contact_count": 0,
        "prediction_interface_contact_count": 0,
        "shared_interface_contact_count": 0,
        "interface_contact_precision_proxy": 0.0,
        "interface_contact_recall_proxy": 0.0,
        "interface_patch_jaccard_proxy": 0.0,
        "interface_qsbest_proxy": 0.0,
        "interface_irmsd_A": 0.0,
        "dockq_proxy": 0.0,
    }
    if not blockers:
        prediction_entries = _parse_ca_entries(prediction_path)
        native_entries = _parse_ca_entries(native_path)
        prediction_ca = _coords(prediction_entries)
        native_ca = _coords(native_entries)
        prediction_chains = _chain_ids(prediction_entries)
        native_chains = _chain_ids(native_entries)
        common_keys = sorted(set(prediction_entries) & set(native_entries), key=lambda item: (item[0], item[1], item[2]))
        keys, prediction, native = _matched_points(prediction_ca, native_ca)
        pairing_mode = "chain_residue_key_intersection" if common_keys else "order_fallback"
        identity_fraction = _identity_match_fraction(keys, prediction_entries, native_entries)
        chain_exact_match = bool(prediction_chains and prediction_chains == native_chains)
        prediction_ca_coverage = len(common_keys) / len(prediction_entries) if prediction_entries else 0.0
        native_ca_coverage = len(common_keys) / len(native_entries) if native_entries else 0.0
        metrics.update(
            {
                "prediction_ca_count": int(len(prediction_entries)),
                "native_ca_count": int(len(native_entries)),
                "prediction_chain_count": int(len(prediction_chains)),
                "native_chain_count": int(len(native_chains)),
                "matched_chain_count": int(_matched_chain_count(keys)),
                "prediction_ca_coverage": round(prediction_ca_coverage, 6),
                "native_ca_coverage": round(native_ca_coverage, 6),
                "sequence_identity_match_fraction": round(identity_fraction, 6),
                "sequence_exact_match": bool(identity_fraction >= float(args.min_sequence_match_fraction)),
                "chain_exact_match": chain_exact_match,
                "coordinate_pairing_mode": pairing_mode,
            }
        )
        if not common_keys and not args.allow_order_fallback:
            blockers.append("residue_key_overlap_missing")
        if not chain_exact_match:
            blockers.append("prediction_native_chain_ids_mismatch")
        if scope == "complex" and (len(prediction_chains) < 2 or len(native_chains) < 2):
            blockers.append("complex_scope_requires_multichain")
        if scope != "complex" and (len(prediction_chains) != 1 or len(native_chains) != 1):
            blockers.append("monomer_scope_requires_single_chain")
        if identity_fraction < float(args.min_sequence_match_fraction):
            blockers.append("prediction_native_residue_identity_mismatch")
        if len(keys) < int(args.min_ca_count):
            blockers.append("matched_ca_count_below_threshold")
        if prediction_ca_coverage < float(args.min_ca_coverage):
            blockers.append("prediction_ca_coverage_below_threshold")
        if native_ca_coverage < float(args.min_ca_coverage):
            blockers.append("native_ca_coverage_below_threshold")
        if (
            len(keys) >= int(args.min_ca_count)
            and prediction_ca_coverage >= float(args.min_ca_coverage)
            and native_ca_coverage >= float(args.min_ca_coverage)
        ):
            aligned = _superpose(prediction, native)
            distances = np.linalg.norm(aligned - native, axis=1)
            metrics.update(
                {
                    "matched_ca_count": int(len(keys)),
                    "ca_rmsd_A": round(float(math.sqrt(np.mean(distances**2))), 4),
                    "tm_score_proxy": round(_tm_proxy(distances), 6),
                    "gdt_ts_proxy": round(
                        float(np.mean([_fraction_within(distances, threshold) for threshold in (1.0, 2.0, 4.0, 8.0)])),
                        6,
                    ),
                    "gdt_ha_proxy": round(
                        float(np.mean([_fraction_within(distances, threshold) for threshold in (0.5, 1.0, 2.0, 4.0)])),
                        6,
                    ),
                    "ca_lddt_proxy": round(_ca_lddt_proxy(native, aligned), 6),
                }
            )
            if scope == "complex":
                interface_metrics = _interface_proxy_metrics(keys, native, aligned)
                metrics.update(interface_metrics)
                if metrics["native_interface_contact_count"] <= 0:
                    blockers.append("native_interface_contacts_missing")
                if metrics["prediction_interface_contact_count"] <= 0:
                    blockers.append("prediction_interface_contacts_missing")
                if metrics["tm_score_proxy"] < float(args.complex_tm_threshold):
                    blockers.append("complex_tm_below_threshold")
                if metrics["interface_contact_f1_proxy"] < float(args.complex_interface_f1_threshold):
                    blockers.append("complex_interface_f1_below_threshold")
                if metrics["dockq_proxy"] < float(args.complex_dockq_threshold):
                    blockers.append("complex_dockq_below_threshold")
            else:
                if metrics["tm_score_proxy"] < float(args.monomer_tm_threshold):
                    blockers.append("monomer_tm_below_threshold")
                if metrics["gdt_ts_proxy"] < float(args.monomer_gdt_ts_threshold):
                    blockers.append("monomer_gdt_ts_below_threshold")
                if metrics["ca_lddt_proxy"] < float(args.monomer_lddt_threshold):
                    blockers.append("monomer_lddt_below_threshold")
    status = "pass" if not blockers else "blocked"
    return {
        "benchmark_id": benchmark_id,
        "target_id": target_id,
        "scope": scope,
        "split": _text(row.get("split")) or "historical",
        "leakage_clearance": leakage or "missing",
        "prediction_pdb": _artifact(prediction_path),
        "native_pdb": _artifact(native_path),
        "benchmark_status": status,
        **metrics,
        "blockers": ",".join(sorted(set(blockers))),
    }


def _mean(rows: list[dict[str, Any]], key: str, *, scope: str | None = None) -> float:
    values = [
        float(row.get(key, 0.0) or 0.0)
        for row in rows
        if row.get("benchmark_status") == "pass" and (scope is None or row.get("scope") == scope)
    ]
    return round(sum(values) / len(values), 6) if values else 0.0


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    manifest_rows, manifest_blockers = _read_manifest(args.manifest_csv)
    rows = [_score_one(row, args) for row in manifest_rows]
    pass_count = sum(1 for row in rows if row["benchmark_status"] == "pass")
    monomer_rows = [row for row in rows if row.get("scope") != "complex"]
    complex_rows = [row for row in rows if row.get("scope") == "complex"]
    monomer_pass_count = sum(1 for row in monomer_rows if row["benchmark_status"] == "pass")
    complex_pass_count = sum(1 for row in complex_rows if row["benchmark_status"] == "pass")
    sequence_exact_match_count = sum(1 for row in rows if row.get("sequence_exact_match") is True)
    chain_exact_match_count = sum(1 for row in rows if row.get("chain_exact_match") is True)
    blocked_count = len(rows) - pass_count
    if manifest_blockers:
        blocked_count = max(blocked_count, 1)
    summary = {
        "packet_type": "casp17_historical_benchmark_packet",
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "manifest_csv": _artifact(args.manifest_csv),
        "benchmark_count": len(rows),
        "pass_count": pass_count,
        "blocked_count": blocked_count,
        "monomer_benchmark_count": len(monomer_rows),
        "monomer_pass_count": monomer_pass_count,
        "complex_benchmark_count": len(complex_rows),
        "complex_pass_count": complex_pass_count,
        "sequence_exact_match_count": sequence_exact_match_count,
        "chain_exact_match_count": chain_exact_match_count,
        "historical_benchmark_status": "pass" if rows and blocked_count == 0 else "blocked",
        "monomer_win_tier_status": "pass" if monomer_rows and monomer_pass_count == len(monomer_rows) else "blocked",
        "complex_win_tier_status": "pass" if complex_rows and complex_pass_count == len(complex_rows) else "blocked",
        "mean_tm_score_proxy": _mean(rows, "tm_score_proxy"),
        "mean_gdt_ts_proxy": _mean(rows, "gdt_ts_proxy"),
        "mean_ca_lddt_proxy": _mean(rows, "ca_lddt_proxy"),
        "mean_complex_interface_f1_proxy": _mean(rows, "interface_contact_f1_proxy", scope="complex"),
        "mean_complex_interface_precision_proxy": _mean(
            rows, "interface_contact_precision_proxy", scope="complex"
        ),
        "mean_complex_interface_recall_proxy": _mean(rows, "interface_contact_recall_proxy", scope="complex"),
        "mean_complex_interface_patch_jaccard_proxy": _mean(
            rows, "interface_patch_jaccard_proxy", scope="complex"
        ),
        "mean_complex_qsbest_proxy": _mean(rows, "interface_qsbest_proxy", scope="complex"),
        "mean_complex_dockq_proxy": _mean(rows, "dockq_proxy", scope="complex"),
        "manifest_blockers": ",".join(manifest_blockers),
        "thresholds": {
            "monomer_tm": float(args.monomer_tm_threshold),
            "monomer_gdt_ts": float(args.monomer_gdt_ts_threshold),
            "monomer_lddt": float(args.monomer_lddt_threshold),
            "complex_tm": float(args.complex_tm_threshold),
            "complex_interface_f1": float(args.complex_interface_f1_threshold),
            "complex_dockq": float(args.complex_dockq_threshold),
            "min_ca_count": int(args.min_ca_count),
            "min_ca_coverage": float(args.min_ca_coverage),
            "min_sequence_match_fraction": float(args.min_sequence_match_fraction),
        },
        "claim_boundary": "Local no-leak historical benchmark proxy only; not official CASP scoring, not current-target native accuracy evidence, and not portal submission.",
    }
    return {"summary": summary, "rows": rows}


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# CASP17 Historical Benchmark Packet",
        "",
        f"- generated: `{summary['generated_at_local']}`",
        f"- manifest_csv: `{summary['manifest_csv']}`",
        f"- status: `{summary['historical_benchmark_status']}`",
        f"- benchmark_count: `{summary['benchmark_count']}`",
        f"- pass/blocked: `{summary['pass_count']}/{summary['blocked_count']}`",
        f"- monomer pass/count: `{summary['monomer_pass_count']}/{summary['monomer_benchmark_count']}`",
        f"- complex pass/count: `{summary['complex_pass_count']}/{summary['complex_benchmark_count']}`",
        f"- sequence-exact rows: `{summary['sequence_exact_match_count']}/{summary['benchmark_count']}`",
        f"- chain-exact rows: `{summary['chain_exact_match_count']}/{summary['benchmark_count']}`",
        f"- mean TM/GDT_TS/lDDT proxy: `{summary['mean_tm_score_proxy']}/{summary['mean_gdt_ts_proxy']}/{summary['mean_ca_lddt_proxy']}`",
        "",
        "| benchmark | target | scope | status | CA | CA coverage | chains | seq exact | RMSD A | TM proxy | GDT_TS | lDDT | interface F1 | IPS | QSbest | DockQ | blockers |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['benchmark_id']}` | `{row['target_id']}` | `{row['scope']}` | `{row['benchmark_status']}` | "
            f"{row['matched_ca_count']} | {row['prediction_ca_coverage']}/{row['native_ca_coverage']} | "
            f"{row['matched_chain_count']} | {row['sequence_exact_match']} | "
            f"{row['ca_rmsd_A']} | {row['tm_score_proxy']} | {row['gdt_ts_proxy']} | "
            f"{row['ca_lddt_proxy']} | {row['interface_contact_f1_proxy']} | "
            f"{row['interface_patch_jaccard_proxy']} | {row['interface_qsbest_proxy']} | "
            f"{row['dockq_proxy']} | {row['blockers'] or '-'} |"
        )
    if not payload["rows"]:
        lines.append("| - | - | - | `blocked` | 0 | 0/0 | 0 | False | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | manifest missing or empty |")
    lines.extend(["", "## Claim Boundary", "", str(summary["claim_boundary"]), ""])
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build no-leak historical native benchmark proxy packet for CASP17 internal predictions.")
    parser.add_argument("--manifest-csv", default=DEFAULT_MANIFEST_CSV)
    parser.add_argument("--min-ca-count", type=int, default=20)
    parser.add_argument("--monomer-tm-threshold", type=float, default=0.90)
    parser.add_argument("--monomer-gdt-ts-threshold", type=float, default=0.80)
    parser.add_argument("--monomer-lddt-threshold", type=float, default=0.75)
    parser.add_argument("--complex-tm-threshold", type=float, default=0.75)
    parser.add_argument("--complex-interface-f1-threshold", type=float, default=0.50)
    parser.add_argument("--complex-dockq-threshold", type=float, default=0.58)
    parser.add_argument("--min-sequence-match-fraction", type=float, default=1.0)
    parser.add_argument("--min-ca-coverage", type=float, default=1.0)
    parser.add_argument(
        "--allow-order-fallback",
        action="store_true",
        help="Allow coordinate scoring when prediction/native CA chain+residue keys do not overlap; status still records order_fallback.",
    )
    parser.add_argument("--fail-on-blocked", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_md(args.out_md, payload)
    if args.fail_on_blocked and payload["summary"]["blocked_count"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
