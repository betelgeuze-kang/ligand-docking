#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from core.definitions import ResearchConstants
from tools.curate_structure_quality import curate_structure_rows
from tools.fetch_public_structure_set import fetch_public_structure_set


def _ns(**kwargs: Any) -> argparse.Namespace:
    return SimpleNamespace(**kwargs)


def _parse_targets(spec: str, sources_csv: str = "") -> List[str]:
    s = str(spec).strip().lower()
    if s in {"sources_all", "csv_all", "manifest_all"}:
        src = str(sources_csv).strip()
        if src and os.path.exists(src):
            try:
                df = pd.read_csv(src)
                if "target" in df.columns:
                    out = [str(x).strip() for x in df["target"].astype(str).tolist() if str(x).strip()]
                    uniq: List[str] = []
                    seen = set()
                    for t in out:
                        if t in seen:
                            continue
                        uniq.append(t)
                        seen.add(t)
                    if len(uniq) > 0:
                        return uniq
            except Exception:
                pass
    if s == "all":
        return list(ResearchConstants.CHALLENGES.keys())
    out = [x.strip() for x in str(spec).split(",") if x.strip()]
    uniq: List[str] = []
    seen = set()
    for t in out:
        if t in seen:
            continue
        uniq.append(t)
        seen.add(t)
    return uniq


def _normalize_target_key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _read_ca_coords_by_chain(path: str) -> Dict[str, np.ndarray]:
    chain_coords: Dict[str, List[List[float]]] = {}
    model_seen = False
    in_first_model = True
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            rec = line[0:6].strip().upper()
            if rec == "MODEL":
                if not model_seen:
                    model_seen = True
                    in_first_model = True
                else:
                    in_first_model = False
                continue
            if rec == "ENDMDL" and model_seen:
                break
            if model_seen and (not in_first_model):
                continue
            if not line.startswith("ATOM"):
                continue
            atom_name = line[12:16].strip()
            if atom_name != "CA":
                continue
            chain_id = str(line[21:22]).strip() or "_"
            try:
                x = float(line[30:38].strip())
                y = float(line[38:46].strip())
                z = float(line[46:54].strip())
            except Exception:
                continue
            chain_coords.setdefault(chain_id, []).append([x, y, z])
    out: Dict[str, np.ndarray] = {}
    for cid, rows in chain_coords.items():
        if len(rows) <= 0:
            continue
        out[str(cid)] = np.asarray(rows, dtype=np.float64)
    return out


def _kabsch_aligned_rmsd(a: np.ndarray, b: np.ndarray) -> float:
    xa = np.asarray(a, dtype=np.float64)
    xb = np.asarray(b, dtype=np.float64)
    xa = xa - xa.mean(axis=0, keepdims=True)
    xb = xb - xb.mean(axis=0, keepdims=True)
    cov = xa.T @ xb
    u, _s, vh = np.linalg.svd(cov, full_matrices=False)
    d = np.linalg.det(u @ vh)
    if d < 0.0:
        u[:, -1] *= -1.0
    rot = u @ vh
    xr = xa @ rot
    diff = xr - xb
    return float(np.sqrt(np.mean(np.sum(diff * diff, axis=1))))


def _best_windowed_rmsd(small: np.ndarray, large: np.ndarray) -> Tuple[float, int]:
    n = int(small.shape[0])
    m = int(large.shape[0])
    if n <= 0 or m < n:
        return float("inf"), -1
    best_r = float("inf")
    best_i = -1
    for i in range(0, m - n + 1):
        seg = large[i : i + n]
        r = _kabsch_aligned_rmsd(small, seg)
        if r < best_r:
            best_r = float(r)
            best_i = int(i)
    return best_r, best_i


def _best_chain_pair_match(
    pdb_chains: Dict[str, np.ndarray],
    afdb_chains: Dict[str, np.ndarray],
    *,
    max_length_ratio: float,
    enable_windowed_match: bool,
    max_windowed_rmsd: float,
    min_pair_ca: int,
) -> Dict[str, Any]:
    best: Optional[Dict[str, Any]] = None
    for pdb_chain_id, ca_pdb in pdb_chains.items():
        if not isinstance(ca_pdb, np.ndarray) or ca_pdb.shape[0] <= 0:
            continue
        for afdb_chain_id, ca_afdb in afdb_chains.items():
            if not isinstance(ca_afdb, np.ndarray) or ca_afdb.shape[0] <= 0:
                continue
            row: Dict[str, Any] = {
                "pdb_chain": str(pdb_chain_id),
                "afdb_chain": str(afdb_chain_id),
                "pdb_ca": int(ca_pdb.shape[0]),
                "afdb_ca": int(ca_afdb.shape[0]),
                "paired": 0,
                "reason": "no_chain_pair_match",
                "ca_used": None,
                "ca_length_ratio": None,
                "window_start": None,
                "windowed_match": 0,
                "rmsd_aligned_A": None,
                "window_on": "",
            }

            small_n = float(min(ca_pdb.shape[0], ca_afdb.shape[0]))
            large_n = float(max(ca_pdb.shape[0], ca_afdb.shape[0]))
            ratio = (large_n / max(small_n, 1.0)) if large_n > 0 else 1.0
            row["ca_length_ratio"] = float(ratio)

            if ratio > float(max_length_ratio):
                if bool(enable_windowed_match):
                    if ca_pdb.shape[0] <= ca_afdb.shape[0]:
                        small = ca_pdb
                        large = ca_afdb
                        window_on = "afdb"
                    else:
                        small = ca_afdb
                        large = ca_pdb
                        window_on = "pdb"
                    win_rmsd, win_start = _best_windowed_rmsd(small=small, large=large)
                    if (
                        win_start >= 0
                        and np.isfinite(win_rmsd)
                        and win_rmsd <= float(max_windowed_rmsd)
                        and int(small.shape[0]) >= int(min_pair_ca)
                    ):
                        row["paired"] = 1
                        row["reason"] = "ok_windowed"
                        row["windowed_match"] = 1
                        row["window_start"] = int(win_start)
                        row["ca_used"] = int(small.shape[0])
                        row["rmsd_aligned_A"] = float(win_rmsd)
                        row["window_on"] = str(window_on)
                if int(row.get("paired", 0)) != 1:
                    row["reason"] = "ca_length_mismatch"
            else:
                n = int(min(ca_pdb.shape[0], ca_afdb.shape[0]))
                row["ca_used"] = n
                if n < int(min_pair_ca):
                    row["reason"] = "insufficient_ca_overlap"
                else:
                    best_local_rmsd: Optional[float] = None
                    best_local_mode = "direct"
                    best_local_win_start: Optional[int] = None
                    best_local_window_on = ""
                    try:
                        direct_rmsd = _kabsch_aligned_rmsd(ca_pdb[:n], ca_afdb[:n])
                        best_local_rmsd = float(direct_rmsd)
                    except Exception as exc:
                        row["reason"] = f"rmsd_error:{exc}"
                    else:
                        # Even when length ratio is acceptable, windowed match can remove terminal mismatch noise.
                        if bool(enable_windowed_match):
                            if ca_pdb.shape[0] <= ca_afdb.shape[0]:
                                small = ca_pdb
                                large = ca_afdb
                                window_on = "afdb"
                            else:
                                small = ca_afdb
                                large = ca_pdb
                                window_on = "pdb"
                            win_rmsd, win_start = _best_windowed_rmsd(small=small, large=large)
                            if (
                                win_start >= 0
                                and np.isfinite(win_rmsd)
                                and win_rmsd <= float(max_windowed_rmsd)
                                and int(small.shape[0]) >= int(min_pair_ca)
                            ):
                                if (best_local_rmsd is None) or (float(win_rmsd) < float(best_local_rmsd)):
                                    best_local_rmsd = float(win_rmsd)
                                    best_local_mode = "windowed"
                                    best_local_win_start = int(win_start)
                                    best_local_window_on = str(window_on)

                        if best_local_rmsd is not None:
                            row["paired"] = 1
                            row["reason"] = "ok_windowed" if best_local_mode == "windowed" else "ok"
                            row["rmsd_aligned_A"] = float(best_local_rmsd)
                            if best_local_mode == "windowed":
                                row["windowed_match"] = 1
                                row["window_start"] = best_local_win_start
                                row["window_on"] = best_local_window_on

            if int(row.get("paired", 0)) != 1:
                continue
            if best is None:
                best = row
                continue
            prev = float(best.get("rmsd_aligned_A", float("inf")) or float("inf"))
            cur = float(row.get("rmsd_aligned_A", float("inf")) or float("inf"))
            if cur < prev:
                best = row

    if best is None:
        return {"paired": 0, "reason": "no_chain_pair_match"}
    return best


def _pick_best_row(rows: pd.DataFrame, source_kind: str) -> Optional[Dict[str, Any]]:
    if rows.empty:
        return None
    kinds = rows["source_kind"].astype(str).str.strip().str.lower()
    key = str(source_kind).strip().lower()
    if key == "afdb":
        sub = rows[kinds.str.startswith("afdb")].copy()
    elif key == "pdb_or_other":
        sub = rows[kinds.isin(["pdb_or_other", "pdb", "experimental", "native"])].copy()
    else:
        sub = rows[kinds == key].copy()
    if sub.empty:
        return None
    sub["include_i"] = pd.to_numeric(sub.get("include"), errors="coerce").fillna(0).astype(int)
    sub["sample_weight_f"] = pd.to_numeric(sub.get("sample_weight"), errors="coerce").fillna(0.0)
    sub["plddt_mean_f"] = pd.to_numeric(sub.get("plddt_mean"), errors="coerce").fillna(0.0)
    sub = sub.sort_values(
        by=["include_i", "sample_weight_f", "plddt_mean_f"],
        ascending=[False, False, False],
    )
    return sub.iloc[0].to_dict()


def _augment_manifest_with_proxy(
    manifest_csv: str,
    targets: List[str],
    out_manifest_csv: str,
    enable_proxy_manifest: bool,
) -> Dict[str, Any]:
    df = pd.read_csv(manifest_csv)
    if "target" not in df.columns or "source_kind" not in df.columns:
        raise ValueError(f"manifest missing required columns target/source_kind: {manifest_csv}")

    if not bool(enable_proxy_manifest):
        return {
            "manifest_used_csv": manifest_csv,
            "manifest_with_proxy_csv": None,
            "proxy_rows_added": 0,
            "proxy_targets_added": [],
        }

    work = df.copy()
    existing_afdb = set()
    for _, row in work.iterrows():
        t = str(row.get("target", "")).strip()
        if not t:
            continue
        kind = str(row.get("source_kind", "")).strip().lower()
        if kind.startswith("afdb"):
            existing_afdb.add(_normalize_target_key(t))

    proxy_rows: List[Dict[str, Any]] = []
    for target in targets:
        tkey = _normalize_target_key(target)
        if tkey in existing_afdb:
            continue
        sub = work[work["target"].astype(str).str.strip() == str(target)].copy()
        if sub.empty:
            continue
        pdb_sub = sub[
            sub["source_kind"].astype(str).str.lower().isin(["pdb", "pdb_or_other", "experimental", "native"])
        ].copy()
        if pdb_sub.empty:
            pdb_sub = sub.copy()
        base = pdb_sub.iloc[0].to_dict()
        base["source_kind"] = "afdb_proxy"
        base["source_id"] = str(base.get("pdb_id") or base.get("source_id") or "proxy") + "_proxy"
        base["status"] = "proxy"
        base["error"] = ""
        base["url"] = "proxy://pdb_or_other_fallback"
        base["fallback_attempts"] = 0
        base["proxy_generated"] = 1
        base["proxy_reason"] = "missing_afdb_source_for_target"
        proxy_rows.append(base)

    if len(proxy_rows) > 0:
        work = pd.concat([work, pd.DataFrame(proxy_rows)], ignore_index=True)
    os.makedirs(os.path.dirname(out_manifest_csv) or ".", exist_ok=True)
    work.to_csv(out_manifest_csv, index=False)
    return {
        "manifest_used_csv": out_manifest_csv,
        "manifest_with_proxy_csv": out_manifest_csv,
        "proxy_rows_added": int(len(proxy_rows)),
        "proxy_targets_added": sorted({str(r.get("target", "")) for r in proxy_rows if str(r.get("target", "")).strip()}),
    }


def _load_domain_tags(domain_tags_csv: str, sources_csv: str) -> Dict[str, str]:
    tags: Dict[str, str] = {}
    path = str(domain_tags_csv).strip()
    if path and os.path.exists(path):
        df = pd.read_csv(path)
        if "target" in df.columns and "domain" in df.columns:
            for _, row in df.iterrows():
                t = str(row.get("target", "")).strip()
                d = str(row.get("domain", "")).strip().lower()
                if t and d:
                    tags[t] = d
            return tags
    src = str(sources_csv).strip()
    if src and os.path.exists(src):
        df = pd.read_csv(src)
        if "target" in df.columns:
            cand_cols = [c for c in ("domain", "domain_tag", "family", "notes") if c in df.columns]
            if cand_cols:
                c0 = cand_cols[0]
                for _, row in df.iterrows():
                    t = str(row.get("target", "")).strip()
                    d = str(row.get(c0, "")).strip().lower()
                    if t and d:
                        tags[t] = d
    return tags


def run_ood_batch(args: argparse.Namespace) -> Dict[str, Any]:
    date_tag = str(args.date_tag).strip() or dt.date.today().isoformat()
    out_prefix = str(args.out_prefix).strip() or f"runs/ood_first_validation_batch_{date_tag}"
    out_dir = str(args.out_dir).strip() or f"data/public_structures/{date_tag}_ood_first"
    targets = _parse_targets(str(args.targets), str(args.sources_csv))
    if len(targets) <= 0:
        raise ValueError(f"no targets resolved from --targets={args.targets} --sources-csv={args.sources_csv}")

    manifest_csv = str(getattr(args, "manifest_csv", "")).strip() or f"{out_prefix}_manifest.csv"
    manifest_with_proxy_csv = f"{out_prefix}_manifest_with_proxy.csv"
    fetch_summary_json = f"{out_prefix}_fetch_summary.json"
    curated_csv = str(getattr(args, "curated_csv", "")).strip() or f"{out_prefix}_curated.csv"
    curated_json = str(getattr(args, "curated_json", "")).strip() or f"{out_prefix}_curated.json"
    pair_csv = f"{out_prefix}_pair_metrics.csv"
    summary_json = f"{out_prefix}_summary.json"

    fetch_payload: Dict[str, Any]
    if bool(args.skip_fetch):
        if not os.path.exists(manifest_csv):
            raise FileNotFoundError(f"--skip-fetch was set but manifest_csv is missing: {manifest_csv}")
        fetch_payload = {
            "summary": {
                "skipped": True,
                "manifest_csv": manifest_csv,
            }
        }
    else:
        fetch_payload = fetch_public_structure_set(
            sources_csv=str(args.sources_csv),
            targets_spec=",".join(targets),
            out_dir=out_dir,
            out_manifest_csv=manifest_csv,
            out_summary_json=fetch_summary_json,
            download_pdb=bool(args.download_pdb),
            download_afdb=bool(args.download_afdb),
            afdb_model_versions=str(args.afdb_model_versions),
            timeout_sec=float(args.timeout_sec),
            overwrite=bool(args.overwrite),
            dry_run=bool(args.dry_run),
            strict=bool(args.strict_fetch),
            write_template_if_missing=bool(args.write_template_if_missing),
        )

    proxy_info = _augment_manifest_with_proxy(
        manifest_csv=manifest_csv,
        targets=targets,
        out_manifest_csv=manifest_with_proxy_csv,
        enable_proxy_manifest=bool(args.enable_proxy_manifest),
    )
    manifest_for_curation = str(proxy_info.get("manifest_used_csv") or manifest_csv)
    domain_tags = _load_domain_tags(
        domain_tags_csv=str(getattr(args, "domain_tags_csv", "")),
        sources_csv=str(args.sources_csv),
    )

    if bool(args.skip_curation):
        if not os.path.exists(curated_csv):
            raise FileNotFoundError(f"--skip-curation was set but curated_csv is missing: {curated_csv}")
        curated_df = pd.read_csv(curated_csv)
        curated_payload = {}
        if os.path.exists(curated_json):
            try:
                with open(curated_json, "r", encoding="utf-8") as f:
                    curated_payload = json.load(f)
            except Exception:
                curated_payload = {}
        curated_rows = curated_df.to_dict(orient="records")
        curated_summary = (
            curated_payload.get("summary", {})
            if isinstance(curated_payload.get("summary"), dict)
            else {
                "rows": int(curated_df.shape[0]),
                "included": int(
                    pd.to_numeric(curated_df.get("include"), errors="coerce").fillna(0).astype(int).sum()
                )
                if "include" in curated_df.columns
                else None,
                "skipped": True,
            }
        )
    else:
        curated_rows, curated_summary = curate_structure_rows(
            _ns(
                pdb_glob=[],
                pdb_file=[],
                manifest_csv=manifest_for_curation,
                manifest_path_col="path",
                manifest_target_col="target",
                manifest_source_kind_col="source_kind",
                targets=",".join(targets),
                min_ca_residues=int(args.min_ca_residues),
                min_ca_coverage=float(args.min_ca_coverage),
                plddt_medium_threshold=float(args.plddt_medium_threshold),
                plddt_high_threshold=float(args.plddt_high_threshold),
                plddt_min_threshold=float(args.plddt_min_threshold),
                allow_bfactor_as_plddt=False,
                weight_high=float(args.weight_high),
                weight_medium=float(args.weight_medium),
                weight_low=float(args.weight_low),
                experimental_weight=float(args.experimental_weight),
            )
        )
        os.makedirs(os.path.dirname(curated_csv) or ".", exist_ok=True)
        curated_df = pd.DataFrame(curated_rows)
        curated_df.to_csv(curated_csv, index=False)
        with open(curated_json, "w", encoding="utf-8") as f:
            json.dump({"summary": curated_summary, "rows": curated_rows}, f, indent=2, ensure_ascii=False)

    pair_rows: List[Dict[str, Any]] = []
    candidates_with_both = 0
    for target in targets:
        sub = curated_df[curated_df["target"].astype(str) == str(target)].copy() if not curated_df.empty else pd.DataFrame()
        pdb_row = _pick_best_row(sub, source_kind="pdb_or_other")
        afdb_row = _pick_best_row(sub, source_kind="afdb")
        row: Dict[str, Any] = {
            "target": target,
            "paired": 0,
            "reason": "",
            "pdb_path": pdb_row.get("source_file") if pdb_row else None,
            "afdb_path": afdb_row.get("source_file") if afdb_row else None,
            "afdb_source_kind": str(afdb_row.get("source_kind", "")) if afdb_row else "",
            "afdb_is_proxy": 0,
            "pdb_ca": None,
            "afdb_ca": None,
            "ca_used": None,
            "ca_length_ratio": None,
            "window_start": None,
            "windowed_match": 0,
            "rmsd_aligned_A": None,
        }
        if not pdb_row or not afdb_row:
            row["reason"] = "missing_pdb_or_afdb"
            pair_rows.append(row)
            continue
        afdb_kind = str(afdb_row.get("source_kind", "")).strip().lower()
        row["afdb_source_kind"] = afdb_kind
        row["afdb_is_proxy"] = 1 if afdb_kind.startswith("afdb_proxy") else 0
        if bool(getattr(args, "require_real_afdb", False)) and row["afdb_is_proxy"] == 1:
            row["reason"] = "afdb_proxy_not_allowed"
            pair_rows.append(row)
            continue
        candidates_with_both += 1
        pdb_path = str(pdb_row.get("source_file") or "")
        afdb_path = str(afdb_row.get("source_file") or "")
        if (not os.path.exists(pdb_path)) or (not os.path.exists(afdb_path)):
            row["reason"] = "missing_file_on_disk"
            pair_rows.append(row)
            continue
        pdb_chain_map = _read_ca_coords_by_chain(pdb_path)
        afdb_chain_map = _read_ca_coords_by_chain(afdb_path)
        row["pdb_chain_count"] = int(len(pdb_chain_map))
        row["afdb_chain_count"] = int(len(afdb_chain_map))
        row["pdb_ca"] = int(sum(int(v.shape[0]) for v in pdb_chain_map.values()))
        row["afdb_ca"] = int(sum(int(v.shape[0]) for v in afdb_chain_map.values()))
        if row["pdb_ca"] == 0 or row["afdb_ca"] == 0:
            row["reason"] = "missing_ca_atoms"
            pair_rows.append(row)
            continue
        best_chain_pair = _best_chain_pair_match(
            pdb_chains=pdb_chain_map,
            afdb_chains=afdb_chain_map,
            max_length_ratio=float(args.max_length_ratio),
            enable_windowed_match=bool(args.enable_windowed_match),
            max_windowed_rmsd=float(args.max_windowed_rmsd),
            min_pair_ca=int(args.min_pair_ca),
        )
        if int(best_chain_pair.get("paired", 0)) != 1:
            row["reason"] = str(best_chain_pair.get("reason", "no_chain_pair_match"))
            pair_rows.append(row)
            continue
        row["paired"] = 1
        row["reason"] = str(best_chain_pair.get("reason", "ok"))
        row["rmsd_aligned_A"] = float(best_chain_pair.get("rmsd_aligned_A", float("nan")))
        row["ca_used"] = int(best_chain_pair.get("ca_used", 0) or 0)
        row["ca_length_ratio"] = float(best_chain_pair.get("ca_length_ratio", float("nan")))
        row["windowed_match"] = int(best_chain_pair.get("windowed_match", 0) or 0)
        row["window_start"] = best_chain_pair.get("window_start")
        row["window_on"] = str(best_chain_pair.get("window_on", ""))
        row["pdb_chain"] = str(best_chain_pair.get("pdb_chain", ""))
        row["afdb_chain"] = str(best_chain_pair.get("afdb_chain", ""))
        pair_rows.append(row)

    pair_df = pd.DataFrame(pair_rows)
    pair_df.to_csv(pair_csv, index=False)

    paired_df = pair_df[pd.to_numeric(pair_df["paired"], errors="coerce").fillna(0).astype(int) == 1].copy()
    rmsd_vals = pd.to_numeric(paired_df["rmsd_aligned_A"], errors="coerce").dropna().to_numpy(dtype=np.float64)
    paired_targets = int(paired_df.shape[0])
    proxy_pair_count = int(paired_df["afdb_is_proxy"].fillna(0).astype(int).sum()) if "afdb_is_proxy" in paired_df.columns else 0
    real_pair_count = int(max(paired_targets - proxy_pair_count, 0))
    real_pair_coverage = float(real_pair_count / max(paired_targets, 1)) if paired_targets > 0 else 0.0
    requested_min_pairs = int(args.min_pairs)
    min_pairs = int(min(requested_min_pairs, max(candidates_with_both, 0)))
    mean_rmsd = float(np.mean(rmsd_vals)) if rmsd_vals.size > 0 else None
    pass_pairs = paired_targets >= min_pairs
    pass_rmsd = True
    if mean_rmsd is not None and float(args.max_mean_pair_rmsd) > 0.0:
        pass_rmsd = mean_rmsd <= float(args.max_mean_pair_rmsd)

    max_proxy_rows_cfg = int(getattr(args, "max_proxy_rows", -1))
    proxy_rows_added = int(proxy_info.get("proxy_rows_added", 0) or 0)
    pass_proxy_rows = True if max_proxy_rows_cfg < 0 else (proxy_rows_added <= max_proxy_rows_cfg)
    require_real_afdb = bool(getattr(args, "require_real_afdb", False))
    pass_real_afdb = ((proxy_pair_count == 0) and (proxy_rows_added == 0)) if require_real_afdb else True
    paired_targets_list = set(paired_df["target"].astype(str).tolist()) if not paired_df.empty else set()
    covered_domains = sorted({domain_tags[t] for t in paired_targets_list if t in domain_tags and str(domain_tags[t]).strip()})
    min_domain_coverage = int(getattr(args, "min_domain_coverage", 0) or 0)
    domain_coverage_value = int(len(covered_domains))
    pass_domain_coverage = True if min_domain_coverage <= 0 else (domain_coverage_value >= min_domain_coverage)

    summary = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "date_tag": date_tag,
        "targets": targets,
        "target_count": int(len(targets)),
        "pass": bool(pass_pairs and pass_rmsd and pass_proxy_rows and pass_real_afdb and pass_domain_coverage),
        "gates": {
            "min_pairs": {
                "threshold_requested": requested_min_pairs,
                "threshold_effective": min_pairs,
                "value": paired_targets,
                "pass": bool(pass_pairs),
            },
            "max_mean_pair_rmsd": {
                "threshold": float(args.max_mean_pair_rmsd),
                "value": mean_rmsd,
                "pass": bool(pass_rmsd),
            },
            "max_proxy_rows": {
                "threshold": max_proxy_rows_cfg,
                "value": proxy_rows_added,
                "pass": bool(pass_proxy_rows),
            },
            "require_real_afdb": {
                "enabled": bool(require_real_afdb),
                "proxy_pairs": int(proxy_pair_count),
                "pass": bool(pass_real_afdb),
            },
            "min_domain_coverage": {
                "threshold": int(min_domain_coverage),
                "value": int(domain_coverage_value),
                "pass": bool(pass_domain_coverage),
            },
        },
        "pair_metrics": {
            "candidates_with_both_sources": int(candidates_with_both),
            "paired_targets": paired_targets,
            "real_paired_targets": int(real_pair_count),
            "proxy_paired_targets": int(proxy_pair_count),
            "real_pair_coverage": float(real_pair_coverage),
            "domain_coverage": int(domain_coverage_value),
            "covered_domains": covered_domains,
            "avg_pair_rmsd_aligned_A": mean_rmsd,
            "max_pair_rmsd_aligned_A": float(np.max(rmsd_vals)) if rmsd_vals.size > 0 else None,
            "min_pair_rmsd_aligned_A": float(np.min(rmsd_vals)) if rmsd_vals.size > 0 else None,
            "windowed_matches": int(
                pair_df["windowed_match"].fillna(0).astype(int).sum()
            )
            if "windowed_match" in pair_df.columns
            else 0,
        },
        "artifacts": {
            "manifest_csv": manifest_csv,
            "manifest_with_proxy_csv": proxy_info.get("manifest_with_proxy_csv"),
            "manifest_used_for_curation": manifest_for_curation,
            "fetch_summary_json": fetch_summary_json,
            "curated_csv": curated_csv,
            "curated_json": curated_json,
            "pair_csv": pair_csv,
            "summary_json": summary_json,
        },
        "fetch_summary": fetch_payload.get("summary", {}),
        "curation_summary": curated_summary,
        "proxy_summary": proxy_info,
    }
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    if bool(args.strict_fail) and (not bool(summary["pass"])):
        raise RuntimeError(
            "ood first validation failed: "
            f"paired={paired_targets} (min_effective={min_pairs}, requested={requested_min_pairs}), "
            f"avg_pair_rmsd={mean_rmsd}, "
            f"proxy_rows_added={proxy_rows_added}, "
            f"proxy_pairs={proxy_pair_count}, "
            f"domain_coverage={domain_coverage_value}"
        )
    return summary


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run OOD first validation batch (public PDB/AFDB fetch + quality curation + pairwise drift metrics)."
    )
    p.add_argument("--targets", type=str, default="all")
    p.add_argument("--date-tag", type=str, default=dt.date.today().isoformat())
    p.add_argument("--sources-csv", type=str, default="config/structure_sources_10targets.csv")
    p.add_argument("--out-dir", type=str, default="")
    p.add_argument("--out-prefix", type=str, default="")
    p.add_argument("--manifest-csv", type=str, default="")
    p.add_argument("--curated-csv", type=str, default="")
    p.add_argument("--curated-json", type=str, default="")
    p.add_argument("--download-pdb", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--download-afdb", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--afdb-model-versions", type=str, default="v6,v5,v4")
    p.add_argument("--timeout-sec", type=float, default=30.0)
    p.add_argument("--overwrite", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--strict-fetch", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--skip-fetch", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--skip-curation", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument("--write-template-if-missing", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--enable-proxy-manifest",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Add afdb_proxy rows from pdb_or_other for targets missing AFDB sources.",
    )
    p.add_argument("--min-ca-residues", type=int, default=8)
    p.add_argument("--min-ca-coverage", type=float, default=0.70)
    p.add_argument("--plddt-medium-threshold", type=float, default=70.0)
    p.add_argument("--plddt-high-threshold", type=float, default=85.0)
    p.add_argument("--plddt-min-threshold", type=float, default=50.0)
    p.add_argument("--weight-high", type=float, default=1.0)
    p.add_argument("--weight-medium", type=float, default=0.6)
    p.add_argument("--weight-low", type=float, default=0.2)
    p.add_argument("--experimental-weight", type=float, default=0.5)
    p.add_argument("--min-pair-ca", type=int, default=8)
    p.add_argument(
        "--max-length-ratio",
        type=float,
        default=1.5,
        help="Skip pair RMSD if max(ca_count)/min(ca_count) exceeds this ratio.",
    )
    p.add_argument(
        "--enable-windowed-match",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When lengths differ, search best Kabsch RMSD window on longer structure.",
    )
    p.add_argument(
        "--max-windowed-rmsd",
        type=float,
        default=12.0,
        help="Accept windowed match only when best RMSD <= this threshold.",
    )
    p.add_argument("--min-pairs", type=int, default=8)
    p.add_argument("--max-mean-pair-rmsd", type=float, default=6.0)
    p.add_argument("--require-real-afdb", action=argparse.BooleanOptionalAction, default=False)
    p.add_argument(
        "--max-proxy-rows",
        type=int,
        default=-1,
        help="Fail gate when proxy rows exceed this value. Negative disables this gate.",
    )
    p.add_argument("--domain-tags-csv", type=str, default="")
    p.add_argument(
        "--min-domain-coverage",
        type=int,
        default=0,
        help="Minimum unique domain tags among paired targets. 0 disables this gate.",
    )
    p.add_argument("--strict-fail", action=argparse.BooleanOptionalAction, default=False)
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = run_ood_batch(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
