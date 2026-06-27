#!/usr/bin/env python3
"""Emit the H-Bond BackMap (ONSPS-4) candidate report surface as JSON + MD + CSV.

Read-only accounting builder. It does NOT run any scoring or simulation; it
reads an existing backmapping-scoring scores CSV (produced by
``tools/run_ligand_backmapping_scoring.py`` /
``betelgeuze_engine/product/runners/backmapping_scoring.py``), maps each
per-candidate ``onsps_backmap_*`` / ``hbond_*`` column into the engine evidence
shape, and runs it through the dependency-free report/governance layer
(``betelgeuze_product.hbond_backmap_report``) to produce a stable, claim-safe
candidate table + batch KPI for the GUI and evidence bundle.

Governance:
- H-Bond BackMap is **local interpretability evidence**, not a docking-accuracy
  or binding-affinity claim (see ``docs/hbond_backmap_contract.md`` and
  ``.kiro/steering/claim_safe_wording.md``).
- ``execution_enabled=false`` / ``external_state_mutated=false``: this builder
  only reads a CSV and writes report artifacts.
- Fail-closed: a missing/empty/columnless scores CSV yields a ``blocked``
  artifact (no claim-safe rate) and a non-zero exit, never a fabricated green.

Dependency-free (stdlib + ``betelgeuze_product.hbond_backmap_report``) so it is
unit-testable without numpy/RDKit/pandas/FastAPI.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from betelgeuze_product.hbond_backmap_report import (
    CLAIM_BOUNDARY,
    HBOND_BACKMAP_REPORT_VERSION,
    build_hbond_backmap_batch_report,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/hbond_backmap_report_current.json"
DEFAULT_OUT_MD = "runs/hbond_backmap_report_current.md"
DEFAULT_OUT_CSV = "runs/hbond_backmap_report_current.csv"

# Per-candidate scores-CSV columns emitted by the backmapping scoring runner
# (see betelgeuze_engine/product/runners/backmapping_scoring.py).
COL_CLAIM_SAFE = "onsps_backmap_claim_safe"
COL_STATUS = "onsps_backmap_status"
COL_SOURCE = "onsps_backmap_source"
COL_BLOCKED_REASON = "onsps_backmap_blocked_reason"
COL_SITE_COUNT = "onsps_backmap_site_count"
COL_MAPPED_SITE_COUNT = "onsps_backmap_mapped_site_count"
COL_DONOR = "hbond_donor_site_count"
COL_ACCEPTOR = "hbond_acceptor_site_count"
COL_HBOND_BLOCKED_REASON = "hbond_blocked_reason"
COL_ANGLE_FRACTION = "hbond_angle_pass_fraction"

# Any one of these columns proves the CSV came from the backmapping scoring path.
REQUIRED_ANY_COLUMNS = (COL_CLAIM_SAFE, COL_STATUS, COL_MAPPED_SITE_COUNT)

STATUS_OK = "hbond_backmap_report_ready"
STATUS_BLOCKED_MISSING = "blocked_missing_scores_csv"
STATUS_BLOCKED_EMPTY = "blocked_empty_scores_csv"
STATUS_BLOCKED_SCHEMA = "blocked_scores_csv_missing_onsps_columns"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _to_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "t"}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any) -> float | None:
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _entry_id(row: dict[str, Any], index: int) -> str:
    target = str(row.get("target") or "").strip()
    ligand = str(row.get("ligand_id") or row.get("queue_id") or "").strip()
    if target and ligand:
        return f"{target}::{ligand}"
    if ligand:
        return ligand
    if target:
        return target
    return f"candidate_{index}"


def _row_to_batch_entry(row: dict[str, Any], index: int) -> dict[str, Any]:
    """Map one scores-CSV row into a build_hbond_backmap_batch_report entry."""

    blocked_reason = str(row.get(COL_BLOCKED_REASON) or row.get(COL_HBOND_BLOCKED_REASON) or "")
    evidence: dict[str, Any] = {
        "claim_safe": _to_bool(row.get(COL_CLAIM_SAFE)),
        "role_counts": {
            "donor": _to_int(row.get(COL_DONOR)),
            "acceptor": _to_int(row.get(COL_ACCEPTOR)),
            "none": 0,
        },
        "blocked_reason": blocked_reason,
        "mapped_site_count": _to_int(row.get(COL_MAPPED_SITE_COUNT)),
        "site_count": _to_int(row.get(COL_SITE_COUNT)),
        "mapping_source": str(row.get(COL_SOURCE) or ""),
        "backmap_status": str(row.get(COL_STATUS) or ""),
        # polar-site elements are not persisted to the scores CSV; the report
        # surfaces an empty list rather than fabricating elements.
        "elements": [],
    }
    return {
        "entry_id": _entry_id(row, index),
        "evidence": evidence,
        "hbond_angle_score": _to_float(row.get(COL_ANGLE_FRACTION)),
    }


def _read_scores_rows(scores_csv: Path) -> tuple[list[dict[str, Any]], list[str]]:
    with scores_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return rows, fieldnames


def _blocked_artifact(status: str, scores_csv: Path, detail: str) -> dict[str, Any]:
    return {
        "report_version": HBOND_BACKMAP_REPORT_VERSION,
        "status": status,
        "execution_enabled": False,
        "external_state_mutated": False,
        "scores_csv": str(scores_csv),
        "detail": detail,
        "summary": {
            "report_version": HBOND_BACKMAP_REPORT_VERSION,
            "candidate_count": 0,
            "claim_safe_count": 0,
            "evidence_only_count": 0,
            "claim_safe_rate": 0.0,
            "total_donor_sites": 0,
            "total_acceptor_sites": 0,
            "evidence_only_reason_counts": {},
            "claim_boundary": CLAIM_BOUNDARY,
        },
        "rows": [],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def build_hbond_backmap_report_artifact(scores_csv: str | Path) -> dict[str, Any]:
    """Build the report artifact dict from a backmapping-scoring scores CSV.

    Returns a dict with ``status``, read-only accounting flags, the batch
    ``summary`` (KPI), and per-candidate ``rows``. Fail-closed on missing /
    empty / wrong-schema CSV.
    """

    path = _resolve(scores_csv)
    if not path.exists():
        return _blocked_artifact(STATUS_BLOCKED_MISSING, path, "scores CSV does not exist")

    rows, fieldnames = _read_scores_rows(path)
    if not rows:
        return _blocked_artifact(STATUS_BLOCKED_EMPTY, path, "scores CSV has no candidate rows")
    if not any(col in fieldnames for col in REQUIRED_ANY_COLUMNS):
        return _blocked_artifact(
            STATUS_BLOCKED_SCHEMA,
            path,
            "scores CSV is missing onsps_backmap_* columns; not a backmapping-scoring output",
        )

    batch = build_hbond_backmap_batch_report(
        [_row_to_batch_entry(row, idx) for idx, row in enumerate(rows)]
    )
    return {
        "report_version": HBOND_BACKMAP_REPORT_VERSION,
        "status": STATUS_OK,
        "execution_enabled": False,
        "external_state_mutated": False,
        "scores_csv": str(path),
        "detail": "",
        "summary": batch["summary"],
        "rows": batch["rows"],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _render_markdown(artifact: dict[str, Any]) -> str:
    summary = artifact["summary"]
    lines = [
        "# H-Bond BackMap Candidate Report (current)",
        "",
        "Per-candidate H-Bond BackMap (ONSPS-4) interpretability evidence, generated by",
        "`tools/product/build_hbond_backmap_report.py` from a backmapping-scoring scores",
        "CSV. **Local interpretability evidence, not a docking-accuracy or binding-affinity",
        "claim.** See `docs/hbond_backmap_contract.md`.",
        "",
        f"- status: `{artifact['status']}`",
        f"- execution_enabled: `{str(artifact['execution_enabled']).lower()}`",
        f"- external_state_mutated: `{str(artifact['external_state_mutated']).lower()}`",
        f"- scores_csv: `{artifact['scores_csv']}`",
    ]
    if artifact["status"] != STATUS_OK:
        lines.extend(["", f"> **Blocked (fail-closed):** {artifact['detail']}", ""])
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            f"- candidates: `{summary['candidate_count']}`",
            f"- claim-safe: `{summary['claim_safe_count']}`",
            f"- evidence-only: `{summary['evidence_only_count']}`",
            f"- **claim_safe_rate**: `{summary['claim_safe_rate']}`",
            f"- total donor sites: `{summary['total_donor_sites']}`",
            f"- total acceptor sites: `{summary['total_acceptor_sites']}`",
            "",
        ]
    )
    reason_counts = summary.get("evidence_only_reason_counts") or {}
    if reason_counts:
        lines.extend(["## Evidence-only reason counts", "", "| reason_code | count |", "| --- | --: |"])
        for code, count in sorted(reason_counts.items()):
            lines.append(f"| `{code}` | {count} |")
        lines.append("")

    lines.extend(
        [
            "## Candidates",
            "",
            "| entry | tier | claim_safe | mapped | donor | acceptor | mapping_source | status | reason_code |",
            "| --- | --- | :--: | --: | --: | --: | --- | --- | --- |",
        ]
    )
    for row in artifact["rows"]:
        lines.append(
            "| `{entry}` | `{tier}` | {safe} | {mapped} | {donor} | {acceptor} | `{src}` | `{status}` | `{reason}` |".format(
                entry=row["entry_id"],
                tier=row["evidence_tier"],
                safe="yes" if row["claim_safe"] else "no",
                mapped=row["mapped_site_count"],
                donor=row["donor_count"],
                acceptor=row["acceptor_count"],
                src=row["mapping_source"],
                status=row["backmap_status"],
                reason=row["reason_code"],
            )
        )
    lines.append("")
    return "\n".join(lines)


_CSV_COLUMNS = [
    "entry_id",
    "evidence_tier",
    "claim_safe",
    "mapped_site_count",
    "site_count",
    "donor_count",
    "acceptor_count",
    "polar_site_elements",
    "mapping_source",
    "backmap_status",
    "reason_code",
    "reason_detail",
    "two_bead_vs_four_bead_delta",
    "hbond_angle_score",
]


def _write_csv(out_csv: Path, rows: list[dict[str, Any]]) -> None:
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "entry_id": row["entry_id"],
                    "evidence_tier": row["evidence_tier"],
                    "claim_safe": str(row["claim_safe"]).lower(),
                    "mapped_site_count": row["mapped_site_count"],
                    "site_count": row["site_count"],
                    "donor_count": row["donor_count"],
                    "acceptor_count": row["acceptor_count"],
                    "polar_site_elements": ";".join(row["polar_site_elements"]),
                    "mapping_source": row["mapping_source"],
                    "backmap_status": row["backmap_status"],
                    "reason_code": row["reason_code"],
                    "reason_detail": row["reason_detail"],
                    "two_bead_vs_four_bead_delta": (
                        "" if row["two_bead_vs_four_bead_delta"] is None else row["two_bead_vs_four_bead_delta"]
                    ),
                    "hbond_angle_score": ("" if row["hbond_angle_score"] is None else row["hbond_angle_score"]),
                }
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the H-Bond BackMap candidate report surface.")
    parser.add_argument(
        "--scores-csv",
        required=True,
        help="Backmapping-scoring scores CSV with onsps_backmap_*/hbond_* columns.",
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = parser.parse_args(argv)

    artifact = build_hbond_backmap_report_artifact(args.scores_csv)

    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_csv = _resolve(args.out_csv)
    for out in (out_json, out_md, out_csv):
        out.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    out_md.write_text(_render_markdown(artifact), encoding="utf-8")
    _write_csv(out_csv, artifact["rows"])

    # Fail-closed: a blocked artifact returns non-zero so callers/CI never treat
    # a missing/wrong-schema scores CSV as a green report.
    return 0 if artifact["status"] == STATUS_OK else 1


if __name__ == "__main__":
    raise SystemExit(main())
