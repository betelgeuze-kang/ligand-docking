from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from tools.accounting import build_ligand_mapping_queue as canonical

_DEFAULT_BEAD0 = (-0.8, 0.0, 0.0)
_DEFAULT_BEAD1 = (0.8, 0.0, 0.0)
_EXPLICIT_POCKET_SOURCES = {"target_pocket_csv", "target_native_csv_pocket_xyz"}


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def _bool_env(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "") or "").strip().lower()
    if not raw:
        return bool(default)
    if raw in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "f", "no", "n", "off"}:
        return False
    return bool(default)


def _slug(value: Any) -> str:
    return canonical._slug(_text(value))  # type: ignore[attr-defined]


def _read_csv(path: str) -> pd.DataFrame:
    src = _text(path)
    if not src or not os.path.exists(src):
        return pd.DataFrame()
    return pd.read_csv(src)


def _path_exists(path: str) -> bool:
    src = _text(path)
    if not src:
        return False
    return os.path.exists(src)


def _with_report_suffix(path: str, suffix: str) -> str:
    p = Path(path)
    return str(p.with_name(f"{p.stem}{suffix}{p.suffix or '.json'}"))


def _load_explicit_bead_ligand_ids(ligand_csv: str) -> set[str]:
    df = _read_csv(ligand_csv)
    if df.empty or "bead_coords_json" not in df.columns:
        return set()
    out: set[str] = set()
    for row in df.to_dict(orient="records"):
        if not _text(row.get("bead_coords_json")):
            continue
        raw = _text(row.get("ligand_id") or row.get("id") or row.get("name"))
        if not raw:
            continue
        out.add(raw)
        out.add(_slug(raw))
    return out


def _load_native_rows(target_native_csv: str) -> dict[str, dict[str, Any]]:
    df = _read_csv(target_native_csv)
    if df.empty or "target" not in df.columns:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in df.to_dict(orient="records"):
        target = _text(row.get("target"))
        if target:
            out[target] = dict(row)
    return out


def _load_pocket_targets(target_pocket_csv: str) -> set[str]:
    df = _read_csv(target_pocket_csv)
    if df.empty or "target" not in df.columns:
        return set()
    return {_text(row.get("target")) for row in df.to_dict(orient="records") if _text(row.get("target"))}


def _native_source_for_target(target: str, native_rows: dict[str, dict[str, Any]]) -> str:
    row = native_rows.get(target, {})
    native_path = _text(row.get("native_pdb_path"))
    if native_path and _path_exists(native_path):
        return "target_native_csv"
    lower = f"data/native/{target.lower()}.pdb"
    if _path_exists(lower):
        return "data_native_lowercase"
    slug_path = f"data/native/{canonical._safe_slug_path_target(target)}.pdb"  # type: ignore[attr-defined]
    if _path_exists(slug_path):
        return "data_native_slug"
    return "missing"


def _pocket_source_for_target(target: str, native_rows: dict[str, dict[str, Any]], pocket_targets: set[str]) -> str:
    if target in pocket_targets:
        return "target_pocket_csv"
    row = native_rows.get(target, {})
    if all(_text(row.get(col)) for col in ("pocket_x", "pocket_y", "pocket_z")):
        return "target_native_csv_pocket_xyz"
    if _native_source_for_target(target, native_rows) != "missing":
        return "inferred_geometric_or_centroid_from_native"
    return "zero_fallback"


def _near(a: Any, b: float) -> bool:
    try:
        return abs(float(a) - float(b)) <= 1e-6
    except Exception:
        return False


def _row_uses_default_beads(row: dict[str, Any]) -> bool:
    return all(
        [
            _near(row.get("ligand_bead0_x"), _DEFAULT_BEAD0[0]),
            _near(row.get("ligand_bead0_y"), _DEFAULT_BEAD0[1]),
            _near(row.get("ligand_bead0_z"), _DEFAULT_BEAD0[2]),
            _near(row.get("ligand_bead1_x"), _DEFAULT_BEAD1[0]),
            _near(row.get("ligand_bead1_y"), _DEFAULT_BEAD1[1]),
            _near(row.get("ligand_bead1_z"), _DEFAULT_BEAD1[2]),
        ]
    )


def _ligand_rows_by_id(ligand_json: str) -> dict[str, dict[str, Any]]:
    src = _text(ligand_json)
    if not src or not os.path.exists(src):
        return {}
    try:
        payload = json.loads(Path(src).read_text(encoding="utf-8"))
    except Exception:
        return {}
    rows = payload.get("rows") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ligand_id = _text(row.get("ligand_id"))
        if ligand_id:
            out[ligand_id] = dict(row)
    return out


def _ligand_geometry_source(
    *,
    row: dict[str, Any],
    ligand_row: dict[str, Any],
    explicit_bead_ids: set[str],
    csv_relax_3d: bool,
) -> tuple[str, bool, str]:
    ligand_id = _text(row.get("ligand_id"))
    ligand_source = _text(row.get("ligand_source") or ligand_row.get("source"))
    default_beads = _row_uses_default_beads(row)
    if ligand_id in explicit_bead_ids:
        return "explicit_bead_coords_json", False, "explicit_bead_coordinates"
    if ligand_source == "sdf":
        if default_beads:
            return "sdf_default_bead_fallback", True, "fallback_default_2bead"
        return "sdf_conformer_2bead_kmeans", False, "sdf_conformer_kmeans"
    if default_beads:
        reason = "rdkit_unavailable_or_embed_failed" if bool(csv_relax_3d) else "csv_relax_3d_disabled"
        return "fallback_default_2bead", True, reason
    if bool(csv_relax_3d):
        return "rdkit_etkdg_mmff_uff_2bead", False, "rdkit_relaxed_conformer_kmeans"
    return "csv_non_default_beads", False, "csv_non_default_geometry"


def build_input_provenance_report(args: argparse.Namespace, summary: dict[str, Any]) -> dict[str, Any]:
    queue_path = _text(args.out_queue_csv)
    ligand_json = _text(args.out_ligand_json)
    strict = bool(getattr(args, "production_strict_inputs", False))
    queue = pd.read_csv(queue_path) if queue_path and os.path.exists(queue_path) else pd.DataFrame()
    native_rows = _load_native_rows(str(args.target_native_csv))
    pocket_targets = _load_pocket_targets(str(args.target_pocket_csv))
    explicit_bead_ids = _load_explicit_bead_ligand_ids(str(args.ligand_csv))
    ligands_by_id = _ligand_rows_by_id(ligand_json)
    report_rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    annotated_rows: list[dict[str, Any]] = []
    for raw_row in queue.to_dict(orient="records"):
        row = dict(raw_row)
        target = _text(row.get("target"))
        ligand_id = _text(row.get("ligand_id"))
        ligand_row = ligands_by_id.get(ligand_id, {})
        geometry_source, fallback_beads_used, conformer_status = _ligand_geometry_source(
            row=row,
            ligand_row=ligand_row,
            explicit_bead_ids=explicit_bead_ids,
            csv_relax_3d=bool(args.csv_relax_3d),
        )
        native_source = _native_source_for_target(target, native_rows)
        pocket_source = _pocket_source_for_target(target, native_rows, pocket_targets)
        row_blockers: list[str] = []
        if fallback_beads_used:
            row_blockers.append("fallback_ligand_geometry")
        if native_source == "missing":
            row_blockers.append("native_structure_missing")
        if pocket_source not in _EXPLICIT_POCKET_SOURCES:
            row_blockers.append("pocket_source_not_explicit")
        if geometry_source.startswith("fallback") and bool(args.csv_relax_3d) and canonical.Chem is None:  # type: ignore[attr-defined]
            row_blockers.append("rdkit_unavailable_for_strict_ligand_geometry")
        if not _text(row.get("ligand_smiles")):
            row_blockers.append("ligand_smiles_missing")
        risk = "high" if row_blockers else ("medium" if pocket_source.startswith("inferred") else "low")
        row.update(
            {
                "production_strict_inputs": bool(strict),
                "ligand_geometry_source": geometry_source,
                "ligand_conformer_status": conformer_status,
                "fallback_beads_used": bool(fallback_beads_used),
                "pocket_source": pocket_source,
                "native_structure_source": native_source,
                "science_input_risk_level": risk,
                "science_input_blockers_json": json.dumps(row_blockers, ensure_ascii=False, sort_keys=True),
            }
        )
        annotated_rows.append(row)
        report_row = {
            "queue_id": _text(row.get("queue_id")),
            "target": target,
            "ligand_id": ligand_id,
            "ligand_geometry_source": geometry_source,
            "ligand_conformer_status": conformer_status,
            "fallback_beads_used": bool(fallback_beads_used),
            "pocket_source": pocket_source,
            "native_structure_source": native_source,
            "science_input_risk_level": risk,
            "blockers": row_blockers,
        }
        report_rows.append(report_row)
        if row_blockers:
            blockers.append(report_row)

    if annotated_rows:
        pd.DataFrame(annotated_rows).to_csv(queue_path, index=False)

    unique_blockers = sorted({code for row in blockers for code in row.get("blockers", [])})
    report = {
        "summary": {
            "status": "pass" if (not strict or not blockers) else "blocked_strict_input_contract",
            "pass": bool((not strict) or (not blockers)),
            "production_strict_inputs": bool(strict),
            "queue_csv": queue_path,
            "ligand_json": ligand_json,
            "row_count": int(len(report_rows)),
            "blocked_row_count": int(len(blockers)),
            "fallback_bead_row_count": int(sum(1 for row in report_rows if row["fallback_beads_used"])),
            "explicit_pocket_row_count": int(sum(1 for row in report_rows if row["pocket_source"] in _EXPLICIT_POCKET_SOURCES)),
            "missing_native_row_count": int(sum(1 for row in report_rows if row["native_structure_source"] == "missing")),
            "unique_blockers": unique_blockers,
        },
        "rows": report_rows,
    }
    report_path = _with_report_suffix(str(args.out_summary_json), "_input_provenance")
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    summary_path = Path(str(args.out_summary_json))
    if summary_path.exists():
        try:
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            summary_payload = dict(summary)
    else:
        summary_payload = dict(summary)
    artifacts = summary_payload.get("artifacts") if isinstance(summary_payload.get("artifacts"), dict) else {}
    artifacts["production_input_provenance_json"] = report_path
    summary_payload["artifacts"] = artifacts
    summary_payload["production_input_provenance"] = report["summary"]
    summary_path.write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = canonical.build_parser()
    parser.add_argument(
        "--production-strict-inputs",
        action=argparse.BooleanOptionalAction,
        default=_bool_env("BETELGEUZE_PRODUCT_STRICT_INPUTS", False),
        help=(
            "Fail closed after queue materialization when ligand geometry, native structure, "
            "or pocket provenance falls back to non-production sources."
        ),
    )
    return parser


def run(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = build_parser().parse_args(argv)
    summary = canonical.build_queue(args)
    report = build_input_provenance_report(args, summary)
    if bool(getattr(args, "production_strict_inputs", False)) and not bool(report["summary"].get("pass", False)):
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        raise SystemExit(
            "production_strict_inputs_failed: "
            + ",".join(str(x) for x in report["summary"].get("unique_blockers", []))
        )
    return summary


def main(argv: Sequence[str] | None = None) -> None:
    payload = run(argv)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
