#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

import pandas as pd

from tools import audit_ligand_leakage

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CANDIDATES_CSV = "config/gpcr_non_adrb2_positive_candidates_v1.csv"
DEFAULT_BASE_SPLITS_CSV = "config/ligand_eval_splits_blind_gpcr_adrb2_chembl50_v1.csv"
DEFAULT_BASE_REFERENCE_CSV = "config/ligand_binding_reference_blind_gpcr_adrb2_chembl50_v1.csv"
DEFAULT_OUT_JSON = "runs/gpcr_non_adrb2_positive_candidates_leakage_audit_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_non_adrb2_positive_candidates_leakage_audit_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_non_adrb2_positive_candidates_leakage_audit_current.md"

REQUIRED_CANDIDATE_COLUMNS = {
    "target",
    "ligand_id",
    "target_family",
    "is_binder",
    "reference_binding_kcal_mol",
    "smiles",
    "scaffold",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "t", "yes", "y", "pass", "curated"}


def _as_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _parse_roles(spec: str | Sequence[str]) -> list[str]:
    if isinstance(spec, str):
        return [tok.strip() for tok in spec.split(",") if tok.strip()]
    return [str(tok).strip() for tok in spec if str(tok).strip()]


def _infer_family(target: Any, explicit: Any = "") -> str:
    family = _text(explicit).lower()
    if family and family != "nan":
        return family
    target_text = _text(target).upper()
    if "GPCR" in target_text or "ADRB" in target_text or target_text in {"DRD2", "HTR2A", "OPRM1"}:
        return "gpcr"
    if "KINASE" in target_text or target_text in {"EGFR", "LRRK2", "STK17B"}:
        return "kinase"
    if "PROTEASE" in target_text or "Mpro" in target_text:
        return "protease"
    return ""


def _empty_audit_payload(
    *,
    reason: str,
    candidates_csv: Path,
    base_splits_csv: Path,
    base_reference_csv: Path,
    fit_roles: list[str],
    candidate_eval_role: str,
) -> dict[str, Any]:
    return {
        "generated_at_local": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "pass": False,
        "split_csv": "",
        "fit_roles": fit_roles,
        "eval_roles": [candidate_eval_role],
        "fit_rows": 0,
        "eval_rows": 0,
        "fit_unique_keys": 0,
        "eval_unique_keys": 0,
        "key_overlap_count": 0,
        "target_overlap_count": 0,
        "ligand_overlap_count": 0,
        "family_overlap_count": 0,
        "family_overlap_ratio": None,
        "max_sequence_identity": None,
        "sequence_leak_count": 0,
        "max_pocket_jaccard": None,
        "pocket_leak_count": 0,
        "scaffold_overlap_count": 0,
        "scaffold_overlap_ratio": None,
        "failed_rules": [{"metric": reason, "value": 1, "threshold": 0}],
        "overlap_examples": {
            "keys": [],
            "targets": [],
            "ligands": [],
            "families": [],
            "scaffolds": [],
            "sequence_pairs": [],
            "pocket_pairs": [],
        },
        "artifacts": {},
        "source_artifacts": {
            "candidates_csv": str(candidates_csv),
            "base_splits_csv": str(base_splits_csv),
            "base_reference_csv": str(base_reference_csv),
        },
    }


def _candidate_blockers(candidates: pd.DataFrame) -> list[str]:
    blockers: list[str] = []
    missing = sorted(REQUIRED_CANDIDATE_COLUMNS - set(candidates.columns))
    if missing:
        return [f"candidate_csv_missing_columns:{','.join(missing)}"]
    if candidates.empty:
        return ["candidate_csv_empty"]

    for idx, row in candidates.iterrows():
        prefix = f"candidate_row_{idx}"
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        if not target:
            blockers.append(f"{prefix}_missing_target")
        if not ligand_id:
            blockers.append(f"{prefix}_missing_ligand_id")
        if "ADRB2" in target.upper():
            blockers.append(f"{prefix}_adrb2_target_not_allowed")
        if _infer_family(target, row.get("target_family")) != "gpcr":
            blockers.append(f"{prefix}_not_gpcr_target")
        if not _as_bool(row.get("is_binder")):
            blockers.append(f"{prefix}_not_positive_binder")
        if _as_float(row.get("reference_binding_kcal_mol")) is None:
            blockers.append(f"{prefix}_missing_reference_binding_kcal_mol")
    return blockers


def _build_audit_inputs(
    *,
    candidates: pd.DataFrame,
    base_splits: pd.DataFrame,
    base_reference: pd.DataFrame,
    out_dir: Path,
    fit_roles: list[str],
    candidate_eval_role: str,
) -> tuple[Path, Path, Path]:
    required_split_cols = {"target", "ligand_id", "role"}
    missing_split = sorted(required_split_cols - set(base_splits.columns))
    if missing_split:
        raise ValueError(f"base splits csv missing columns: {missing_split}")
    if "target" not in base_reference.columns or "ligand_id" not in base_reference.columns:
        raise ValueError("base reference csv missing columns: ['target', 'ligand_id']")

    fit_rows = base_splits[base_splits["role"].astype(str).isin(fit_roles)][["target", "ligand_id", "role"]].copy()
    eval_rows = candidates[["target", "ligand_id"]].copy()
    eval_rows["role"] = candidate_eval_role
    split = pd.concat([fit_rows, eval_rows], ignore_index=True)

    base_meta = base_reference.copy()
    for col in ("smiles", "scaffold", "target_family"):
        if col not in base_meta.columns:
            base_meta[col] = ""
    candidate_meta = candidates.copy()
    for col in ("smiles", "scaffold", "target_family"):
        if col not in candidate_meta.columns:
            candidate_meta[col] = ""
    meta = pd.concat(
        [
            base_meta[["target", "ligand_id", "smiles", "scaffold", "target_family"]],
            candidate_meta[["target", "ligand_id", "smiles", "scaffold", "target_family"]],
        ],
        ignore_index=True,
    )
    meta["target_family"] = [_infer_family(row["target"], row["target_family"]) for _, row in meta.iterrows()]

    target_meta = meta[["target", "target_family"]].drop_duplicates().copy()
    ligand_meta = meta[["ligand_id", "smiles", "scaffold"]].drop_duplicates().copy()

    out_dir.mkdir(parents=True, exist_ok=True)
    split_csv = out_dir / "gpcr_non_adrb2_positive_candidates_leakage_audit_input_split.csv"
    target_meta_csv = out_dir / "gpcr_non_adrb2_positive_candidates_leakage_audit_input_target_meta.csv"
    ligand_meta_csv = out_dir / "gpcr_non_adrb2_positive_candidates_leakage_audit_input_ligand_meta.csv"
    split.to_csv(split_csv, index=False)
    target_meta.to_csv(target_meta_csv, index=False)
    ligand_meta.to_csv(ligand_meta_csv, index=False)
    return split_csv, target_meta_csv, ligand_meta_csv


def _blockers_from_audit(audit_payload: dict[str, Any]) -> list[str]:
    blockers = []
    if audit_payload.get("pass") is not True:
        blockers.append("audit_ligand_leakage_not_pass")
    for metric in (
        "key_overlap_count",
        "target_overlap_count",
        "ligand_overlap_count",
        "family_overlap_count",
        "scaffold_overlap_count",
        "sequence_leak_count",
        "pocket_leak_count",
    ):
        if int(audit_payload.get(metric) or 0) > 0:
            blockers.append(metric)
    return sorted(set(blockers))


def _finalize_payload(
    payload: dict[str, Any],
    *,
    blockers: list[str],
    candidate_rows: int,
    candidates_csv: Path,
    base_splits_csv: Path,
    base_reference_csv: Path,
    out_json: Path,
    out_csv: Path,
    out_md: Path,
) -> dict[str, Any]:
    blockers = sorted(set(blockers))
    payload["pass"] = not blockers
    payload.setdefault("failed_rules", [])
    for blocker in blockers:
        if not any(rule.get("metric") == blocker for rule in payload["failed_rules"]):
            payload["failed_rules"].append({"metric": blocker, "value": 1, "threshold": 0})
    payload["summary"] = {
        "status": "pass" if payload["pass"] else "blocked",
        "candidate_rows": int(candidate_rows),
        "blocker_count": int(len(blockers)),
        "blockers": blockers,
        "claim_promotion_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
    }
    payload["claim_boundary"] = {
        "claim_promotion_allowed": False,
        "router_claim_allowed": False,
        "platform_claim_allowed": False,
        "fake_pass_allowed": False,
    }
    payload["source_artifacts"] = {
        "candidates_csv": str(candidates_csv),
        "base_splits_csv": str(base_splits_csv),
        "base_reference_csv": str(base_reference_csv),
    }
    payload["artifacts"] = {
        **dict(payload.get("artifacts") or {}),
        "out_json": str(out_json),
        "out_csv": str(out_csv),
        "out_md": str(out_md),
    }
    return payload


def _write_outputs(out_json: Path, out_csv: Path, out_md: Path, payload: dict[str, Any]) -> None:
    _write_json(out_json, payload)
    pd.DataFrame(
        [
            {
                "pass": payload["pass"],
                "status": payload["summary"]["status"],
                "candidate_rows": payload["summary"]["candidate_rows"],
                "blocker_count": payload["summary"]["blocker_count"],
                "blockers": ";".join(payload["summary"]["blockers"]),
                "target_overlap_count": payload.get("target_overlap_count", 0),
                "ligand_overlap_count": payload.get("ligand_overlap_count", 0),
                "family_overlap_count": payload.get("family_overlap_count", 0),
                "scaffold_overlap_count": payload.get("scaffold_overlap_count", 0),
                "claim_promotion_allowed": False,
            }
        ]
    ).to_csv(out_csv, index=False)
    lines = [
        "# GPCR Non-ADRB2 Candidate Leakage Audit",
        "",
        f"- status: `{payload['summary']['status']}`",
        f"- pass: `{str(payload['pass']).lower()}`",
        "- claim_promotion_allowed: `false`",
        f"- candidate_rows: `{payload['summary']['candidate_rows']}`",
        f"- blockers: `{', '.join(payload['summary']['blockers'])}`",
        f"- target_overlap_count: `{payload.get('target_overlap_count', 0)}`",
        f"- ligand_overlap_count: `{payload.get('ligand_overlap_count', 0)}`",
        f"- family_overlap_count: `{payload.get('family_overlap_count', 0)}`",
        f"- scaffold_overlap_count: `{payload.get('scaffold_overlap_count', 0)}`",
        "",
    ]
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")


def build_audit(
    *,
    candidates_csv: str | Path = DEFAULT_CANDIDATES_CSV,
    base_splits_csv: str | Path = DEFAULT_BASE_SPLITS_CSV,
    base_reference_csv: str | Path = DEFAULT_BASE_REFERENCE_CSV,
    out_json: str | Path = DEFAULT_OUT_JSON,
    out_csv: str | Path = DEFAULT_OUT_CSV,
    out_md: str | Path = DEFAULT_OUT_MD,
    fit_roles: str | Sequence[str] = "fit",
    candidate_eval_role: str = "candidate_eval",
) -> dict[str, Any]:
    candidates_path = _resolve(candidates_csv)
    splits_path = _resolve(base_splits_csv)
    reference_path = _resolve(base_reference_csv)
    out_json_path = _resolve(out_json)
    out_csv_path = _resolve(out_csv)
    out_md_path = _resolve(out_md)

    for path, label in (
        (candidates_path, "candidates csv"),
        (splits_path, "base splits csv"),
        (reference_path, "base reference csv"),
    ):
        if not path.exists():
            raise FileNotFoundError(f"{label} not found: {path}")

    fit_role_list = _parse_roles(fit_roles)
    if not fit_role_list:
        raise ValueError("fit roles are empty")
    candidate_eval_role = _text(candidate_eval_role)
    if not candidate_eval_role:
        raise ValueError("candidate eval role is empty")

    candidates = pd.read_csv(candidates_path)
    base_splits = pd.read_csv(splits_path)
    base_reference = pd.read_csv(reference_path)
    candidate_blockers = _candidate_blockers(candidates)

    if candidate_blockers:
        payload = _empty_audit_payload(
            reason=candidate_blockers[0],
            candidates_csv=candidates_path,
            base_splits_csv=splits_path,
            base_reference_csv=reference_path,
            fit_roles=fit_role_list,
            candidate_eval_role=candidate_eval_role,
        )
        payload = _finalize_payload(
            payload,
            blockers=candidate_blockers,
            candidate_rows=len(candidates),
            candidates_csv=candidates_path,
            base_splits_csv=splits_path,
            base_reference_csv=reference_path,
            out_json=out_json_path,
            out_csv=out_csv_path,
            out_md=out_md_path,
        )
        _write_outputs(out_json_path, out_csv_path, out_md_path, payload)
        return payload

    input_dir = out_json_path.parent
    split_csv, target_meta_csv, ligand_meta_csv = _build_audit_inputs(
        candidates=candidates,
        base_splits=base_splits,
        base_reference=base_reference,
        out_dir=input_dir,
        fit_roles=fit_role_list,
        candidate_eval_role=candidate_eval_role,
    )
    audit_args = SimpleNamespace(
        split_csv=str(split_csv),
        split_target_col="target",
        split_ligand_col="ligand_id",
        split_role_col="role",
        fit_roles=",".join(fit_role_list),
        eval_roles=candidate_eval_role,
        target_meta_csv=str(target_meta_csv),
        target_meta_target_col="target",
        target_family_col="target_family",
        target_sequence_col="sequence",
        target_pocket_fp_col="pocket_fingerprint",
        ligand_meta_csv=str(ligand_meta_csv),
        ligand_meta_ligand_col="ligand_id",
        ligand_smiles_col="smiles",
        ligand_scaffold_col="scaffold",
        max_key_overlap=0,
        max_target_overlap=0,
        max_family_overlap_ratio=0.0,
        max_scaffold_overlap_ratio=0.0,
        max_allowed_seq_identity=0.30,
        max_allowed_pocket_jaccard=0.40,
        max_examples=10,
        out_json=str(out_json_path),
        out_csv=str(out_csv_path),
        out_md=str(out_md_path),
    )
    payload = audit_ligand_leakage.run_audit(audit_args)
    blockers = _blockers_from_audit(payload)
    payload = _finalize_payload(
        payload,
        blockers=blockers,
        candidate_rows=len(candidates),
        candidates_csv=candidates_path,
        base_splits_csv=splits_path,
        base_reference_csv=reference_path,
        out_json=out_json_path,
        out_csv=out_csv_path,
        out_md=out_md_path,
    )
    _write_outputs(out_json_path, out_csv_path, out_md_path, payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build GPCR non-ADRB2 candidate leakage audit artifacts.")
    parser.add_argument("--candidates-csv", default=DEFAULT_CANDIDATES_CSV)
    parser.add_argument("--base-splits-csv", default=DEFAULT_BASE_SPLITS_CSV)
    parser.add_argument("--base-reference-csv", default=DEFAULT_BASE_REFERENCE_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--fit-roles", default="fit")
    parser.add_argument("--candidate-eval-role", default="candidate_eval")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_audit(
        candidates_csv=args.candidates_csv,
        base_splits_csv=args.base_splits_csv,
        base_reference_csv=args.base_reference_csv,
        out_json=args.out_json,
        out_csv=args.out_csv,
        out_md=args.out_md,
        fit_roles=args.fit_roles,
        candidate_eval_role=args.candidate_eval_role,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if payload.get("pass") is not True:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
