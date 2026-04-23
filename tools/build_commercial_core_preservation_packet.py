#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import rows_by_family, write_csv_rows

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_COMMERCIALIZATION_JSON = "runs/commercialization_readiness_current.json"
DEFAULT_HANDOFF_JSON = "runs/execution_handoff_dashboard_current.json"
DEFAULT_GPCR_ENDPOINT_JSON = "runs/gpcr_residual_chembl50_v4_endpoint_note_current.json"
DEFAULT_IDP_SCOPE_JSON = "runs/idp_pretest_scope_note_current.json"
DEFAULT_CROSSFAMILY_JSON = "runs/cross_family_residual_shadow_layer_current.json"
DEFAULT_OUT_JSON = "runs/commercial_core_preservation_packet_current.json"
DEFAULT_OUT_CSV = "runs/commercial_core_preservation_packet_current.csv"
DEFAULT_OUT_MD = "runs/commercial_core_preservation_packet_current.md"


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


def build_payload(
    commercialization_payload: dict[str, Any],
    handoff_payload: dict[str, Any],
    gpcr_endpoint_payload: dict[str, Any],
    idp_scope_payload: dict[str, Any],
    crossfamily_payload: dict[str, Any],
) -> dict[str, Any]:
    comm_rows = rows_by_family(commercialization_payload)
    handoff_rows = rows_by_family(handoff_payload)
    cross_rows = rows_by_family(crossfamily_payload)
    gpcr_summary = dict(gpcr_endpoint_payload.get("summary", {}) or {})
    idp_summary = dict(idp_scope_payload.get("summary", {}) or {})

    rows = [
        {
            "family": "gpcr",
            "commercialization_score": comm_rows.get("gpcr", {}).get("score", ""),
            "must_preserve": "chembl50_v4 locked-decoy apply-safe endpoint parity and no new router promotion",
            "safe_scope": "locked-decoy equal-size shadow/apply endpoint only",
            "do_not_regress": "Do not lose locked-decoy apply-safe status or re-open 100k router work before PR regression is removed.",
            "protection_rule": "Keep router blocked and preserve current core parity / chembl50 EF1 signal.",
            "source_artifact": "runs/gpcr_residual_chembl50_v4_endpoint_note_current.md",
        },
        {
            "family": "ion_channel",
            "commercialization_score": comm_rows.get("ion_channel", {}).get("score", ""),
            "must_preserve": "measured noop-shadow stability",
            "safe_scope": "measured family with locked-decoy noop shadow",
            "do_not_regress": "Do not introduce new family-specific corrections that disturb the measured noop-shadow baseline.",
            "protection_rule": "Treat ion_channel as a stable commercial anchor while expansion families mature.",
            "source_artifact": comm_rows.get("ion_channel", {}).get("source_artifact", ""),
        },
        {
            "family": "kinase",
            "commercialization_score": comm_rows.get("kinase", {}).get("score", ""),
            "must_preserve": "measured noop-shadow stability",
            "safe_scope": "measured family with locked-decoy noop shadow",
            "do_not_regress": "Do not disturb the measured commercial lane with expansion-family heuristics.",
            "protection_rule": "Treat kinase as a stable commercial anchor while expansion families mature.",
            "source_artifact": comm_rows.get("kinase", {}).get("source_artifact", ""),
        },
        {
            "family": "idp",
            "commercialization_score": comm_rows.get("idp", {}).get("score", ""),
            "must_preserve": "legacy validated literature-anchor subset basis plus controlled commercial-pretest guardrails",
            "safe_scope": "controlled shadow-only commercial-pretest lane built on a literature-anchor subset basis",
            "do_not_regress": "Do not broaden to full-IDP, add coordinate correction, or add ranking/gate override before a larger safe slice passes.",
            "protection_rule": (
                f"Preserve the literature-anchor validated basis, keep `{idp_summary.get('default_feature_mask', 'rg_sasa_only')}`, and keep broader promotion blocked while the current operator lane remains controlled commercial-pretest only."
            ),
            "source_artifact": "runs/idp_commercial_pretest_packet_current.md",
        },
    ]

    summary = {
        "preservation_family_count": len(rows),
        "strongest_ready_families": commercialization_payload.get("summary", {}).get("strongest_ready_families", []),
        "run_now_count": handoff_payload.get("summary", {}).get("run_now_count", ""),
        "prepare_next_count": handoff_payload.get("summary", {}).get("prepare_next_count", ""),
        "manual_review_only_count": handoff_payload.get("summary", {}).get("manual_review_only_count", ""),
        "core_commercial_lane_score": commercialization_payload.get("summary", {}).get("core_commercial_lane_score", ""),
        "all_category_expansion_score": commercialization_payload.get("summary", {}).get("all_category_expansion_score", ""),
        "gpcr_router_status": gpcr_summary.get("router_status", ""),
        "idp_blocked_now": idp_summary.get("blocked_now", ""),
        "cross_family_shadow_status": crossfamily_payload.get("summary", {}).get("cross_family_shadow_status", ""),
        "next_required_step": "Keep GPCR, ion_channel, kinase, and IDP within their preserved safe scopes while CA2/PXR/transporter continue evidence and manual-review burndown. Expansion work must not change these core preservation rules.",
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# Commercial Core Preservation Packet",
        "",
        f"- preservation_family_count: `{s['preservation_family_count']}`",
        f"- strongest_ready_families: `{', '.join(s['strongest_ready_families'])}`",
        f"- run_now_count: `{s['run_now_count']}`",
        f"- prepare_next_count: `{s['prepare_next_count']}`",
        f"- manual_review_only_count: `{s['manual_review_only_count']}`",
        f"- core_commercial_lane_score: `{s['core_commercial_lane_score']}`",
        f"- all_category_expansion_score: `{s['all_category_expansion_score']}`",
        f"- gpcr_router_status: `{s['gpcr_router_status']}`",
        f"- idp_blocked_now: `{s['idp_blocked_now']}`",
        f"- cross_family_shadow_status: `{s['cross_family_shadow_status']}`",
        "",
        "## Next Step",
        "",
        f"- {s['next_required_step']}",
        "",
        "## Non-Regression Rules",
        "",
        "| family | commercialization_score | must_preserve | safe_scope | do_not_regress | protection_rule | source_artifact |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['family']}` | {row['commercialization_score']} | {row['must_preserve']} | `{row['safe_scope']}` | {row['do_not_regress']} | {row['protection_rule']} | `{row['source_artifact']}` |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a packet describing what the commercial core must preserve while expansion families mature.")
    parser.add_argument("--commercialization-json", default=DEFAULT_COMMERCIALIZATION_JSON)
    parser.add_argument("--execution-handoff-json", default=DEFAULT_HANDOFF_JSON)
    parser.add_argument("--gpcr-endpoint-json", default=DEFAULT_GPCR_ENDPOINT_JSON)
    parser.add_argument("--idp-scope-json", default=DEFAULT_IDP_SCOPE_JSON)
    parser.add_argument("--crossfamily-json", default=DEFAULT_CROSSFAMILY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.commercialization_json),
        _load_json(args.execution_handoff_json),
        _load_json(args.gpcr_endpoint_json),
        _load_json(args.idp_scope_json),
        _load_json(args.crossfamily_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
