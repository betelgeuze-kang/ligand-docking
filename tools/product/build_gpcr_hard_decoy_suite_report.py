#!/usr/bin/env python3
"""Materialize the GPCR hard-decoy suite report (read-only).

Broad GPCR/router generalization is the repo's main remaining ranking blocker.
The diagnostics for DRD2 / HTR2A / OPRM1 are real but scattered across many
``runs/`` artifacts. This builder collapses operator/diagnostic *aggregate rows*
(one row per target) into a single auditable fail-closed claim gate by running
them through the existing dependency-free evaluator
(``betelgeuze_product.gpcr_hard_decoy_suite``) and writing
``runs/gpcr_hard_decoy_suite_current.{json,md,csv}``.

Governance:
- This is a **read-only materializer**: it runs no scoring, generates no decoys,
  relaxes no thresholds, and emits no broad-GPCR claim. It evaluates the rows it
  is given and reports the gate decision (see
  ``docs/gpcr_hard_decoy_suite_contract.md``).
- ``execution_enabled=false`` / ``external_state_mutated=false`` /
  ``docking_results_emitted=false`` are preserved in the summary.
- Fail-closed: a missing/empty/schema-invalid input CSV or a malformed row
  yields a ``blocked`` artifact (no fabricated family-ready) and a non-zero exit.
- A correctly-evaluated ``broad_family_locked`` result is a SUCCESS of the
  materializer (exit 0): the gate honestly reporting "locked" is the point.

Dependency-free (stdlib + ``betelgeuze_product.gpcr_hard_decoy_suite``).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.gpcr_hard_decoy_suite import (
    CLAIM_BOUNDARY,
    GpcrHardDecoyError,
    build_gpcr_hard_decoy_suite,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_CSV = "config/gpcr_hard_decoy_suite_current.csv"
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_suite_current.json"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_suite_current.md"
DEFAULT_OUT_CSV = "runs/gpcr_hard_decoy_suite_current.csv"

PACKET_TYPE = "gpcr_hard_decoy_suite_report"
REPORT_SCHEMA_VERSION = "gpcr_hard_decoy_suite_report_v1"

# Minimal required input columns; the rest are optional metric/decoy columns
# consumed by the evaluator.
REQUIRED_INPUT_COLUMNS = ("target_id", "positive_count")
OPTIONAL_NUMERIC_COLUMNS = (
    "ranking_pr_auc",
    "ranking_pr_auc_ci_low",
    "top20_hit_rate",
    "decoys_above_positive_count",
    "positive_target_rank",
    "positive_anchor_distance_a",
    "top_decoy_anchor_distance_a",
    "retained_target_row_count",
    "retained_positive_count",
    "top_decoy_retained_count",
)
DECOY_CLASS_COUNTS_COLUMN = "decoy_class_counts"

STATUS_MATERIALIZED = "materialized"
STATUS_BLOCKED_MISSING = "blocked_missing_input_csv"
STATUS_BLOCKED_EMPTY = "blocked_empty_input_csv"
STATUS_BLOCKED_SCHEMA = "blocked_input_schema_missing_required_columns"
STATUS_BLOCKED_INVALID_ROW = "blocked_invalid_input_row"

_READ_ONLY_FLAGS = {
    "execution_enabled": False,
    "external_state_mutated": False,
    "docking_results_emitted": False,
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _parse_decoy_class_counts(raw: Any) -> Any:
    """Parse the decoy_class_counts JSON-string cell into a dict.

    Empty/blank -> {} (evaluator yields all-zero counts). Invalid JSON or a
    non-object is surfaced as GpcrHardDecoyError so it lands fail-closed.
    """

    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GpcrHardDecoyError(f"invalid decoy_class_counts json: {text!r}") from exc
    if not isinstance(parsed, dict):
        raise GpcrHardDecoyError(f"decoy_class_counts must be a JSON object, got: {text!r}")
    return parsed


def _row_to_target(row: dict[str, Any]) -> dict[str, Any]:
    target: dict[str, Any] = {
        "target_id": str(row.get("target_id") or "").strip(),
        "positive_count": row.get("positive_count"),
    }
    for column in OPTIONAL_NUMERIC_COLUMNS:
        if column in row:
            target[column] = row[column]
    if DECOY_CLASS_COUNTS_COLUMN in row:
        target[DECOY_CLASS_COUNTS_COLUMN] = _parse_decoy_class_counts(row.get(DECOY_CLASS_COUNTS_COLUMN))
    return target


def _blocked_artifact(status: str, input_csv: Path, detail: str) -> dict[str, Any]:
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": REPORT_SCHEMA_VERSION,
        "materializer_status": status,
        "input_csv": str(input_csv),
        "detail": detail,
        "summary": {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": "broad_family_locked",
            "family_claim_safe": False,
            "target_count": 0,
            **_READ_ONLY_FLAGS,
        },
        "targets": [],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_gpcr_hard_decoy_suite_report_artifact(
    input_csv: str | Path,
    *,
    required_target_ids: list[str] | None = None,
    claim_lock_reason: str = "",
) -> dict[str, Any]:
    """Build the report artifact dict from an aggregate per-target input CSV.

    Fail-closed on missing/empty/schema-invalid CSV or a malformed row.
    """

    path = _resolve(input_csv)
    if not path.exists():
        return _blocked_artifact(STATUS_BLOCKED_MISSING, path, "input CSV does not exist")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]

    if not rows:
        return _blocked_artifact(STATUS_BLOCKED_EMPTY, path, "input CSV has no target rows")
    missing_columns = [col for col in REQUIRED_INPUT_COLUMNS if col not in fieldnames]
    if missing_columns:
        return _blocked_artifact(
            STATUS_BLOCKED_SCHEMA,
            path,
            f"input CSV missing required columns: {missing_columns}",
        )

    try:
        targets = [_row_to_target(row) for row in rows]
        suite = build_gpcr_hard_decoy_suite(targets, required_target_ids=required_target_ids)
    except GpcrHardDecoyError as exc:
        return _blocked_artifact(STATUS_BLOCKED_INVALID_ROW, path, str(exc))

    summary = {**suite["summary"], **_READ_ONLY_FLAGS}
    claim_lock_text = str(claim_lock_reason or "").strip()
    if claim_lock_text:
        summary.update(
            {
                "claim_locked": True,
                "claim_lock_reason": claim_lock_text,
                "diagnostic_status_before_claim_lock": summary.get("status"),
                "diagnostic_family_claim_safe_before_claim_lock": bool(summary.get("family_claim_safe")),
                "status": "claim_locked_gpcr_hard_decoy_diagnostic_probe",
                "family_claim_safe": False,
            }
        )
    else:
        summary["claim_locked"] = False
    return {
        "packet_type": PACKET_TYPE,
        "schema_version": REPORT_SCHEMA_VERSION,
        "materializer_status": STATUS_MATERIALIZED,
        "input_csv": str(path),
        "detail": "",
        "summary": summary,
        "targets": suite["targets"],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _render_markdown(artifact: dict[str, Any]) -> str:
    summary = artifact["summary"]
    lines = [
        "# GPCR Hard-Decoy Suite Report (current)",
        "",
        "Fail-closed broad-GPCR (DRD2 / HTR2A / OPRM1) claim gate, materialized by",
        "`tools/product/build_gpcr_hard_decoy_suite_report.py` from operator/diagnostic",
        "aggregate rows. **Read-only: no scoring, no decoy generation, no threshold",
        "relaxation, no broad-GPCR claim.** See `docs/gpcr_hard_decoy_suite_contract.md`.",
        "",
        f"- materializer_status: `{artifact['materializer_status']}`",
        f"- input_csv: `{artifact['input_csv']}`",
        f"- execution_enabled: `{str(summary.get('execution_enabled')).lower()}`",
        f"- external_state_mutated: `{str(summary.get('external_state_mutated')).lower()}`",
    ]
    if artifact["materializer_status"] != STATUS_MATERIALIZED:
        lines.extend(["", f"> **Blocked (fail-closed):** {artifact['detail']}", ""])
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            f"- status: `{summary.get('status')}`",
            f"- family_claim_safe: `{str(summary.get('family_claim_safe')).lower()}`",
            f"- claim_locked: `{str(summary.get('claim_locked')).lower()}`",
            f"- required_target_ids: `{', '.join(summary.get('required_target_ids', []))}`",
            f"- green_target_ids: `{', '.join(summary.get('green_target_ids', [])) or '(none)'}`",
            f"- blocked_target_ids: `{', '.join(summary.get('blocked_target_ids', [])) or '(none)'}`",
            f"- missing_required_target_ids: `{', '.join(summary.get('missing_required_target_ids', [])) or '(none)'}`",
            f"- first_blocked_required_target: `{summary.get('first_blocked_required_target') or '(none)'}`",
        ]
    )
    if summary.get("claim_locked"):
        lines.extend(
            [
                f"- diagnostic_status_before_claim_lock: `{summary.get('diagnostic_status_before_claim_lock')}`",
                "- diagnostic_family_claim_safe_before_claim_lock: "
                f"`{str(summary.get('diagnostic_family_claim_safe_before_claim_lock')).lower()}`",
                f"- claim_lock_reason: `{summary.get('claim_lock_reason')}`",
                "",
            ]
        )
    lines.extend(
        [
            "",
            "## Targets",
            "",
            "| target | gate | CI-low | top20 | decoys_above | anchor_margin | retained_decoys | blockers | root_cause_tags |",
            "| --- | --- | --: | --: | --: | --: | --: | --- | --- |",
        ]
    )
    for target in artifact["targets"]:
        def _fmt(value: Any) -> str:
            return "" if value is None else (f"{value:.4f}" if isinstance(value, float) else str(value))

        lines.append(
            "| `{tid}` | `{gate}` | {ci} | {top20} | {decoys} | {margin} | {retained_decoys} | {blockers} | {roots} |".format(
                tid=target["target_id"],
                gate=target["gate_status"],
                ci=_fmt(target["ranking_pr_auc_ci_low"]),
                top20=_fmt(target["top20_hit_rate"]),
                decoys=_fmt(target["decoys_above_positive_count"]),
                margin=_fmt(target.get("anchor_margin_a")),
                retained_decoys=_fmt(target.get("top_decoy_retained_count")),
                blockers=", ".join(target["blockers"]) or "(none)",
                roots=", ".join(target["root_cause_tags"]) or "(none)",
            )
        )
    lines.append("")
    return "\n".join(lines)


_CSV_COLUMNS = [
    "target_id",
    "gate_status",
    "claim_safe",
    "ranking_pr_auc",
    "ranking_pr_auc_ci_low",
    "top20_hit_rate",
    "decoys_above_positive_count",
    "positive_anchor_distance_a",
    "top_decoy_anchor_distance_a",
    "anchor_margin_a",
    "retained_target_row_count",
    "retained_positive_count",
    "top_decoy_retained_count",
    "blockers",
    "root_cause_tags",
    "decoy_class_counts",
]


def _write_csv(out_csv: Path, targets: list[dict[str, Any]]) -> None:
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for target in targets:
            writer.writerow(
                {
                    "target_id": target["target_id"],
                    "gate_status": target["gate_status"],
                    "claim_safe": str(target["claim_safe"]).lower(),
                    "ranking_pr_auc": "" if target["ranking_pr_auc"] is None else target["ranking_pr_auc"],
                    "ranking_pr_auc_ci_low": (
                        "" if target["ranking_pr_auc_ci_low"] is None else target["ranking_pr_auc_ci_low"]
                    ),
                    "top20_hit_rate": "" if target["top20_hit_rate"] is None else target["top20_hit_rate"],
                    "decoys_above_positive_count": (
                        ""
                        if target["decoys_above_positive_count"] is None
                        else target["decoys_above_positive_count"]
                    ),
                    "positive_anchor_distance_a": (
                        "" if target["positive_anchor_distance_a"] is None else target["positive_anchor_distance_a"]
                    ),
                    "top_decoy_anchor_distance_a": (
                        "" if target["top_decoy_anchor_distance_a"] is None else target["top_decoy_anchor_distance_a"]
                    ),
                    "anchor_margin_a": "" if target.get("anchor_margin_a") is None else target["anchor_margin_a"],
                    "retained_target_row_count": target.get("retained_target_row_count", ""),
                    "retained_positive_count": target.get("retained_positive_count", ""),
                    "top_decoy_retained_count": (
                        "" if target.get("top_decoy_retained_count") is None else target["top_decoy_retained_count"]
                    ),
                    "blockers": ";".join(target["blockers"]),
                    "root_cause_tags": ";".join(target["root_cause_tags"]),
                    "decoy_class_counts": json.dumps(target["decoy_class_counts"], sort_keys=True),
                }
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize the GPCR hard-decoy suite report (read-only).")
    parser.add_argument("--input-csv", default=DEFAULT_INPUT_CSV)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument(
        "--required-target-ids",
        default="",
        help="Comma-separated required target ids (default: DRD2,HTR2A,OPRM1).",
    )
    parser.add_argument(
        "--claim-lock-reason",
        default="",
        help="Optional reason to keep a diagnostic-green report out of product claim promotion.",
    )
    args = parser.parse_args(argv)

    required = [tid.strip() for tid in args.required_target_ids.split(",") if tid.strip()] or None
    artifact = build_gpcr_hard_decoy_suite_report_artifact(
        args.input_csv,
        required_target_ids=required,
        claim_lock_reason=args.claim_lock_reason,
    )

    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    for out in (out_json, out_md, out_csv):
        out.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    out_md.write_text(_render_markdown(artifact), encoding="utf-8")
    _write_csv(out_csv, artifact["targets"])

    return 0 if artifact["materializer_status"] == STATUS_MATERIALIZED else 1


if __name__ == "__main__":
    raise SystemExit(main())
