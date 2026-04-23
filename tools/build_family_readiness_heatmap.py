#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_PRETEST_JSON = "runs/pretest_execution_readiness_current.json"
DEFAULT_COMMERCIALIZATION_JSON = "runs/commercialization_readiness_current.json"
DEFAULT_CROSSFAMILY_JSON = "runs/cross_family_residual_shadow_layer_current.json"
DEFAULT_OUT_JSON = "runs/family_readiness_heatmap_current.json"
DEFAULT_OUT_CSV = "runs/family_readiness_heatmap_current.csv"
DEFAULT_OUT_MD = "runs/family_readiness_heatmap_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _rows_by_key(payload: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {
        str(row.get(key, "")).strip(): dict(row)
        for row in payload.get("rows", []) or []
        if str(row.get(key, "")).strip()
    }


def _heat_bucket(pretest_ready: str) -> str:
    if pretest_ready == "yes":
        return "run-now"
    if pretest_ready == "partial":
        return "prep"
    if pretest_ready == "no":
        return "manual-review"
    return "blocked"


def _heat_rank(bucket: str) -> int:
    return {
        "run-now": 0,
        "prep": 1,
        "manual-review": 2,
        "blocked": 3,
    }.get(bucket, 9)


def _blocked_subscope(pretest_row: dict[str, Any], commercial_row: dict[str, Any]) -> str:
    family = str(pretest_row.get("family", "")).strip()
    pretest_bucket = str(pretest_row.get("pretest_ready", "")).strip()
    if family == "gpcr":
        return "100k_router"
    if family == "idp":
        return "broader_full_idp"
    if family in {"non_kinase_enzyme_ca2", "nuclear_receptor_pxr"}:
        return "authoritative_apply"
    if family == "transporter":
        return "authoritative_apply_and_donor_policy"
    if pretest_bucket == "no":
        return str(commercial_row.get("primary_blocker", "")).strip() or "blocked"
    return ""


def _heat_note(pretest_row: dict[str, Any], commercial_row: dict[str, Any]) -> str:
    family = str(pretest_row.get("family", "")).strip()
    scope = str(pretest_row.get("runtime_scope_now", "")).strip()
    blocker = str(pretest_row.get("primary_blocker", "")).strip()
    if family == "gpcr":
        return f"Run-now only inside `{scope}`; router remains blocked by `{blocker}`."
    if family == "idp":
        return f"Run-now only inside `{scope}`; broader promotion remains blocked by `{blocker}`."
    if family in {"ion_channel", "kinase"}:
        return f"Measured family is ready in `{scope}` with no current pretest blocker."
    if family in {"non_kinase_enzyme_ca2", "nuclear_receptor_pxr"}:
        return f"Partial-authoritative prep only; blocker is `{blocker}` before broader apply."
    if family == "transporter":
        return f"Manual-review only; blocker is `{blocker}` and no authoritative packet rows exist yet."
    return str(commercial_row.get("primary_blocker", "")).strip()


def build_payload(
    pretest_payload: dict[str, Any],
    commercialization_payload: dict[str, Any],
    crossfamily_payload: dict[str, Any],
) -> dict[str, Any]:
    pretest_rows = _rows_by_key(pretest_payload, "family")
    commercial_rows = _rows_by_key(commercialization_payload, "family")
    cross_rows = _rows_by_key(crossfamily_payload, "family")

    rows: list[dict[str, Any]] = []
    for family, pretest_row in pretest_rows.items():
        commercial_row = commercial_rows.get(family, {})
        cross_row = cross_rows.get(family, {})
        bucket = _heat_bucket(str(pretest_row.get("pretest_ready", "")).strip())
        row = {
            "family": family,
            "heat_bucket": bucket,
            "heat_rank": _heat_rank(bucket),
            "commercialization_score": commercial_row.get("score", pretest_row.get("commercialization_score", "")),
            "run_scope": str(pretest_row.get("runtime_scope_now", "")).strip(),
            "claim_safe_scope": str(commercial_row.get("claim_safe_scope", pretest_row.get("claim_safe_test_ready", ""))).strip(),
            "blocked_subscope": _blocked_subscope(pretest_row, commercial_row),
            "current_state": str(pretest_row.get("current_state", cross_row.get("current_state", ""))).strip(),
            "primary_blocker": str(pretest_row.get("primary_blocker", commercial_row.get("primary_blocker", ""))).strip(),
            "heat_note": _heat_note(pretest_row, commercial_row),
            "next_required_step": str(pretest_row.get("next_required_step", commercial_row.get("next_required_step", ""))).strip(),
        }
        rows.append(row)

    rows.sort(key=lambda row: (row["heat_rank"], -float(row["commercialization_score"] or 0), row["family"]))
    summary = {
        "family_count": len(rows),
        "run_now_count": sum(1 for row in rows if row["heat_bucket"] == "run-now"),
        "prep_count": sum(1 for row in rows if row["heat_bucket"] == "prep"),
        "manual_review_count": sum(1 for row in rows if row["heat_bucket"] == "manual-review"),
        "blocked_count": sum(1 for row in rows if row["heat_bucket"] == "blocked"),
        "next_required_step": "Use run-now families only within their scoped lanes, treat prep families as evidence-closure work, and keep manual-review families out of real apply until their blockers are reduced.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Family Readiness Heatmap",
        "",
        f"- family_count: `{s['family_count']}`",
        f"- run_now_count: `{s['run_now_count']}`",
        f"- prep_count: `{s['prep_count']}`",
        f"- manual_review_count: `{s['manual_review_count']}`",
        f"- blocked_count: `{s['blocked_count']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Heatmap",
        "",
        "| family | heat_bucket | commercialization_score | run_scope | claim_safe_scope | blocked_subscope | primary_blocker |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | `{row['heat_bucket']}` | {row['commercialization_score']} | "
            f"`{row['run_scope']}` | `{row['claim_safe_scope']}` | `{row['blocked_subscope']}` | `{row['primary_blocker']}` |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
        ]
    )
    for row in payload["rows"]:
        lines.append(f"- `{row['family']}`: {row['heat_note']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a family readiness heatmap across current family lanes.")
    parser.add_argument("--pretest-json", default=DEFAULT_PRETEST_JSON)
    parser.add_argument("--commercialization-json", default=DEFAULT_COMMERCIALIZATION_JSON)
    parser.add_argument("--crossfamily-json", default=DEFAULT_CROSSFAMILY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.pretest_json),
        _load_json(args.commercialization_json),
        _load_json(args.crossfamily_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
