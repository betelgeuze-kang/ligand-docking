#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from core.definitions import ResearchConstants
from tools.native_target_registry import candidate_target_keys, canonicalize_target_name

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGET = "T. cruzi PDE"
DEFAULT_NATIVE_CSV = "config/real_drug_targets_native_v1.csv"
DEFAULT_PROFILE_JSON = "config/long_stability_target_tuned_all10_2026-02-15.json"
DEFAULT_OUT_JSON = "runs/strict_release_target_registration_packet_current.json"
DEFAULT_OUT_MD = "runs/strict_release_target_registration_packet_current.md"


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _safe_int(value: Any) -> int | None:
    try:
        if value in {"", None, "missing"}:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_ratio(numerator: Any, denominator: Any) -> float | None:
    top = _safe_int(numerator)
    bottom = _safe_int(denominator)
    if top is None or bottom in {None, 0}:
        return None
    return round(top / int(bottom), 6)


def _read_csv_rows(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{str(k): str(v or "") for k, v in row.items()} for row in csv.DictReader(handle)]


def _target_key_set(target: Any, *, aliases: Any = None) -> set[str]:
    return set(candidate_target_keys(target, extra_aliases=aliases))


def _find_native_row(rows: list[dict[str, str]], target: str) -> dict[str, str]:
    target_keys = _target_key_set(target)
    for row in rows:
        row_keys = _target_key_set(row.get("target"), aliases=row.get("target_aliases"))
        if target_keys & row_keys:
            return dict(row)
    return {}


def _challenge_target_map() -> dict[str, str]:
    return {
        "".join(ch for ch in str(name).lower() if ch.isalnum()): name
        for name in ResearchConstants.CHALLENGES
    }


def _profile_target_map(profile_json: str | Path) -> dict[str, str]:
    path = _resolve(profile_json)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    targets = payload.get("targets")
    if not isinstance(targets, dict):
        return {}
    return {
        "".join(ch for ch in str(name).lower() if ch.isalnum()): str(name)
        for name in targets.keys()
    }


def _pdb_stats(path: Path) -> dict[str, Any]:
    base: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "atom_count": 0,
        "ca_count": 0,
        "residue_count": 0,
        "hetero_residue_count": 0,
        "chain_count": 0,
        "chains": [],
    }
    if not path.exists():
        return base

    chain_stats: dict[str, dict[str, Any]] = {}
    seqres_counts: dict[str, int] = {}
    dbref_ranges: dict[str, tuple[int, int]] = {}
    missing_residues: dict[str, set[tuple[str, str]]] = {}
    all_residues: set[tuple[str, str, str]] = set()
    all_het_residues: set[tuple[str, str, str]] = set()
    atom_count = 0
    ca_count = 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith("SEQRES"):
                parts = line.split()
                if len(parts) >= 4:
                    chain = parts[2]
                    count = _safe_int(parts[3])
                    if chain and count is not None:
                        seqres_counts[chain] = count
                continue
            if line.startswith("DBREF"):
                parts = line.split()
                if len(parts) >= 5:
                    chain = parts[2]
                    start = _safe_int(parts[3])
                    end = _safe_int(parts[4])
                    if chain and start is not None and end is not None:
                        dbref_ranges[chain] = (start, end)
                continue
            if line.startswith("REMARK 465"):
                parts = line.split()
                if len(parts) >= 5 and parts[0] == "REMARK" and parts[1] == "465":
                    residue_parts = parts[2:]
                    if residue_parts[0].isdigit() and len(residue_parts) >= 4:
                        residue_name, chain, residue_number = residue_parts[1:4]
                    else:
                        residue_name, chain, residue_number = residue_parts[0:3]
                    if (
                        len(residue_name) == 3
                        and chain
                        and _safe_int(residue_number) is not None
                    ):
                        missing_residues.setdefault(chain, set()).add((residue_number, residue_name))
                continue
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            is_atom = line.startswith("ATOM  ")
            atom_count += 1
            atom_name = line[12:16].strip()
            chain = line[21].strip() or "_"
            residue_key = (chain, line[22:26].strip(), line[26].strip())
            rec = chain_stats.setdefault(
                chain,
                {
                    "chain": chain,
                    "atom_count": 0,
                    "ca_count": 0,
                    "residue_count": 0,
                    "hetero_residue_count": 0,
                    "_residues": set(),
                    "_het_residues": set(),
                },
            )
            rec["atom_count"] += 1
            if is_atom:
                all_residues.add(residue_key)
                rec["_residues"].add(residue_key)
            else:
                all_het_residues.add(residue_key)
                rec["_het_residues"].add(residue_key)
            if is_atom and atom_name == "CA":
                ca_count += 1
                rec["ca_count"] += 1

    chains: list[dict[str, Any]] = []
    for chain, rec in sorted(chain_stats.items()):
        residues = rec.pop("_residues")
        het_residues = rec.pop("_het_residues")
        rec["residue_count"] = len(residues)
        rec["hetero_residue_count"] = len(het_residues)
        seqres_count = seqres_counts.get(chain)
        dbref_start, dbref_end = dbref_ranges.get(chain, (None, None))
        missing_count = len(missing_residues.get(chain, set()))
        rec["seqres_count"] = seqres_count
        rec["missing_residue_count"] = missing_count
        rec["observed_ca_fraction"] = _safe_ratio(rec.get("ca_count"), seqres_count)
        rec["dbref_start"] = dbref_start
        rec["dbref_end"] = dbref_end
        rec["dbref_length"] = (dbref_end - dbref_start + 1) if dbref_start is not None and dbref_end is not None else None
        chains.append(rec)

    return {
        **base,
        "atom_count": atom_count,
        "ca_count": ca_count,
        "residue_count": len(all_residues),
        "hetero_residue_count": len(all_het_residues),
        "chain_count": len(chains),
        "chains": chains,
    }


def _canonical_chain_recommendation(pdb_stats: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        dict(row)
        for row in pdb_stats.get("chains", [])
        if (_safe_int(row.get("ca_count")) or 0) > 0
    ]
    if not candidates:
        return {
            "canonical_chain_recommendation_ready": False,
            "recommended_canonical_chain": "",
            "recommended_seqres_n_res": None,
            "recommended_observed_ca_count": None,
            "recommended_missing_residue_count": None,
            "canonical_chain_recommendation_reason": "no_observed_ca_chain_candidates",
        }

    def _rank(row: dict[str, Any]) -> tuple[int, int, int, str]:
        ca_count = _safe_int(row.get("ca_count")) or 0
        seqres_count = _safe_int(row.get("seqres_count")) or 0
        missing_count = _safe_int(row.get("missing_residue_count"))
        missing_rank = missing_count if missing_count is not None else 10**9
        return (-ca_count, -seqres_count, missing_rank, str(row.get("chain") or ""))

    selected = sorted(candidates, key=_rank)[0]
    seqres_count = _safe_int(selected.get("seqres_count"))
    missing_count = _safe_int(selected.get("missing_residue_count"))
    reason = "max_observed_ca_count"
    if seqres_count is not None and missing_count is not None:
        reason = f"{reason}_with_seqres_{seqres_count}_and_missing_residue_count_{missing_count}"
    elif seqres_count is not None:
        reason = f"{reason}_with_seqres_{seqres_count}"

    return {
        "canonical_chain_recommendation_ready": True,
        "recommended_canonical_chain": str(selected.get("chain") or ""),
        "recommended_seqres_n_res": seqres_count,
        "recommended_observed_ca_count": _safe_int(selected.get("ca_count")),
        "recommended_missing_residue_count": missing_count,
        "canonical_chain_recommendation_reason": reason,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    target = _text(args.target, DEFAULT_TARGET)
    canonical_target = canonicalize_target_name(target)
    native_rows = _read_csv_rows(args.native_csv)
    native_row = _find_native_row(native_rows, target)
    native_path_text = _text(native_row.get("native_pdb_path") if native_row else "")
    native_path = _resolve(native_path_text) if native_path_text else Path("")
    pdb_stats = _pdb_stats(native_path) if native_path_text else {
        "path": "",
        "exists": False,
        "atom_count": 0,
        "ca_count": 0,
        "residue_count": 0,
        "hetero_residue_count": 0,
        "chain_count": 0,
        "chains": [],
    }

    target_keys = _target_key_set(target)
    challenge_map = _challenge_target_map()
    challenge_name = next((challenge_map[key] for key in target_keys if key in challenge_map), "")
    challenge_entry = ResearchConstants.CHALLENGES.get(challenge_name, {}) if challenge_name else {}
    challenge_n_res = _safe_int(challenge_entry.get("n_res")) if challenge_entry else None

    profile_map = _profile_target_map(args.profile_json)
    profile_name = next((profile_map[key] for key in target_keys if key in profile_map), "")

    canonical_chain = _text(args.canonical_chain)
    chain_lookup = {str(row.get("chain")): row for row in pdb_stats.get("chains", [])}
    selected_chain = chain_lookup.get(canonical_chain, {}) if canonical_chain else {}
    selected_chain_ca = _safe_int(selected_chain.get("ca_count")) if selected_chain else None
    selected_chain_residues = _safe_int(selected_chain.get("residue_count")) if selected_chain else None
    selected_chain_seqres = _safe_int(selected_chain.get("seqres_count")) if selected_chain else None
    selected_chain_missing = _safe_int(selected_chain.get("missing_residue_count")) if selected_chain else None
    chain_count = int(pdb_stats.get("chain_count", 0))
    recommendation = _canonical_chain_recommendation(pdb_stats)
    canonical_chain_ready = bool(
        canonical_chain
        and selected_chain
        and selected_chain_ca
        and selected_chain_residues
    )
    if not canonical_chain:
        canonical_chain_reason = "canonical_chain_not_selected"
    elif not selected_chain:
        canonical_chain_reason = "canonical_chain_not_found"
    elif not selected_chain_ca:
        canonical_chain_reason = "canonical_chain_has_no_ca_atoms"
    else:
        canonical_chain_reason = ""

    n_res_match = bool(
        canonical_chain_ready
        and challenge_n_res is not None
        and int(challenge_n_res) == int(selected_chain_ca)
    )
    if challenge_n_res is None:
        n_res_reason = "target_not_registered_in_research_constants"
    elif not canonical_chain_ready:
        n_res_reason = canonical_chain_reason
    elif not n_res_match:
        n_res_reason = f"n_res_mismatch:challenge={challenge_n_res},canonical_chain_ca={selected_chain_ca}"
    else:
        n_res_reason = ""

    blockers: list[str] = []
    if not native_row:
        blockers.append("native_registry_row_missing")
    if not bool(pdb_stats.get("exists")):
        blockers.append("native_pdb_missing")
    if chain_count > 1 and not canonical_chain:
        blockers.append("canonical_chain_not_selected")
    if not challenge_name:
        blockers.append("research_constants_target_missing")
    if not profile_name:
        blockers.append("long_stability_profile_target_missing")
    if challenge_name and canonical_chain_ready and not n_res_match:
        blockers.append("research_constants_n_res_mismatch")

    ready = not blockers
    next_required_step = (
        "Target registration is ready for strict-release use."
        if ready
        else "Resolve blockers before generating a strict-release summary for this target."
    )
    if "canonical_chain_not_selected" in blockers:
        next_required_step = (
            "Select and document the canonical PDB chain for T. cruzi PDE, then register "
            "the matching n_res/profile before strict-release execution."
        )
    if "research_constants_target_missing" in blockers:
        if canonical_chain_ready and selected_chain_ca is not None:
            profile_suffix = (
                ", then add a matching long-stability profile"
                if "long_stability_profile_target_missing" in blockers
                else ""
            )
            next_required_step = (
                f"Register {target} with canonical_chain={canonical_chain} and "
                f"n_res={selected_chain_ca} in ResearchConstants.CHALLENGES{profile_suffix}."
            )
        else:
            next_required_step = (
                "Register the target in ResearchConstants.CHALLENGES only after canonical chain "
                "and n_res provenance are fixed."
            )

    return {
        "schema": "strict_release_target_registration_packet.v1",
        "summary": {
            "target": target,
            "canonical_target": canonical_target,
            "registration_ready": ready,
            "status": "ready" if ready else "blocked",
            "blockers": blockers,
            "native_registry_ready": bool(native_row),
            "native_pdb_ready": bool(pdb_stats.get("exists")),
            "research_constants_ready": bool(challenge_name),
            "profile_ready": bool(profile_name),
            "canonical_chain_ready": canonical_chain_ready,
            "canonical_chain_recommendation_ready": recommendation["canonical_chain_recommendation_ready"],
            "n_res_match": n_res_match,
            "next_required_step": next_required_step,
        },
        "sources": {
            "native_csv": _text(args.native_csv),
            "profile_json": _text(args.profile_json),
        },
        "native_registry": {
            "row_found": bool(native_row),
            "target": native_row.get("target", "") if native_row else "",
            "native_pdb_path": str(native_path) if native_path_text else "",
            "pdb_id": native_row.get("pdb_id", "") if native_row else "",
            "target_aliases": native_row.get("target_aliases", "") if native_row else "",
            "notes": native_row.get("notes", "") if native_row else "",
        },
        "native_pdb": pdb_stats,
        "strict_release_registry": {
            "research_constants_target": challenge_name,
            "research_constants_n_res": challenge_n_res,
            "available_research_constants_targets": list(ResearchConstants.CHALLENGES.keys()),
            "profile_target": profile_name,
            "profile_json": _text(args.profile_json),
            "canonical_chain": canonical_chain,
            "selected_chain_ca_count": selected_chain_ca,
            "selected_chain_residue_count": selected_chain_residues,
            "selected_chain_seqres_count": selected_chain_seqres,
            "selected_chain_missing_residue_count": selected_chain_missing,
            "selected_chain_dbref_start": selected_chain.get("dbref_start") if selected_chain else None,
            "selected_chain_dbref_end": selected_chain.get("dbref_end") if selected_chain else None,
            "selected_chain_dbref_length": selected_chain.get("dbref_length") if selected_chain else None,
            **recommendation,
            "canonical_chain_reason": canonical_chain_reason,
            "n_res_reason": n_res_reason,
        },
        "safety": {
            "auto_register_allowed": False,
            "fake_pass_allowed": False,
            "threshold_relaxation_allowed": False,
            "rescue_manifest_promotion_allowed": False,
        },
    }


def _build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    native = payload["native_registry"]
    pdb = payload["native_pdb"]
    registry = payload["strict_release_registry"]
    lines = [
        "# Strict-Release Target Registration Packet",
        "",
        f"- target: `{summary['target']}`",
        f"- status: `{summary['status']}`",
        f"- registration_ready: `{summary['registration_ready']}`",
        f"- blockers: `{', '.join(summary['blockers']) or 'none'}`",
        f"- next_required_step: `{summary['next_required_step']}`",
        "",
        "## Native Reference",
        "",
        f"- row_found: `{native['row_found']}`",
        f"- pdb_id: `{native['pdb_id']}`",
        f"- native_pdb_path: `{native['native_pdb_path']}`",
        f"- native_pdb_ready: `{summary['native_pdb_ready']}`",
        f"- chain_count: `{pdb.get('chain_count')}`",
        f"- ca_count: `{pdb.get('ca_count')}`",
        f"- hetero_residue_count: `{pdb.get('hetero_residue_count')}`",
        "",
        "## Strict Registry",
        "",
        f"- research_constants_target: `{registry['research_constants_target'] or '<missing>'}`",
        f"- research_constants_n_res: `{registry['research_constants_n_res']}`",
        f"- profile_target: `{registry['profile_target'] or '<missing>'}`",
        f"- canonical_chain: `{registry['canonical_chain'] or '<missing>'}`",
        f"- recommended_canonical_chain: `{registry['recommended_canonical_chain'] or '<missing>'}`",
        f"- recommendation_reason: `{registry['canonical_chain_recommendation_reason']}`",
        f"- recommended_seqres_n_res: `{registry['recommended_seqres_n_res']}`",
        f"- recommended_observed_ca_count: `{registry['recommended_observed_ca_count']}`",
        f"- recommended_missing_residue_count: `{registry['recommended_missing_residue_count']}`",
        f"- canonical_chain_reason: `{registry['canonical_chain_reason'] or 'ready'}`",
        f"- n_res_reason: `{registry['n_res_reason'] or 'ready'}`",
        "",
        "## Chain Candidates",
        "",
    ]
    for row in pdb.get("chains", []):
        lines.append(
            f"- `{row['chain']}`: ca=`{row['ca_count']}`, seqres=`{row.get('seqres_count')}`, "
            f"missing=`{row.get('missing_residue_count')}`, residues=`{row['residue_count']}`, "
            f"hetero_residues=`{row.get('hetero_residue_count')}`, atoms=`{row['atom_count']}`"
        )
    lines.append("")
    return "\n".join(lines)


def run_build(args: argparse.Namespace) -> dict[str, Any]:
    payload = build_payload(args)
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(_build_markdown(payload), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a fail-closed strict-release target registration readiness packet."
    )
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--native-csv", default=DEFAULT_NATIVE_CSV)
    parser.add_argument("--profile-json", default=DEFAULT_PROFILE_JSON)
    parser.add_argument("--canonical-chain", default="")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_build(args)
    print(f"Wrote: {args.out_json}")
    print(f"Wrote: {args.out_md}")
    print(f"registration_ready={payload['summary']['registration_ready']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
